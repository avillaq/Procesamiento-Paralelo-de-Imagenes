import os
import logging
import time
from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc
from proto import bully_pb2_grpc

from bully_service import BullyService
from coordinador_service import CoordinadorService
from imagen_helper import ImagenHelper
from monitoreo.metricas_nodo import MetricasServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProcesadorImagen(procesador_pb2_grpc.ProcesadorImagenServicer):
    def __init__(self, nodo_id, bully_service, coordinador_service, imagen_helper, recolector_metricas_nodo):
        self.nodo_id = nodo_id
        self.bully_service = bully_service
        self.coordinador_service = coordinador_service
        self.imagen_helper = imagen_helper
        self.recolector_metricas_nodo = recolector_metricas_nodo
    
    # implementacion
    def EstadoNodo(self, request, context):
        """Retorna el estado del nodo"""
        es_coordinador = self.bully_service.es_coordinador
        return procesador_pb2.EstadoReply(es_coordinador=es_coordinador, nodo_id=self.nodo_id)

    def ProcesarImagen(self, request, context):
        """Punto de entrada principal"""
        inicio = time.time()
        try:
            tamano_imagen = self._clasificar_tamano_imagen(len(request.data))

            # Si es coordinador, dividir y distribuir
            if self.bully_service.es_coordinador:
                resultado = self.coordinador_service.procesar_imagen_distribuida(request.data)
            else:
                # se convierte a escala de grises
                resultado = self.imagen_helper.procesar_parte_individual(request.data)
            
            duracion = time.time() - inicio
            estado = "exito" if resultado.status == "ok" else "error"

            self.recolector_metricas_nodo.track_procesamiento_imagen(
                duracion, estado, tamano_imagen, "escala grises"
            )
            
            return resultado
        
        except Exception as e:
            duracion = time.time() - inicio
            self.recolector_metricas_nodo.track_procesamiento_imagen(
                duracion, "error", "desconocido", "escala grises"
            )

            logger.error(f"Error en nodo {self.nodo_id}: {e}")
            return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje=str(e))

    def _clasificar_tamano_imagen(self, tamano_bytes):
        """Clasifica el tamaño de la imagen"""
        tamano_mb = tamano_bytes / (1024 * 1024)

        if tamano_mb < 1:
            return "pequeña"
        elif tamano_mb < 5:
            return "mediana"
        elif tamano_mb < 15:
            return "grande"
        else:
            return "muy_grande"

def serve():
    # configuracion del nodo
    nodo_id = int(os.environ.get("NODO_ID", "1"))
    nodos_conocidos = os.environ.get("NODOS_CONOCIDOS", "").split(",")
    nodos_conocidos = [node.strip() for node in nodos_conocidos if node.strip()]

    # servidor de métricas
    metricas_nodo_server = MetricasServer(nodo_id,puerto=8000)
    metricas_nodo_server.start()
    recolector_metricas_nodo = metricas_nodo_server.get_recolector()

    # servicios
    bully_service = BullyService(nodo_id, nodos_conocidos)
    imagen_helper = ImagenHelper(nodo_id)
    coordinador_service = CoordinadorService(nodo_id, bully_service, imagen_helper)

    # servicio principal
    procesador = ProcesadorImagen(nodo_id, bully_service, coordinador_service, imagen_helper, recolector_metricas_nodo)

    # servidor de procesamiento de imagenes
    server_procesamiento = grpc.server(futures.ThreadPoolExecutor(max_workers=4), options=[
                                        ('grpc.max_receive_message_length', 20 * 1024 * 1024),  # 20MB
                                        ('grpc.max_send_message_length', 20 * 1024 * 1024)]
                                    )
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
    logger.info(f"Métricas: puerto 8000")
    logger.info(f"Nodos conocidos: {nodos_conocidos}")
    try:
        server_procesamiento.wait_for_termination()
    except KeyboardInterrupt:
        logger.info(f"Deteniendo nodo {nodo_id}...")
        bully_service.detener_servicios()
        metricas_nodo_server.stop()
        server_procesamiento.stop(0)
        server_bully.stop(0)

if __name__ == "__main__":
    serve()