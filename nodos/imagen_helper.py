import numpy as np
import cv2
import grpc
import logging

from proto import procesador_pb2, procesador_pb2_grpc

logger = logging.getLogger(__name__)

class ImagenHelper():
    def __init__(self, nodo_id):
        self.nodo_id = nodo_id

    def procesar_parte_individual(self, imagen_data):
        """Procesa una parte individual de imagen"""
        try:
            imagen_np = np.frombuffer(imagen_data, dtype=np.uint8)
            img = cv2.imdecode(imagen_np, cv2.IMREAD_COLOR)
            
            if img is None:
                return procesador_pb2.ImagenReply(
                    status="error", 
                    imagen_data=b"", 
                    mensaje="Error al decodificar imagen"
                )

            logger.info(f"Nodo {self.nodo_id}: Procesando parte individual")
            
            # se convierte a escala de grises
            img_gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, buf = cv2.imencode(".png", img_gris)
            
            return procesador_pb2.ImagenReply(
                status="ok", 
                imagen_data=buf.tobytes()
            )
            
        except Exception as e:
            logger.error(f"Error procesando imagen en nodo {self.nodo_id}: {e}")
            return procesador_pb2.ImagenReply(
                status="error", 
                imagen_data=b"", 
                mensaje=str(e)
            )

    def dividir_imagen(self, img, num_partes):
        """Divide una imagen en partes horizontales"""
        # division en partes
        alto = img.shape[0] # altura
        alto_parte = alto // num_partes
        resto = alto % num_partes
        
        partes = []
        inicio = 0
        
        for i in range(num_partes):
            # se distrinuye el resto entre las primeras partes
            extra = 1 if i < resto else 0
            final = inicio + alto_parte + extra
            
            if i == num_partes - 1:  # ultima parte toma todo lo que queda
                final = alto
                
            partes.append(img[inicio:final, :])
            inicio = final
            
        return partes

    def unir_imagen(self, partes):
        """Une partes procesadas en una imagen final"""
        try:
            imagen_final = np.vstack(partes)
            _, buf = cv2.imencode(".png", imagen_final)
            return buf.tobytes()
        except Exception as e:
            logger.error(f"Error uniendo partes de imagen: {e}")
            raise

    def enviar_parte_a_nodo(self, parte, nodo_direccion):
        """Envia parte a un nodo especifico para procesamiento"""
        try:
            _, buf = cv2.imencode(".png", parte)
            parte_bytes = buf.tobytes()

            with grpc.insecure_channel(nodo_direccion, options=[
                    ('grpc.max_receive_message_length', 20 * 1024 * 1024),  # 20MB
                    ('grpc.max_send_message_length', 20 * 1024 * 1024)
            ]) as channel:
                stub = procesador_pb2_grpc.ProcesadorImagenStub(channel)
                response = stub.ProcesarImagen(
                    procesador_pb2.ImagenRequest(data=parte_bytes),
                    timeout=10.0
                )
                
                if response.status == "ok":
                    part_np = np.frombuffer(response.imagen_data, np.uint8)
                    return cv2.imdecode(part_np, cv2.IMREAD_GRAYSCALE)
                else:
                    logger.warning(f"Error en respuesta de {nodo_direccion}: {response.mensaje}")
                    
        except Exception as e:
            logger.error(f"Error enviando parte a {nodo_direccion}: {e}")
        
        return None