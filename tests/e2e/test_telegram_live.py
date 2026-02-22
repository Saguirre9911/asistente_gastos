import json
import os
import time
from urllib import request

import pytest


def _first_allowed_chat_id() -> int | None:
    raw = os.getenv("ALLOWED_CHAT_IDS", "")
    for piece in raw.split(","):
        value = piece.strip()
        if not value:
            continue
        try:
            return int(value)
        except ValueError:
            continue
    return None


def _invoke_local_lambda(command: str) -> dict:
    invoke_url = os.getenv(
        "LOCAL_LAMBDA_INVOKE_URL",
        "http://localhost:9000/2015-03-31/functions/function/invocations",
    )
    secret = os.getenv("TELEGRAM_SECRET_TOKEN", "")
    chat_id = _first_allowed_chat_id()

    if not secret:
        pytest.skip("Missing TELEGRAM_SECRET_TOKEN in environment")
    if chat_id is None:
        pytest.skip("Missing ALLOWED_CHAT_IDS in environment")

    payload = {
        "headers": {"X-Telegram-Bot-Api-Secret-Token": secret},
        "body": json.dumps(
            {
                "message": {
                    "text": command,
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": chat_id, "first_name": "Smoke"},
                }
            }
        ),
    }

    req = request.Request(
        invoke_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_TELEGRAM_LIVE_TESTS") != "1",
    reason="Set RUN_TELEGRAM_LIVE_TESTS=1 to run live Telegram smoke tests",
)


def test_live_menu_and_summaries():
    for command in ["/menu", "/resumen_hoy", "/resumen_semana", "/resumen_mes"]:
        response = _invoke_local_lambda(command)
        assert response["statusCode"] == 200
        assert response["body"] == "ok"


def test_live_g_command():
    command = f"/g 1234 smoke_{int(time.time())}"
    response = _invoke_local_lambda(command)
    assert response["statusCode"] == 200
    assert response["body"] == "ok"
