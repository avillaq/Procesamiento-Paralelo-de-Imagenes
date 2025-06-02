from pathlib import Path
import sys
import io
import numpy as np
import cv2
import time
import os

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

class AdministradorNodos:
    def __init__(self):
        nodos_disponibles = os.environ.get("NODOS_DISPONIBLES")
        self.nodos = [f"{node.strip()}" for node in nodos_disponibles.split(",")]
        self.indice_actual = 0
        
    def obtener_nodos(self):
        return self.nodos

    def obtener_nodo(self):
        nodo = self.nodos[self.indice_actual]
        self.indice_actual = (self.indice_actual + 1) % len(self.nodos)
        return nodo

class Servidor(procesador_pb2_grpc.ProcesadorImagenServicer):
    def __init__(self):
        self.administrador_nodos = AdministradorNodos()

    def procesar_parte(self, nodo, parte_bytes):
        with grpc.insecure_channel(nodo) as channel:
            stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
            response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=parte_bytes))
            if response.status == "ok":
                parte_procesada = np.frombuffer(response.imagen_data, np.uint8)
                img_procesada = cv2.imdecode(parte_procesada, cv2.IMREAD_GRAYSCALE)
                print(f"- Parte procesada correctamente en el nodo {nodo}")
                return img_procesada

            else:
                raise Exception("Error al procesar la imagen en el nodo")

    def ProcesarImagen(self, request, context):
        imagen_np = np.frombuffer(request.data, dtype=np.uint8)
        img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)

        num_nodos = len(self.administrador_nodos.obtener_nodos())

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
            nodo = self.administrador_nodos.obtener_nodo()
            _, buf = cv2.imencode(".png", pt)
            parte_bytes = buf.tobytes()
            # TODO: Enviar las partes a los diferentes nodos. Por el momento se envian a un nodo
            time.sleep(1)  # pequeños retrasos para la simulacion 
            parte_procesada = self.procesar_parte(nodo, parte_bytes)
            partes_procesadas.append(parte_procesada)

        final = np.vstack(partes_procesadas)
        _, buf = cv2.imencode(".png", final)
        completo_bytes = buf.tobytes()

        return procesador_pb2.ImagenReply(status="ok", imagen_data=completo_bytes)

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