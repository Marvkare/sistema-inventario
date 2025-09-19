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

@traspaso_bp.route('/traspasar_resguardo/<int:id_resguardo>', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def traspasar_resguardo(id_resguardo):

    conn = None
    cursor = None
    areas_data = get_areas_data()
    areas_list = list(areas_data.keys())

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # --- Proceso de Traspaso (POST) ---
            form_data = request.form.to_dict()
            
            # Obtener datos del resguardo anterior
            cursor.execute("SELECT r.id_bien, b.No_Inventario FROM resguardos r JOIN bienes b ON r.id_bien = b.id WHERE r.id = %s", (id_resguardo,))
            old_resguardo_data = cursor.fetchone()
            if not old_resguardo_data:
                return jsonify({"message": "Resguardo anterior no encontrado.", "category": "danger"}), 404
            
            id_bien = old_resguardo_data['id_bien']
            
            # Obtener id de la nueva área
            new_area_name = form_data.get('Area_Nueva')
            new_area_id = areas_data.get(new_area_name)
            if not new_area_id:
                return jsonify({"message": "Área seleccionada no válida.", "category": "danger"}), 400
            print(form_data) 
            # Se obtiene el valor del formulario y se convierte a entero directamente
            tipo_resguardo_nuevo_str = form_data.get('Tipo_De_Resguardo_Value')
            print(f"Tipo de resguardo nuevo: {tipo_resguardo_nuevo_str}")
            try:
                tipo_resguardo_nuevo_int = int(tipo_resguardo_nuevo_str)
            except (ValueError, TypeError):
                print(f"Tipo de resguardo no válido: {tipo_resguardo_nuevo_str}")
                return jsonify({"message": "Tipo de resguardo no válido.", "category": "danger"}), 400
            
            # 1. Dar de baja el resguardo anterior
            sql_update_old_resguardo = "UPDATE resguardos SET Activo = FALSE, Fecha_Ultima_Modificacion = NOW() WHERE id = %s"
            cursor.execute(sql_update_old_resguardo, (id_resguardo,))
            
            # 2. Generar el nuevo resguardo para el nuevo resguardante
            sql_insert_new_resguardo = """
                INSERT INTO resguardos (id_bien, id_area, Ubicacion, No_Resguardo, Tipo_De_Resguardo, Fecha_Resguardo,
                                        No_Trabajador, Puesto_Trabajador, Nombre_Del_Resguardante, Nombre_Director_Jefe_De_Area)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            new_resguardo_values = (
                id_bien,
                new_area_id,
                form_data.get('Ubicacion_Nueva'),
                form_data.get('No_Resguardo_Nuevo'),
                tipo_resguardo_nuevo_int,
                form_data.get('Fecha_Resguardo_Nuevo'),
                form_data.get('No_Trabajador_Nuevo'),
                form_data.get('Puesto_Trabajador_Nuevo'),
                form_data.get('Nombre_Del_Resguardante_Nuevo'),
                form_data.get('Nombre_Director_Jefe_De_Area_Nueva')
            )
            cursor.execute(sql_insert_new_resguardo, new_resguardo_values)
            new_resguardo_id = cursor.lastrowid

            # 3. Procesar los oficios y sus imágenes
            oficios_data = []
            for key, value in form_data.items():
                if key.startswith('Oficio_clave_'):
                    index = key.replace('Oficio_clave_', '')
                    oficios_data.append({
                        'Oficio_clave': value,
                        'Dependencia': form_data.get(f'Dependencia_Oficio_{index}'),
                        'Asunto': form_data.get(f'Asunto_Oficio_{index}'),
                        'Lugar_Fecha': form_data.get(f'Lugar_Fecha_Oficio_{index}'),
                        'Secretaria_General_Municipal': form_data.get(f'Secretaria_General_Municipal_{index}'),
                        'files_key': f'archivos_oficios_{index}'
                    })

            for oficio in oficios_data:
                sql_insert_oficio = """
                    INSERT INTO oficios_traspaso (id_resguardo_anterior, id_resguardo_actual, Dependencia, Oficio_clave, Asunto, Lugar_Fecha, Secretaria_General_Municipal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                oficio_values = (
                    id_resguardo,
                    new_resguardo_id,
                    oficio['Dependencia'],
                    oficio['Oficio_clave'],
                    oficio['Asunto'],
                    oficio['Lugar_Fecha'],
                    oficio['Secretaria_General_Municipal']
                )
                cursor.execute(sql_insert_oficio, oficio_values)
                id_oficio = cursor.lastrowid
                
                # Manejar las imágenes de este oficio
                imagenes = request.files.getlist(oficio['files_key'])
                sql_insert_img = "INSERT INTO imagenes_oficios_traspaso (id_oficio, ruta_imagen) VALUES (%s, %s)"
                for file in imagenes:
                    if file.filename:
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}-{filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                        file.save(file_path)
                        cursor.execute(sql_insert_img, (id_oficio, unique_filename))

            conn.commit()
            log_activity(action='Traspaso', resource='Resguardo', resource_id=new_resguardo_id, details=f'Traspaso de resguardo exitoso. ID anterior: {id_resguardo}, ID nuevo: {new_resguardo_id}')
            return jsonify({"message": "Traspaso de resguardo completado exitosamente.", "category": "success", "redirect_url": url_for('resguardos.ver_resguardos')}), 200

        else:
            # --- Vista de Formulario de Traspaso (GET) ---
            sql_select_resguardo = """
                SELECT 
                    r.*, 
                    b.No_Inventario, b.Descripcion_Del_Bien, b.Proveedor, b.Numero_De_Serie,
                    a.nombre AS Area_Anterior_Nombre, 
                    a.numero AS Area_Anterior_Numero
                FROM resguardos r
                JOIN bienes b ON r.id_bien = b.id
                JOIN areas a ON r.id_area = a.id
                WHERE r.id = %s
            """
            cursor.execute(sql_select_resguardo, (id_resguardo,))
            resguardo_anterior = cursor.fetchone()

            if not resguardo_anterior:
                flash('Resguardo no encontrado.', 'danger')
                return redirect(url_for('resguardos.ver_resguardos'))
            print(resguardo_anterior)
            return render_template(
                'traspasar_resguardo.html',
                resguardo_anterior=resguardo_anterior,
                areas=areas_list,
                # En este caso, si no tienes la tabla, no necesitamos enviar los tipos de resguardo al formulario
            )

    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            conn.rollback()
        print(f"Error de base de datos: {err}")
        return jsonify({"message": f"Error de base de datos: {err}", "category": "danger"}), 500
    except Exception as e:
        if conn and conn.is_connected():
            conn.rollback()
        print(f"Ocurrió un error inesperado: {e}")
        return jsonify({"message": f"Ocurrió un error inesperado: {e}", "category": "danger"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


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