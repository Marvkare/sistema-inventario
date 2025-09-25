# your_flask_app/database.py
import mysql.connector
from flask import flash, current_app # current_app para acceder a la config de Flask
from config import AVAILABLE_COLUMNS
import pandas as pd
from io import BytesIO
from config import DB_CONFIG  # Importa la configuración directamente

def get_db_connection():
    """
    Establece una conexión a la base de datos.
    Ahora importa la configuración directamente para evitar el KeyError.
    """
    try:
        # Usa el diccionario DB_CONFIG importado en lugar de current_app.config
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error de conexión a la base de datos: {err}")
        return None
    
def get_db():
    """Establece conexión con la base de datos y devuelve la conexión y el cursor de diccionario."""
    try:
        # Corregido para usar la importación directa
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        return conn, cursor
    except mysql.connector.Error as err:
        flash(f"Error de Conexión a la Base de Datos: {err}. Verifica las credenciales y que MySQL esté corriendo.", 'error')
        return None, None

def get_table_columns(table_name="resguardo"):
    """
    Retrieves column names from the specified table, excluding auto-generated ones.
    Useful for dynamic form generation and validation.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    cursor = conn.cursor()
    columns = []
    try:
        cursor.execute(f"DESCRIBE {table_name}")
        # Exclude columns that are auto-generated or should not be part of the INSERT statement
        excluded_columns = ['id', 'Fecha_Registro'] # Add other auto-generated if any
        columns = [column[0] for column in cursor.fetchall() if column[0] not in excluded_columns]
    except mysql.connector.Error as err:
        print(f"Error getting table columns for {table_name}: {err}")
    finally:
        cursor.close()
        conn.close()
    return columns

def get_full_db_columns(table_name="resguardo"):
    """
    Retrieves all column names from the specified table.
    Useful for error handling when storing raw data.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    cursor = conn.cursor()
    columns = []
    try:
        cursor.execute(f"DESCRIBE {table_name}")
        columns = [column[0] for column in cursor.fetchall()]
    except mysql.connector.Error as err:
        print(f"Error getting full table columns for {table_name}: {err}")
    finally:
        cursor.close()
        conn.close()
    return columns

def map_operator_to_sql(operator):
    """Mapea operadores del frontend a operadores SQL válidos"""
    operator_map = {
        '==': '=',
        '!=': '!=',
        '>': '>',
        '<': '<',
        '>=': '>=',
        '<=': '<=',
        'contains': 'LIKE'
    }
    return operator_map.get(operator, '=')
