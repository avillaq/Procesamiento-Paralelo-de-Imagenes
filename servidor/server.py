from pathlib import Path
import sys
import numpy as np
import cv2
import os
import threading
import time

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc
from proto import bully_pb2_grpc
from servidor.bully_coordinador import BullyCoordinador

class AdministradorNodos:
    def __init__(self, bully_coordinador):
        self.bully_coordinador = bully_coordinador
        self.id_actual = 0
        
    def get_nodos(self):
        return self.bully_coordinador.get_nodos_disponibles()

    def get_nodo(self):
        nodos = self.get_nodos()
        if not nodos:
            raise Exception("No hay nodos disponibles")
        nodo = nodos[self.id_actual % len(nodos)]
        self.id_actual = (self.id_actual + 1) % len(nodos)
        return nodo

class Servidor(procesador_pb2_grpc.ProcesadorImagenServicer):
    def __init__(self, bully_coordinador):
        self.administrador_nodos = AdministradorNodos(bully_coordinador)
        self.bully_coordinador = bully_coordinador

    def procesar_parte(self, nodo, parte_bytes):
        try:
            with grpc.insecure_channel(nodo) as channel:
                stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
                response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=parte_bytes))
                if response.status == "ok":
                    parte_procesada = np.frombuffer(response.imagen_data, np.uint8)
                    img_procesada = cv2.imdecode(parte_procesada, cv2.IMREAD_GRAYSCALE)
                    print(f"- Parte procesada correctamente en el nodo {nodo}")
                    return img_procesada

        except Exception as e:
            print(f"Error al procesar la parte en el nodo {nodo}: {e}")
            return None

    def ProcesarImagen(self, request, context):
        try:
            # se verifica si hay un coordinador disponible
            if not self.bully_coordinador.get_actual_coordinador():
                return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje="No hay coordinador disponible")

            imagen_np = np.frombuffer(request.data, dtype=np.uint8)
            img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
            if img is None:
                return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje="Error al decodificar la imagen")

            nodos_disponibles = self.administrador_nodos.get_nodos()
            if not nodos_disponibles:
                return procesador_pb2.ImagenReply(status="error", imagen_data=b"", mensaje="No hay nodos disponibles")

            # division en partes
            alto = img.shape[0] # Altura
            num_nodos = len(nodos_disponibles)

            # particion de forma horizontal
            alto_parte = alto//num_nodos 
            resto = alto%num_nodos
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
                nodo = self.administrador_nodos.get_nodo()
                _, buf = cv2.imencode(".png", pt)
                parte_bytes = buf.tobytes()

                parte_procesada = self.procesar_parte(nodo, parte_bytes)
                if parte_procesada is None:
                    return procesador_pb2.ImagenReply(status="error", imagen_data=b"")

                partes_procesadas.append(parte_procesada)

            final = np.vstack(partes_procesadas)
            _, buf = cv2.imencode(".png", final)
            completo_bytes = buf.tobytes()

            return procesador_pb2.ImagenReply(status="ok", imagen_data=completo_bytes)
        except Exception as e:
            print(f"Error al procesar la imagen: {e}")
            return procesador_pb2.ImagenReply(status="error", imagen_data=b"")

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