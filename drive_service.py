import os
import io
import uuid
import time
import ssl
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from werkzeug.utils import secure_filename
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from flask import Response

CLIENT_SECRET_FILE = './client_secret_361461075253-ovq8pfn283gcp600al9gl2a89k17pqu9.apps.googleusercontent.com.json'
TOKEN_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
BIENES_FOLDER_ID = '12U5ba-ggUtTTbiY60FRrz7TR6owfVq8V'
RESGUARDOS_FOLDER_ID = '1IZ12Y4G7y7IkjzSJHK0QEPmOB6FTz4Jp'
TRASPASOS_FOLDER_ID = '1fENuZNxz0b8A5pPKDOQcn66GCkJM7prB'
BAJAS_FOLDER_ID = '1VUlf9iXV3PYcvIG7A9ViKznC8Ixnqlpc'
INVENTARIOS_FOLDER_ID = '1myjMPJVMFe4wuX-MJQcihXzwGL8AxgL7'

# Configuración
DRIVE_TIMEOUT = 60
MAX_RETRIES = 5
RETRY_DELAY = 3
TEMP_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads_temp')
if not os.path.exists(TEMP_UPLOAD_FOLDER):
    os.makedirs(TEMP_UPLOAD_FOLDER)

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'image_cache')
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

