from pathlib import Path
import sys
import numpy as np
import cv2
import os
import logging

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc
from proto import bully_pb2_grpc
from bully_service import BullyService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProcesadorImagen(procesador_pb2_grpc.ProcesadorImagenServicer):
    def __init__(self, nodo_id, bully_service):
        self.nodo_id = nodo_id
        self.bully_service = bully_service
        self.indice_nodo = 0

    # implementacion
    def ProcesarImagen(self, request, context):
        try:
            imagen_np = np.frombuffer(request.data, dtype=np.uint8)
            img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
            if img is None:
                return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje="Error al decodificar la imagen")

            # Si es coordinador, dividir y distribuir
            if self.bully_service.es_coordinador:
                return self._procesar_como_coordinador(img)
            else:
                # se convierte a escala de grises
                return self._procesar_parte_individual(img)
            
        except Exception as e:
            logger.error(f"Error en nodo {self.nodo_id}: {e}")
            return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje=str(e))

    def _procesar_como_coordinador(self, img):
        """ Divide la imagen en partes y distribuye a nodos disponibles"""
        nodos_disponibles = self.bully_service.get_nodos_disponibles()
        if not nodos_disponibles:
            return procesador_pb2.ImagenReply(
                status="error", 
                imagen_data=b"", 
                mensaje="No hay nodos disponibles"
            )

        # division en partes
        alto = img.shape[0] # altura
        num_nodos = len(nodos_disponibles)
        alto_parte = alto // num_nodos
        resto = alto % num_nodos
        
        partes = []
        inicio = 0
        
        for i in range(num_nodos):
            # se distrinuye el resto entre las primeras partes
            extra = 1 if i < resto else 0 
            final = inicio + alto_parte + extra

            if i == num_nodos - 1:  # ultima parte toma todo lo que queda
                final = alto
                
            partes.append(img[inicio:final, :])
            inicio = final
        
        partes_procesadas = []
        for i, pt in enumerate(partes):
            resultado = self._procesar_parte_en_nodo(pt, nodos_disponibles[i % len(nodos_disponibles)])
            if resultado is None:
                return procesador_pb2.ImagenReply(
                    status="error", 
                    imagen_data=b"", 
                    mensaje=f"Error procesando parte {i}"
                )

            partes_procesadas.append(resultado)

        imagen_final = np.vstack(partes_procesadas)
        _, buf = cv2.imencode(".png", imagen_final)
        completo_bytes = buf.tobytes()

        return procesador_pb2.ImagenReply(status="ok", imagen_data=completo_bytes)

    def _procesar_parte_individual(self, img):
        """Procesa una parte individual de la imagen"""
        logger.info(f"Nodo {self.nodo_id}: Procesando parte individual")
        img_gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, buf = cv2.imencode(".png", img_gris)
        resultado_bytes = buf.tobytes()
        return procesador_pb2.ImagenReply(status="ok", imagen_data=resultado_bytes)
    
    def _procesar_parte_en_nodo(self, parte, nodo_direccion):
        """Envia parte a un nodo especifico para procesamiento"""
        try:
            _, buf = cv2.imencode(".png", parte)
            parte_bytes = buf.tobytes()
            
            with grpc.insecure_channel(nodo_direccion) as channel:
                stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
                response = stub.ProcesarImagen(
                    procesador_pb2.ImagenRequest(data=parte_bytes),
                    timeout=10.0
                )
                
                if response.status == "ok":
                    parte_np = np.frombuffer(response.imagen_data, np.uint8)
                    return cv2.imdecode(parte_np, cv2.IMREAD_GRAYSCALE)
                    
        except Exception as e:
            logger.error(f"Error procesando en {nodo_direccion}: {e}")
        return None
    
def serve():
    # configuracion del nodo
    nodo_id = int(os.environ.get("NODO_ID", "1"))
    nodos_conocidos = os.environ.get("NODOS_CONOCIDOS", "").split(",")
    nodos_conocidos = [node.strip() for node in nodos_conocidos if node.strip()]

    # servicios
    bully_service = BullyService(nodo_id, nodos_conocidos)
    procesador = ProcesadorImagen(nodo_id, bully_service)
    
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