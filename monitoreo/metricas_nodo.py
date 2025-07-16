import time
import threading
import logging
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
import os
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)

class RecolectorMetricas:
    """Recolector de métricas para los nodos"""
    
    def __init__(self, nodo_id=None):
        self.nodo_id = nodo_id
        self.registro = CollectorRegistry()
        
        # métricas de procesamiento de imagenes
        self.total_imagenes_procesadas = Counter(
            'total_imagenes_procesadas',
            'Total de imágenes procesadas por el nodo',
            ['nodo_id', 'estado', 'tamano_imagen'],
            registry=self.registro
        )
        
        self.duracion_procesamiento_nodo = Histogram(
            'duracion_procesamiento_nodo',
            'Tiempo de procesamiento de imagenes',
            ['nodo_id', 'tamano_imagen', 'tipo_procesamiento'],
            registry=self.registro,
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
        )
        
        # métricas de Bully
        self.total_elecciones_bully = Counter(
            'total_elecciones_bully',
            'Total de elecciones Bully',
            ['nodo_id', 'resultado'],
            registry=self.registro
        )
        
        self.total_cambios_coordinador = Counter(
            'total_cambios_coordinador',
            'Total de cambios de coordinador',
            ['antiguo_c', 'nuevo_c'],
            registry=self.registro
        )
        
        self.es_coordinador = Gauge(
            'es_coordinador',
            'Indica si este nodo es el coordinador (1=si, 0=no)',
            ['nodo_id'],
            registry=self.registro
        )
        
        # métricas de nodos
        self.nodos_activos = Gauge(
            'nodos_activos',
            'Número de nodos activos en el cluster',
            registry=self.registro
        )
        
        # métricas del sistema
        self.porcentaje_uso_cpu = Gauge(
            'porcentaje_uso_cpu',
            'Porcentaje de uso de CPU',
            ['nodo_id'],
            registry=self.registro
        )
        
        self.porcentaje_uso_memoria = Gauge(
            'porcentaje_uso_memoria',
            'Porcentaje de uso de memoria',
            ['nodo_id'],
            registry=self.registro
        )
        
        self._configurar_info()
        self._lock = threading.RLock()

        # Iniciar monitoreo
        self._monitoring_thread = threading.Thread(target=self._monitor_sistema, daemon=True)
        self._monitoring_running = True
        self._monitoring_thread.start()
        
    def _configurar_info(self):
        """Establece información del sistema"""
        info = {
            'nodo_id': str(self.nodo_id),
            'version': '1.0.0',
            'hostname': os.uname().nodename,
            'inicializado': time.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _monitor_sistema(self):
        """Monitor continuo de métricas del sistema"""
        while self._monitoring_running:
            try:
                # CPU y memoria
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                
                with self._lock:
                    self.porcentaje_uso_cpu.labels(nodo_id=str(self.nodo_id)).set(cpu_percent)
                    self.porcentaje_uso_memoria.labels(nodo_id=str(self.nodo_id)).set(memory_percent)
                
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error monitoreando sistema en nodo {self.nodo_id}: {e}")
                time.sleep(10)
        
    def track_procesamiento_imagen(self, duracion, estado="exito", tamano_imagen="mediana", tipo_procesamiento="escala grises"):
        """Finaliza tracking de procesamiento de imagen"""
        with self._lock:
            self.total_imagenes_procesadas.labels(
                nodo_id=str(self.nodo_id),
                estado=estado,
                tamano_imagen=tamano_imagen
            ).inc()
            
            self.duracion_procesamiento_nodo.labels(
                nodo_id=str(self.nodo_id),
                tamano_imagen=tamano_imagen,
                tipo_procesamiento=tipo_procesamiento
            ).observe(duracion)
    
    # Meodos para bully
    def track_eleccion_bully(self, resultado):
        """Registra eleccion Bully"""
        with self._lock:
            self.total_elecciones_bully.labels(
                nodo_id=str(self.nodo_id),
                resultado=resultado
            ).inc()

    def actualizar_es_coordinador(self, es_coordinador_flag):
        """Actualiza si este nodo es coordinador"""
        with self._lock:
            self.es_coordinador.labels(nodo_id=str(self.nodo_id)).set(
                1 if es_coordinador_flag else 0
            )

    def actualizar_nodos_activos(self, cantidad):
        """Actualiza cantidad de nodos activos"""
        with self._lock:
            self.nodos_activos.set(cantidad)
    
    def track_cambio_coordinador(self, antiguo_c, nuevo_c):
        """Registra cambio de coordinador"""
        with self._lock:
            self.total_cambios_coordinador.labels(
                antiguo_c=str(antiguo_c),
                nuevo_c=str(nuevo_c)
            ).inc()

    def stop_monitoring(self):
        """Detiene el monitoreo"""
        self._monitoring_running = False

    def get_metricas(self):
        """Metricas"""
        return generate_latest(self.registro)
    
    
class MetricasHandler(BaseHTTPRequestHandler):
    """Handler HTTP para servir métricas de Prometheus"""

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
                logger.error(f"Error sirviendo métricas del nodo: {e}")
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
    """Servidor de metrias para los nodos"""
    
    def __init__(self, nodo_id, puerto=8000):
        self.nodo_id = nodo_id
        self.puerto = puerto
        self.server = None
        self.server_thread = None
        self.recolector_metricas = RecolectorMetricas(nodo_id)
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
            logger.info(f"Servidor de métricas del nodo {self.nodo_id} iniciado en puerto {self.puerto}")
        except Exception as e:
            logger.error(f"Error iniciando servidor de métricas del nodo {self.nodo_id}: {e}")
            raise
    
    def _run_server(self):
        """Ejecuta servidor HTTP"""
        while self.running:
            try:
                self.server.handle_request()
            except Exception as e:
                if self.running:
                    logger.error(f"Error en servidor de métricas de nodos: {e}")
                break
    
    def stop(self):
        """Detiene servidor"""
        self.running = False
        self.recolector_metricas.stop_monitoring()
        if self.server:
            self.server.server_close()
        logger.info("Servidor de métricas de nodos detenido")

    def get_recolector(self):
        """Obtiene el recolector de métricas"""
        return self.recolector_metricas