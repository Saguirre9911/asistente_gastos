import base64
import json
import logging
import os
import re
from collections import defaultdict
from datetime import date, timedelta

import requests

from .parsing import parse_g_command
from .sheets import append_gasto, list_gastos

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_SECRET_TOKEN = os.environ.get("TELEGRAM_SECRET_TOKEN", "")

_CATEGORY_EMOJIS = {
    "comida": "🍽️",
    "mercado": "🛒",
    "transporte": "🚕",
    "salud": "💊",
    "ocio": "🎉",
    "servicios domesticos": "🏠",
    "gastos": "🧾",
    "otros": "📦",
}

_CARD_LIKE_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def _ok(body: str = "ok") -> dict:
    return {"statusCode": 200, "body": body}


def _parse_allowed_chat_ids() -> set[int]:
    raw = os.getenv("ALLOWED_CHAT_IDS", "")
    values = set()
    for item in raw.split(","):
        piece = item.strip()
        if not piece:
            continue
        try:
            values.add(int(piece))
        except ValueError:
            continue
    logger.info("Allowed chat ids loaded: count=%s", len(values))
    return values


def _get_secret_from_headers(headers: dict | None) -> str:
    if not isinstance(headers, dict):
        return ""
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == "x-telegram-bot-api-secret-token":
            return str(value)
    return ""


def _is_valid_telegram_request(event: dict) -> bool:
    if not TELEGRAM_SECRET_TOKEN:
        logger.warning("TELEGRAM_SECRET_TOKEN is not configured")
        return False

    received = _get_secret_from_headers(event.get("headers", {}))
    is_valid = bool(received and received == TELEGRAM_SECRET_TOKEN)
    logger.info(
        "Telegram secret validation: has_header=%s valid=%s",
        bool(received),
        is_valid,
    )
    return is_valid


def _decode_body(event: dict) -> dict:
    raw_body = event.get("body")
    if not raw_body:
        return {}

    if event.get("isBase64Encoded"):
        logger.info("Decoding base64-encoded request body")
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    if isinstance(raw_body, dict):
        parsed = _normalize_payload_keys(raw_body)
        logger.info("Body decoded from dict: top_level_keys=%s", list(parsed.keys()))
        return parsed

    try:
        parsed = _normalize_payload_keys(json.loads(raw_body))
        logger.info("Body decoded from JSON: top_level_keys=%s", list(parsed.keys()))
        return parsed
    except json.JSONDecodeError:
        logger.warning("Body is not valid JSON")
        return {}


def _normalize_key(raw_key: object) -> object:
    if not isinstance(raw_key, str):
        return raw_key
    key = raw_key.strip()
    return key.strip("\"'")


