import logging
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor, as_completed
from proto import procesador_pb2

logger = logging.getLogger(__name__)

class CoordinadorService:
    def __init__(self, nodo_id, bully_service, imagen_helper):
        self.nodo_id = nodo_id
        self.bully_service = bully_service
        self.imagen_helper = imagen_helper

    def procesar_imagen_distribuida(self, imagen_data):
        """Distribuye imagen a nodos disponibles"""
        try:
            imagen_np = np.frombuffer(imagen_data, dtype=np.uint8)
            img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
            
            if img is None:
                return procesador_pb2.ImagenReply(
                    status="error", 
                    imagen_data=b"", 
                    mensaje="Error al decodificar imagen"
                )

            # nodos disponibles
            nodos_disponibles = self.bully_service.get_nodos_disponibles()
            if not nodos_disponibles:
                return procesador_pb2.ImagenReply(
                    status="error", 
                    imagen_data=b"", 
                    mensaje="No hay nodos disponibles"
                )

            logger.info(f"Coordinador {self.nodo_id}: Procesando imagen con {len(nodos_disponibles)} nodos")
            logger.info(f"Nodos disponibles: {nodos_disponibles}")

            # dividir imagen
            num_nodos = len(nodos_disponibles)
            partes = self.imagen_helper.dividir_imagen(img, num_nodos)

            partes_procesadas = self._procesar_partes_paralelo(partes, nodos_disponibles)

            if len(partes_procesadas) != len(partes):
                return procesador_pb2.ImagenReply(
                    status="error", 
                    imagen_data=b"", 
                    mensaje=f"Solo se procesaron {len(partes_procesadas)}/{len(partes)} partes"
                )

            # se une todas las partes
            imagen_final_bytes = self.imagen_helper.unir_imagen(partes_procesadas)
            
            logger.info(f"Coordinador {self.nodo_id}: Imagen procesada exitosamente")
            return procesador_pb2.ImagenReply(status="ok", imagen_data=imagen_final_bytes)

        except Exception as e:
            logger.error(f"Error en procesamiento distribuido: {e}")
            return procesador_pb2.ImagenReply(
                status="error", 
                imagen_data=b"", 
                mensaje=str(e)
            )

    def _procesar_partes_paralelo(self, partes, nodos_disponibles):
        """Procesa todas las partes en paralelo"""
        partes_procesadas = [None] * len(partes)
        
        max_workers = min(len(nodos_disponibles), 8) # 8 hilos max
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {}
            
            for i, pt in enumerate(partes):
                nodo_objetivo = nodos_disponibles[i % len(nodos_disponibles)]
                
                future = executor.submit(
                    self._procesar_parte_con_reintentos, 
                    pt, 
                    nodo_objetivo, 
                    nodos_disponibles, 
                )
                future_to_index[future] = i
            
            # se recogen los resultados conforme van terminando
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    resultado = future.result(timeout=15.0)  # 15 segundos timeout
                    if resultado is not None:
                        partes_procesadas[index] = resultado
                        logger.info(f"Parte {index} completada")
                    else:
                        logger.error(f"Parte {index} fallo despues de reintentos")
                except Exception as e:
                    logger.error(f"Error en parte {index}: {e}")
        
        # solo resultados validos
        return [p for p in partes_procesadas if p is not None]
    
    def _procesar_parte_con_reintentos(self, parte, nodo_objetivo, nodos_disponibles, max_intentos=2):
        """Procesa una parte con reintentos en diferentes nodos"""

        # con el nodo objetivo 
        resultado = self.imagen_helper.enviar_parte_a_nodo(parte, nodo_objetivo)
        if resultado is not None:
            return resultado
        
        # con otros nodos
        for intento in range(max_intentos):
            for otro in nodos_disponibles:
                if otro != nodo_objetivo:
                    logger.warning(f"Reintentando parte en nodo {otro} (intento {intento + 1})")
                    resultado = self.imagen_helper.enviar_parte_a_nodo(parte, otro)
                    if resultado is not None:
                        return resultado
        
        return None