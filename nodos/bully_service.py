import threading
import time
import grpc
import logging

from proto import bully_pb2
from proto import bully_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BullyService(bully_pb2_grpc.BullyServiceServicer):
    def __init__(self, nodo_id, lista_nodos):
        self.nodo_id = nodo_id
        self.lista_nodos = lista_nodos  # ["nodo1:50053", "nodo2:50053"]
        self.coordinador_actual = None
        self.es_coordinador = False
        self.eleccion_en_proceso = False
        self.intervalo_heartbeat = 5.0  #segundos
        self.timeout_eleccion = 3.0 
        
        self.lock = threading.RLock() #mutex
        
        self.running = True
        
        logger.info(f"Nodo {self.nodo_id} inicializado con nodos conocidos: {self.lista_nodos}")

    def iniciar_servicios(self):
        """Inicia los servicios de Bully"""        
        # se espera un poco antes de iniciar eleccion para que todos los nodos esten listos
        threading.Timer(2.0, self._iniciar_eleccion_inicial).start()

        # se inicia monitor de coordinador
        threading.Thread(target=self._monitor_coordinador, daemon=True).start()

    def _iniciar_eleccion_inicial(self):
        if self.coordinador_actual is None:
            threading.Thread(target=self._iniciar_eleccion, daemon=True).start()

    def detener_servicios(self):
        """Detiene todos los servicios"""
        self.running = False

    # implementacion gRPC
    def Eleccion(self, request, context):
        """Recibe un mensaje de eleccion"""
        with self.lock:
            logger.info(f"Nodo {self.nodo_id}: Recibido mensaje de elección de nodo {request.nodo_id}")
            
            if request.nodo_id < self.nodo_id:
                # se responde y se inicia propia elección
                threading.Thread(target=self._responder_y_elegir, args=(request.nodo_id,), daemon=True).start()
                return bully_pb2.EleccionReply(status="respuesta")
            else:
                return bully_pb2.EleccionReply(status="ok")

    def _responder_y_elegir(self, nodo_solicitante):
        """Envía respuesta y luego inicia elección"""
        try:
            # mensaje de respuesta
            direccion = self._get_nodo_direccion(nodo_solicitante)
            if direccion:
                with grpc.insecure_channel(direccion) as channel:
                    stub = bully_pb2_grpc.BullyServiceStub(channel)
                    stub.Respuesta(bully_pb2.RespuestaRequest(nodo_id=self.nodo_id), timeout=2.0)
        except Exception as e:
            logger.warning(f"Error enviando respuesta a nodo {nodo_solicitante}: {e}")
        
        # se inicia la propia elección
        self._iniciar_eleccion()
    
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
        """Responde a heartbeat"""
        return bully_pb2.HeartbeatReply(status="ok", is_alive=True)

    # funciones auxiliares del algoritmo Bully
    def _iniciar_eleccion(self):
        """Inicia el proceso de elección"""
        with self.lock:
            if self.eleccion_en_proceso:
                return
                
            self.eleccion_en_proceso = True
            logger.info(f"Nodo {self.nodo_id}: Iniciando eleccion")

        # se envian mensajes a los nodos con mayor ID
        nodos_mayores = [nodo for nodo in self.lista_nodos if self._get_nodo_id(nodo) > self.nodo_id]
        
        respuestas_recibidas = False
        
        for direccion in nodos_mayores:
            try:
                with grpc.insecure_channel(direccion) as channel:
                    stub = bully_pb2_grpc.BullyServiceStub(channel)
                    response = stub.Eleccion(
                        bully_pb2.EleccionRequest(nodo_id=self.nodo_id), 
                        timeout=self.timeout_eleccion
                    )
                    if response.status == "respuesta":
                        respuestas_recibidas = True
                        logger.info(f"Nodo {self.nodo_id}: Recibida respuesta de {direccion}")
            except Exception as e:
                logger.warning(f"Nodo {self.nodo_id}: No se pudo contactar {direccion}: {e}")

        # Si no se recibieron respuestas, se convierte en coordinador
        if not respuestas_recibidas:
            time.sleep(2)
            with self.lock:
                if self.eleccion_en_proceso:
                    self._convertirse_coordinador()

    def _convertirse_coordinador(self):
        """Se convierte en coordinador"""
        logger.info(f"Nodo {self.nodo_id}: Convirtiéndose en coordinador")
        
        self.coordinador_actual = self.nodo_id
        self.es_coordinador = True
        self.eleccion_en_proceso = False
        
        for direccion in self.lista_nodos:
            if self._get_nodo_id(direccion) != self.nodo_id:
                try:
                    with grpc.insecure_channel(direccion) as channel:
                        stub = bully_pb2_grpc.BullyServiceStub(channel)
                        stub.Coordinador(
                            bully_pb2.CoordinadorRequest(coordinador_id=self.nodo_id), 
                            timeout=2.0
                        )
                        logger.info(f"Coordinador {self.nodo_id}: Anunciado a {direccion}")
                except Exception as e:
                    logger.warning(f"Error anunciando a {direccion}: {e}")

    def _monitor_coordinador(self):
        """Monitorea coordinador actual"""
        while self.running:
            time.sleep(self.intervalo_heartbeat)
            
            if not self.es_coordinador and self.coordinador_actual is not None:
                if not self._verificar_coordinador_alive():
                    logger.warning(f"Nodo {self.nodo_id}: Coordinador {self.coordinador_actual} no responde")
                    with self.lock:
                        self.coordinador_actual = None
                    threading.Thread(target=self._iniciar_eleccion, daemon=True).start()

    def _verificar_coordinador_alive(self):
        """Verifica si el coordinador actual está vivo"""
        if self.coordinador_actual is None:
            return False
            
        direccion = self._get_nodo_direccion(self.coordinador_actual)
        if not direccion:
            return False
            
        try:
            with grpc.insecure_channel(direccion) as channel:
                stub = bully_pb2_grpc.BullyServiceStub(channel)
                response = stub.Heartbeat(
                    bully_pb2.HeartbeatRequest(nodo_id=self.nodo_id),
                    timeout=2.0
                )
                return response.is_alive
        except Exception:
            return False

    def _get_nodo_id(self, direccion):
        """Extrae el ID del nodo"""
        try:
            nombre = direccion.split(":")[0]
            return int(nombre.replace("nodo", ""))
        except:
            return 0

    def _get_nodo_direccion(self, nodo_id):
        """Obtiene la dirección de un nodo por su ID"""
        for direccion in self.lista_nodos:
            if self._get_nodo_id(direccion) == nodo_id:
                return direccion
        return None

    def get_nodos_disponibles(self):
        """Lista de nodos disponibles para procesamiento"""
        disponibles = []
        for direccion in self.lista_nodos:
            try:
                # se cambia puerto de bully (50053) a procesamiento (50052)
                direccion_proc = direccion.replace(":50053", ":50052")
                with grpc.insecure_channel(direccion_proc) as channel:
                    channel_listo = grpc.channel_ready_future(channel)
                    channel_listo.result(timeout=1.0)
                    disponibles.append(direccion_proc)
            except:
                pass
        return disponibles