import re
from datetime import date

CATEGORIES = [
    "servicios domesticos",
    "gastos",
    "comida",
    "transporte",
    "mercado",
    "ocio",
    "salud",
    "otros",
]

_CATEGORY_KEYWORDS = {
    "servicios domesticos": ["internet", "luz", "agua", "gas", "arriendo", "telefono"],
    "comida": ["comida", "almuerzo", "cena", "desayuno", "restaurante", "domicilio"],
    "transporte": ["uber", "taxi", "bus", "gasolina", "peaje", "transporte"],
    "mercado": ["mercado", "super", "d1", "ara", "carulla", "exito", "jumbo"],
    "ocio": ["cine", "bar", "fiesta", "ocio", "salida", "viaje"],
    "salud": ["medico", "doctor", "farmacia", "salud", "medicina"],
}

_CURRENCY_PREFIXES = {"$", "usd", "us", "mxn"}


def parse_amount(raw: str) -> float | None:
    if not raw:
        return None

    cleaned = re.sub(r"[^\d\.,kK]", "", raw).strip()
    if not cleaned:
        return None

    is_k = cleaned.lower().endswith("k")
    if is_k:
        cleaned = cleaned[:-1]

    if not cleaned:
        return None

    if not re.fullmatch(r"[\d\.,]+", cleaned):
        return None

    parsed: float
    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        last_dot = cleaned.rfind(".")
        last_comma = cleaned.rfind(",")
        dec_sep = "," if last_comma > last_dot else "."
        thou_sep = "." if dec_sep == "," else ","
        decimal_digits = len(cleaned.split(dec_sep)[-1])

        if decimal_digits in {1, 2}:
            int_part, frac_part = cleaned.rsplit(dec_sep, 1)
            int_digits = int_part.replace(thou_sep, "")
            if not int_digits.isdigit() or not frac_part.isdigit():
                return None
            parsed = float(f"{int_digits}.{frac_part}")
        else:
            number = cleaned.replace(".", "").replace(",", "")
            if not number.isdigit():
                return None
            parsed = float(number)
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        parts = cleaned.split(sep)

        if not all(part.isdigit() for part in parts):
            return None

        if len(parts) == 1:
            parsed = float(parts[0])
        elif len(parts) == 2:
            left, right = parts
            if len(right) == 3 and left:
                parsed = float(left + right)
            elif len(right) in {1, 2}:
                parsed = float(f"{left}.{right}")
            else:
                return None
        else:
            if all(len(part) == 3 for part in parts[1:]):
                parsed = float("".join(parts))
            elif len(parts[-1]) in {1, 2}:
                int_digits = "".join(parts[:-1])
                frac_digits = parts[-1]
                if not int_digits.isdigit():
                    return None
                parsed = float(f"{int_digits}.{frac_digits}")
            else:
                return None
    else:
        if not cleaned.isdigit():
            return None
        parsed = float(cleaned)

    if is_k:
        parsed *= 1000

    return float(int(round(parsed)))


def detect_category(description: str) -> str:
    text = (description or "").lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "otros"


def _parse_g_payload(payload: str) -> tuple[float | None, str]:
    tokens = payload.split()
    if not tokens:
        return None, ""

    amount = parse_amount(tokens[0])
    if amount is not None:
        return amount, " ".join(tokens[1:]).strip()

    if len(tokens) >= 2 and tokens[0].lower() in _CURRENCY_PREFIXES:
        amount = parse_amount(tokens[1])
        if amount is not None:
            return amount, " ".join(tokens[2:]).strip()

    return None, ""


def parse_g_command(text: str) -> dict:
    """
    /g <monto> <descripcion>
    """
    match = re.match(r"^/g(?:@\w+)?\s+(.+)$", (text or "").strip(), re.IGNORECASE)
    if not match:
        return {}

    payload = match.group(1).strip()
    if not payload:
        return {"error": "Uso: /g <monto> <descripcion>"}

    amount, description = _parse_g_payload(payload)
    if amount is None:
        return {"error": "Monto inválido. Ejemplo: /g 25000 almuerzo"}

    if not description:
        return {"error": "Debes incluir una descripción. Ejemplo: /g 25000 almuerzo"}

    return {
        "monto": amount,
        "categoria": detect_category(description),
        "descripcion": description,
        "fecha": date.today().isoformat(),
    }
