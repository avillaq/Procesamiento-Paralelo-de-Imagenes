from pathlib import Path
import sys
import io
import numpy as np
import cv2
import requests
import time

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
        alto_parte = alto//num_nodos # TODO : Manejar el caso cuando la imagen no se pueda dividir en partes iguales
        partes = []
        for i in range(num_nodos):
            inicio = i * alto_parte
            final = (i + 1) * alto_parte if i != num_nodos - 1 else alto
            partes.append(img[inicio:final, :])
        
        partes_procesadas = []
        for i, pt in enumerate(partes):
            _, buf = cv2.imencode(".png", pt)
            parte_bytes = buf.tobytes()
            # TODO: Enviar las partes a los diferentes nodos. Por el momento se envian a un nodo
            time.sleep(1)  # pequeños retrasos para la simulacion 
            response = requests.post("http://localhost:8000/procesar-nodo", files={"img": io.BytesIO(parte_bytes)})
            if response.status_code == 200:
                parte_procesada = np.frombuffer(response.content, np.uint8)
                img_procesada = cv2.imdecode(parte_procesada, cv2.IMREAD_GRAYSCALE)
                print(f"- Parte {i} procesada correctamente")
                partes_procesadas.append(img_procesada)

        final = np.vstack(partes_procesadas)
        _, buf = cv2.imencode(".png", final)
        completo_bytes = buf.tobytes()

        # TODO: Enviar la imagen completa procesada al cliente
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