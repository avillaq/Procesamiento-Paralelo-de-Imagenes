from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/procesar", methods=["POST"])
def procesar_imagen():
    archivo_imagen = request.files["img"]
    data = archivo_imagen.read()

    with grpc.insecure_channel("localhost:50051") as channel:
        stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
        response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=data))
        print(f"Respuesta del servidor: {response}")

    print(f"Nombre: {archivo_imagen.filename}")
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)