import threading
import time
import grpc
import logging

from proto import bully_pb2
from proto import bully_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BullyCoordinador(bully_pb2_grpc.BullyServiceServicer):
    def __init__(self, nodo_id, lista_nodos):
        self.nodo_id = nodo_id
        self.lista_nodos = lista_nodos  # ["nodo1:50053", "nodo2:50053"]
        self.coordinador_actual = None
        self.es_coordinador = False
        self.eleccion_en_proceso = False
        self.intervalo_heartbeat = 5.0  #segundos
        self.eleccion_timeout = 3.0 
        
        self.lock = threading.RLock() #mutex
        
        # hilos para monitoreo
        self.heartbeat_thread = None
        self.monitor_thread = None
        self.running = True
        
        logger.info(f"Nodo {self.nodo_id} inicializado con nodos conocidos: {self.lista_nodos}")

    def iniciar_servicios(self):
        """Inicia los servicios de monitoreo y heartbeat"""
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.monitor_thread = threading.Thread(target=self._monitor_coordinador, daemon=True)
        
        self.heartbeat_thread.start()
        self.monitor_thread.start()
        
        # se inicia eleccion si no hay coordinador
        if self.coordinador_actual is None:
            threading.Thread(target=self._iniciar_eleccion, daemon=True).start()

    def detener_servicios(self):
        """Detiene todos los servicios"""
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)

    # implementacion gRPC
    def Eleccion(self, request, context):
        """Recibe un mensaje de elección de un nodo con menor ID"""
        with self.lock:
            logger.info(f"Nodo {self.nodo_id}: Recibido mensaje de elección de nodo {request.nodo_id}")
            
            if request.nodo_id < self.nodo_id:
                threading.Thread(target=self._iniciar_eleccion, daemon=True).start()
                return bully_pb2.EleccionReply(status="respuesta")
            else:
                return bully_pb2.EleccionReply(status="ok")

    def Respuesta(self, request, context):
        """Recibe respuesta de un nodo con mayor ID"""
        with self.lock:
            logger.info(f"Nodo {self.nodo_id}: Recibido Respuesta de nodo {request.nodo_id}")
            self.eleccion_en_proceso = False
            return bully_pb2.RespuestaReply(status="ok")

    def Coordinador(self, request, context):
        """Recibe anuncio de nuevo coordinador"""
        with self.lock:
            logger.info(f"Nodo {self.nodo_id}: Nuevo coordinador anunciado: {request.coordinador_id}")
            self.coordinador_actual = request.coordinador_id
            self.es_coordinador = (request.coordinador_id == self.nodo_id)
            self.eleccion_en_proceso = False
            return bully_pb2.CoordinadorReply(status="ok")

    def Heartbeat(self, request, context):
        """Responde a heartbeat del coordinador"""
        return bully_pb2.HeartbeatReply(status="ok", is_alive=True)

    # Métodos internos del algoritmo Bully
    def _iniciar_eleccion(self):
        """Inicia el proceso de elección"""
        with self.lock:
            if self.eleccion_en_proceso:
                return
                
            self.eleccion_en_proceso = True
            logger.info(f"Nodo {self.nodo_id}: Iniciando elección")

        # se envian mensajes a los nodos con mayor ID
        nodos_mayores = [nodo for nodo in self.lista_nodos if self._get_nodo_id(nodo) > self.nodo_id]
        
        respuesta_recibida = False
        
        for direccion in nodos_mayores:
            try:
                with grpc.insecure_channel(direccion) as channel:
                    stub = bully_pb2_grpc.BullyServiceStub(channel)
                    response = stub.Eleccion(bully_pb2.EleccionRequest(nodo_id=self.nodo_id), timeout=self.eleccion_timeout)
                    if response.status == "respuesta":
                        respuesta_recibida = True
                        logger.info(f"Nodo {self.nodo_id}: Recibida respuesta de {direccion}")
            except Exception as e:
                logger.warning(f"Nodo {self.nodo_id}: No se pudo contactar {direccion}: {e}")

        # Si no se recibieron respuestas, se convierte en coordinador
        if not respuesta_recibida:
            time.sleep(1)  # Esperar un poco antes de anunciarse
            with self.lock:
                if self.eleccion_en_proceso:  # Verificar que no haya sido interrumpido
                    self._convertirse_coordinador()

    def _convertirse_coordinador(self):
        """Se convierte en coordinador y lo anuncia"""
        logger.info(f"Nodo {self.nodo_id}: Convirtiéndose en coordinador")
        
        self.coordinador_actual = self.nodo_id
        self.es_coordinador = True
        self.eleccion_en_proceso = False
        
        # se anuncia  a todos los nodos con menor ID
        nodos_menores = [nodo for nodo in self.lista_nodos if self._get_nodo_id(nodo) < self.nodo_id]
        
        for direccion in nodos_menores:
            try:
                with grpc.insecure_channel(direccion) as channel:
                    stub = bully_pb2_grpc.BullyServiceStub(channel)
                    stub.Coordinador(bully_pb2.CoordinadorRequest(coordinador_id=self.nodo_id), timeout=2.0)
                    logger.info(f"Coordinador {self.nodo_id}: Anunciado a {direccion}")
            except Exception as e:
                logger.warning(f"Coordinador {self.nodo_id}: Error anunciando a {direccion}: {e}")

    def _monitor_coordinador(self):
        """Monitorea el estado del coordinador actual"""
        while self.running:
            time.sleep(self.intervalo_heartbeat)
            
            if not self.es_coordinador and self.coordinador_actual is not None:
                if not self._check_coordinador_alive():
                    logger.warning(f"Nodo {self.nodo_id}: Coordinador {self.coordinador_actual} no responde")
                    with self.lock:
                        self.coordinador_actual = None
                    threading.Thread(target=self._iniciar_eleccion, daemon=True).start()

    def _check_coordinador_alive(self):
        """Verifica si el coordinador actual está vivo"""
        if self.coordinador_actual is None:
            return False
            
        coordinador_addr = self._get_nodo_direccion(self.coordinador_actual)
        if not coordinador_addr:
            return False
            
        try:
            with grpc.insecure_channel(coordinador_addr) as channel:
                stub = bully_pb2_grpc.BullyServiceStub(channel)
                response = stub.Heartbeat(
                    bully_pb2.HeartbeatRequest(nodo_id=self.nodo_id),
                    timeout=2.0
                )
                return response.is_alive
        except Exception:
            return False

    def _heartbeat_loop(self):
        """Loop de heartbeat para el coordinador"""
        while self.running:
            if self.es_coordinador:
                logger.debug(f"Coordinador {self.nodo_id}: Enviando heartbeat")
            time.sleep(self.intervalo_heartbeat)

    def _get_nodo_id(self, direccion):
        """Extrae el ID del nodo de su dirección"""
        # Asume formato "nodoX:puerto"
        try:
            nodo_name = direccion.split(':')[0]
            return int(nodo_name.replace('nodo', ''))
        except:
            return 0

    def _get_nodo_direccion(self, nodo_id):
        """Obtiene la dirección de un nodo por su ID"""
        for addr in self.lista_nodos:
            if self._get_nodo_id(addr) == nodo_id:
                return addr
        return None

    # Métodos públicos para integración
    def get_actual_coordinador(self):
        """Retorna el ID del coordinador actual"""
        return self.current_coordinador

    def es_actual_coordinador(self):
        """Verifica si este nodo es el coordinador actual"""
        return self.es_coordinador

    def get_nodos_disponibles(self):
        """Retorna lista de nodos disponibles para procesamiento"""
        disponibles = []
        for direccion in self.lista_nodos:
            try:
                with grpc.insecure_channel(direccion.replace(':50053', ':50052')) as channel:
                    # Verificar disponibilidad del servicio de procesamiento
                    channel_listo = grpc.channel_ready_future(channel)
                    channel_listo.result(timeout=1.0)
                    disponibles.append(direccion.replace(':50053', ':50052'))
            except:
                pass
        return disponibles