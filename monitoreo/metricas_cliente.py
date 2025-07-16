import threading
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

class RecolectorMetricas:
    """Recolector de métricas para el cliente Flask"""
    
    def __init__(self):
        self.registro = CollectorRegistry()
        
        # métricas HTTP
        self.total_peticiones_http = Counter(
            'total_peticiones_http',
            'Total de peticiones HTTP recibidas',
            ['metodo', 'endpoint', 'codigo_estado'],
            registry=self.registro
        )
        
        self.duracion_peticiones_http = Histogram(
            'duracion_peticiones_http_segundos',
            'Duración de peticiones HTTP',
            ['metodo', 'endpoint'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registro
        )
        
        # procesamiento
        self.total_imagenes_subidas = Counter(
            'total_imagenes_subidas',
            'Total de imágenes subidas',
            ['estado'],
            registry=self.registro
        )

        self.duracion_procesamiento_cliente = Histogram(
            'duracion_procesamiento_cliente',
            'Tiempo de procesamiento de imagenes',
            ['tamano_mb', 'tipo_procesamiento'],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
            registry=self.registro,
        )
        
        # métricas de GlusterFS     
        self.estado_glusterfs = Gauge(
            'estado_glusterfs',
            'Estado de GlusterFS (1=disponible, 0=no disponible)',
            registry=self.registro
        )

        # métricas de coordinación (bully)
        self.tiempo_busqueda_coordinador = Histogram(
            'tiempo_busqueda_coordinador_segundos',
            'Tiempo para encontrar coordinador',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0],
            registry=self.registro
        )

        self.coordinador_actual = Info(
            'coordinador_actual_nodo_id',
            'ID del coordinador actual',
            registry=self.registro
        )
        
        self._configurar_info()
        self._lock = threading.RLock()
        
    def _configurar_info(self):
        """Configura información del cliente"""
        import flask
        import os
        
        info = {
            'version': '1.0.0',
            'flask_version': flask.__version__,
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'inicializado': time.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def track_peticion_http(self, metodo, endpoint, codigo_estado, duracion):
        """Registra petición HTTP"""
        with self._lock:
            self.total_peticiones_http.labels(
                metodo=metodo,
                endpoint=endpoint,
                codigo_estado=str(codigo_estado)
            ).inc()
            
            self.duracion_peticiones_http.labels(
                metodo=metodo,
                endpoint=endpoint
            ).observe(duracion)
    
    def track_imagen_subida(self, estado="exito"):
        """Registra imagen subida"""
        with self._lock:
            self.total_imagenes_subidas.labels(estado=estado).inc()

    def track_procesamiento_imagen(self, duracion, tamano_mb, tipo_procesamiento = "escala grises"):
        """Finaliza tracking de procesamiento de imagen"""
        with self._lock:           
            self.duracion_procesamiento_cliente.labels(
                tamano_mb=tamano_mb,
                tipo_procesamiento=tipo_procesamiento
            ).observe(duracion)
    
    def actualizar_estado_glusterfs(self, disponible):
        """Actualiza estado de GlusterFS"""
        with self._lock:
            self.estado_glusterfs.set(1 if disponible else 0)
    
    def actualizar_coordinador(self, coordinador_id):
        """Actualiza informacion del coordinador"""
        with self._lock:
            self.coordinador_actual.info({'nodo_id': str(coordinador_id),})
    
    def track_tiempo_coordinador(self, duracion):
        """Registra tiempo de búsqueda de coordinador"""
        with self._lock:
            self.tiempo_busqueda_coordinador.observe(duracion)
    
    def get_metricas(self):
        """Obtiene métricas en formato Prometheus"""
        return generate_latest(self.registro)

class MetricasHandler(BaseHTTPRequestHandler):
    """Handler para métricas para el cliente"""
    
    def __init__(self, recolector_metricas, *args, **kwargs):
        self.recolector_metricas = recolector_metricas
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == "/metricas":
            try:
                metricas_data = self.recolector_metricas.get_metricas()
                self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(metricas_data)
                
            except Exception as e:
                logger.error(f"Error sirviendo métricas del cliente: {e}")
                self.send_response(500)
                self.end_headers()

        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{'status': 'healthy'}")

        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

class MetricasServer:
    """Servidor de métricas para el cliente Flask"""
    
    def __init__(self, puerto=8000):
        self.puerto = puerto
        self.server = None
        self.server_thread = None
        self.recolector_metricas = RecolectorMetricas()
        self.running = False
        
    def start(self):
        """Inicia servidor"""
        try:
            def handler(*args, **kwargs):
                return MetricasHandler(self.recolector_metricas, *args, **kwargs)

            self.server = HTTPServer(('', self.puerto), handler)
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.running = True
            self.server_thread.start()
            logger.info(f"Servidor de métricas del cliente iniciado en puerto {self.puerto}")
            
        except Exception as e:
            logger.error(f"Error iniciando servidor de métricas del cliente: {e}")
            raise
    
    def _run_server(self):
        """Ejecuta servidor"""
        while self.running:
            try:
                self.server.handle_request()
            except Exception as e:
                if self.running:
                    logger.error(f"Error en servidor de métricas del cliente: {e}")
                break
    
    def stop(self):
        """Detiene servidor"""
        self.running = False
        if self.server:
            self.server.server_close()
        logger.info("Servidor de métricas del cliente detenido")
    
    def get_recolector(self):
        """Obtiene recolector de métricas"""
        return self.recolector_metricas