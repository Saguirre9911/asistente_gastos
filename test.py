import json

from dotenv import load_dotenv

from src.app.main import lambda_handler

load_dotenv()


def test_e2e_local():
    telegram_event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/webhook/test",
        "headers": {
            "X-Telegram-Bot-Api-Secret-Token": "test-secret",
        },
        "body": json.dumps(
            {
                "message": {
                    "text": "/g 55000 palomitas",
                    "chat": {"id": 2104198203, "type": "private"},
                    "from": {"id": 2104198203, "first_name": "Santiago"},
                }
            }
        ),
    }

    result = lambda_handler(telegram_event, None)
    assert result["statusCode"] == 200


if __name__ == "__main__":
    test_e2e_local()
