FROM python:3.12-slim

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY nodos/requirements.txt .
COPY proto/ ./proto/

RUN pip install --no-cache-dir -r requirements.txt && \
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/procesador.proto

COPY nodos/ .

EXPOSE 50052
CMD ["python", "nodo.py"]