# your_flask_app/config.py
import os

# --- Configuración de la Base de Datos ---
DB_CONFIG_ = {
    'host': 'Marvkare.mysql.pythonanywhere-services.com',
    'user': 'Marvkare',
    'password': 'Pescadovolador1-',
    'database': 'Marvkare$default'
}


DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pescadoroot',
    'database': 'inventario'
}


# --- Rutas de Archivos ---
# app.root_path es la raíz de tu aplicación Flask
PDF_TEMPLATE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'templates', 'PlantillaPrueba.pdf')
# Si quieres un directorio al mismo nivel que tu proyecto
project_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_dir)
UPLOAD_FOLDER = os.path.join(parent_dir, 'uploads')
print(UPLOAD_FOLDER)
# --- Extensiones Permitidas para Subidas ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

SERVICE_ACCOUNT_FILE = 'inventario-379322-8fbb7f3f5f7e.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

def upload_to_google_drive(file_path, file_name):
    """
    Sube un archivo a una carpeta específica en Google Drive.
    """
    try:
        # Autenticación
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
        # Construye el servicio de la API
        service = build('drive', 'v3', credentials=creds)

        # Define los metadatos del archivo (nombre y carpeta padre)
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        
        # Define el contenido multimedia que se va a subir
        media = MediaFileUpload(file_path, mimetype='image/jpeg') # Ajusta el mimetype si es necesario

        # Ejecuta la subida del archivo
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id' # Pide que te devuelva el ID del archivo creado
        ).execute()
        
        print(f"Archivo subido con éxito. ID del archivo: {file.get('id')}")
        return file.get('id')

    except Exception as e:
        print(f"Error al subir el archivo: {e}")
        return None

DRIVE_FOLDER_ID = '1-2070R0Gq6z_g48RB6faOsyGE9-_eXs2'
# Mapeo de columnas del Excel a la base de datos
COLUMN_MAPPING = {
    "NO. DE INVENTARIO": "No_Inventario",
    "NO. FACTURA": "No_Factura",
    "NO. DE CUENTA": "No_Cuenta",
    "PROVEEDOR": "Proveedor",
    "DESCRIPCION DEL BIEN": "Descripcion_Del_Bien",
    "DESCRIPCION CORTA DEL BIEN": "Descripcion_Corta_Del_Bien",
    "RUBRO": "Rubro",
    "NO.POLIZA": "Poliza",
    "FECHA POLIZA": "Fecha_Poliza",
    "SUB-CTA. ARMONIZADORA": "Sub_Cuenta_Armonizadora",
    "FECHA FACTURA": "Fecha_Factura",
    "COSTO INICIAL": "Costo_Inicial",
    "DEPRECIACION ACUMULADA": "Depreciacion_Acumulada",
    "COSTO FINAL": "Costo_Final",
    "CANTIDAD": "Cantidad",
    "ESTADO DEL BIEN": "Estado_Del_Bien",
    "MARCA": "Marca",
    "MODELO": "Modelo",
    "NUMERO DE SERIE": "Numero_De_Serie",
    "TIPO DE ALTA": "Tipo_De_Alta",
    "CLASIFICACION LEGAL": "Clasificacion_Legal",
    "AREA PRESUPUESTAL": "Area_Presupuestal",
    "DOCUMENTO PROPIEDAD": "Documento_Propiedad",
    "FECHA DOCUMENTO PROPIEDAD": "Fecha_Documento_Propiedad",
    "VALOR EN LIBROS": "Valor_En_Libros",
    "FECHA ADQUISICION/ALTA": "Fecha_Adquisicion_Alta",
   #Datos de resguardo 
    "AREA": "id_area_nombre", # Se usará para buscar o crear el id_area
    "UBICACION": "Ubicacion",
    "NO. DE RESGUARDO": "No_Resguardo",
    "TIPO DE RESGUARDO": "Tipo_De_Resguardo",
    "FECHA DE RESGUARDO": "Fecha_Resguardo",
    "NO. DE TRABAJADOR": "No_Trabajador",
    "PUESTO TRABAJADOR": "Puesto_Trabajador",
    "RFC TRABAJADOR": "RFC_Trabajador",
    "NO. DE NOMINA TRABAJADOR": "No_Nomina_Trabajador",
    "NOMBRE DEL RESGUARDANTE": "Nombre_Del_Resguardante",
    "NOMBRE DIRECTOR/JEFES DE AREA": "Nombre_Director_Jefe_De_Area"
    
}
# Columnas de la base de datos (se pueden obtener dinámicamente o definir aquí)
# Si las obtienes dinámicamente, considera mover esa lógica a database.py
# Para simplificar ahora, las pondremos aquí.
VALID_DB_COLUMNS = [
    "No_Inventario", "No_Factura", "No_Cuenta", "No_Resguardo",
    "No_Trabajador", "Proveedor", "Fecha_Resguardo",
    "Descripcion_Del_Bien", "Descripcion_Fisica", "Area", "Rubro", "Poliza",
    "Fecha_Poliza", "Sub_Cuenta_Armonizadora", "Fecha_Factura", "Costo_Inicial",
    "Depreciacion_Acumulada", "Costo_Final", "Cantidad",
    "Puesto", "Nombre_Director_Jefe_De_Area", 
    "Numero_De_Serie", "Tipo_De_Resguardo", "Adscripcion_Direccion_Area",
    "Nombre_Del_Resguardante", "Estado_Del_Bien", "Marca", "Modelo",
    "Imagen_Path" # Asegúrate de que todas las columnas que puedes insertar estén aquí
]

