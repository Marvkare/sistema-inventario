# your_flask_app/config.py
import os

# --- Configuración de la Base de Datos ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pescadoroot',
    'database': 'inventario'
}

# --- Rutas de Archivos ---
# app.root_path es la raíz de tu aplicación Flask
PDF_TEMPLATE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'templates', 'PlantillaPrueba.pdf')
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')
print(UPLOAD_FOLDER)
# --- Extensiones Permitidas para Subidas ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# --- Mapeo de Columnas (si es extenso, podría ir a un archivo separado como mappings.py) ---
COLUMN_MAPPING = {
    "NO.POLIZA": "Poliza",
    "FECHA POLIZA": "Fecha_Poliza",
    "SUB-CTA. ARMONIZADORA": "Sub_Cuenta_Armonizadora",
    "FECHA RESGUARDO":"Fecha_Resguardo",
    "NO. DE CUENTA": "No_Cuenta",
    "NO. DE INVENTARIO": "No_Inventario",
    "NO. DE RESGUARDO": "No_Resguardo",
    "PROVEEDOR": "Proveedor",
    "FACTURA": "No_Factura",
    "FECHA FACTURA": "Fecha_Factura",
    "COSTO INICIAL": "Costo_Inicial",
    "DEPRECIACION ACUMULADA": "Depreciacion_Acumulada",
    "COSTO FINAL": "Costo_Final_Cantidad",
    "CANTIDAD": "Cantidad",
    "DESCRIPCION FISICAS DEL BIEN": "Descripcion_Del_Bien",
    "DESCRIPCION FISICA": "Descripcion_Fisica",
    "AREA": "Area",
    "RUBRO": "Rubro",
    "PUESTO": "Puesto",
    "NO. DE TRABAJADOR": "No_Trabajador",
    "NOMBRE DIRECTOR/JEFES DE AREA": "Nombre_Director_Jefe_De_Area",
    "TIPO DE RESGUARDO": "Tipo_De_Resguardo",
    "ADSCRIPCION DIRECCION AREA": "Adscripcion_Direccion_Area",
    "NOMBRE DEL RESGUARDANTE": "Nombre_Del_Resguardante",
    "ESTADO DEL BIEN": "Estado_Del_Bien",
    "MARCA": "Marca",
    "MODELO": "Modelo",
    "NUMERO DE SERIE": "Numero_De_Serie",
}

# Columnas de la base de datos (se pueden obtener dinámicamente o definir aquí)
# Si las obtienes dinámicamente, considera mover esa lógica a database.py
# Para simplificar ahora, las pondremos aquí.
VALID_DB_COLUMNS = [
    "No_Inventario", "No_Factura", "No_Cuenta", "No_Resguardo",
    "No_Trabajador", "Proveedor", "Fecha_Resguardo",
    "Descripcion_Del_Bien", "Descripcion_Fisica", "Area", "Rubro", "Poliza",
    "Fecha_Poliza", "Sub_Cuenta_Armonizadora", "Fecha_Factura", "Costo_Inicial",
    "Depreciacion_Acumulada", "Costo_Final_Cantidad", "Cantidad",
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
    "Fecha_Factura", "Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final_Cantidad",
    "Cantidad", "Puesto", "Nombre_Director_Jefe_De_Area",
    "Tipo_De_Resguardo", "Adscripcion_Direccion_Area", "Nombre_Del_Resguardante",
    "Estado_Del_Bien", "Marca", "Modelo", "Numero_De_Serie", "Imagen_Path",
    "Fecha_Registro" # Añade Fecha_Registro si es una columna en tu tabla de resguardos_errores
]

AVAILABLE_COLUMNS = [
    'No_Inventario',
    'No_Factura',
    'No_Cuenta',
    'No_Resguardo',
    'No_Trabajador',
    'Proveedor',
    'Fecha_Resguardo',
    'Descripcion_Del_Bien',
    'Descripcion_Fisica',
    'Area',
    'Rubro',
    'Poliza',
    'Fecha_Poliza',
    'Sub_Cuenta_Armonizadora',
    'Fecha_Factura',
    'Costo_Inicial',
    'Depreciacion_Acumulada',
    'Costo_Final_Cantidad',
    'Cantidad',
    
    'Puesto',
    'Nombre_Director_Jefe_De_Area',
    'Tipo_De_Resguardo',
    'Adscripcion_Direccion_Area',
    'Nombre_Del_Resguardante',
    'Estado_Del_Bien',
    'Marca',
    'Modelo',
    'Numero_De_Serie',
    'imagenPath_bien',
    'imagenPath_resguardo'
]

# The name of the Area column in the Excel file
EXCEL_AREA_COL_NAME = 'Area'

# Define which columns belong to each table for a cleaner insertion process
BIENES_COLUMNS = {'No_Inventario', 'No_Factura', 'No_Cuenta', 'Proveedor', 'Descripcion_Del_Bien',
                  'Descripcion_Corta_Del_Bien', 'Rubro', 'Poliza', 'Fecha_Poliza', 'Sub_Cuenta_Armonizadora',
                  'Fecha_Factura', 'Costo_Inicial', 'Depreciacion_Acumulada', 'Costo_Final_Cantidad', 'Cantidad',
                  'Estado_Del_Bien', 'Marca', 'Modelo', 'Numero_De_Serie', 'Imagen_Path'}

RESGUARDOS_COLUMNS = {'No_Resguardo', 'Tipo_De_Resguardo', 'Fecha_Resguardo', 'No_Trabajador', 
                      'Puesto', 'Nombre_Director_Jefe_De_Area', 'Nombre_Del_Resguardante'}


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