from pathlib import Path
import sys
import io
import numpy as np
import cv2
import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

num_nodos = 8 

class Servidor(procesador_pb2_grpc.ProcesadorImagenServicer):
    def ProcesarImagen(self, request, context):
        imagen_np = np.frombuffer(request.data, dtype=np.uint8)
        img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)

        # division en partes
        alto = img.shape[0]
        alto_parte = alto//num_nodos
        partes = []
        for i in range(num_nodos):
            inicio = i * alto_parte
            final = (i + 1) * alto_parte if i != num_nodos - 1 else alto
            partes.append(img[inicio:final, :])
        
        partes_procesadas = []
        for pt in enumerate(partes):
            _, buf = cv2.imencode(".png", pt)
            parte_bytes = buf.tobytes()
            # Por el momento solo se envía la parte de la imagen a un nodo
            response = requests.post("http://localhost:8000/procesar-nodo", files={"img": io.BytesIO(parte_bytes)})
            if response.status_code == 200:
                # TODO: Hacer que los nodos retorne la imagen procesada. Por el momento solo envian un mensaje.
                print(f"- Parte procesada correctamente")
                partes_procesadas.append(pt)
        return procesador_pb2.ImagenReply(status="imagen procesada correctamente")

def serve():
    puerto = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    procesador_pb2_grpc.add_ProcesadorImagenServicer_to_server(Servidor(), server)
    server.add_insecure_port("[::]:" + puerto)
    server.start()
    print("Server iniciado, escuchando en " + puerto)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()