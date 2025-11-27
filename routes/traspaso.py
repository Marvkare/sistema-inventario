# your_flask_app/routes/traspaso.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from database import get_db_connection
from decorators import permission_required
from log_activity import log_activity
from datetime import date, datetime
from werkzeug.utils import secure_filename
import uuid
import os
from config import UPLOAD_FOLDER
import traceback 
import pymysql
from drive_service import (drive_service, BIENES_FOLDER_ID, TRASPASOS_FOLDER_ID, RESGUARDOS_FOLDER_ID)
from pymysql.err import MySQLError

traspaso_bp = Blueprint('traspaso', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    """
    Verifica si un nombre de archivo tiene una extensión permitida.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_areas_data():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre")
        areas = cursor.fetchall()
        return {area['nombre']: area['id'] for area in areas}
    except pymysql.MySQLError as e:
        print(f"Error al obtener áreas: {e}")
        return {}
    finally:
        if conn:
            cursor.close()
            conn.close()

def get_areas_for_form():
    """Obtiene una lista de objetos de área [{id, nombre}] desde la BD."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre")
        return cursor.fetchall()
    except MySQLError as err:
        print(f"Error al obtener áreas: {err}")
        return []
    finally:
        if conn:
            conn.close()

@traspaso_bp.route('/traspasar_resguardo/<int:id_resguardo_anterior>', methods=['GET', 'POST'])
@login_required
@permission_required('traspaso.traspasar_resguardo')
def traspasar_resguardo(id_resguardo_anterior):
    """
    Gestiona el proceso de traspaso de un bien de un resguardo a otro,
    incluyendo la creación de oficios y el guardado de evidencia LOCAL.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # --- LÓGICA GET (sin cambios) ---
        cursor.execute("""
            SELECT 
                r.*, b.No_InventARIO, b.Descripcion_Corta_Del_Bien, b.Proveedor, 
                b.Numero_De_Serie, a.nombre as Area_Anterior_Nombre
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
            WHERE r.id = %s
        """, (id_resguardo_anterior,))
        resguardo_anterior = cursor.fetchone()

        if not resguardo_anterior:
            flash("Resguardo no encontrado.", "danger")
            return redirect(url_for('resguardos.ver_resguardos'))

        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre ASC")
        areas = cursor.fetchall()

        # --- LÓGICA POST ---
        if request.method == 'POST':
            
            # --- 1. PREPARACIÓN DE CARPETAS LOCALES ---
            base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if not base_upload_folder:
                raise Exception("UPLOAD_FOLDER no está configurado en la app.")
            
            # Definimos las rutas físicas
            resguardos_dir = os.path.join(base_upload_folder, 'resguardos')
            traspasos_dir = os.path.join(base_upload_folder, 'traspasos')
            
            # Creamos las carpetas si no existen
            os.makedirs(resguardos_dir, exist_ok=True)
            os.makedirs(traspasos_dir, exist_ok=True)

            form_data = request.form
            
            area_nueva_id = form_data.get('Area_Nueva')
            if not area_nueva_id:
                return jsonify({"message": "Error: Debe seleccionar una nueva área para el resguardo.", "category": "danger"}), 400

            # --- Lógica de Base de Datos (Update Resguardo Anterior) ---
            cursor.execute("UPDATE resguardos SET Activo = 0, Fecha_Ultima_Modificacion = NOW() WHERE id = %s", (id_resguardo_anterior,))
            
            # --- Insertar Nuevo Resguardo ---
            no_nomina_str = form_data.get('No_Nomina_Trabajador_Nuevo')
            no_nomina = int(no_nomina_str) if no_nomina_str and no_nomina_str.strip() else None

            sql_nuevo_resguardo = """
                INSERT INTO resguardos (id_bien, id_area, Ubicacion, No_Resguardo, Tipo_De_Resguardo, Fecha_Resguardo, 
                                        No_Trabajador, Puesto_Trabajador, No_Nomina_Trabajador, Nombre_Del_Resguardante, 
                                        Nombre_Director_Jefe_De_Area, Activo, usuario_id_registro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
            """
            valores_nuevo_resguardo = (
                resguardo_anterior['id_bien'], area_nueva_id, form_data.get('Ubicacion_Nueva'),
                form_data.get('No_Resguardo_Nuevo'), form_data.get('Tipo_De_Resguardo_Nuevo'),
                form_data.get('Fecha_Resguardo_Nuevo'), form_data.get('No_Trabajador_Nuevo'),
                form_data.get('Puesto_Trabajador_Nuevo'), no_nomina,
                form_data.get('Nombre_Del_Resguardante_Nuevo'), form_data.get('Nombre_Director_Jefe_De_Area_Nueva'),
                current_user.id
            )
            cursor.execute(sql_nuevo_resguardo, valores_nuevo_resguardo)
            id_resguardo_nuevo = cursor.lastrowid

            # --- Insertar Registro de Traspaso ---
            sql_traspaso = """
                INSERT INTO traspaso (
                    id_resguardo, fecha_traspaso, area_origen_id, area_destino_id,
                    usuario_origen_nombre, usuario_destino_nombre, motivo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            valores_traspaso = (
                id_resguardo_nuevo, datetime.now(),
                resguardo_anterior['id_area'], area_nueva_id,
                resguardo_anterior['Nombre_Del_Resguardante'],
                form_data.get('Nombre_Del_Resguardante_Nuevo'),
                form_data.get('Asunto_Oficio_1') 
            )
            cursor.execute(sql_traspaso, valores_traspaso)

            # =====================================================================
            # ✅ 2. GUARDADO LOCAL: Imágenes del Nuevo Resguardo
            # =====================================================================
            imagenes_nuevo_resguardo = request.files.getlist('imagen_nuevo_resguardo')
            for imagen in imagenes_nuevo_resguardo:
                # Asegúrate de importar allowed_file y secure_filename
                if imagen and allowed_file(imagen.filename):
                    
                    filename = secure_filename(imagen.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # Guardar físico en carpeta 'resguardos'
                    save_path = os.path.join(resguardos_dir, unique_filename)
                    imagen.save(save_path)
                    
                    # Ruta relativa para la BD
                    db_path = os.path.join('resguardos', unique_filename)

                    cursor.execute(
                        """
                        INSERT INTO imagenes_resguardo 
                            (id_resguardo, ruta_imagen, fecha_subida) 
                        VALUES (%s, %s, NOW())
                        """,
                        (id_resguardo_nuevo, db_path) 
                    )
            
            # =====================================================================
            # ✅ 3. GUARDADO LOCAL: Fotos de los Oficios
            # =====================================================================
            oficio_index = 1
            while True:
                oficio_clave = form_data.get(f'Oficio_clave_{oficio_index}')
                if oficio_clave is None:
                    break 

                # Insertar datos del oficio
                sql_oficio = """
                    INSERT INTO oficios_traspaso (id_resguardo_anterior, id_resguardo_actual, Dependencia, Oficio_clave, Asunto, 
                                                  Lugar_Fecha, Nombre_Solicitante, id_area_solicitante, Jefe_Area_Solicitante) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores_oficio = (
                    id_resguardo_anterior, id_resguardo_nuevo,
                    form_data.get(f'Dependencia_Oficio_{oficio_index}'),
                    oficio_clave, form_data.get(f'Asunto_Oficio_{oficio_index}'),
                    form_data.get(f'Lugar_Fecha_Oficio_{oficio_index}') if form_data.get(f'Lugar_Fecha_Oficio_{oficio_index}') else None,
                    form_data.get(f'Nombre_Solicitante_{oficio_index}'),
                    form_data.get(f'Area_Solicitante_{oficio_index}'),
                    form_data.get(f'Jefe_Area_Solicitante_{oficio_index}')
                )
                cursor.execute(sql_oficio, valores_oficio)
                id_oficio_nuevo = cursor.lastrowid

                # Guardar fotos del oficio localmente
                fotos_oficio = request.files.getlist(f'fotos_oficio_{oficio_index}')
                for foto in fotos_oficio:
                    if foto and allowed_file(foto.filename):
                        
                        filename = secure_filename(foto.filename)
                        # Usamos un prefijo para identificar que es de un oficio
                        unique_filename = f"oficio-{uuid.uuid4()}-{filename}"
                        
                        # Guardar físico en carpeta 'traspasos'
                        save_path = os.path.join(traspasos_dir, unique_filename)
                        foto.save(save_path)
                        
                        # Ruta relativa para la BD
                        db_path = os.path.join('traspasos', unique_filename)

                        cursor.execute(
                            """
                            INSERT INTO imagenes_oficios_traspaso 
                                (id_oficio, ruta_imagen, fecha_subida) 
                            VALUES (%s, %s, NOW())
                            """,
                            (id_oficio_nuevo, db_path)
                        )
                
                oficio_index += 1

            # Confirmar transacción
            conn.commit()
            log_activity(
                action="Traspaso de Resguardo", 
                category="Traspasos", 
                resource_id=id_resguardo_nuevo, 
                details=f"Usuario '{current_user.username}' realizó traspaso del resguardo ID {id_resguardo_anterior} al {id_resguardo_nuevo}"
            )
            
            flash("Traspaso realizado con éxito.", "success")
            return jsonify({"redirect_url": url_for('resguardos.ver_resguardo', id_resguardo=id_resguardo_nuevo)}), 200

    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        if request.method == 'POST':
            return jsonify({"message": f"Error interno al realizar el traspaso: {str(e)}", "category": "danger"}), 500
        else:
            flash(f"Error al cargar la página de traspaso: {str(e)}", "danger")
            return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn :
            conn.close()

    return render_template(
        'traspasos/traspasar_resguardo.html', 
        resguardo_anterior=resguardo_anterior, 
        areas=areas
    )


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
        cursor = conn.cursor(pymysql.cursors.DictCursor)
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

    except MySQLError as err:
        print(f"Error de base de datos al ver oficios: {err}")
        flash(f"Error de base de datos: {err}", 'danger')
        return redirect(url_for('resguardos.ver_resguardos'))
    except Exception as e:
        print(f"Ocurrió un error inesperado al ver oficios: {e}")
        flash(f"Ocurrió un error inesperado: {e}", 'danger')
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn:
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

@traspaso_bp.route('/ver_traspasos')
@login_required
@permission_required('traspaso.ver_traspasos') # Permiso recomendado
def ver_traspasos():
    """
    Muestra una lista de todos los traspasos realizados, con un conteo de oficios
    y una barra de búsqueda para filtrar.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        search_query = request.args.get('q', '').strip()

        # Esta consulta es más compleja: une Traspaso con los resguardos (anterior y actual)
        # y cuenta el número de oficios asociados a la transacción.
        sql_base = """
            SELECT
                t.id AS traspaso_id,
                t.fecha_traspaso,
                b.No_Inventario,
                r_anterior.Nombre_Del_Resguardante AS Resguardante_Anterior,
                a_anterior.nombre AS Area_Anterior,
                r_actual.Nombre_Del_Resguardante AS Resguardante_Actual,
                a_actual.nombre AS Area_Actual,
                COUNT(ot.id) AS numero_oficios
            FROM traspaso t
            JOIN resguardos r_actual ON t.id_resguardo = r_actual.id
            JOIN bienes b ON r_actual.id_bien = b.id
            JOIN areas a_actual ON r_actual.id_area = a_actual.id
            LEFT JOIN oficios_traspaso ot ON r_actual.id = ot.id_resguardo_actual
            LEFT JOIN resguardos r_anterior ON ot.id_resguardo_anterior = r_anterior.id
            LEFT JOIN areas a_anterior ON r_anterior.id_area = a_anterior.id
        """
        
        params = []
        if search_query:
            sql_base += """
                WHERE b.No_Inventario LIKE %s
                OR r_anterior.Nombre_Del_Resguardante LIKE %s
                OR r_actual.Nombre_Del_Resguardante LIKE %s
            """
            like_query = f"%{search_query}%"
            params.extend([like_query, like_query, like_query])

        sql_base += """
            GROUP BY t.id, t.fecha_traspaso, b.No_Inventario, 
                     Resguardante_Anterior, Area_Anterior, 
                     Resguardante_Actual, Area_Actual
            ORDER BY t.fecha_traspaso DESC
        """
        
        cursor.execute(sql_base, params)
        traspasos = cursor.fetchall()
        
        return render_template(
            'traspasos/ver_traspasos.html', 
            traspasos=traspasos, 
            search_query=search_query
        )

    except Exception as e:
        flash(f"Error al cargar los traspasos: {e}", "danger")
        traceback.print_exc()
        return redirect(url_for('main.dashboard'))
    finally:
        if conn :
            conn.close()


@traspaso_bp.route('/detalles/<int:traspaso_id>')
@login_required
@permission_required('traspaso.ver_traspasos') # Reutilizamos el permiso
def ver_detalles_traspaso(traspaso_id):
    """
    Muestra la información detallada de un único traspaso, incluyendo
    datos del bien, resguardos y todos los oficios asociados.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 1. Obtener la información principal del traspaso y los resguardos
        sql_traspaso_details = """
            SELECT
                t.id AS traspaso_id,
                t.fecha_traspaso,
                b.id AS bien_id,
                b.No_Inventario,
                b.Descripcion_Corta_Del_Bien,
                
                -- CAMBIO: Se usa u_bien.nombres
                u_bien.nombres AS usuario_que_registro_el_bien,
                
                r_actual.id AS resguardo_actual_id,
                r_actual.Nombre_Del_Resguardante AS resguardante_actual,
                r_actual.No_Trabajador AS trabajador_actual_no,
                a_actual.nombre AS area_actual,
                (SELECT id_resguardo_anterior 
                 FROM oficios_traspaso 
                 WHERE id_resguardo_actual = r_actual.id LIMIT 1) AS resguardo_anterior_id
                 
            FROM traspaso t
            JOIN resguardos r_actual ON t.id_resguardo = r_actual.id
            JOIN bienes b ON r_actual.id_bien = b.id
            
            -- CAMBIO: Se hace LEFT JOIN con la tabla 'user' (no 'usuarios')
            LEFT JOIN user u_bien ON b.usuario_id_registro = u_bien.id
            
            JOIN areas a_actual ON r_actual.id_area = a_actual.id
            WHERE t.id = %s
        """
        cursor.execute(sql_traspaso_details, (traspaso_id,))
        traspaso = cursor.fetchone()

        if not traspaso:
            flash("Traspaso no encontrado.", "danger")
            return redirect(url_for('traspaso.ver_traspasos'))

        # 2. Obtener detalles del resguardo anterior (si existe)
        resguardo_anterior = None
        if traspaso['resguardo_anterior_id']:
            cursor.execute("""
                SELECT r.*, a.nombre as nombre_area FROM resguardos r
                JOIN areas a ON r.id_area = a.id
                WHERE r.id = %s
            """, (traspaso['resguardo_anterior_id'],))
            resguardo_anterior = cursor.fetchone()

        # 3. Obtener todos los oficios asociados al resguardo actual de este traspaso
        sql_oficios = """
            SELECT o.*, a.nombre as nombre_area_solicitante FROM oficios_traspaso o
            LEFT JOIN areas a ON o.id_area_solicitante = a.id
            WHERE o.id_resguardo_actual = %s
        """
        cursor.execute(sql_oficios, (traspaso['resguardo_actual_id'],))
        oficios = cursor.fetchall()

        # 4. Obtener todas las imágenes de esos oficios en una sola consulta
        fotos_por_oficio = {}
        if oficios:
            oficio_ids = [o['id'] for o in oficios]
            format_strings = ','.join(['%s'] * len(oficio_ids))
            cursor.execute(
                f"SELECT id_oficio, ruta_imagen FROM imagenes_oficios_traspaso WHERE id_oficio IN ({format_strings})",
                tuple(oficio_ids)
            )
            for foto in cursor.fetchall():
                oficio_id = foto['id_oficio']
                if oficio_id not in fotos_por_oficio:
                    fotos_por_oficio[oficio_id] = []
                fotos_por_oficio[oficio_id].append(foto['ruta_imagen'])

        return render_template(
            'traspasos/detalles_traspaso.html',
            traspaso=traspaso,
            resguardo_anterior=resguardo_anterior,
            oficios=oficios,
            fotos_por_oficio=fotos_por_oficio
        )

    except Exception as e:
        flash(f"Error al cargar los detalles del traspaso: {e}", "danger")
        traceback.print_exc()
        return redirect(url_for('traspaso.ver_traspasos'))
    finally:
        if conn :
            conn.close()