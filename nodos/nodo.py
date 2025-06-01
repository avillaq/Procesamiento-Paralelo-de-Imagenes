from pathlib import Path
import sys
import io
import numpy as np
import cv2

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

class Nodo(procesador_pb2_grpc.ProcesadorImagenServicer):
    def ProcesarImagen(self, request, context):
        imagen_np = np.frombuffer(request.data, dtype=np.uint8)
        img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)

        # Se puede realizar otro procesamiento pero por el momento solo se convierte a escala de grises
        img_gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, buf = cv2.imencode(".png", img_gris)
        resultado_bytes = buf.tobytes()

        return procesador_pb2.ImagenReply(status="ok", imagen_data=resultado_bytes)

def serve():
    puerto = "50052"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    procesador_pb2_grpc.add_ProcesadorImagenServicer_to_server(Nodo(), server)
    server.add_insecure_port("[::]:" + puerto)
    server.start()
    print("Nodo iniciado, escuchando en " + puerto)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()