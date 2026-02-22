FROM public.ecr.aws/lambda/python:3.12

# Instalamos dependencias del requirements.txt
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código fuente
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# Hacemos que Python encuentre el paquete 'src'
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}/src"

# Handler de Lambda
CMD ["src.app.main.lambda_handler"]