# FULL_DB_COLUMNS (para errores), si es muy dinámico, es mejor generarlo en tiempo de ejecución
# Si no cambia mucho, puedes copiarlo aquí después de ejecutar el script una vez
# o tener una función en database.py para obtenerlo.
# Por ahora, para que funcione, podrías copiar el resultado de tu print(FULL_DB_COLUMNS) aquí
FULL_DB_COLUMNS = [
    "id", "No_Inventario", "No_Factura", "No_Cuenta", "No_Resguardo", "No_Trabajador",
    "Proveedor", "Fecha_Resguardo", "Descripcion_Del_Bien", "Descripcion_Fisica",
    "Area", "Rubro", "Poliza", "Fecha_Poliza", "Sub_Cuenta_Armonizadora",
    "Fecha_Factura", "Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final",
    "Cantidad", "Puesto", "Nombre_Director_Jefe_De_Area",
    "Tipo_De_Resguardo", "Adscripcion_Direccion_Area", "Nombre_Del_Resguardante",
    "Estado_Del_Bien", "Marca", "Modelo", "Numero_De_Serie", "Imagen_Path",
    "Fecha_Registro" # Añade Fecha_Registro si es una columna en tu tabla de resguardos_errores
]

AVAILABLE_COLUMNS = [
    # --- Columnas Clave de Identificación ---
    'No_Inventario',
    'No_Resguardo',
    
    # --- Columnas Descriptivas del Bien ---
    'Descripcion_Del_Bien',
    'Descripcion_Corta_Del_Bien',
    'Marca',
    'Modelo',
    'Numero_De_Serie',
    'Estado_Del_Bien',
    'Cantidad',

    # --- Columnas del Resguardo y Ubicación ---
    'Nombre_Del_Resguardante',
    'Area',  # Representa el nombre del área (a.nombre)
    'Ubicacion',
    'Puesto_Trabajador',
    'No_Trabajador',
    'RFC_Trabajador',
    'No_Nomina_Trabajador',
    'Nombre_Director_Jefe_De_Area',
    'Tipo_De_Resguardo',
    'Fecha_Resguardo',

    # --- Columnas Financieras y de Adquisición ---
    'Costo_Inicial',
    'Costo_Final',
    'Depreciacion_Acumulada',
    'Valor_En_Libros',
    'No_Factura',
    'Fecha_Factura',
    'Proveedor',
    'No_Cuenta',
    'Poliza',
    'Fecha_Poliza',
    'Rubro',
    'Sub_Cuenta_Armonizadora',
    
    # --- Columnas Administrativas y Legales ---
    'Tipo_De_Alta',
    'Fecha_Adquisicion_Alta',
    'Clasificacion_Legal',
    'Area_Presupuestal',
    'Documento_Propiedad',
    'Fecha_Documento_Propiedad',
    
    # --- Columnas de Estado y Virtuales ---
    'Activo',
    'imagenPath_bien',
    'imagenPath_resguardo',
]
# The name of the Area column in the Excel file
EXCEL_AREA_COL_NAME = 'Area'

# Define which columns belong to each table for a cleaner insertion process
BIENES_COLUMNS = [
    'No_Inventario', 'No_Factura', 'No_Cuenta', 'Proveedor',
    'Descripcion_Del_Bien', 'Descripcion_Corta_Del_Bien', 'Rubro', 'Poliza',
    'Fecha_Poliza', 'Sub_Cuenta_Armonizadora', 'Fecha_Factura', 'Costo_Inicial',
    'Depreciacion_Acumulada', 'Costo_Final', 'Cantidad', 'Estado_Del_Bien',
    'Marca', 'Modelo', 'Numero_De_Serie', 'Tipo_De_Alta',
    # --- Columnas que faltaban ---
    'Clasificacion_Legal',
    'Area_Presupuestal',
    'Documento_Propiedad',
    'Fecha_Documento_Propiedad',
    'Valor_En_Libros',
    'Fecha_Adquisicion_Alta'
]

RESGUARDOS_COLUMNS = [
    'No_Resguardo', 'Ubicacion', 'Tipo_De_Resguardo', 'Fecha_Resguardo',
    'No_Trabajador', 'Puesto_Trabajador', 'Nombre_Del_Resguardante',
    'Nombre_Director_Jefe_De_Area',
    # --- Columnas que faltaban ---
    'RFC_Trabajador',
    'No_Nomina_Trabajador'
]
# Unir todas las columnas para el manejo de errores

FULL_DB_COLUMNS = BIENES_COLUMNS + RESGUARDOS_COLUMNS + ['error_message', 'upload_id']

def map_operator_to_sql(operator):
    """
    Convierte operadores del formulario a operadores SQL.
    """
    operator_map = {
        '==': '=',
        '!=': '!=',
        '>': '>',
        '>=': '>=',
        '<': '<',
        '<=': '<=',
        'contains': 'LIKE',
        'not_contains': 'NOT LIKE',
        'starts_with': 'LIKE',
        'ends_with': 'LIKE'
    }
    return operator_map.get(operator, '=')