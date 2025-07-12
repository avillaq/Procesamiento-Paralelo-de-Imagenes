import os
import logging

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc
from proto import bully_pb2_grpc

from bully_service import BullyService
from coordinador_service import CoordinadorService
from imagen_helper import ImagenHelper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProcesadorImagen(procesador_pb2_grpc.ProcesadorImagenServicer):
    def __init__(self, nodo_id, bully_service, coordinador_service, imagen_helper):
        self.nodo_id = nodo_id
        self.bully_service = bully_service
        self.coordinador_service = coordinador_service
        self.imagen_helper = imagen_helper
    
    # implementacion
    def EstadoNodo(self, request, context):
        """Retorna el estado del nodo"""
        return procesador_pb2.EstadoReply(es_coordinador=self.bully_service.es_coordinador)

    def ProcesarImagen(self, request, context):
        """Punto de entrada principal"""
        try:
            # Si es coordinador, dividir y distribuir
            if self.bully_service.es_coordinador:
                return self.coordinador_service.procesar_imagen_distribuida(request.data)
            else:
                # se convierte a escala de grises
                return self.imagen_helper.procesar_parte_individual(request.data)

        except Exception as e:
            logger.error(f"Error en nodo {self.nodo_id}: {e}")
            return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje=str(e))

def serve():
    # configuracion del nodo
    nodo_id = int(os.environ.get("NODO_ID", "1"))
    nodos_conocidos = os.environ.get("NODOS_CONOCIDOS", "").split(",")
    nodos_conocidos = [node.strip() for node in nodos_conocidos if node.strip()]

    # servicios
    bully_service = BullyService(nodo_id, nodos_conocidos)
    imagen_helper = ImagenHelper(nodo_id)
    coordinador_service = CoordinadorService(nodo_id, bully_service, imagen_helper)

    # servicio principal
    procesador = ProcesadorImagen(nodo_id, bully_service, coordinador_service, imagen_helper)

    # servidor de procesamiento de imagenes
    server_procesamiento = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    procesador_pb2_grpc.add_ProcesadorImagenServicer_to_server(procesador, server_procesamiento)
    server_procesamiento.add_insecure_port("[::]:" + "50052")

    # servidor para Bully
    server_bully = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    bully_pb2_grpc.add_BullyServiceServicer_to_server(bully_service, server_bully)
    server_bully.add_insecure_port("[::]:" + "50053")

    server_procesamiento.start()
    server_bully.start()
    bully_service.iniciar_servicios()

    logger.info(f"=== NODO {nodo_id} INICIADO ===")
    logger.info(f"Procesamiento: puerto 50052")
    logger.info(f"Bully: puerto 50053")
    logger.info(f"  - Nodos conocidos: {nodos_conocidos}")
    try:
        server_procesamiento.wait_for_termination()
    except KeyboardInterrupt:
        logger.info(f"Deteniendo nodo {nodo_id}...")
        bully_service.detener_servicios()
        server_procesamiento.stop(0)
        server_bully.stop(0)

if __name__ == "__main__":
    serve()