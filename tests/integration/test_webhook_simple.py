import json
from datetime import date

from src.app import main


def test_webhook_g_command_simple(monkeypatch):
    sent_messages = []
    saved_expenses = []

    monkeypatch.setattr(main, "TELEGRAM_SECRET_TOKEN", "secret123")
    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(main, "_parse_allowed_chat_ids", lambda: {12345})

    monkeypatch.setattr(
        main,
        "_send_message",
        lambda chat_id, text, reply_markup=None: sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        ),
    )

    monkeypatch.setattr(
        main,
        "append_gasto",
        lambda gasto: saved_expenses.append(gasto),
    )

    event = {
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "secret123",
        },
        "body": json.dumps(
            {
                "message": {
                    "text": "/g 30000 mercado de la semana",
                    "chat": {"id": 12345, "type": "group"},
                    "from": {"id": 777, "first_name": "Santi"},
                }
            }
        ),
    }

    result = main.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert len(saved_expenses) == 1
    assert saved_expenses[0]["monto"] == 30000
    assert any("✅ Registrado" in message["text"] for message in sent_messages)
    assert any("💵 Monto: $30.000" in message["text"] for message in sent_messages)


def test_webhook_accepts_string_ids(monkeypatch):
    sent_messages = []

    monkeypatch.setattr(main, "TELEGRAM_SECRET_TOKEN", "secret123")
    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(main, "_parse_allowed_chat_ids", lambda: {-5126713881})
    monkeypatch.setattr(
        main,
        "_send_message",
        lambda chat_id, text, reply_markup=None: sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        ),
    )

    event = {
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "secret123",
        },
        "body": json.dumps(
            {
                "message": {
                    "text": "/menu",
                    "chat": {"id": "-5126713881", "type": "supergroup"},
                    "from": {"id": "2104198203", "first_name": "Santiago"},
                }
            }
        ),
    }

    result = main.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert len(sent_messages) == 1
    assert sent_messages[0]["chat_id"] == -5126713881
    assert sent_messages[0]["reply_markup"] is not None


def test_webhook_accepts_payload_with_quoted_keys(monkeypatch):
    sent_messages = []

    monkeypatch.setattr(main, "TELEGRAM_SECRET_TOKEN", "secret123")
    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(main, "_parse_allowed_chat_ids", lambda: {-5126713881})
    monkeypatch.setattr(
        main,
        "_send_message",
        lambda chat_id, text, reply_markup=None: sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        ),
    )

    event = {
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "secret123",
        },
        "body": json.dumps(
            {
                '"message"': {
                    '"text"': "/menu",
                    '"chat"': {'"id"': "-5126713881", '"type"': "supergroup"},
                    '"from"': {'"id"': "2104198203", '"first_name"': "Santiago"},
                }
            }
        ),
    }

    result = main.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert len(sent_messages) == 1
    assert sent_messages[0]["chat_id"] == -5126713881
    assert sent_messages[0]["reply_markup"] is not None


def test_webhook_resumen_mes(monkeypatch):
    sent_messages = []
    captured_range = {}

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 2, 22)

    monkeypatch.setattr(main, "date", FakeDate)
    monkeypatch.setattr(main, "TELEGRAM_SECRET_TOKEN", "secret123")
    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(main, "_parse_allowed_chat_ids", lambda: {12345})

    def fake_list_gastos(start_date=None, end_date=None):
        captured_range["start_date"] = start_date
        captured_range["end_date"] = end_date
        return [
            {
                "fecha": "2026-02-10",
                "monto": 25000,
                "categoria": "comida",
                "descripcion": "almuerzo",
                "quien": "Santi",
            }
        ]

    monkeypatch.setattr(main, "list_gastos", fake_list_gastos)
    monkeypatch.setattr(
        main,
        "_send_message",
        lambda chat_id, text, reply_markup=None: sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        ),
    )

    event = {
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "secret123",
        },
        "body": json.dumps(
            {
                "message": {
                    "text": "/resumen_mes",
                    "chat": {"id": 12345, "type": "private"},
                    "from": {"id": 777, "first_name": "Santi"},
                }
            }
        ),
    }

    result = main.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert captured_range["start_date"] == FakeDate(2026, 2, 1)
    assert captured_range["end_date"] == FakeDate(2026, 2, 28)
    assert any(
        "💸 Resumen mes (2026-02-01 a 2026-02-28)" in message["text"]
        for message in sent_messages
    )
    assert any(
        "🧾 Total general: $25.000" in message["text"] for message in sent_messages
    )
    assert any("👤 Santi" in message["text"] for message in sent_messages)
    assert any(
        "💰 Total Santi: $25.000" in message["text"] for message in sent_messages
    )


