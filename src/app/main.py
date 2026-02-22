import base64
import json
import logging
import os
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
    return bool(received and received == TELEGRAM_SECRET_TOKEN)



def _decode_body(event: dict) -> dict:
    raw_body = event.get("body")
    if not raw_body:
        return {}

    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    if isinstance(raw_body, dict):
        return raw_body

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return {}



def _send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

    payload: dict = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json=payload,
        timeout=8,
    )
    response.raise_for_status()



def _menu_markup() -> dict:
    return {
        "keyboard": [
            [{"text": "/g 25000 almuerzo"}],
            [{"text": "/resumen_hoy"}, {"text": "/resumen_semana"}, {"text": "/resumen_mes"}],
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


def _format_summary(gastos: list[dict], title: str, include_people: bool = False) -> str:
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
    for category, amount in sorted(by_category.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {_category_emoji(category)} {category}: {_format_money(amount)}")

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
    _send_message(
        chat_id,
        _format_summary(gastos, f"Resumen de hoy ({today.isoformat()})", include_people=True),
    )



def _handle_resumen_semana(chat_id: int) -> None:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    gastos = list_gastos(start_date=start, end_date=end)
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
    parsed = parse_g_command(text)
    if not parsed:
        _send_message(chat_id, "Uso: /g <monto> <descripcion>")
        return

    if parsed.get("error"):
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
    message = payload.get("message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return

    allowed_chat_ids = _parse_allowed_chat_ids()
    if allowed_chat_ids and chat_id not in allowed_chat_ids:
        logger.warning("Blocked chat_id not allowed: %s", chat_id)
        return

    if not isinstance(text, str) or not text.strip():
        return

    command = text.strip().split()[0].lower()

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
    logger.info("Lambda start")

    try:
        if not _is_valid_telegram_request(event):
            logger.warning("Rejected request: invalid telegram secret")
            return _ok()

        payload = _decode_body(event)
        if not payload:
            return _ok("No message to process")

        _handle_message(payload)
        return _ok()
    except Exception:
        logger.exception("Critical error in lambda_handler")
        return _ok("error")
