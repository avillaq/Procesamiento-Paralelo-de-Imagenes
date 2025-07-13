import os
import json
import hashlib
import subprocess
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# replicación automatica, alta disponibilidad y tolerancia a fallos
class GlusterFS:
    def __init__(self, mnt_punto="/mnt/almacenamiento_dist"):
        self.mnt_punto = mnt_punto
        self.usuarios_dir = os.path.join(mnt_punto, "usuarios")
        self.cluster_dir = os.path.join(mnt_punto, "cluster")
        
        # se verifica y configura glusterFS
        self._verificar_gluster_mnt()
        self._iniciar_estructura_directorios()
    
    def _verificar_gluster_mnt(self):
        """Verifica que GlusterFS esta montado"""
        try:
            if not os.path.exists(self.mnt_punto):
                raise Exception(f"Punto de montaje {self.mnt_punto} no existe")
            
            # estadisticas
            stat_info = os.statvfs(self.mnt_punto)
            espacio_total_gb = (stat_info.f_blocks * stat_info.f_frsize) / (1024**3)
            logger.info(f"Espacio total disponible: {espacio_total_gb:.2f} GB")
            
        except Exception as e:
            logger.error(f"Error verificando GlusterFS: {e}")
            raise
    
    def _iniciar_estructura_directorios(self):
        """Inicializa la estructura de directorios"""
        directorios = [
            self.usuarios_dir,
            self.cluster_dir,
            os.path.join(self.cluster_dir, "health"),
        ]
        
        for direc in directorios:
            try:
                os.makedirs(direc, exist_ok=True)
            except Exception as e:
                logger.error(f"Error creando directorio {direc}: {e}")

    def guardar_imagen(self, usuario_id, imagen_data, tipo_imagen="procesada"):
        """
        Almacena imagen en el sistema distribuido con replicación automática
        
        Args:
            usuario_id: ID único del usuario
            imagen_data: Datos binarios de la imagen
            tipo_imagen: 'original' o 'procesada'
            
        Returns:
            imagen_id: ID único de la imagen almacenada
        """
        
        # genera id de imagen
        imagen_hash = hashlib.sha256(imagen_data).hexdigest()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        imagen_id = f"{timestamp}_{imagen_hash[:12]}"
        
        try:
            # estructura de directorio del usuario
            usuario_path = os.path.join(self.usuarios_dir, usuario_id)
            tipo_imagen_path = os.path.join(usuario_path, tipo_imagen)
            metadata_path = os.path.join(usuario_path, "metadata")
            
            for path in [usuario_path, tipo_imagen_path, metadata_path]:
                os.makedirs(path, exist_ok=True)
            
            # se guarda la imagen principal
            imagen_nombre = f"{imagen_id}.jpg"
            imagen_principal_path = os.path.join(tipo_imagen_path, imagen_nombre)
            
            # se escribe la imagen en disco
            temp_path = imagen_principal_path + ".tmp"
            with open(temp_path, "wb") as f:
                f.write(imagen_data)
                f.flush()
                os.fsync(f.fileno())
            
            os.rename(temp_path, imagen_principal_path)
            
            # crear metadatos
            imagen_metadata = {
                "imagen_id": imagen_id,
                "usuario_id": usuario_id,
                "tipo": tipo_imagen,
                "fecha_creado": datetime.now().isoformat(),
                "tamano_mb": round(len(imagen_data) / (1024 * 1024), 2),
                "principal_path": imagen_principal_path,
                "imagen_hash": imagen_hash,
                "alta_disponibilidad": True
            }
            
            # guradar metadatos
            metadata_path = os.path.join(metadata_path, f"{imagen_id}.json")
            with open(metadata_path, "w") as f:
                json.dump(imagen_metadata, f, indent=2)
            
            logger.info(f"Imagen {imagen_id} almacenada exitosamente")
            return imagen_id
            
        except Exception as e:
            logger.error(f"Error almacenando imagen {imagen_id}: {e}")
            raise
    

    def get_imagenes_usuario(self, usuario_id, tipo_imagen=None, limite=None):
        """Lista de imagenes de un usuario"""
        try:
            metadata_dir = os.path.join(self.usuarios_dir, usuario_id, "metadata")
            
            if not os.path.exists(metadata_dir):
                logger.info(f"Usuario {usuario_id} no tiene imagenes almacenadas")
                return []
            
            imagenes = []
            
            # se leen todos metadatos
            for metadt in os.listdir(metadata_dir):
                if metadt.endswith(".json"):
                    metadata_path = os.path.join(metadata_dir, metadt)
                    
                    try:
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                        
                        # se filtra por tipo
                        if tipo_imagen and metadata.get("tipo") != tipo_imagen:
                            continue
                        
                        principal_path = metadata.get("principal_path")
                        if principal_path and os.path.exists(principal_path): # se verifica que exista la imagen principal
                            metadata["disponible"] = self._verificar_imagen_disponible(usuario_id, metadata["imagen_id"])
                            imagenes.append(metadata)
                        else:
                            logger.warning(f"Imagen {metadata.get('imagen_id')} no encontrada")
                    
                    except Exception as e:
                        logger.error(f"Error leyendo metadatos {metadt}: {e}")
            
            if limite:
                imagenes = imagenes[:limite]
            return imagenes
            
        except Exception as e:
            logger.error(f"Error obteniendo imagenes del usuario {usuario_id}: {e}")
            return []
    
    def get_imagen_distribuida(self, usuario_id, imagen_id):
        """Obtiene imagen del sistema distribuido"""
        
        search_paths = [
            os.path.join(self.usuarios_dir, usuario_id, "original", f"{imagen_id}.jpg"),
            os.path.join(self.usuarios_dir, usuario_id, "procesada", f"{imagen_id}.jpg")
        ]
        
        # Intentar desde ubicaciones principales
        for path in search_paths:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        imagen_data = f.read()
                    logger.info(f"Imagen {imagen_id} recuperada desde ubicación principal")
                    return imagen_data
                except Exception as e:
                    logger.warning(f"Error leyendo desde {path}: {e}")
        
        return None
    
    def _verificar_imagen_disponible(self, usuario_id, imagen_id):
        """Verifica disponibilidad de imagen"""
        disponibilidad = {
            "disponibilidad_principal": False,
            "total_copias": 0
        }
    
        principal_paths = [
            os.path.join(self.usuarios_dir, usuario_id, "original", f"{imagen_id}.jpg"),
            os.path.join(self.usuarios_dir, usuario_id, "procesada", f"{imagen_id}.jpg")
        ]
        
        for path in principal_paths:
            if os.path.exists(path):
                disponibilidad["disponibilidad_principal"] = True
                disponibilidad["total_copias"] += 1
                break
        
        return disponibilidad
    
    def get_cluster_health(self):
        """Obtiene estado de salud completo dle sistema"""
        try:
            # estadisticas
            stat = os.statvfs(self.mnt_punto)
            espacio_total = stat.f_blocks * stat.f_frsize
            espacio_libre = stat.f_available * stat.f_frsize
            espacio_usado = espacio_total - espacio_libre
            
            # toral archivos
            total_usuarios = 0
            total_imagenes = 0
            
            if os.path.exists(self.usuarios_dir):
                for u_dir in os.listdir(self.usuarios_dir):
                    usuario_path = os.path.join(self.usuarios_dir, u_dir)
                    if os.path.isdir(usuario_path):
                        total_usuarios += 1
                        imagenes_usuario = self.get_imagenes_usuario(u_dir)
                        total_imagenes += len(imagenes_usuario)
            
            # informacion de glusterfs
            gluster_info = self._get_gluster_info()
            
            data = {
                "estado": "healthy",
                "timestamp": datetime.now().isoformat(),
                "sistema_archivo": {
                    "mnt_punto": self.mnt_punto,
                    "tipo": "glusterfs",
                    "espacio_total_gb": round(espacio_total / (1024**3), 2),
                    "espacio_usado_gb": round(espacio_usado / (1024**3), 2),
                    "espacio_libre_gb": round(espacio_libre / (1024**3), 2),
                    "porcentaje_uso": round((espacio_usado / espacio_total) * 100, 2)
                },
                "datos_distribucion": {
                    "total_usuarios": total_usuarios,
                    "total_imagenes": total_imagenes,
                    "alta_disponibilidad": True
                },
                "gluster_info": gluster_info
            }
            
            # guardar datos
            health_file = os.path.join(self.cluster_dir, "health", "cluster_health.json")
            os.makedirs(os.path.dirname(health_file), exist_ok=True)
            with open(health_file, "w") as f:
                json.dump(data, f, indent=2)
            
            return data
            
        except Exception as e:
            logger.error(f"Error obteniendo estado del cluster: {e}")
            return {
                "estado": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _get_gluster_info(self):
        """Obtiene informacion especifica del volumen glusterfs"""
        try:
            result = subprocess.run(['gluster', 'volume', 'info'], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    "informacion_disponible": True,
                    "estado_volumen": "online",
                    "salida": result.stdout.split('\n')[:10]
                }
            else:
                return {
                    "informacion_disponible": False,
                    "error": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {
                "informacion_disponible": False,
                "error": "timeout"
            }
        except Exception as e:
            return {
                "informacion_disponible": False,
                "error": str(e)
            }