def _normalize_payload_keys(value: object) -> object:
    if isinstance(value, dict):
        return {
            _normalize_key(key): _normalize_payload_keys(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_payload_keys(item) for item in value]
    return value


def _to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if re.fullmatch(r"-?\d+", cleaned):
            return int(cleaned)
    return None


def _sanitize_for_logs(text: str, max_len: int = 160) -> str:
    if not isinstance(text, str):
        return ""

    def _mask_card(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 4:
            return "***"
        return f"[card_ending_{digits[-4:]}]"

    sanitized = _CARD_LIKE_PATTERN.sub(_mask_card, text)
    if len(sanitized) > max_len:
        return f"{sanitized[:max_len]}..."
    return sanitized


def _send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    payload: dict = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    logger.info(
        "Sending Telegram message: chat_id=%s has_reply_markup=%s text_chars=%s",
        chat_id,
        bool(reply_markup),
        len(text),
    )
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json=payload,
        timeout=8,
    )
    response.raise_for_status()
    logger.info(
        "Telegram sendMessage success: chat_id=%s status=%s",
        chat_id,
        response.status_code,
    )


def _menu_markup() -> dict:
    return {
        "keyboard": [
            [{"text": "/g 25000 almuerzo"}],
            [
                {"text": "/resumen_hoy"},
                {"text": "/resumen_semana"},
                {"text": "/resumen_mes"},
            ],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def _format_money(value: float | int) -> str:
    amount = int(round(float(value)))
    sign = "-" if amount < 0 else ""
    grouped = f"{abs(amount):,}".replace(",", ".")
    return f"{sign}${grouped}"


def _category_emoji(category: str) -> str:
    return _CATEGORY_EMOJIS.get(category, "💸")


def _format_summary(
    gastos: list[dict], title: str, include_people: bool = False
) -> str:
    if not gastos:
        return f"💸 {title}\nSin gastos registrados."

    total = sum(float(item["monto"]) for item in gastos)
    by_category: dict[str, float] = defaultdict(float)
    by_person_total: dict[str, float] = defaultdict(float)
    by_person_category: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )

    for item in gastos:
        amount = float(item["monto"])
        category = str(item.get("categoria") or "otros")
        by_category[category] += amount

        if include_people:
            person = str(item.get("quien") or "").strip() or "sin_nombre"
            by_person_total[person] += amount
            by_person_category[person][category] += amount

    lines = [
        f"💸 {title}",
        f"🧾 Total general: {_format_money(total)}",
        "",
        "🏷️ Categorías (global):",
    ]
    for category, amount in sorted(
        by_category.items(), key=lambda item: item[1], reverse=True
    ):
        lines.append(
            f"- {_category_emoji(category)} {category}: {_format_money(amount)}"
        )

    if include_people:
        lines.extend(["", "👥 Desglose por persona:"])
        for person, total_by_person in sorted(
            by_person_total.items(), key=lambda item: item[1], reverse=True
        ):
            lines.append(f"👤 {person}")
            person_categories = by_person_category.get(person, {})
            for category, amount in sorted(
                person_categories.items(), key=lambda item: item[1], reverse=True
            ):
                lines.append(
                    f"- {_category_emoji(category)} {category}: {_format_money(amount)}"
                )
            lines.append(f"💰 Total {person}: {_format_money(total_by_person)}")
            lines.append("")

        if lines and not lines[-1].strip():
            lines.pop()

    return "\n".join(lines)


def _handle_resumen_hoy(chat_id: int) -> None:
    today = date.today()
    gastos = list_gastos(start_date=today, end_date=today)
    logger.info("Resumen hoy: chat_id=%s gastos=%s", chat_id, len(gastos))
    _send_message(
        chat_id,
        _format_summary(
            gastos, f"Resumen de hoy ({today.isoformat()})", include_people=True
        ),
    )


def _handle_resumen_semana(chat_id: int) -> None:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    gastos = list_gastos(start_date=start, end_date=end)
    logger.info(
        "Resumen semana: chat_id=%s start=%s end=%s gastos=%s",
        chat_id,
        start.isoformat(),
        end.isoformat(),
        len(gastos),
    )
    _send_message(
        chat_id,
        _format_summary(
            gastos,
            f"Resumen semana ({start.isoformat()} a {end.isoformat()})",
            include_people=True,
        ),
    )


def _handle_resumen_mes(chat_id: int) -> None:
    today = date.today()
    start = today.replace(day=1)

    if today.month == 12:
        next_month_start = date(today.year + 1, 1, 1)
    else:
        next_month_start = date(today.year, today.month + 1, 1)
    end = next_month_start - timedelta(days=1)

    gastos = list_gastos(start_date=start, end_date=end)
    logger.info(
        "Resumen mes: chat_id=%s start=%s end=%s gastos=%s",
        chat_id,
        start.isoformat(),
        end.isoformat(),
        len(gastos),
    )
    _send_message(
        chat_id,
        _format_summary(
            gastos,
            f"Resumen mes ({start.isoformat()} a {end.isoformat()})",
            include_people=True,
        ),
    )


def _resolve_actor(chat_id: int, user: dict) -> str:
    username = user.get("username") if isinstance(user, dict) else ""
    first_name = user.get("first_name") if isinstance(user, dict) else ""

    if username:
        return str(username)
    if first_name:
        return str(first_name)
    return f"chat_{chat_id}"


def _handle_g_command(chat_id: int, text: str, user: dict) -> None:
    logger.info(
        "Handling /g command: chat_id=%s text_chars=%s text_preview=%s",
        chat_id,
        len(text),
        _sanitize_for_logs(text),
    )
    parsed = parse_g_command(text)
    if not parsed:
        logger.warning("Invalid /g format: chat_id=%s", chat_id)
        _send_message(chat_id, "Uso: /g <monto> <descripcion>")
        return

    if parsed.get("error"):
        logger.warning(
            "Parse /g error: chat_id=%s error=%s text_preview=%s",
            chat_id,
            parsed["error"],
            _sanitize_for_logs(text),
        )
        _send_message(chat_id, parsed["error"])
        return

    gasto = {
        "fecha": parsed["fecha"],
        "monto": parsed["monto"],
        "categoria": parsed["categoria"],
        "descripcion": parsed["descripcion"],
        "quien": _resolve_actor(chat_id, user),
    }

    try:
        append_gasto(gasto)
        logger.info(
            "Expense persisted: chat_id=%s category=%s amount=%s",
            chat_id,
            gasto["categoria"],
            gasto["monto"],
        )
    except Exception:
        logger.exception("Error writing to Google Sheets")
        _send_message(chat_id, "No pude guardar el gasto en este momento.")
        return

    _send_message(
        chat_id,
        (
            "✅ Registrado\n"
            f"💵 Monto: {_format_money(gasto['monto'])}\n"
            f"🏷️ Categoría: {gasto['categoria']}\n"
            f"📝 Descripción: {gasto['descripcion']}\n"
            f"📅 Fecha: {gasto['fecha']}"
        ),
    )


def _handle_message(payload: dict) -> None:
    if isinstance(payload, dict):
        logger.info("Handling payload: keys=%s", list(payload.keys()))
    message = payload.get("message", {})
    if not isinstance(message, dict):
        logger.warning("Ignored payload without message dict")
        return

    text = message.get("text", "")
    chat = message.get("chat", {})
    user = message.get("from", {})

    if not isinstance(chat, dict):
        logger.warning("Ignored message without chat dict")
        return

    chat_id = _to_int(chat.get("id"))
    if chat_id is None:
        logger.warning("Ignored message with invalid chat id type")
        return

    allowed_chat_ids = _parse_allowed_chat_ids()
    if allowed_chat_ids and chat_id not in allowed_chat_ids:
        logger.warning("Blocked chat_id not allowed: %s", chat_id)
        return

    if not isinstance(text, str) or not text.strip():
        logger.warning("Ignored message without text")
        return

    if isinstance(user, dict):
        coerced_user_id = _to_int(user.get("id"))
        if coerced_user_id is not None:
            user["id"] = coerced_user_id

    command = text.strip().split()[0].lower()
    logger.info(
        "Processing command=%s chat_id=%s chat_type=%s user_id=%s text_preview=%s",
        command,
        chat_id,
        chat.get("type"),
        user.get("id") if isinstance(user, dict) else None,
        _sanitize_for_logs(text),
    )

    if command == "/menu":
        _send_message(chat_id, "Menú de comandos", reply_markup=_menu_markup())
        return

    if command == "/resumen_hoy":
        _handle_resumen_hoy(chat_id)
        return

    if command == "/resumen_semana":
        _handle_resumen_semana(chat_id)
        return

    if command == "/resumen_mes":
        _handle_resumen_mes(chat_id)
        return

    if command == "/g":
        _handle_g_command(chat_id, text.strip(), user)
        return

    _send_message(
        chat_id,
        "Comando no reconocido. Usa /menu o /g <monto> <descripcion>",
    )


def lambda_handler(event, context):
    del context
    logger.info(
        "Lambda start: has_headers=%s has_body=%s is_base64=%s",
        bool(event.get("headers")) if isinstance(event, dict) else False,
        bool(event.get("body")) if isinstance(event, dict) else False,
        bool(event.get("isBase64Encoded")) if isinstance(event, dict) else False,
    )

    try:
        if not _is_valid_telegram_request(event):
            logger.warning("Rejected request: invalid telegram secret")
            return _ok()

        payload = _decode_body(event)
        if not payload:
            logger.warning("No message to process after body decode")
            return _ok("No message to process")

        _handle_message(payload)
        return _ok()
    except Exception:
        logger.exception("Critical error in lambda_handler")
        return _ok("error")
