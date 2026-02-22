## Pruebas locales simples

### 1) Levantar Lambda runtime local

```bash
docker buildx build --platform linux/amd64 -t asistente-gastos:latest .
docker run --rm -p 9000:8080 --env-file .env asistente-gastos:latest
```

### 2) Probar comandos simulando webhook Telegram

#### /g
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "headers": {"X-Telegram-Bot-Api-Secret-Token": "TU_TELEGRAM_SECRET_TOKEN"},
    "body": "{\"message\":{\"text\":\"/g 25000 almuerzo\",\"chat\":{\"id\":12345,\"type\":\"private\"},\"from\":{\"id\":12345,\"first_name\":\"Santi\"}}}"
  }'
```

#### /menu
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "headers": {"X-Telegram-Bot-Api-Secret-Token": "TU_TELEGRAM_SECRET_TOKEN"},
    "body": "{\"message\":{\"text\":\"/menu\",\"chat\":{\"id\":12345,\"type\":\"private\"},\"from\":{\"id\":12345,\"first_name\":\"Santi\"}}}"
  }'
```

#### /resumen_hoy
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "headers": {"X-Telegram-Bot-Api-Secret-Token": "TU_TELEGRAM_SECRET_TOKEN"},
    "body": "{\"message\":{\"text\":\"/resumen_hoy\",\"chat\":{\"id\":12345,\"type\":\"private\"},\"from\":{\"id\":12345,\"first_name\":\"Santi\"}}}"
  }'
```

#### /resumen_semana
```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{
    "headers": {"X-Telegram-Bot-Api-Secret-Token": "TU_TELEGRAM_SECRET_TOKEN"},
    "body": "{\"message\":{\"text\":\"/resumen_semana\",\"chat\":{\"id\":12345,\"type\":\"private\"},\"from\":{\"id\":12345,\"first_name\":\"Santi\"}}}"
  }'
```
