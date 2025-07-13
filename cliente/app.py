import os
import uuid
from werkzeug.utils import secure_filename
import logging

from flask import Flask, render_template, request, jsonify, send_from_directory, url_for

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

from glusterFS import GlusterFS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CARPETA_SUBIDOS = "subidos"
CARPETA_PROCESADOS = "procesados"

os.makedirs(CARPETA_SUBIDOS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

try:
    gfs = GlusterFS()
except Exception as e:
    logger.error(f"Error inicializando GlusterFS: {e}")
    gfs = None

NODOS_CONOCIDOS = os.environ.get("NODOS_CONOCIDOS", "").split(",")
def encontrar_coordinador():
    for direccion in NODOS_CONOCIDOS:
        direccion_proc = direccion.replace(":50053", ":50052") 
        try:
            with grpc.insecure_channel(direccion_proc) as channel:
                stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
                response = stub.EstadoNodo(procesador_pb2.EstadoRequest(), timeout=2.0)
                logger.info(f"Coordinador encontrado en {direccion_proc}: {response.es_coordinador}")
                if response.es_coordinador:
                    return direccion_proc
        except Exception:
            continue
    return None

@app.route("/")
def index():
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        usuario_id = str(uuid.uuid4())

    # lista de imagenes del usuario
    imagenes = []
    if gfs:
        try:
            imagenes = gfs.get_imagenes_usuario(usuario_id=usuario_id, limite=6)
        except Exception as e:
            logger.error(f"Error obteniendo imagenes del usuario: {e}")
    return render_template("index.html", 
                         imagenes=imagenes)

@app.route("/resultado")
def resultado():
    original = request.args.get("original", "")
    final = request.args.get("final", "")
    return render_template("resultado.html", original=original, final=final)

@app.route("/procesar", methods=["POST"])
def procesar_imagen():
    usuario_id = request.cookies.get('usuario_id', str(uuid.uuid4()))

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

    imagen_original_id = None
    if gfs:
        try:
            imagen_original_id = gfs.guardar_imagen(
                usuario_id=usuario_id,
                imagen_data=data,
                tipo_imagen="original",
            )
        except Exception as e:
            logger.error(f"Error almacenando en GlusterFS: {e}")

    # se intenta encontrar un nodo coordinador
    coordinador = encontrar_coordinador()
    if not coordinador:
        return jsonify({"error": "No hay nodos coordinadores disponibles"}), 503

    logger.info(f"Enviando imagen a coordinador {coordinador} para procesamiento...")
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

@app.route("/cluster/health")
def cluster_health():
    if not gfs:
        return jsonify({"error": "Sistema de archivos distribuido no disponible"}), 503
    
    try:
        data = gfs.get_gluster_health()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error obteniendo estado del cluster: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route("/subidos/<nombre_archivo>")
def archivos_subidos(nombre_archivo):
    return send_from_directory(CARPETA_SUBIDOS, nombre_archivo)

@app.route("/procesados/<nombre_archivo>")
def archivos_procesados(nombre_archivo):
    return send_from_directory(CARPETA_PROCESADOS, nombre_archivo)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)