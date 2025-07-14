import time
import threading
import logging
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CollectorRegistry
import os

import psutil


logger = logging.getLogger(__name__)

class RecolectorMetricas:
    """Recolector de métricas"""
    
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
        
        # métricas del sistema de archivos distribuido
        self.total_operaciones_glusterfs = Counter(
            'total_operaciones_glusterfs',
            'Operaciones en sistema de archivos distribuido',
            ['operation', 'estado'],
            registry=self.registro
        )
        
        self.total_archivos_almacenados = Gauge(
            'total_archivos_almacenados',
            'Total de archivos en almacenamiento distribuido',
            ['usuario_id', 'tipo_archivo'],
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
            self.coordinador_actual.set(coordinador_id)
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

    # Metodos para sistema de archivos distribuido
    def track_operacion_glusterfs(self, operation, estado = "exito"):
        """Registra operacion en almacenamiento distribuido"""
        with self._lock:
            self.total_operaciones_glusterfs.labels(
                operation=operation,
                estado=estado
            ).inc()

    def actualizar_metricas_almacenamiento(self, archivo_usuario_tipo):
        """Actualiza métricas de almacenamiento"""
        with self._lock:
            for (usuario_id, tipo_archivo), count in archivo_usuario_tipo.items():
                self.total_archivos_almacenados.labels(
                    usuario_id=usuario_id,
                    tipo_archivo=tipo_archivo
                ).set(count)
    
    def get_metricas(self):
        """Metricas"""
        return generate_latest(self.registro)