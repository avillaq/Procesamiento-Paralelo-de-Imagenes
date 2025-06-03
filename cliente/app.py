from pathlib import Path
import sys
import os
import uuid
from werkzeug.utils import secure_filename
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request, jsonify
import base64

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

app = Flask(__name__)

CARPETA_SUBIDOS = "subidos"
CARPETA_PROCESADOS = "procesados"

os.makedirs(CARPETA_SUBIDOS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/resultado")
def resultado():
    original = request.args.get("original", "")
    final = request.args.get("final", "")
    return render_template("resultado.html", original=original, final=final)

@app.route("/procesar", methods=["POST"])
def procesar_imagen():
    archivo_imagen = request.files["img"]

    # TODO: Incrementar el limite de tamaño de la imagen

    nombre_imagen = str(uuid.uuid4()) + "-" + secure_filename(archivo_imagen.filename)
    path_original = os.path.join(CARPETA_SUBIDOS, nombre_imagen)

    #guardar imagen original
    archivo_imagen.save(path_original)

    #nombre final de la imagen procesada
    nombre_final_imagen = "final-" + nombre_imagen
    path_final = os.path.join(CARPETA_PROCESADOS, nombre_final_imagen)

    with open(path_original, "rb") as f:
        data = f.read()

    with grpc.insecure_channel("servidor:50051") as channel:
        stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
        response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=data))
        if response.status == "ok":
            with open(path_final, "wb") as f:
                f.write(response.imagen_data)
                return jsonify({
                        "success": True,
                        "original": path_original,
                        "final": path_final,
                })
        else:
            return jsonify({"error": "Error en el procesamiento de la imagen: " + response.status}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)