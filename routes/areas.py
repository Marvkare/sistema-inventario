# your_flask_app/routes/resguardos.py
# app.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file,jsonify
from flask_login import login_required, current_user
import os
import traceback
from pypdf import PdfReader, PdfWriter
import pypdf.generic
from werkzeug.utils import secure_filename
from decorators import permission_required
from database import get_db_connection, get_db_connection, get_table_columns
from log_activity import log_activity
import pymysql

areas_bp = Blueprint('areas', __name__)


@areas_bp.route('/get_areas', methods=['GET'])
@login_required
@permission_required('resguardos.crear_resguardo')
def get_areas():
    """
    API route to fetch all unique areas (id and name) from the 'areas' table.
    Returns a JSON array of objects.
    """
    conn = None
    cursor = None
    try:
        # Use a dictionary cursor to get results as key-value pairs
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Failed to connect to the database"}), 500
        
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        # Select both id and name from the areas table
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre ASC")
        areas = cursor.fetchall()
        
        # The cursor returns a list of dictionaries, which is the format
        # the frontend needs to populate the dropdown with both ID and name.
        return jsonify(areas)
    
    except mysql.connector.Error as e:
        print(f"Database error fetching areas: {e}")
        return jsonify({"error": "Failed to fetch areas"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()


@areas_bp.route('/add_area', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def add_area():
    """
    API route to add a new area to the 'areas' table.
    Expects JSON data with 'area_name'.
    """
    conn, cursor = get_db_connection()
    if not conn:
        # Flash message for user feedback if DB connection fails
        flash("Error: No se pudo conectar a la base de datos para agregar el área.", 'error')
        return jsonify({"message": "Error interno del servidor."}), 500

    try:
        data = request.get_json()
        area_name = data.get('area_name')

        if not area_name:
            flash("Error: El nombre del área no puede estar vacío.", 'warning')
            return jsonify({"message": "El nombre del área es requerido."}), 400

        # Check if area already exists (case-insensitive for better user experience)
        # Using LOWER() on both sides for a case-insensitive comparison
        cursor.execute("SELECT COUNT(*) FROM areas WHERE LOWER(nombre) = LOWER(%s)", (area_name,))
        if cursor.fetchone()[0] > 0:
            flash(f"Advertencia: El área '{area_name}' ya existe.", 'warning')
            return jsonify({"message": f"El área '{area_name}' ya existe."}), 409

        # Insert the new area into the 'areas' table
        cursor.execute("INSERT INTO areas (nombre) VALUES (%s)", (area_name,))
        conn.commit() # Commit changes to the database

        flash(f"El área '{area_name}' ha sido agregada correctamente.", 'success')
        return manage_areasjsonify({"message": f"Área '{area_name}' agregada correctamente."}), 201 # 201 Created

    except mysql.connector.Error as e:
        # Rollback in case of a database error during insertion
        conn.rollback()
        print(f"Database error adding area: {e}") # Log the specific database error
        flash(f"Error en la base de datos al agregar el área: {e}", 'error')
        return jsonify({"message": "Error al guardar el área en la base de datos."}), 500
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error adding area: {e}") # Log unexpected errors
        flash(f"Ocurrió un error inesperado al agregar el área: {e}", 'error')
        return jsonify({"message": "Ocurrió un error inesperado."}), 500
    finally:
        # Ensure the database connection and cursor are closed
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@areas_bp.route('/manage_areas', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def manage_areas():
    conn = None
    cursor = None
    
    try:
        # --- CORRECCIÓN 1: Obtener conn y LUEGO cursor ---
        conn = get_db_connection()
        if not conn:
            flash("Error: No se pudo conectar a la base de datos.", 'error')
            return render_template('error.html', message="Error de conexión a la base de datos."), 500
        
        # --- CORRECCIÓN 2: Usar el cursor de PyMySQL (DictCursor) ---
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if request.method == 'POST':
            area_id = request.form.get('area_id')
            area_name = request.form.get('area_name', '').strip()
            area_numero = request.form.get('area_numero', '').strip()

            if not area_name:
                flash("El nombre del área no puede estar vacío.", 'warning')
                return redirect(url_for('areas.manage_areas'))

            try:
                area_numero = int(area_numero) if area_numero else None
            except ValueError:
                flash("El número de área debe ser un número entero válido o estar vacío.", 'warning')
                return redirect(url_for('areas.manage_areas'))

            # --- CORRECCIÓN 3: Mejorar la consulta COUNT ---
            # Usar 'AS count' es más limpio que .get('COUNT(*)')
            if area_id: # Editando
                cursor.execute("SELECT COUNT(*) AS count FROM areas WHERE LOWER(nombre) = LOWER(%s) AND id != %s", (area_name, area_id))
            else: # Agregando
                cursor.execute("SELECT COUNT(*) AS count FROM areas WHERE LOWER(nombre) = LOWER(%s)", (area_name,))
            
            result = cursor.fetchone()
            if result and result['count'] > 0:
                flash(f"El área '{area_name}' ya existe.", 'warning')
                return redirect(url_for('areas.manage_areas'))

            if area_id: # Update
                cursor.execute("UPDATE areas SET nombre = %s, numero = %s WHERE id = %s", (area_name, area_numero, area_id))
                log_activity(
                        action="Actualización de Área", 
                        category="Areas", 
                        resource_id=area_id, 
                        details=f"Se actualizó el área: {area_name}"
                    )
                flash(f"Área '{area_name}' actualizada correctamente.", 'success')
            else: # Insert
                cursor.execute("INSERT INTO areas (nombre, numero) VALUES (%s, %s)", (area_name, area_numero))
                new_area_id = cursor.lastrowid 
                log_activity(
                    action="Creación de Área", 
                    category="Areas", 
                    resource_id=new_area_id, 
                    details=f"Se creó la nueva área: {area_name}"
                )
                flash(f"Área '{area_name}' agregada correctamente.", 'success')
            
            conn.commit()
            return redirect(url_for('areas.manage_areas'))

        else: # GET request
            cursor.execute("SELECT id, nombre, numero FROM areas ORDER BY nombre ASC")
            # El DictCursor hace que 'row' sea un diccionario
            areas_data = cursor.fetchall() 
            print(areas_data)
            return render_template('areas.html', areas=areas_data)

    # --- CORRECCIÓN 4: Manejo de errores de PyMySQL ---
    except pymysql.MySQLError as e:
        if conn: conn.rollback()
        print(f"Database error in manage_areas: {type(e).__name__}: {e}")
        traceback.print_exc()
        flash(f"Error en la base de datos al guardar el área: {e}", 'error')
    
    except Exception as e:
        if conn: conn.rollback()
        print(f"Unexpected error in manage_areas: {type(e).__name__}: {e}")
        traceback.print_exc()
        flash(f"Ocurrió un error inesperado: {e}", 'error')
    
    finally:
        # --- CORRECCIÓN 5: Cierre de conexión de PyMySQL ---
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    # Si hubo un error, redirige de vuelta
    return redirect(url_for('areas.manage_areas'))

@areas_bp.route('/delete_area/<int:area_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def delete_area(area_id):
    conn, cursor = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Error interno del servidor: No se pudo conectar a la base de datos."}), 500

    try:
        # Optional: Check for dependencies before deleting (e.g., if any resguardo uses this area)
        # For example:
        # cursor.execute("SELECT COUNT(*) FROM resguardos WHERE Area = (SELECT nombre FROM areas WHERE id = %s)", (area_id,))
        # if cursor.fetchone()[0] > 0:
        #     flash("No se puede eliminar el área porque está asociada a uno o más resguardos.", 'error')
        #     return jsonify({"success": False, "message": "El área está en uso y no puede ser eliminada."}), 400

        cursor.execute("DELETE FROM areas WHERE id = %s", (area_id,))
        conn.commit()
        flash("Área eliminada correctamente.", 'success')
        return jsonify({"success": True, "message": "Área eliminada correctamente."}), 200

    except mysql.connector.Error as e:
        conn.rollback()
        print(f"Database error deleting area: {e}")
        flash(f"Error en la base de datos al eliminar el área: {e}", 'error')
        return jsonify({"success": False, "message": "Error al eliminar el área en la base de datos."}), 500
    except Exception as e:
        print(f"Unexpected error deleting area: {e}")
        flash(f"Ocurrió un error inesperado al eliminar el área: {e}", 'error')
        return jsonify({"success": False, "message": "Ocurrió un error inesperado."}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

