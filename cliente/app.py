from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request
import base64

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

    if not data:
        return render_template("index.html", error="La imagen esta vacia")

    # TODO: Incrementar el limite de tamaño de la imagen

    with grpc.insecure_channel("servidor:50051") as channel:
        stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
        response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=data))
        if response.status == "ok":
            imagen_base64 = base64.b64encode(response.imagen_data).decode("utf-8")
            return render_template("resultado.html", imagen_procesada=imagen_base64)
        else:
            return render_template("index.html", error="Error en el procesamiento de la imagen")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)