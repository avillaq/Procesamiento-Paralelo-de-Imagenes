from functools import wraps
import os
import uuid
import time
from werkzeug.utils import secure_filename
import logging

from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, Response

import grpc
from proto import procesador_pb2
from proto import procesador_pb2_grpc

from glusterFS import GlusterFS
from monitoreo.metricas_cliente import MetricasServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CARPETA_SUBIDOS = "subidos"
CARPETA_PROCESADOS = "procesados"

os.makedirs(CARPETA_SUBIDOS, exist_ok=True)
os.makedirs(CARPETA_PROCESADOS, exist_ok=True)

metricas_cliente_server = MetricasServer(puerto=8000)
recolector_metricas_cliente = None

# Variables para calcular speedup
nodos_activos_actuales = 0

try:
    metricas_cliente_server.start()
    recolector_metricas_cliente = metricas_cliente_server.get_recolector()
    logger.info("Servidor de métricas iniciado exitosamente")
except Exception as e:
    logger.error(f" Error iniciando servidor de métricas: {e}")

try:
    gfs = GlusterFS()
    recolector_metricas_cliente.actualizar_estado_glusterfs(True)
except Exception as e:
    logger.error(f"Error inicializando GlusterFS: {e}")
    gfs = None
    recolector_metricas_cliente.actualizar_estado_glusterfs(False)

def encontrar_coordinador():
    inicio = time.time()
    NODOS_CONOCIDOS = os.environ.get("NODOS_CONOCIDOS", "").split(",")
    
    coordinador_encontrado = None

    for direccion in NODOS_CONOCIDOS:
        direccion_proc = direccion.replace(":50053", ":50052") 
        try:
            with grpc.insecure_channel(direccion_proc) as channel:
                stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
                response = stub.EstadoNodo(procesador_pb2.EstadoRequest(), timeout=2.0)
                
                logger.info(f"Nodo {direccion_proc}: activo, coordinador={response.es_coordinador}")
                if response.es_coordinador and not coordinador_encontrado:
                    coordinador_encontrado = direccion_proc
                    recolector_metricas_cliente.actualizar_coordinador(response.nodo_id)
        except Exception as e:
            logger.debug(f"Nodo {direccion_proc} no disponible: {e}")
            continue
    
    duracion = time.time() - inicio
    recolector_metricas_cliente.track_tiempo_coordinador(duracion)
    
    if not coordinador_encontrado:
        recolector_metricas_cliente.actualizar_coordinador(0)
    
    return coordinador_encontrado

def categorizar_tamano_mb(tamano_mb):
    """Categoriza el tamaño de imagen en MB"""
    if tamano_mb < 1:
        return "< 1MB"
    elif tamano_mb < 3:
        return "1-3MB"
    elif tamano_mb < 5:
        return "3-5MB"
    elif tamano_mb < 10:
        return "5-10MB"
    else:
        return "> 10MB"

def get_url_base(request):
    if 'localhost' in request.host or '127.0.0.1' in request.host:
        return f"http://127.0.0.1:8080"
    else:
        return f"https://super-duper-spoon-gwppvv75j45c94wg-8080.app.github.dev"
    
