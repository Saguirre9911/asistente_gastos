
# 🧠 Asistente de Gastos – Serverless AI Tracker
---

### ✨ Autor

**Santiago Aguirre — Senior Machine Learning Engineer**
[LinkedIn](https://www.linkedin.com/in/daniel-santiago-aguirre/)
Proyecto personal de automatización financiera con IA.
Tecnologías: AWS Lambda · Docker · Python 3.13 · Terraform · Gemini API · Google Sheets · Telegram Bot API

---
## 📘 Descripción General

El **Asistente de Gastos** es una aplicación **serverless inteligente** desplegada sobre **AWS Lambda**, diseñada para registrar gastos personales desde **Telegram** y clasificarlos automáticamente con ayuda de **IA generativa (Gemini)**.  
La información procesada se almacena directamente en **Google Sheets**, generando un control financiero simple, automatizado y escalable.

---

## 🧩 Arquitectura

```mermaid
graph TD
    TG[Usuario en Telegram] -->|Mensaje| BOT[Telegram Bot API]
    BOT -->|Webhook JSON| LAMBDA[AWS Lambda Docker + Python 3.13]
    LAMBDA --> GEM[Google Gemini API]
    LAMBDA --> SHEETS[Google Sheets API]
    LAMBDA -->|Respuesta formateada| BOT
    subgraph AWS Cloud
        LAMBDA
    end
    subgraph GCP
        GEM
        SHEETS
    end
````

---

## ⚙️ Estructura del Proyecto

```
asistente_gastos/
├── src/
│   ├── app/
│   │   ├── main.py          # Handler principal de Lambda
│   │   ├── llm.py           # Integración con Gemini (IA)
│   │   └── sheets.py        # Conexión a Google Sheets
│   └── __init__.py
├── infraestructure/
│   ├── modules/
│   │   └── lambda_function/ # Módulo Terraform base
│   └── prod/
│       └── lambda/
│           └── terragrunt.hcl
├── Dockerfile
├── requirements.txt / pyproject.toml
├── .env                     # Variables de entorno (no versionar)
└── google_sa.json           # Credenciales de servicio (no versionar)
```

---

## 🐳 Dockerfile

```dockerfile
FROM public.ecr.aws/lambda/python:3.13

COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ${LAMBDA_TASK_ROOT}/src/
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/src"

CMD ["src.app.main.lambda_handler"]
```

---

## 🧠 Variables de Entorno (.env)

```bash
TELEGRAM_BOT_TOKEN=<tu_token_de_bot>
GEMINI_API_KEY=<tu_clave_api_gemini>
GOOGLE_SHEET_ID=<id_de_tu_hoja>
GOOGLE_CREDENTIALS_JSON=<json_base64_credenciales_servicio>
```

---

## 🧪 Prueba Local

```bash
docker buildx build --platform linux/amd64 -t asistente-gastos:latest .
docker run -p 9000:8080 --env-file .env asistente-gastos:latest
```

```bash
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -H "Content-Type: application/json" \
  -d '{"message":{"text":"gasté 20000 en empanadas","chat":{"id":12345}}}'
```

---

## ☁️ Despliegue en AWS Lambda

1. **Build y push al ECR**

```bash
docker buildx build --platform linux/amd64 -t asistente-gastos:<versión> .
docker tag asistente-gastos:<versión> <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/asistente-gastos:<versión>
docker push <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/asistente-gastos:<versión>
```

2. **Actualizar la Lambda existente**

```bash
aws lambda update-function-code \
  --function-name asistente-gastos \
  --image-uri <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/asistente-gastos:<versión> \
  --region <AWS_REGION>
```

3. **Verificar el despliegue**

```bash
aws lambda get-function \
  --function-name asistente-gastos \
  --region <AWS_REGION> \
  --query '{ImageUri: Code.ImageUri, LastModified: Configuration.LastModified}'
```

> 💡 Reemplaza:
>
> * `<AWS_ACCOUNT_ID>` por tu ID de cuenta de AWS
> * `<AWS_REGION>` por tu región (ej. `us-east-1`, `sa-east-1`)
> * `<versión>` por el tag de la imagen (ej. `v1`, `v2`, `v7`, etc.)

---

## 🔁 CD Automático (GitHub Actions)

Se agregó el workflow `.github/workflows/deploy-lambda.yml` con estos triggers:

- `push` a `main`
- `workflow_dispatch` (manual)

### Qué hace

1. Build de imagen Docker (`linux/amd64`)
2. Push a ECR (`<repo>:<sha>` y `:latest`)
3. Update de Lambda con la nueva imagen
4. Update de variables de entorno de Lambda
5. Refresh del webhook de Telegram (en push siempre, manual opcional)

### Variables de GitHub (Repository Variables)

- `AWS_REGION` (ej. `sa-east-1`)
- `ECR_REPOSITORY` (ej. `asistente-gastos`)
- `LAMBDA_FUNCTION_NAME` (ej. `asistente-gastos`)

### Secrets de GitHub (Repository Secrets)

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_SECRET_TOKEN`
- `ALLOWED_CHAT_IDS`
- `DEFAULT_CURRENCY` (opcional, default en workflow: `COP`)
- `GEMINI_API_KEY`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON_BASE64`

### Ejecución manual

Desde Actions > `Deploy Lambda` > `Run workflow` puedes:

- desplegar con tag automático (SHA corto), o
- pasar `image_tag` manual.

---

## 🧠 Prueba en Producción (Lambda URL)

```bash
curl -X POST "https://<lambda-id>.lambda-url.<AWS_REGION>.on.aws/" \
  -H "Content-Type: application/json" \
  -d '{"message":{"text":"gasté 45000 en mercado","chat":{"id":98765}}}'
```

**Respuesta esperada:**

```json
{"statusCode":200,"body":"ok"}
```

---

## 📊 Logs y Monitoreo

```bash
aws logs tail /aws/lambda/asistente-gastos --region <AWS_REGION> --since 5m --follow
```

---

## 🧱 Terraform + Terragrunt

```hcl
module "lambda_function" {
  source   = "../../modules/lambda_function"
  function_name  = "asistente-gastos"
  image_uri      = "<AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/asistente-gastos:<versión>"

  environment_variables = {
    TELEGRAM_BOT_TOKEN      = get_env("TELEGRAM_BOT_TOKEN")
    GEMINI_API_KEY          = get_env("GEMINI_API_KEY")
    GOOGLE_SHEET_ID         = get_env("GOOGLE_SHEET_ID")
    GOOGLE_CREDENTIALS_JSON = get_env("GOOGLE_CREDENTIALS_JSON")
  }
}
```

---

## 🪄 Comandos útiles

```bash
# Rebuild rápido
docker buildx build --platform linux/amd64 -t asistente-gastos:vX .

# Subir imagen
docker push <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/asistente-gastos:vX

# Actualizar Lambda
aws lambda update-function-code \
  --function-name asistente-gastos \
  --image-uri <AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/asistente-gastos:vX \
  --region <AWS_REGION>
```

---

## 🤖 Integración del Webhook de Telegram con AWS Lambda

Una vez que tu Lambda está desplegada y funcionando correctamente, puedes conectar tu bot de **Telegram** para que los mensajes se envíen automáticamente al endpoint público de tu Lambda.

### 1️⃣ Obtener el Token del Bot

- Crea tu bot con **@BotFather** en Telegram.
- Guarda el valor de tu token (formato `123456789:ABCdefGHI...`).

### 2️⃣ Configurar el Webhook

Telegram necesita saber a qué URL enviar los mensajes.  
Ejecuta el siguiente comando reemplazando los valores por los tuyos:

```bash
curl -X POST \
  "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://<lambda-id>.lambda-url.<AWS_REGION>.on.aws/webhook/$TELEGRAM_BOT_TOKEN"
````

> 🔹 **Ejemplo**
> Si tu Lambda URL es
> `https://abc123xyz.lambda-url.us-east-1.on.aws/`
> y tu bot token es almacenado en la variable `$TELEGRAM_BOT_TOKEN`,
> el comando se vería así:
>
> ```bash
> curl -X POST \
>   "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
>   -d "url=https://abc123xyz.lambda-url.us-east-1.on.aws/webhook/$TELEGRAM_BOT_TOKEN"
> ```

### 3️⃣ Verificar el Webhook

Puedes comprobar que la conexión está activa:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

Deberías obtener una respuesta como:

```json
{
  "ok": true,
  "result": {
    "url": "https://abc123xyz.lambda-url.us-east-1.on.aws/webhook/123456789:ABCdefGHI...",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

---

### 4️⃣ Probar el flujo completo

Envia un mensaje a tu bot desde Telegram:

> 💬 “Gasté 20000 en empanadas”

Si el flujo está correctamente configurado, tu Lambda registrará el evento y responderá en el chat con el mensaje confirmado, similar a:

```
Registrado ✅  
20000 COP  
Categoría: Comida  
Descripción: empanadas  
Fecha: 2025-10-29
```

---

### 🧠 Notas Técnicas

* El endpoint `/webhook/<token>` se define en tu handler (`main.py`) al procesar el evento recibido.
* Telegram enviará actualizaciones vía `POST` con formato JSON estándar.
* Tu función Lambda debe retornar `statusCode=200` para confirmar la recepción.
* En CloudWatch puedes monitorear cada invocación para ver mensajes entrantes.

---

### ⚡ Recomendaciones

| Elemento                | Descripción                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------------------ |
| **Seguridad**           | No publiques tu token en código ni en logs. Usa variables de entorno.                                  |
| **Logs**                | Revisa `/aws/lambda/asistente-gastos` en CloudWatch para auditar tráfico.                              |
| **Webhook persistente** | Si actualizas tu Lambda URL o región, vuelve a ejecutar `setWebhook`.                                  |
| **Desactivación**       | Para borrar el webhook: `curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"` |

---

🧩 **Con esta integración**, tu bot de Telegram y la Lambda quedan conectados end-to-end:
usuario → mensaje → webhook → Lambda → Gemini → Sheets → respuesta al chat.


## ✅ Estado Actual

| Componente           | Estado | Observaciones                 |
| -------------------- | ------ | ----------------------------- |
| Docker Build         | ✅      | Arquitectura linux/amd64      |
| ECR Upload           | ✅      | Versionado por tag            |
| Lambda Handler       | ✅      | `src.app.main.lambda_handler` |
| Variables de Entorno | ✅      | Cargadas desde `.env`         |
| Gemini API           | ✅      | Autenticación correcta        |
| Google Sheets        | 🟡     | Pendiente de validación       |
| Telegram Bot         | ✅      | Responde vía webhook o curl   |

---

## 🚀 Próximos pasos
3. Añadir un pipeline **CI/CD con GitHub Actions** para build + push + deploy automático.
4. Implementar **monitoring y alerting** en CloudWatch.

