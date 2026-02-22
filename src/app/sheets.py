import base64
import json
import os
import re
from datetime import date

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .parsing import parse_amount

SHEET_RANGE = "registros!A:E"



def get_google_credentials():
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON_BASE64") or os.getenv(
        "GOOGLE_CREDENTIALS_JSON"
    )
    if not creds_b64:
        raise RuntimeError(
            "Missing GOOGLE_CREDENTIALS_JSON_BASE64 (or GOOGLE_CREDENTIALS_JSON)"
        )

    creds_json = base64.b64decode(creds_b64).decode("utf-8")
    creds_dict = json.loads(creds_json)

    return service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )



def _service():
    return build(
        "sheets",
        "v4",
        credentials=get_google_credentials(),
        cache_discovery=False,
    )



def _sheet_id() -> str:
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError("Missing GOOGLE_SHEET_ID")
    return sheet_id



def append_gasto(gasto: dict) -> None:
    values = [
        [
            gasto["fecha"],
            gasto["monto"],
            gasto["categoria"],
            gasto["descripcion"],
            gasto["quien"],
        ]
    ]
    body = {"values": values}

    (
        _service()
        .spreadsheets()
        .values()
        .append(
            spreadsheetId=_sheet_id(),
            range=SHEET_RANGE,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )



def _parse_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None

    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw):
        day, month, year = raw.split("/")
        return date(int(year), int(month), int(day))

    return None



def list_gastos(start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    result = (
        _service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=_sheet_id(), range=SHEET_RANGE)
        .execute()
    )

    rows = result.get("values", [])
    gastos = []

    for row in rows:
        if len(row) < 2:
            continue

        if str(row[0]).strip().lower() in {"fecha", "date"}:
            continue

        fecha = _parse_date(str(row[0]))
        monto = parse_amount(str(row[1]))
        categoria = str(row[2]).strip().lower() if len(row) > 2 else "otros"
        descripcion = str(row[3]).strip() if len(row) > 3 else ""
        quien = str(row[4]).strip() if len(row) > 4 else ""

        if fecha is None or monto is None:
            continue

        if start_date and fecha < start_date:
            continue
        if end_date and fecha > end_date:
            continue

        gastos.append(
            {
                "fecha": fecha.isoformat(),
                "monto": float(monto),
                "categoria": categoria or "otros",
                "descripcion": descripcion,
                "quien": quien,
            }
        )

    return gastos
