FROM python:3.12-slim

WORKDIR /usr/src/app

COPY cliente/requirements.txt .
COPY proto/ ./proto/
COPY monitoreo/ ./monitoreo/

COPY cliente/iniciar_cliente.sh /iniciar_cliente.sh

RUN apt-get update && \
    apt-get install -y glusterfs-client && \
    apt-get install -y glusterfs-server && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/procesador.proto

COPY cliente/ .


RUN chmod +x /iniciar_cliente.sh
EXPOSE 8080
ENTRYPOINT ["/iniciar_cliente.sh"]