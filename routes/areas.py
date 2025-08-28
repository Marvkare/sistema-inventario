# your_flask_app/routes/resguardos.py
# app.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file,jsonify
from flask_login import login_required, current_user
import mysql.connector
import os
import traceback
from pypdf import PdfReader, PdfWriter
import pypdf.generic
from werkzeug.utils import secure_filename
from decorators import permission_required
from database import get_db, get_db_connection, get_table_columns

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
        
        cursor = conn.cursor(dictionary=True)
        
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
        if conn and conn.is_connected():
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
    conn, cursor = get_db()
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


# ... your get_db() function and app configuration ...

@areas_bp.route('/manage_areas', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def manage_areas():
    conn, cursor = get_db()
    if not conn:
        flash("Error: No se pudo conectar a la base de datos.", 'error')
        return render_template('error.html', message="Error de conexión a la base de datos."), 500

    if request.method == 'POST':
        area_id = request.form.get('area_id')
        area_name = request.form.get('area_name', '').strip()
        area_numero = request.form.get('area_numero', '').strip() # Get the 'numero' value as string

        if not area_name:
            flash("El nombre del área no puede estar vacío.", 'warning')
            return redirect(url_for('areas.manage_areas'))

        # Convert area_numero to an integer, or None if empty
        # This handles the INT NULL type in your database
        try:
            area_numero = int(area_numero) if area_numero else None
        except ValueError:
            flash("El número de área debe ser un número entero válido o estar vacío.", 'warning')
            return redirect(url_for('areas.manage_areas'))

        try:
            # Check for name uniqueness, excluding the current area if editing
            if area_id: # Editing an existing area
                # Check for existing name, excluding the current ID being edited
                cursor.execute("SELECT COUNT(*) FROM areas WHERE LOWER(nombre) = LOWER(%s) AND id != %s", (area_name, area_id))
            else: # Adding a new area
                # Check for existing name
                cursor.execute("SELECT COUNT(*) FROM areas WHERE LOWER(nombre) = LOWER(%s)", (area_name,))
            result = cursor.fetchone()
            if result and result.get('COUNT(*)', result.get('count', 0)) > 0:
                flash(f"El área '{area_name}' ya existe.", 'warning')
                return redirect(url_for('areas.manage_areas'))

            if area_id: # Update existing area
                # Ensure correct parameter order for UPDATE
                cursor.execute("UPDATE areas SET nombre = %s, numero = %s WHERE id = %s", (area_name, area_numero, area_id))
                flash(f"Área '{area_name}' actualizada correctamente.", 'success')
            else: # Add new area
                # Ensure correct parameter order for INSERT
                print("UWU nueva area")
                cursor.execute("INSERT INTO areas (nombre, numero) VALUES (%s, %s)", (area_name, area_numero))
                flash(f"Área '{area_name}' agregada correctamente.", 'success')
            
            conn.commit()

        except mysql.connector.Error as e:
            conn.rollback()
            # **IMPROVED ERROR LOGGING**
            print(f"Database error in manage_areas POST: {type(e).__name__}: {e}")
            flash(f"Error en la base de datos al guardar el área: {e}", 'error')
        except Exception as e:
            # **IMPROVED ERROR LOGGING**
            print(f"Unexpected error in manage_areas POST: {type(e).__name__}: {e}")
            flash(f"Ocurrió un error inesperado al guardar el área: {e}", 'error')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
        
        return redirect(url_for('areas.manage_areas'))

    else: # GET request
        try:
            cursor.execute("SELECT id, nombre, numero FROM areas ORDER BY nombre")
            # Using dictionary cursor, so access by key
            areas_data = [{'id': row['id'], 'name': row['nombre'], 'numero': row['numero']} for row in cursor.fetchall()]
            
        except Exception as e:
            # **IMPROVED ERROR LOGGING**
            print(f"Database error fetching areas for display: {type(e).__name__}: {e}")
            flash("Error al cargar las áreas existentes.", 'error')
            areas_data = []
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()

        return render_template('areas.html', areas=areas_data)


@areas_bp.route('/delete_area/<int:area_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def delete_area(area_id):
    conn, cursor = get_db()
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

