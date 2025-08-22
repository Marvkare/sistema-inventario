# your_flask_app/database.py
import mysql.connector
from flask import flash, current_app # current_app para acceder a la config de Flask
from config import AVAILABLE_COLUMNS
import pandas as pd
from io import BytesIO
def get_db_connection():
    """Establece conexión con la base de datos."""
    try:
        conn = mysql.connector.connect(**current_app.config['DB_CONFIG'])
        return conn
    except mysql.connector.Error as err:
        flash(f"Error de Conexión a la Base de Datos: {err}. Verifica las credenciales y que MariaDB esté corriendo.", 'error')
        return None
    
def get_db():
    """Establece conexión con la base de datos y devuelve la conexión y el cursor de diccionario."""
    try:
        conn = mysql.connector.connect(**current_app.config['DB_CONFIG'])
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

# --- Core Helper Function (get_filtered_resguardo_data) ---
# This function MUST be defined before any route or function that calls it.
def get_filtered_resguardo_data(selected_columns, filters, limit=None):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Use dictionary=True for dict-like rows
        
        where_clauses = []
        params = []
        for f in filters:
            field = f.get('field')
            operator = f.get('operator')
            value = f.get('value')

            if not (field and operator and value):
                continue

            if field not in AVAILABLE_COLUMNS:
                continue

            # Use %s for placeholders in MySQL queries
            if operator == '==':
                where_clauses.append(f"`{field}` = %s")
                params.append(value)
            elif operator == '!=':
                where_clauses.append(f"`{field}` != %s")
                params.append(value)
            elif operator == '>':
                where_clauses.append(f"`{field}` > %s")
                params.append(value)
            elif operator == '<':
                where_clauses.append(f"`{field}` < %s")
                params.append(value)
            elif operator == 'contains':
                where_clauses.append(f"`{field}` LIKE %s")
                params.append(f"%{value}%")
        
        columns_sql = ", ".join([f"`{col}`" for col in selected_columns])
        query = f"SELECT {columns_sql} FROM resguardo"
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        results = cursor.fetchall() # With dictionary=True, fetchall() already returns list of dictionaries
        
        return results
    except Exception as e:
        raise Exception(f"Error al obtener datos de resguardo: {e}") # Re-raise to be caught by the calling route
    finally:
        if conn:
            conn.close()