def test_webhook_resumen_hoy_includes_people_breakdown(monkeypatch):
    sent_messages = []

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 2, 22)

    monkeypatch.setattr(main, "date", FakeDate)
    monkeypatch.setattr(main, "TELEGRAM_SECRET_TOKEN", "secret123")
    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(main, "_parse_allowed_chat_ids", lambda: {12345})
    monkeypatch.setattr(
        main,
        "list_gastos",
        lambda start_date=None, end_date=None: [
            {
                "fecha": "2026-02-22",
                "monto": 25000,
                "categoria": "comida",
                "descripcion": "almuerzo",
                "quien": "Santi",
            },
            {
                "fecha": "2026-02-22",
                "monto": 12000,
                "categoria": "transporte",
                "descripcion": "uber",
                "quien": "Lau",
            },
        ],
    )
    monkeypatch.setattr(
        main,
        "_send_message",
        lambda chat_id, text, reply_markup=None: sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        ),
    )

    event = {
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "secret123",
        },
        "body": json.dumps(
            {
                "message": {
                    "text": "/resumen_hoy",
                    "chat": {"id": 12345, "type": "private"},
                    "from": {"id": 777, "first_name": "Santi"},
                }
            }
        ),
    }

    result = main.lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert len(sent_messages) == 1
    assert "👥 Desglose por persona:" in sent_messages[0]["text"]
    assert "🧾 Total general: $37.000" in sent_messages[0]["text"]
    assert "👤 Santi" in sent_messages[0]["text"]
    assert "👤 Lau" in sent_messages[0]["text"]
    assert "💰 Total Santi: $25.000" in sent_messages[0]["text"]
    assert "💰 Total Lau: $12.000" in sent_messages[0]["text"]


def test_webhook_resumen_semana_includes_people_breakdown(monkeypatch):
    sent_messages = []
    captured_range = {}

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 2, 22)

    monkeypatch.setattr(main, "date", FakeDate)
    monkeypatch.setattr(main, "TELEGRAM_SECRET_TOKEN", "secret123")
    monkeypatch.setattr(main, "TELEGRAM_TOKEN", "token123")
    monkeypatch.setattr(main, "_parse_allowed_chat_ids", lambda: {12345})

    def fake_list_gastos(start_date=None, end_date=None):
        captured_range["start_date"] = start_date
        captured_range["end_date"] = end_date
        return [
            {
                "fecha": "2026-02-20",
                "monto": 32000,
                "categoria": "comida",
                "descripcion": "almuerzo",
                "quien": "Santiago",
            },
            {
                "fecha": "2026-02-21",
                "monto": 2000,
                "categoria": "otros",
                "descripcion": "varios",
                "quien": "Santiago",
            },
            {
                "fecha": "2026-02-21",
                "monto": 20334,
                "categoria": "comida",
                "descripcion": "cena",
                "quien": "Lauren",
            },
            {
                "fecha": "2026-02-22",
                "monto": 23230,
                "categoria": "otros",
                "descripcion": "snacks",
                "quien": "Lauren",
            },
        ]

    monkeypatch.setattr(main, "list_gastos", fake_list_gastos)
    monkeypatch.setattr(
        main,
        "_send_message",
        lambda chat_id, text, reply_markup=None: sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}
        ),
    )

    event = {
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "secret123",
        },
        "body": json.dumps(
            {
                "message": {
                    "text": "/resumen_semana",
                    "chat": {"id": 12345, "type": "private"},
                    "from": {"id": 777, "first_name": "Santi"},
                }
            }
        ),
    }

    result = main.lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert captured_range["start_date"] == FakeDate(2026, 2, 16)
    assert captured_range["end_date"] == FakeDate(2026, 2, 22)
    assert len(sent_messages) == 1
    assert "👤 Santiago" in sent_messages[0]["text"]
    assert "👤 Lauren" in sent_messages[0]["text"]
    assert "💰 Total Santiago: $34.000" in sent_messages[0]["text"]
    assert "💰 Total Lauren: $43.564" in sent_messages[0]["text"]
