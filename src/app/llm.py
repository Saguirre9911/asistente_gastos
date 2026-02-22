import json
import os
import re
from datetime import date
from zoneinfo import ZoneInfo

import dotenv
from google import genai

dotenv.load_dotenv()
TZ = ZoneInfo("America/Bogota")

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """
Eres un extractor de información. Devuelves SOLO JSON válido, sin texto adicional, sin ```.

El JSON DEBE ser exactamente este:
{
  "monto": float,
  "categoria": string,
  "descripcion": string,
  "fecha": "YYYY-MM-DD" | null
}

Reglas:
- NO inventes fechas.
- Si el usuario NO menciona una fecha explícita (o relativa), devuelve "fecha": null.
- Categorías permitidas: servicios domesticos, gastos, comida, transporte, mercado, ocio, salud, otros.
- No incluyas comentarios, explicaciones ni texto fuera del JSON.
"""


# ==============================
# 🔧 Cliente
# ==============================
def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("❌ GEMINI_API_KEY no está configurada.")
    return genai.Client(api_key=api_key)


# ==============================
# 🧹 Limpieza de JSON (crítico)
# ==============================
def clean_json_output(raw: str) -> str:
    """
    Limpia la salida del modelo para que sea JSON válido.
    Elimina ```json, ``` y extrae el bloque { ... }.
    """
    if not raw:
        return raw

    # Quitar ```json y ```
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    # Extraer contenido entre { ... }
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        return match.group(0)

    # Si no encuentra JSON, devolver raw (esto causará fallback)
    return cleaned.strip()


# ==============================
# 🧠 Parseo con Gemini
# ==============================
def parse_gasto(texto: str) -> dict:
    prompt = SYSTEM_PROMPT + "\nUsuario: " + texto

    try:
        client = get_client()

        response = client.models.generate_content(model=MODEL, contents=prompt)

        raw = response.text.strip()
        print("RAW OUTPUT LLM:", raw)

        cleaned = clean_json_output(raw)
        print("CLEANED JSON:", cleaned)

        data = json.loads(cleaned)

    except Exception as e:
        print("⚠️ Gemini falló, usando fallback:", e)
        return fallback_parse(texto)

    # Completar fecha si viene null
    if not data.get("fecha"):
        data["fecha"] = date.today().isoformat()

    return data


# ==============================
# 🔄 Fallback
# ==============================
def fallback_parse(texto: str) -> dict:
    """
    Última línea de defensa: heurística simple si Gemini falla.
    """
    import re

    monto = 0
    m = re.search(r"(\d[\d\.]*)", texto)
    if m:
        monto = float(m.group(1))

    return {
        "monto": monto,
        "categoria": "otros",
        "descripcion": texto,
        "fecha": date.today().isoformat(),
    }
