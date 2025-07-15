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
            'Total de imagenes procesadas',
            ['nodo_id', 'estado', 'tipo_procesamiento'],
            registry=self.registro
        )
        
        self.duracion_procesamiento = Histogram(
            'duracion_procesamiento',
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
        
        self.coordinador_actual = Gauge(
            'coordinador_actual_nodo_id',
            'ID del coordinador actual',
            registry=self.registro
        )

        self.es_coordinador = Gauge(
            'es_coordinador',
            'Indica si este nodo es el coordinador (1=si, 0=no)',
            ['nodo_id'],
            registry=self.registro
        )
        
        # métricas de gRPC
        self.total_peticiones_grpc = Counter(
            'total_peticiones_grpc',
            'Total de peticiones gRPC',
            ['nodo_id', 'metodo', 'estado'],
            registry=self.registro
        )
        
        self.duracion_peticion_grpc = Histogram(
            'duracion_peticion_grpc',
            'Duración de peticiones gRPC',
            ['nodo_id', 'metodo'],
            registry=self.registro
        )
        
        # métricas de nodos
        self.nodos_activos = Gauge(
            'nodos_activos',
            'Número de nodos activos en el cluster',
            registry=self.registro
        )
        
        self.estado_nodo = Gauge(
            'estado_nodo',
            'Estado de salud del nodo (1=healthy, 0=unhealthy)',
            ['nodo_id'],
            registry=self.registro
        )
        
        # métricas del sistema
        self.uso_cpu = Gauge(
            'porcentaje_uso_cpu',
            'Uso de CPU del nodo',
            ['nodo_id'],
            registry=self.registro
        )
        
        self.uso_memoria = Gauge(
            'porcentaje_uso_memoria',
            'Uso de memoria del nodo',
            ['nodo_id'],
            registry=self.registro
        )
        
        self.carga_trabajo = Gauge(
            'carga_trabajo_actual',
            'Carga de trabajo actual del nodo',
            ['nodo_id'],
            registry=self.registro
        )
        
        # info del sistema
        self.info_sistema = Info(
            'info_sistema',
            'Informacion del sistema',
            registry=self.registro
        )
        
        self._configurar_info_sistema()
        
        self._lock = threading.RLock()
        self._ultima_actualizacion = time.time()

        # Iniciar metricas
        self.estado_nodo.labels(nodo_id=str(nodo_id)).set(1)
        self.es_coordinador.labels(nodo_id=str(nodo_id)).set(0)
        
    def _configurar_info_sistema(self):
        """Establece información del sistema"""
        info = {
            'nodo_id': str(self.nodo_id),
            'version': '1.0.0',
            'hostname': os.uname().nodename,
            'arquitectura': os.uname().machine,
            'sistema_operativo': os.uname().sysname,
            'inicializado': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        self.info_sistema.info(info)
    
    def actualizar_metricas_sistema(self):
        """Actualiza métricas del sistema operativo"""
        try:
            with self._lock:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                self.uso_cpu.labels(nodo_id=str(self.nodo_id)).set(cpu_percent)
                
                # Memoria
                memoria = psutil.virtual_memory()
                self.uso_memoria.labels(nodo_id=str(self.nodo_id)).set(memoria.percent)
                
                self._ultima_actualizacion = time.time()
                
        except Exception as e:
            logger.error(f"Error actualizando métricas del sistema: {e}")
    
    # Metodos para tracking de imagenes
    def track_procesamiento_imagen(self, duracion, estado = "exito", tamano_imagen = "mediana", tipo_procesamiento = "escala grises"):
        """Finaliza tracking de procesamiento de imagen"""
        with self._lock:
            self.total_imagenes_procesadas.labels(
                nodo_id=str(self.nodo_id),
                estado=estado,
                tipo_procesamiento=tipo_procesamiento
            ).inc()
            
            self.duracion_procesamiento.labels(
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

    def actualizar_coordinador(self, coordinador_id, es_coordinador_local=False):
        """Actualiza información del coordinador"""
        with self._lock:
            self.coordinador_actual.set(float(coordinador_id))
            self.es_coordinador.labels(nodo_id=str(self.nodo_id)).set(
                1 if es_coordinador_local else 0
            )
    
    def track_cambio_coordinador(self, antiguo_c, nuevo_c):
        """Registra cambio de coordinador"""
        with self._lock:
            self.total_cambios_coordinador.labels(
                antiguo_c=str(antiguo_c),
                nuevo_c=str(nuevo_c)
            ).inc()

    def actualizar_cluster_info(self, nodos_activos, estados_nodos):
        """Actualiza información del cluster"""
        with self._lock:
            self.nodos_activos.set(nodos_activos)
            
            for nodo_id, estado in estados_nodos.items():
                self.estado_nodo.labels(nodo_id=str(nodo_id)).set(1 if estado else 0)
    
    # Metodos para gRPC
    def track_peticion_grpc(self, metodo, duracion, estado = "exito"):
        """Finaliza tracking de peticion gRPC"""        
        with self._lock:
            self.total_peticiones_grpc.labels(
                nodo_id=str(self.nodo_id),
                metodo=metodo,
                estado=estado
            ).inc()
            
            self.duracion_peticion_grpc.labels(
                nodo_id=str(self.nodo_id),
                metodo=metodo
            ).observe(duracion)

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
                self.recolector_metricas.actualizar_metricas_sistema()
                metricas_data = self.recolector_metricas.get_metricas()
                self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.end_headers()
                self.wfile.write(metricas_data)
            except Exception as e:
                logger.error(f"Error sirviendo métricas: {e}")
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
            logger.info(f"Servidor de metricas de nodos iniciado en puerto {self.puerto}")
        except Exception as e:
            logger.error(f"Error iniciando servidor de métricas: {e}")
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
        if self.server:
            self.server.server_close()
        logger.info("Servidor de métricas de nodos detenido")

    def get_recolector(self):
        """Obtiene el recolector de métricas"""
        return self.recolector_metricas