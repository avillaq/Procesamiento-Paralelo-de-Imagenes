FROM python:3.12-slim

WORKDIR /usr/src/app

COPY cliente/requirements.txt .
COPY proto/ ./proto/

RUN pip install --no-cache-dir -r requirements.txt && \
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/procesador.proto

COPY cliente/ .

EXPOSE 8080
CMD ["python", "app.py"]