# decorador para monitorear peticiones HTTP
def monitor_request(endpoint):
    """Decorador para monitorear peticiones HTTP"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):           
            inicio = time.time()
            metodo = request.method
            codigo_estado = 200
            
            try:
                resultado = func(*args, **kwargs)
                
                if isinstance(resultado, tuple):
                    codigo_estado = resultado[1] if len(resultado) > 1 else 200
                elif hasattr(resultado, 'status_code'):
                    codigo_estado = resultado.status_code
                
                return resultado
                
            except Exception as e:
                codigo_estado = 500
                raise
            finally:
                duracion = time.time() - inicio
                recolector_metricas_cliente.track_peticion_http(
                    metodo, endpoint, codigo_estado, duracion
                )
        
        return wrapper
    return decorator

@app.route("/")
@monitor_request("index")
def index():
    usuario_id = request.cookies.get("usuario_id")
    if not usuario_id:
        usuario_id = str(uuid.uuid4())

    # lista de imagenes del usuario
    imagenes = []
    if gfs:
        try:
            imagenes = gfs.get_imagenes_usuario(usuario_id=usuario_id, limite=6)
            base_url = get_url_base(request)
            for imagen in imagenes:
                if imagen.get('imagen_id'):
                    imagen['url'] = f"{base_url}/usuario/{usuario_id}/imagen/{imagen['imagen_id']}"
        except Exception as e:
            logger.error(f"Error obteniendo imagenes del usuario: {e}")
    return render_template("index.html", 
                         imagenes=imagenes, 
                         usuario_id=usuario_id,
                         glusterfs_disponible=gfs is not None)

@app.route("/galeria")
@monitor_request("galeria")
def galeria():
    usuario_id = request.cookies.get("usuario_id", str(uuid.uuid4()))
    
    # todas las imagenes del usuario  
    imagenes_originales = []
    imagenes_procesadas = []
    total_imagenes = 0

    if gfs:
        try:
            imagenes_originales = gfs.get_imagenes_usuario(usuario_id, "original")
            imagenes_procesadas = gfs.get_imagenes_usuario(usuario_id, "procesada")
            base_url = get_url_base(request)
            for imagen in imagenes_originales:
                if imagen.get('imagen_id'):
                    imagen['url'] = f"{base_url}/usuario/{usuario_id}/imagen/{imagen['imagen_id']}"
            for imagen in imagenes_procesadas:
                if imagen.get('imagen_id'):
                    imagen['url'] = f"{base_url}/usuario/{usuario_id}/imagen/{imagen['imagen_id']}"
            total_imagenes = len(imagenes_originales) + len(imagenes_procesadas)
        except Exception as e:
            logger.error(f"Error obteniendo galería del usuario: {e}")

    return render_template("galeria.html", 
                         originales=imagenes_originales,
                         procesadas=imagenes_procesadas,
                         usuario_id=usuario_id,
                         total_imagenes=total_imagenes
                        )

@app.route("/resultado")
@monitor_request("resultado")
def resultado():
    original = request.args.get("original", "")
    final = request.args.get("final", "")
    return render_template("resultado.html", original=original, final=final)

@app.route("/procesar", methods=["POST"])
@monitor_request("procesar")
def procesar_imagen():
    usuario_id = request.cookies.get('usuario_id', str(uuid.uuid4()))
    try:
        if "img" not in request.files:
            recolector_metricas_cliente.track_imagen_subida("error_no_archivo")
            return jsonify({"error": "No se ha enviado ninguna imagen"}), 400
        
        archivo_imagen = request.files["img"]

        if archivo_imagen.filename.split(".")[-1].lower() not in ["jpg", "jpeg", "png", "webp"]:
            recolector_metricas_cliente.track_imagen_subida("error_formato")
            return jsonify({"error": "Formato de imagen no soportado"}), 400
        
        data = archivo_imagen.read()
        tamaño_mb = len(data) / (1024 * 1024)
        categoria_tamano = categorizar_tamano_mb(tamaño_mb)
        
        if tamaño_mb > 20:
            recolector_metricas_cliente.track_imagen_subida("error_tamaño")
            return jsonify({"error": "El tamaño de la imagen no debe exceder los 20 MB"}), 400
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
            recolector_metricas_cliente.track_imagen_subida("error_no_coordinador")
            return jsonify({"error": "No hay nodos coordinadores disponibles"}), 503

        logger.info(f"Enviando imagen a coordinador {coordinador} para procesamiento...")
        
        procesamiento_inicio = time.time()
        with grpc.insecure_channel(coordinador, options=[
                ('grpc.max_receive_message_length', 20 * 1024 * 1024),  # 20MB
                ('grpc.max_send_message_length', 20 * 1024 * 1024)
            ]) as channel:
            
            stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
            response = stub.ProcesarImagen(procesador_pb2.ImagenRequest(data=data), timeout=30.0)
            
            procesamiento_duracion = time.time() - procesamiento_inicio        
            recolector_metricas_cliente.track_procesamiento_imagen(
                procesamiento_duracion, 
                categoria_tamano, 
                "escala grises"
            )
            if response.status == "ok":
                with open(path_final, "wb") as f:
                    f.write(response.imagen_data)

                imagen_procesada_id = None
                if gfs:
                    try:
                        imagen_procesada_id = gfs.guardar_imagen(
                            usuario_id=usuario_id,
                            imagen_data=response.imagen_data,
                            tipo_imagen="procesada",
                        )
                    except Exception as e:
                        logger.error(f"Error almacenando en GlusterFS: {e}")
                        
                base_url = get_url_base(request)
                response_data = {}
                if imagen_procesada_id and imagen_original_id:
                    response_data.update({
                        "original": f"{base_url}/usuario/{usuario_id}/imagen/{imagen_original_id}",
                        "final": f"{base_url}/usuario/{usuario_id}/imagen/{imagen_procesada_id}",
                    })
                else:
                    response_data.update({
                        "original": f"{base_url}/subidos/{nombre_imagen}",
                        "final": f"{base_url}/procesados/{nombre_final_imagen}",
                    })

                recolector_metricas_cliente.track_imagen_subida("exito")
                
                response = make_response(jsonify(response_data))
                response.set_cookie("usuario_id", usuario_id, max_age=30*24*60*60)
                return response, 200
            else:
                recolector_metricas_cliente.track_imagen_subida("error_procesamiento")
                return jsonify({"error": "Error en el procesamiento de la imagen: " + response.mensaje}), 500
                
    except grpc.RpcError as e:
        logger.error(f"Error gRPC procesando imagen: {e}")
        recolector_metricas_cliente.track_imagen_subida("error_grpc")
        recolector_metricas_cliente.track_procesamiento_imagen(0, "error", "error")
        return jsonify({"error": "Error de comunicación con el servidor"}), 503
        
    except Exception as e:
        recolector_metricas_cliente.track_imagen_subida("error_general")
        recolector_metricas_cliente.track_procesamiento_imagen(0, "error", "error")

        logger.error(f"Error procesando imagen: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/usuario/<usuario_id>/imagen/<imagen_id>")
@monitor_request("imagen_distribuida")
def get_imagen_distribuida(usuario_id, imagen_id):
    if not gfs:
        return "Sistema de archivos distribuido no disponible", 503
    
    try:
        imagen_data = gfs.get_imagen_distribuida(usuario_id, imagen_id)
        
        if imagen_data:
            return Response(imagen_data, mimetype='image/jpeg')
        else:
            return "Imagen no encontrada en sistema distribuido", 404
            
    except Exception as e:
        logger.error(f"Error sirviendo imagen distribuida: {e}")
        return "Error accediendo al sistema distribuido", 500
    
@app.route("/cluster/health")
@monitor_request("cluster_health")
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
@monitor_request("archivo_subido")
def archivos_subidos(nombre_archivo):
    return send_from_directory(CARPETA_SUBIDOS, nombre_archivo)

@app.route("/procesados/<nombre_archivo>")
@monitor_request("archivo_procesado")
def archivos_procesados(nombre_archivo):
    return send_from_directory(CARPETA_PROCESADOS, nombre_archivo)

def inicializar_metricas():
    """Inicializa métricas al inicio de la aplicación"""
    if gfs:
        try:
            gfs.get_gluster_health()
            recolector_metricas_cliente.actualizar_estado_glusterfs(True)
            logger.info("GlusterFS inicializado y disponible")
        except Exception as e:
            logger.error(f"Error verificando GlusterFS: {e}")
            recolector_metricas_cliente.actualizar_estado_glusterfs(False)
    
    # Buscar coordinador inicial
    coordinador = encontrar_coordinador()
    if coordinador:
        logger.info(f"Coordinador inicial encontrado: {coordinador}")
    else:
        logger.warning("No se encontró coordinador inicial")

import atexit
def cleanup():
    """Limpieza al cerrar la aplicación"""
    if metricas_cliente_server:
        try:
            metricas_cliente_server.stop()
            logger.info("Servidor de métricas detenido correctamente")
        except Exception as e:
            logger.error(f"Error deteniendo servidor de métricas: {e}")
atexit.register(cleanup)

if __name__ == "__main__":
    inicializar_metricas()
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)