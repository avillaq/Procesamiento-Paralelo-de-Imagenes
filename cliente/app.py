from pathlib import Path
import sys
import os
import uuid
from werkzeug.utils import secure_filename
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request, jsonify, send_from_directory, url_for

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

app = Flask(__name__)

CARPETA_SUBIDOS = "subidos"
CARPETA_PROCESADOS = "procesados"

os.makedirs(CARPETA_SUBIDOS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

NODOS_DISPONIBLES = [ # estaticos por ahora 
    "nodo1:50052",
    "nodo2:50052", 
    "nodo3:50052",
    "nodo4:50052"
]

def encontrar_coordinador():
    for nodo in NODOS_DISPONIBLES:
        try:
            with grpc.insecure_channel(nodo) as channel:
                future = grpc.channel_ready_future(channel)
                future.result(timeout=2.0)
                return nodo
        except Exception:
            continue
    return None

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
    if "img" not in request.files:
        return jsonify({"error": "No se ha enviado ninguna imagen"}), 400
    
    archivo_imagen = request.files["img"]

    if archivo_imagen.filename.split(".")[-1].lower() not in ["jpg", "jpeg", "png", "webp"]:
        return jsonify({"error": "Formato de imagen no soportado"}), 400
    
    data = archivo_imagen.read()
    tamaño_mb = len(data) / (1024 * 1024)
    if tamaño_mb > 4:
        return jsonify({"error": "El tamaño de la imagen no debe exceder los 4 MB"}), 400
    archivo_imagen.seek(0)

    nombre_imagen = str(uuid.uuid4()) + "-" + secure_filename(archivo_imagen.filename)
    path_original = os.path.join(CARPETA_SUBIDOS, nombre_imagen)

    #guardar imagen original
    archivo_imagen.save(path_original)

    #nombre final de la imagen procesada
    nombre_final_imagen = "final-" + nombre_imagen
    path_final = os.path.join(CARPETA_PROCESADOS, nombre_final_imagen)

    with open(path_original, "rb") as f:
        data = f.read()

    # se intenta encontrar un nodo coordinador
    coordinador = encontrar_coordinador()
    if not coordinador:
        return jsonify({"error": "No hay nodos coordinadores disponibles"}), 503

    with grpc.insecure_channel(coordinador) as channel:
        stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
        response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=data), timeout=30.0)
        if response.status == "ok":
            with open(path_final, "wb") as f:
                f.write(response.imagen_data)
                return jsonify({
                    "original": url_for("archivos_subidos", nombre_archivo=nombre_imagen, _external=True),
                    "final": url_for("archivos_procesados", nombre_archivo=nombre_final_imagen, _external=True),
                })
        else:
            return jsonify({"error": "Error en el procesamiento de la imagen: " + response.status}), 500

@app.route("/subidos/<nombre_archivo>")
def archivos_subidos(nombre_archivo):
    return send_from_directory(CARPETA_SUBIDOS, nombre_archivo)

@app.route("/procesados/<nombre_archivo>")
def archivos_procesados(nombre_archivo):
    return send_from_directory(CARPETA_PROCESADOS, nombre_archivo)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)