class DriveImageService:
    def __init__(self, client_secret, token_file):
        self.client_secret_file = client_secret
        self.token_file = token_file
        self.creds = None
        self.service = self._get_drive_service()

    def _get_drive_service(self):
        """
        Construye el servicio de Drive usando credenciales OAuth2.
        """
        self.creds = None
        
        if os.path.exists(self.token_file):
            self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Error al refrescar token, pidiendo nuevo: {e}")
                    self.creds = self._run_local_auth_flow()
            else:
                print("No hay token.json, iniciando autorización por navegador...")
                self.creds = self._run_local_auth_flow()
            
            with open(self.token_file, 'w') as token:
                token.write(self.creds.to_json())
        
        try:
            # Construir el servicio directamente con las credenciales
            service = build(
                'drive', 
                'v3', 
                credentials=self.creds,
                cache_discovery=False
            )
            
            print("Servicio de Google Drive inicializado correctamente.")
            return service
            
        except Exception as error:
            print(f'Error inesperado al construir el servicio: {error}')
            return None

    def _run_local_auth_flow(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            self.client_secret_file, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        return creds

    def _execute_with_retry(self, request_func, *args, **kwargs):
        """
        Ejecuta una función con reintentos automáticos.
        """
        last_exception = None
        
        for attempt in range(MAX_RETRIES):
            try:
                return request_func(*args, **kwargs).execute()
            
            except (HttpError, TimeoutError, ConnectionError, ssl.SSLError, requests.exceptions.RequestException) as e:
                last_exception = e
                
                if "WRONG_VERSION_NUMBER" in str(e) or "DECRYPTION_FAILED" in str(e):
                    if attempt == 0:
                        print(f"Error SSL específico, no se reintentará: {e}")
                        break
                
                if attempt == MAX_RETRIES - 1:
                    break
                    
                wait_time = RETRY_DELAY * (attempt + 1)
                print(f"Intento {attempt + 1} fallado, reintentando en {wait_time} segundos... Error: {e}")
                time.sleep(wait_time)
        
        if last_exception:
            raise last_exception

    def upload(self, file_storage, model_type, target_folder_id):
        if not self.service:
            print("Error: El servicio de Drive no está inicializado.")
            return None
        if not file_storage or not file_storage.filename:
            return None
        
        local_temp_path = ""
        try:
            filename = secure_filename(file_storage.filename)
            unique_filename = f"{model_type}-{uuid.uuid4()}-{filename}"
            local_temp_path = os.path.join(TEMP_UPLOAD_FOLDER, unique_filename)
            file_storage.save(local_temp_path)
            
            file_metadata = {
                'name': unique_filename,
                'parents': [target_folder_id]
            }
            media = MediaFileUpload(local_temp_path, mimetype=file_storage.mimetype)
            
            file = self._execute_with_retry(
                self.service.files().create,
                body=file_metadata,
                media_body=media,
                fields='id'
            )
            
            drive_id = file.get('id')
            print(f"Archivo subido a {target_folder_id} con ID: {drive_id}")
            return drive_id
            
        except Exception as e:
            print(f"Error al subir archivo: {e}")
            return None
        finally:
            if local_temp_path and os.path.exists(local_temp_path):
                try: 
                    os.remove(local_temp_path)
                except: 
                    pass

    def delete(self, file_id):
        if not self.service or not file_id: 
            return False
        try:
            self._execute_with_retry(
                self.service.files().delete,
                fileId=file_id
            )
            return True
        except Exception as e:
            print(f"Error al borrar archivo {file_id}: {e}")
            return False

    def get_file_content(self, file_id):
        if not self.service: 
            raise Exception("Servicio de Drive no inicializado")
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = self._execute_with_retry(lambda: request)
            return file_content
            
        except Exception as e:
            print(f"Error al obtener contenido {file_id}: {e}")
            raise e

    def get_file_metadata(self, file_id):
        if not self.service: 
            raise Exception("Servicio de Drive no inicializado")
        try:
            file_metadata = self._execute_with_retry(
                self.service.files().get,
                fileId=file_id, 
                fields='id,name,mimeType,size,createdTime,modifiedTime'
            )
            return file_metadata
        except Exception as e:
            print(f"Error al obtener metadata {file_id}: {e}")
            raise e

    def download_file(self, file_id):
        """
        Método mejorado para descargar archivos usando MediaIoBaseDownload
        """
        if not self.service:
            raise Exception("Servicio de Drive no inicializado")
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Descargando {file_id}: {int(status.progress() * 100)}%")
            
            file_io.seek(0)
            return file_io.getvalue()
            
        except Exception as e:
            print(f"Error al descargar archivo {file_id}: {e}")
            raise e

    def test_connection(self):
        if not self.service:
            print("No hay servicio de Drive inicializado.")
            return False
        try:
            results = self._execute_with_retry(
                self.service.files().list,
                pageSize=1,
                fields="files(id, name)"
            )
            items = results.get('files', [])
            print(f"Conexión a Drive exitosa. Se encontraron {len(items)} archivos.")
            return True
        except Exception as e:
            print(f"Error probando conexión a Drive: {e}")
            return False

# --- Instancia global ---
try:
    drive_service = DriveImageService(CLIENT_SECRET_FILE, TOKEN_FILE)
    if drive_service and drive_service.service:
        print("✅ Servicio Drive inicializado correctamente")
        if drive_service.test_connection():
            print("✅ Conexión a Drive exitosa")
        else:
            print("⚠️  Advertencia: No se pudo verificar la conexión a Drive")
    else:
        print("❌ Servicio Drive no se pudo inicializar")
        drive_service = None
except Exception as e:
    print(f"❌ Error crítico al inicializar Drive Service: {e}")
    drive_service = None

# --- Funciones de Caché (mejoradas) ---
def get_cached_image(file_id):
    cache_file = os.path.join(CACHE_DIR, f"{file_id}.cache")
    if os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < 3600:
            try:
                with open(cache_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                print(f"Error leyendo cache: {e}")
                os.remove(cache_file)
    return None

def save_to_cache(file_id, content):
    try:
        cache_file = os.path.join(CACHE_DIR, f"{file_id}.cache")
        with open(cache_file, 'wb') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error guardando en cache: {e}")
        return False

def serve_drive_image(file_id):
    """
    Función mejorada para servir imágenes desde Drive
    """
    if not drive_service or not drive_service.service:
        return serve_default_image()
    
    # Verificar caché primero
    cached_content = get_cached_image(file_id)
    if cached_content:
        return Response(cached_content, mimetype='image/jpeg')
    
    try:
        print(f"Descargando imagen {file_id} desde Drive...")
        
        # Usar el método de descarga mejorado
        file_content = drive_service.download_file(file_id)
        
        if file_content:
            # Guardar en caché
            save_to_cache(file_id, file_content)
            return Response(file_content, mimetype='image/jpeg')
        else:
            return serve_default_image()
            
    except Exception as e:
        print(f"Error al servir archivo {file_id} desde Drive: {e}")
        return serve_default_image()

def serve_default_image():
    default_image_path = os.path.join(os.path.dirname(__file__), 'static', 'images', 'default-image.jpg')
    if os.path.exists(default_image_path):
        try:
            with open(default_image_path, 'rb') as f:
                return Response(f.read(), mimetype='image/jpeg')
        except Exception as e:
            print(f"Error al servir imagen por defecto: {e}")
    return "Imagen no disponible", 404