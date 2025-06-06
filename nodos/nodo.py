from pathlib import Path
import sys
import numpy as np
import cv2
import os

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

class Nodo(procesador_pb2_grpc.ProcesadorImagenServicer):
    def __init__(self):
        self.id_nodo = os.environ.get("ID")

    def ProcesarImagen(self, request, context):
        try:
            imagen_np = np.frombuffer(request.data, dtype=np.uint8)
            img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
            if img is None:
                return procesador_pb2.ImagenReply(status="error", imagen_data=b"")

            # Se puede realizar otro procesamiento pero por el momento solo se convierte a escala de grises
            img_gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, buf = cv2.imencode(".png", img_gris)
            resultado_bytes = buf.tobytes()
            print(f"Proceso terminado. Nodo: {self.id_nodo}")
            return procesador_pb2.ImagenReply(status="ok", imagen_data=resultado_bytes)
        except Exception as e:
            print(f"Error al procesar la imagen en el nodo {self.id_nodo}: {e}")
            return procesador_pb2.ImagenReply(status="error", imagen_data=b"")

def serve():
    puerto = os.environ.get("PORT")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    procesador_pb2_grpc.add_ProcesadorImagenServicer_to_server(Nodo(), server)
    server.add_insecure_port("[::]:" + puerto)
    server.start()
    print("Nodo iniciado, escuchando en " + puerto)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()