import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys
from pathlib import Path
from prometheus_client import CONTENT_TYPE_LATEST

sys.path.append(str(Path(__file__).resolve().parent.parent))
from monitoreo.recolector_metricas import RecolectorMetricas

logger = logging.getLogger(__name__)

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
            logger.info(f"Servidor de metrias iniciado en puerto {self.puerto}")
        except Exception as e:
            logger.error(f"Error iniciando servidor de métricas: {e}")
            raise
    
    def _run_server(self):
        """Ejecuta servidor HTTP"""
        while self.running:
            try:
                self.server.serve_request()
            except Exception as e:
                if self.running:
                    logger.error(f"Error en servidor de métricas: {e}")
                break
    
    def stop(self):
        """Detiene servidor"""
        self.running = False
        if self.server:
            self.server.server_close()
        logger.info("Servidor de métricas detenido")

    def get_recolector(self):
        """Obtiene el recolector de métricas"""
        return self.recolector_metricas