# --- Core Helper Function (get_filtered_resguardo_data) ---
# This function MUST be defined before any route or function that calls it.
def get_image_paths(table_name, foreign_key_col, record_id):
    """
    Helper function to get all image paths for a record ID.
    """
    conn = None
    paths = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT ruta_imagen FROM {table_name} WHERE {foreign_key_col} = %s ORDER BY id"
        cursor.execute(query, (record_id,))
        results = cursor.fetchall()
        paths = [row['ruta_imagen'] for row in results]
        print(f"Found {len(paths)} images in {table_name} for {foreign_key_col}={record_id}")
    except mysql.connector.Error as err:
        print(f"Database error in get_image_paths: {err}")
    except Exception as e:
        print(f"An unexpected error occurred in get_image_paths: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            conn.close()
    return paths

def get_filtered_resguardo_data(selected_columns, filters):
    """
    Gets filtered data from the resguardos and bienes tables.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Separar columnas reales de columnas virtuales (imágenes)
        real_columns = [col for col in selected_columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
        image_columns = [col for col in selected_columns if col in ['imagenPath_bien', 'imagenPath_resguardo']]
        
        # Build the SELECT clause solo con columnas reales
        select_clause = ", ".join(real_columns) if real_columns else "r.id as id_resguardo, b.id as id_bien, r.*, b.*, a.nombre as Area_Nombre"
        
        # Siempre incluir los IDs necesarios para recuperar imágenes
        id_columns = []
        if 'imagenPath_bien' in image_columns and 'b.id' not in real_columns and 'id_bien' not in real_columns:
            select_clause += ", b.id AS id_bien"
            id_columns.append('id_bien')
        
        if 'imagenPath_resguardo' in image_columns and 'r.id' not in real_columns and 'id_resguardo' not in real_columns:
            select_clause += ", r.id AS id_resguardo"
            id_columns.append('id_resguardo')

        # Build the JOINs
        query_tables = "resguardos r JOIN bienes b ON r.id_bien = b.id JOIN areas a ON r.id_area = a.id"

        # Build the WHERE clause from filters
        where_clause = ""
        filter_values = []
        if filters:
            where_clauses = []
            for f in filters:
                field_name = f.get('field', '')
                field_value = f.get('value', '')
                field_operator = f.get('operator', '==')
                
                if field_name == 'No_Inventario':
                    where_clauses.append("b.No_Inventario LIKE %s")
                    filter_values.append(f"%{field_value}%")
                elif field_name == 'No_Resguardo':
                    where_clauses.append("r.No_Resguardo LIKE %s")
                    filter_values.append(f"%{field_value}%")
                elif field_name == 'Nombre_Del_Resguardante':
                    where_clauses.append("r.Nombre_Del_Resguardante LIKE %s")
                    filter_values.append(f"%{field_value}%")
                elif field_name == 'Area':
                    where_clauses.append("a.id = %s")
                    filter_values.append(field_value)
            if where_clauses:
                where_clause = " WHERE " + " AND ".join(where_clauses)

        # Final query
        query = f"SELECT {select_clause} FROM {query_tables} {where_clause}"
        print(f"Executing query: {query}")
        print(f"With parameters: {filter_values}")

        cursor.execute(query, tuple(filter_values))
        data = cursor.fetchall()
        print(f"Query returned {len(data)} rows.")

        if not data:
            print("No data found for the given filters.")
            return [], 0, 0

        # Obtener el máximo número de imágenes por tipo para determinar cuántas columnas necesitamos
        max_bien_images = 0
        max_resguardo_images = 0
        
        for row in data:
            id_bien = row.get('id_bien')
            id_resguardo = row.get('id_resguardo')
            
            if id_bien and 'imagenPath_bien' in image_columns:
                bien_images = get_image_paths('imagenes_bien', 'id_bien', id_bien)
                max_bien_images = max(max_bien_images, len(bien_images))
            
            if id_resguardo and 'imagenPath_resguardo' in image_columns:
                resguardo_images = get_image_paths('imagenes_resguardo', 'id_resguardo', id_resguardo)
                max_resguardo_images = max(max_resguardo_images, len(resguardo_images))

        # Agregar las imágenes a cada registro
        for row in data:
            # Para imágenes de bienes
            if 'imagenPath_bien' in image_columns:
                id_bien = row.get('id_bien')
                if id_bien:
                    bien_images = get_image_paths('imagenes_bien', 'id_bien', id_bien)
                    # Crear columnas individuales para cada imagen
                    for i, image_path in enumerate(bien_images):
                        row[f'imagen_bien_{i+1}'] = image_path
                    # También guardar la lista completa para referencia
                    row['imagenPath_bien'] = bien_images
                else:
                    row['imagenPath_bien'] = []

            # Para imágenes de resguardos
            if 'imagenPath_resguardo' in image_columns:
                id_resguardo = row.get('id_resguardo')
                if id_resguardo:
                    resguardo_images = get_image_paths('imagenes_resguardo', 'id_resguardo', id_resguardo)
                    # Crear columnas individuales para cada imagen
                    for i, image_path in enumerate(resguardo_images):
                        row[f'imagen_resguardo_{i+1}'] = image_path
                    # También guardar la lista completa para referencia
                    row['imagenPath_resguardo'] = resguardo_images
                else:
                    row['imagenPath_resguardo'] = []

            # Remover las columnas de ID temporales si no se solicitaron originalmente
            for id_col in id_columns:
                if id_col not in selected_columns:
                    row.pop(id_col, None)

        return data, max_bien_images, max_resguardo_images
        
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return [], 0, 0
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return [], 0, 0
    finally:
        if conn and conn.is_connected():
            conn.close()

