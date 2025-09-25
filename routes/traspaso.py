# your_flask_app/routes/traspaso.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import mysql.connector
from database import get_db_connection
from decorators import permission_required
from log_activity import log_activity
from datetime import date
from werkzeug.utils import secure_filename
import uuid
import os
from config import UPLOAD_FOLDER
import traceback 
traspaso_bp = Blueprint('traspaso', __name__)

def get_areas_data():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre")
        areas = cursor.fetchall()
        return {area['nombre']: area['id'] for area in areas}
    except mysql.connector.Error as err:
        print(f"Error al obtener áreas: {err}")
        return {}
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_areas_for_form():
    """Obtiene una lista de objetos de área [{id, nombre}] desde la BD."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre")
        return cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error al obtener áreas: {err}")
        return []
    finally:
        if conn and conn.is_connected():
            conn.close()


@traspaso_bp.route('/traspasar_resguardo/<int:id_resguardo_anterior>', methods=['GET', 'POST'])
@login_required
@permission_required('traspaso.traspasar_resguardo')
def traspasar_resguardo(id_resguardo_anterior):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.*, b.No_Inventario, b.Descripcion_Corta_Del_Bien 
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            WHERE r.id = %s
        """, (id_resguardo_anterior,))
        resguardo_anterior = cursor.fetchone()

        if not resguardo_anterior:
            flash("Resguardo no encontrado.", "danger")
            return redirect(url_for('resguardos.ver_resguardos'))

        areas = get_areas_for_form()

        if request.method == 'POST':
            form_data = request.form
            
            area_nueva_id = form_data.get('Area_Nueva')
            if not area_nueva_id:
                return jsonify({"message": "Debe seleccionar una nueva área.", "category": "danger"}), 400

            sql_update_old_resguardo = "UPDATE resguardos SET Activo = 0, Fecha_Ultima_Modificacion = NOW() WHERE id = %s"
            cursor.execute(sql_update_old_resguardo, (id_resguardo_anterior,))
            
            id_bien = resguardo_anterior['id_bien']
            
            sql_nuevo_resguardo = """
                INSERT INTO resguardos (id_bien, id_area, Ubicacion, No_Resguardo, Tipo_De_Resguardo, Fecha_Resguardo, 
                                        No_Trabajador, Puesto_Trabajador, No_Nomina_Trabajador, Nombre_Del_Resguardante, 
                                        Nombre_Director_Jefe_De_Area, Activo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores_nuevo_resguardo = (
                id_bien, area_nueva_id, form_data.get('Ubicacion_Nueva'),
                form_data.get('No_Resguardo_Nuevo'), form_data.get('Tipo_De_Resguardo_Nuevo'),
                form_data.get('Fecha_Resguardo_Nuevo'), form_data.get('No_Trabajador_Nuevo'),
                form_data.get('Puesto_Trabajador_Nuevo'), form_data.get('No_Nomina_Trabajador_Nuevo'),
                form_data.get('Nombre_Del_Resguardante_Nuevo'), form_data.get('Nombre_Director_Jefe_De_Area_Nueva'),
                1
            )
            cursor.execute(sql_nuevo_resguardo, valores_nuevo_resguardo)
            id_resguardo_nuevo = cursor.lastrowid

            sql_oficio = """
                INSERT INTO oficios_traspaso (id_resguardo_anterior, id_resguardo_actual, Dependencia, Oficio_clave, Asunto, Lugar_Fecha)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            valores_oficio = (
                id_resguardo_anterior, id_resguardo_nuevo, form_data.get('Dependencia_Oficio_1'),
                form_data.get('Oficio_clave_1'), form_data.get('Asunto_Oficio_1'),
                form_data.get('Lugar_Fecha_Oficio_1') if form_data.get('Lugar_Fecha_Oficio_1') else None
            )
            cursor.execute(sql_oficio, valores_oficio)

            conn.commit()
            log_activity(
                action="Traspaso de Resguardo", category="Traspasos", resource_id=id_resguardo_nuevo, 
                details=f"Traspaso del resguardo {id_resguardo_anterior} al {id_resguardo_nuevo} para el bien {resguardo_anterior['No_Inventario']}"
            )
            
            # --- CORRECCIÓN CLAVE ---
            # 1. Se utiliza la función flash() de Flask para preparar el mensaje de éxito.
            flash("Traspaso realizado con éxito.", "success")
            
            # 2. El JSON ahora solo necesita enviar la URL de redirección.
            return jsonify({
                "redirect_url": url_for('resguardos.ver_resguardo', id_resguardo=id_resguardo_nuevo)
            }), 200

    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return jsonify({"message": f"Error al realizar el traspaso: {e}", "category": "danger"}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

    return render_template('/traspasar_resguardo.html', resguardo_anterior=resguardo_anterior, areas=areas)


# --- NUEVA RUTA PARA VER OFICIOS DE TRASPASO ---
@traspaso_bp.route('/ver_oficios_traspaso')
@login_required
def ver_oficios_traspaso():
    """
    Muestra una vista con todos los oficios de traspaso registrados.
    """
    conn = None
    cursor = None
    oficios_con_datos = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Consulta principal para obtener los datos de los oficios y los resguardos
        sql_select_oficios = """
            SELECT
                ot.*,
                ro.No_Resguardo AS No_Resguardo_Anterior,
                ro.Nombre_Del_Resguardante AS Resguardante_Anterior,
                bo.No_Inventario AS No_Inventario_Anterior,
                ao.nombre AS Area_Anterior,
                rn.No_Resguardo AS No_Resguardo_Actual,
                rn.Nombre_Del_Resguardante AS Resguardante_Actual,
                bn.No_Inventario AS No_Inventario_Actual,
                an.nombre AS Area_Actual
            FROM
                oficios_traspaso ot
            JOIN resguardos ro ON ot.id_resguardo_anterior = ro.id
            JOIN bienes bo ON ro.id_bien = bo.id
            JOIN areas ao ON ro.id_area = ao.id
            JOIN resguardos rn ON ot.id_resguardo_actual = rn.id
            JOIN bienes bn ON rn.id_bien = bn.id
            JOIN areas an ON rn.id_area = an.id
            ORDER BY ot.Fecha_Registro DESC
        """
        cursor.execute(sql_select_oficios)
        oficios = cursor.fetchall()
        
        # Para cada oficio, obtener sus imágenes
        for oficio in oficios:
            oficio_id = oficio['id']
            oficio['imagenes'] = get_oficio_images(oficio_id)
            oficios_con_datos.append(oficio)

        return render_template('ver_oficios_traspaso.html', oficios=oficios_con_datos)

    except mysql.connector.Error as err:
        print(f"Error de base de datos al ver oficios: {err}")
        flash(f"Error de base de datos: {err}", 'danger')
        return redirect(url_for('resguardos.ver_resguardos'))
    except Exception as e:
        print(f"Ocurrió un error inesperado al ver oficios: {e}")
        flash(f"Ocurrió un error inesperado: {e}", 'danger')
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def get_oficio_images(oficio_id):
    """Función auxiliar para obtener las rutas de las imágenes de un oficio."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT ruta_imagen FROM imagenes_oficios_traspaso WHERE id_oficio = %s", (oficio_id,))
        images = cursor.fetchall()
        return [img['ruta_imagen'] for img in images]
    except mysql.connector.Error as err:
        print(f"Error al obtener imágenes del oficio: {err}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()