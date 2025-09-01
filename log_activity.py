from flask import current_app
from flask_login import current_user
import mysql.connector
from datetime import datetime
from database import get_db_connection
# Asume que esta función ya está en tu archivo de utilidades o en un módulo
# accesible para todas tus rutas.


def log_activity(action, resource, resource_id=None, details=None):
    """
    Registra una acción de usuario en la tabla activity_log.

    Obtiene automáticamente el ID del usuario actual de Flask-Login.

    Args:
        action (str): Descripción de la acción (e.g., 'Inicio de sesión', 'Agregar').
        resource (str): Tipo de recurso afectado (e.g., 'Área', 'Usuario').
        resource_id (int, optional): ID del recurso afectado. Por defecto es None.
        details (str, optional): Detalles adicionales sobre la acción. Por defecto es None.
    """
    # Verifica si hay un usuario logueado para obtener su ID
    if not current_user.is_authenticated:
        user_id = None # O un valor por defecto si lo prefieres
    else:
        user_id = current_user.id

    conn = get_db_connection()
    if conn is None:
        print("No se pudo registrar la actividad: Fallo en la conexión a la base de datos.")
        return

    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO activity_log (user_id, action, resource, resource_id, details)
            VALUES (%s, %s, %s, %s, %s)
        """
        data = (user_id, action, resource, resource_id, details)
        
        cursor.execute(query, data)
        conn.commit()
    except mysql.connector.Error as e:
        print(f"Error en la base de datos al registrar la actividad: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()