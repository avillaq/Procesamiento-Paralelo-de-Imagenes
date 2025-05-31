from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from concurrent import futures

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

class Servidor(procesador_pb2_grpc.ProcesadorImagenServicer):
    def ProcesarImagen(self, request, context):
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