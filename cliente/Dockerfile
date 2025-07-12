FROM python:3.12-slim

WORKDIR /usr/src/app

COPY cliente/requirements.txt .
COPY proto/ ./proto/
COPY cliente/iniciar_cliente.sh /iniciar_cliente.sh

RUN apt-get update && \
    apt-get install -y glusterfs-client && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/procesador.proto

COPY cliente/ .

EXPOSE 8080
RUN chmod +x /iniciar_cliente.sh
ENTRYPOINT ["/iniciar_cliente.sh"]