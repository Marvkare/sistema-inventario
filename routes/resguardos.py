# your_flask_app/routes/resguardos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify
from flask_login import login_required, current_user
import mysql.connector
import os
import traceback
from pypdf import PdfReader, PdfWriter
import pypdf.generic
from werkzeug.utils import secure_filename
from datetime import date,datetime
import uuid
from database import get_db, get_db_connection, AVAILABLE_COLUMNS
from config import UPLOAD_FOLDER;
from decorators import permission_required
from log_activity import log_activity
from models import Resguardo, Bienes, Area
import math
resguardos_bp = Blueprint('resguardos', __name__)



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


# Añade esta nueva ruta en cualquier parte de tu archivo resguardos.py
@resguardos_bp.route('/api/areas', methods=['GET'])
@login_required
def get_areas_api():
    """Devuelve la lista de áreas en formato JSON."""
    try:
        areas = get_areas_for_form()
        return jsonify(areas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Reemplaza tu función crear_resguardo con esta versión corregida
@resguardos_bp.route('/crear_resguardo', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def crear_resguardo():
    conn = None
    areas = get_areas_for_form()
    
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            if not conn: raise Exception("No se pudo conectar a la base de datos.")
            cursor = conn.cursor()
            
            form_data = request.form
            id_bien_existente = form_data.get('id_bien_existente')
            id_bien = None
            
            if id_bien_existente:
                id_bien = id_bien_existente
            else:
                # Lógica para crear un nuevo bien
                sql_bien = """INSERT INTO bienes (No_Inventario, No_Factura, No_Cuenta, Proveedor, Descripcion_Del_Bien, Descripcion_Corta_Del_Bien, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora, Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final, Cantidad, Estado_Del_Bien, Marca, Modelo, Numero_De_Serie, Clasificacion_Legal, usuario_id_registro, Area_Presupuestal, Documento_Propiedad, Fecha_Documento_Propiedad, Valor_En_Libros, Fecha_Adquisicion_Alta, Activo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                bien_values = (form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'), form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'), form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final'), form_data.get('Cantidad'), form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'), form_data.get('Numero_De_Serie'), form_data.get('Clasificacion_Legal'), current_user.id, form_data.get('Area_Presupuestal'), form_data.get('Documento_Propiedad'), form_data.get('Fecha_Documento_Propiedad'), form_data.get('Valor_En_Libros'), form_data.get('Fecha_Adquisicion_Alta'), 1)
                cursor.execute(sql_bien, bien_values)
                id_bien = cursor.lastrowid
                
                for file in request.files.getlist('imagenes_bien'):
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}-{filename}"
                        file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                        cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", (id_bien, unique_filename))

            area_id = form_data.get('Area')
            sql_resguardo = """
                INSERT INTO resguardos (
                    id_bien, id_area, No_Resguardo, Tipo_De_Resguardo, Fecha_Resguardo, 
                    No_Trabajador, No_Nomina_Trabajador, Puesto_Trabajador, RFC_Trabajador, Ubicacion,
                    Nombre_Director_Jefe_De_Area, Nombre_Del_Resguardante, Activo, usuario_id_registro
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            resguardo_values = (
                id_bien, area_id, form_data.get('No_Resguardo'), 
                form_data.get('Tipo_De_Resguardo'), form_data.get('Fecha_Resguardo'), 
                form_data.get('No_Trabajador'), form_data.get('No_Nomina_Trabajador'), 
                form_data.get('Puesto_Trabajador'), form_data.get('RFC_Trabajador'),
                form_data.get('Ubicacion'), form_data.get('Nombre_Director_Jefe_De_Area'), 
                form_data.get('Nombre_Del_Resguardante'), 1, current_user.id
            )
            cursor.execute(sql_resguardo, resguardo_values)
            id_resguardo = cursor.lastrowid

            for file in request.files.getlist('imagenes_resguardo'):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    cursor.execute("INSERT INTO imagenes_resguardo (id_resguardo, ruta_imagen) VALUES (%s, %s)", (id_resguardo, unique_filename))
            
            conn.commit()
            log_activity(action='Creación de Resguardo', category='Resguardos', resource_id=id_resguardo)
            # --- CORRECCIÓN: Se retorna solo el JSON, que es lo esperado para un envío de formulario con JS ---
            jsonify({"message": "Resguardo creado exitosamente.", "category": "success", "redirect_url": url_for('resguardos.ver_resguardos')}), 200
            return redirect(url_for('resguardos.ver_resguardos'))

        except mysql.connector.Error as e:
            if conn: conn.rollback()
            if e.errno == 1062:
                 return jsonify({"message": f"Error: Ya existe un bien con el mismo 'No. de Inventario'.", "category": "danger"}), 409
            traceback.print_exc()
            return jsonify({"message": f"Ocurrió un error de base de datos: {e}", "category": "danger"}), 500
        finally:
            if conn and conn.is_connected(): conn.close()
            
    return render_template('/resguardos/resguardo_form.html', areas=areas, form_data={}, bien_precargado=False)

@resguardos_bp.route('/crear_resguardo_de_bien/<int:id_bien>', methods=['GET'])
@login_required
@permission_required('resguardos.crear_resguardo')
def crear_resguardo_de_bien(id_bien):
    conn = None
    areas = get_areas_for_form()
    try:
        conn = get_db_connection()
        if not conn: raise Exception("No se pudo conectar a la base de datos.")
        cursor = conn.cursor(dictionary=True)
        
        # Se obtienen los datos del bien
        cursor.execute("SELECT * FROM bienes WHERE id = %s", (id_bien,))
        bien_data = cursor.fetchone()

        if not bien_data:
            flash("Bien no encontrado.", "danger")
            return redirect(url_for('bienes.listar_bienes'))

        # --- CORRECCIÓN CLAVE ---
        # Ahora también se obtienen las imágenes existentes del bien.
        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (id_bien,))
        imagenes_bien_db = cursor.fetchall()
        print(bien_data)
        # Se pasan las imágenes a la plantilla con la variable 'imagenes_bien_db'
        return render_template('resguardos/resguardo_form.html', 
                               areas=areas, 
                               form_data=bien_data, 
                               is_edit=False, 
                               bien_precargado=True,
                               imagenes_bien_db=imagenes_bien_db)
    except Exception as e:
        flash(f"Ocurrió un error: {e}", "danger")
        return redirect(url_for('bienes.listar_bienes'))
    finally:
        if conn and conn.is_connected(): conn.close()


@resguardos_bp.route('/editar_resguardo/<int:id_resguardo>', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.editar_resguardo')
def editar_resguardo(id_resguardo):
    conn = None
    areas = get_areas_for_form()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            form_data = request.form
            
            id_bien = form_data.get('id_bien')
            area_id = form_data.get('Area')

            def to_null(value):
                return None if value == '' else value

            sql_update_bien = "UPDATE bienes SET No_Inventario=%s, No_Factura=%s, No_Cuenta=%s, Proveedor=%s, Descripcion_Del_Bien=%s, Descripcion_Corta_Del_Bien=%s, Rubro=%s, Poliza=%s, Fecha_Poliza=%s, Sub_Cuenta_Armonizadora=%s, Fecha_Factura=%s, Costo_Inicial=%s, Depreciacion_Acumulada=%s, Costo_Final=%s, Cantidad=%s, Estado_Del_Bien=%s, Marca=%s, Modelo=%s, Numero_De_Serie=%s WHERE id=%s"
            bien_values = (
                form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), 
                form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), 
                form_data.get('Descripcion_Corta_Del_Bien'), form_data.get('Rubro'), 
                form_data.get('Poliza'), to_null(form_data.get('Fecha_Poliza')), 
                form_data.get('Sub_Cuenta_Armonizadora'), to_null(form_data.get('Fecha_Factura')), 
                to_null(form_data.get('Costo_Inicial')), to_null(form_data.get('Depreciacion_Acumulada')), 
                to_null(form_data.get('Costo_Final')), to_null(form_data.get('Cantidad')), 
                form_data.get('Estado_Del_Bien'), form_data.get('Marca'), 
                form_data.get('Modelo'), form_data.get('Numero_De_Serie'), id_bien
            )
            cursor.execute(sql_update_bien, bien_values)
            
            sql_update_resguardo = "UPDATE resguardos SET id_area=%s, No_Resguardo=%s, Tipo_De_Resguardo=%s, Fecha_Resguardo=%s, No_Trabajador=%s, No_Nomina_Trabajador=%s, Puesto_trabajador=%s, Nombre_Director_Jefe_De_Area=%s, Nombre_Del_Resguardante=%s WHERE id=%s"
            resguardo_values = (
                area_id, form_data.get('No_Resguardo'), 
                form_data.get('Tipo_De_Resguardo'), to_null(form_data.get('Fecha_Resguardo')),
                form_data.get('No_Trabajador'), to_null(form_data.get('No_Nomina_Trabajador')),
                form_data.get('Puesto_Trabajador'), form_data.get('Nombre_Director_Jefe_De_Area'),
                form_data.get('Nombre_Del_Resguardante'), id_resguardo
            )
            cursor.execute(sql_update_resguardo, resguardo_values)
            
            # --- CORRECCIÓN CLAVE: Lógica para AÑADIR y ELIMINAR imágenes ---

            # 1. Eliminar imágenes marcadas
            for img_id in request.form.getlist('eliminar_imagen_bien[]'):
                cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id = %s", (img_id,))
                imagen = cursor.fetchone()
                if imagen:
                    os.remove(os.path.join(UPLOAD_FOLDER, imagen['ruta_imagen']))
                    cursor.execute("DELETE FROM imagenes_bien WHERE id = %s", (img_id,))

            for img_id in request.form.getlist('eliminar_imagen_resguardo[]'):
                cursor.execute("SELECT ruta_imagen FROM imagenes_resguardo WHERE id = %s", (img_id,))
                imagen = cursor.fetchone()
                if imagen:
                    os.remove(os.path.join(UPLOAD_FOLDER, imagen['ruta_imagen']))
                    cursor.execute("DELETE FROM imagenes_resguardo WHERE id = %s", (img_id,))
            
            # 2. Añadir nuevas imágenes
            for file in request.files.getlist('imagenes_bien'):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", (id_bien, unique_filename))

            for file in request.files.getlist('imagenes_resguardo'):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    cursor.execute("INSERT INTO imagenes_resguardo (id_resguardo, ruta_imagen) VALUES (%s, %s)", (id_resguardo, unique_filename))

            conn.commit()
            log_activity(action='Edición de Resguardo', category='Resguardos', resource_id=id_resguardo)
            flash('Resguardo actualizado exitosamente.', 'success')

            return redirect(url_for('resguardos.ver_resguardos'))

        # Lógica GET
        sql_select = "SELECT r.*, b.*, r.id AS resguardo_id, b.id AS bien_id, a.id as Area_id FROM resguardos r JOIN bienes b ON r.id_bien = b.id JOIN areas a ON r.id_area = a.id WHERE r.id = %s"
        cursor.execute(sql_select, (id_resguardo,))
        resguardo_data = cursor.fetchone()
        if not resguardo_data: abort(404)

        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (resguardo_data['bien_id'],))
        imagenes_bien_db = cursor.fetchall()
        cursor.execute("SELECT id, ruta_imagen FROM imagenes_resguardo WHERE id_resguardo = %s", (resguardo_data['resguardo_id'],))
        imagenes_resguardo_db = cursor.fetchall()
        print(resguardo_data)
        return render_template('resguardos/resguardo_form.html', is_edit=True, form_data=resguardo_data, areas=areas, imagenes_bien_db=imagenes_bien_db, imagenes_resguardo_db=imagenes_resguardo_db)

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al editar el resguardo: {e}", 'danger')
        traceback.print_exc()
        
        form_data_on_error = request.form.to_dict()
        form_data_on_error['resguardo_id'] = id_resguardo
        form_data_on_error['bien_id'] = request.form.get('id_bien')
        
        imagenes_bien_db, imagenes_resguardo_db = [], []
        id_bien_from_form = request.form.get('id_bien')
        if id_bien_from_form:
            try:
                if not conn or not conn.is_connected():
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (id_bien_from_form,))
                imagenes_bien_db = cursor.fetchall()
                cursor.execute("SELECT id, ruta_imagen FROM imagenes_resguardo WHERE id_resguardo = %s", (id_resguardo,))
                imagenes_resguardo_db = cursor.fetchall()
            except Exception as inner_e:
                print(f"Error al recuperar imágenes durante el manejo de errores: {inner_e}")

        return render_template('resguardos/resguardo_form.html', 
                               is_edit=True, 
                               form_data=form_data_on_error, 
                               areas=areas,
                               imagenes_bien_db=imagenes_bien_db,
                               imagenes_resguardo_db=imagenes_resguardo_db)
    finally:
        if conn and conn.is_connected(): conn.close()



@resguardos_bp.route('/ver_resguardo/<int:id_resguardo>', methods=['GET'])
@login_required
@permission_required('resguardos.crear_resguardo')
def ver_resguardo(id_resguardo):
    """
    Muestra los detalles completos de un resguardo específico, incluyendo sus imágenes.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # --- CAMBIO: La consulta ahora trae TODOS los campos de bien y resguardo (b.*, r.*) ---
        # --- y se une con 'user' para obtener el nombre de quien registró el resguardo. ---
        sql_select_resguardo = """
            SELECT 
                r.*,
                b.*,
                r.id AS id_resguardo,
                b.id AS id_bien,
                a.nombre AS Area_Nombre,
                u.username AS registrado_por_nombre
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
            JOIN user u ON r.usuario_id_registro = u.id
            WHERE r.id = %s
        """
        cursor.execute(sql_select_resguardo, (id_resguardo,))
        resguardo = cursor.fetchone()

        if not resguardo:
            flash('Resguardo no encontrado.', 'danger')
            return redirect(url_for('resguardos.ver_resguardos'))

        # Obtener imágenes del bien
        cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (resguardo['id_bien'],))
        imagenes_bien = [row['ruta_imagen'] for row in cursor.fetchall()]
        
        # Obtener imágenes del resguardo
        cursor.execute("SELECT ruta_imagen FROM imagenes_resguardo WHERE id_resguardo = %s", (resguardo['id_resguardo'],))
        imagenes_resguardo = [row['ruta_imagen'] for row in cursor.fetchall()]

        return render_template(
            'ver_resguardo.html',
            resguardo=resguardo,
            imagenes_bien=imagenes_bien,
            imagenes_resguardo=imagenes_resguardo
        )
    except mysql.connector.Error as err:
        flash(f"Error de base de datos: {err}", "danger")
        return redirect(url_for('resguardos.ver_resguardos'))
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", "danger")
        traceback.print_exc()
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# It's good practice to have a helper function to get areas
def get_areas_list_from_db():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT nombre FROM areas ORDER BY nombre")
        areas = [row['nombre'] for row in cursor.fetchall()]
        return areas
    except Exception as e:
        print(f"Error fetching areas from DB: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()



@resguardos_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def delete_resguardo(id):
    """Elimina un registro de la base de datos."""
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        query = "DELETE FROM resguardo WHERE No_Folio = %s"
        cursor.execute(query, (id,))
        conn.commit()
        log_activity(action='Resguardos', resource='Resguardo', resource_id=id, details=f'Se elimino resguardo y bien, ID: {id}')
        flash("Resguardo eliminado correctamente.", 'success')
    except mysql.connector.Error as err:
        flash(f"Error al eliminar resguardo: {err}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index'))




# En tu archivo routes/resguardos.py

# ... (tus otras importaciones como Flask, render_template, request, etc.)

# =================================================================
# VISTAS DE RESGUARDOS (RUTAS)
# =================================================================

@resguardos_bp.route('/resguardos')
@login_required
def ver_resguardos():
    """
    Muestra la lista de TODOS los resguardos.
    Llama a la función principal para hacer el trabajo pesado.
    """
    return _get_resguardos_list(control_only=False)


@resguardos_bp.route('/resguardos_sujeto_control')
@login_required
@permission_required('resguardos.ver_resguardo')
def ver_resguardos_sujeto_control():
    """
    Muestra la lista de resguardos que son 'Sujeto de Control'.
    Llama a la función principal para hacer el trabajo pesado.
    """
    return _get_resguardos_list(control_only=True)


# =================================================================
# FUNCIÓN LÓGICA PRINCIPAL (EL MOTOR)
# =================================================================

def _get_resguardos_list(control_only=False):
    """
    Función unificada y COMPLETA para obtener listas de resguardos.
    Ahora solo maneja la paginación numerada.
    """
    conn = None
    try:
        # --- 1. Obtener Parámetros de la Petición ---
        page = request.args.get('page', 1, type=int)
        limit = 100
        offset = (page - 1) * limit
        search_column = request.args.get('search_column', 'all')
        search_query = request.args.get('search_query', '').strip()
        
        # --- 2. Conexión a la Base de Datos ---
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # --- 3. Construcción de la Consulta SQL (Count y Select) ---
        select_cols = """
            SELECT
                r.id, r.No_Resguardo, r.Tipo_De_Resguardo, r.Activo,
                r.Nombre_Del_Resguardante, r.Puesto_Trabajador, r.Fecha_Resguardo,
                r.No_Trabajador, r.Nombre_Director_Jefe_De_Area,
                b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Proveedor,
                b.Descripcion_Del_Bien, b.Descripcion_Corta_Del_Bien,
                b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
                b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada,
                b.Costo_Final, b.Cantidad, b.Estado_Del_Bien,
                b.Marca, b.Modelo, b.Numero_De_Serie,
                a.nombre AS Area_Nombre
        """
        from_tables = " FROM resguardos r JOIN bienes b ON r.id_bien = b.id JOIN areas a ON r.id_area = a.id "
        
        where_clauses = []
        sql_params = []

        if control_only:
            where_clauses.append("r.Tipo_De_Resguardo = 1")
        else:
            where_clauses.append("r.Tipo_De_Resguardo = 0")
        if search_query:
            # (Tu lógica de búsqueda se mantiene aquí)
            searchable_cols = [
                'b.No_Inventario', 'b.Descripcion_Corta_Del_Bien', 'a.nombre', 
                'r.No_Resguardo', 'r.Nombre_Del_Resguardante', 'b.Proveedor'
            ]
            all_cols_clause = " OR ".join([f"{col} LIKE %s" for col in searchable_cols])
            where_clauses.append(f"({all_cols_clause})")
            sql_params.extend([f"%{search_query}%"] * len(searchable_cols))

        # --- Consulta para el conteo total de items (sin LIMIT ni OFFSET) ---
        count_query = "SELECT COUNT(*) " + from_tables
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)
        
        cursor.execute(count_query, sql_params)
        total_items = cursor.fetchone()['COUNT(*)']
        total_pages = math.ceil(total_items / limit)

        # --- Consulta para obtener los datos de la página actual ---
        final_query = select_cols + from_tables
        if where_clauses:
            final_query += " WHERE " + " AND ".join(where_clauses)
        
        final_query += " ORDER BY r.id DESC LIMIT %s OFFSET %s"
        sql_params.extend([limit, offset])

        # --- 4. Ejecución y Renderizado ---
        cursor.execute(final_query, sql_params)
        resguardos_data = cursor.fetchall()
        
        template_name = 'resguardos_list.html'
        return render_template(
            template_name,
            resguardos=resguardos_data,
            search_column=search_column,
            search_query=search_query,
            available_columns_for_search=AVAILABLE_COLUMNS,
            current_page=page,
            total_pages=total_pages, # Ahora pasamos el total de páginas
            limit=limit,
            is_sujeto_control=control_only
        )

    except Exception as e:
        traceback.print_exc()
        flash(f"Ocurrió un error al obtener los resguardos: {e}", "error")
        return render_template('resguardos_list.html', resguardos=[], available_columns_for_search=AVAILABLE_COLUMNS, current_page=1, total_pages=1, is_sujeto_control=control_only)
    finally:
        if conn:
            conn.close()

@resguardos_bp.route('/imprimir/<int:id_resguardo>')
@login_required # Es muy recomendable proteger esta ruta
def imprimir_resguardo(id_resguardo):
    """
    Obtiene los datos completos de un resguardo específico y los renderiza
    en una plantilla diseñada para la impresión.
    """
    conn = None
    try:
        # --- 1. Conexión a la Base de Datos ---
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # --- 2. Construcción de la Consulta SQL ---
        # Esta consulta es similar a la de tu lista, pero para un solo ID.
        # Une las tres tablas (resguardos, bienes, areas) para obtener toda la info.
        sql_query = """
            SELECT
                r.id, r.No_Resguardo, r.Tipo_De_Resguardo, r.Activo,
                r.Nombre_Del_Resguardante, r.Puesto_Trabajador, r.Fecha_Resguardo,
                r.No_Trabajador, r.Nombre_Director_Jefe_De_Area, r.No_Nomina_Trabajador,
                b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Proveedor,
                b.Descripcion_Del_Bien, b.Descripcion_Corta_Del_Bien,
                b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
                b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada,
                b.Costo_Final, b.Cantidad, b.Estado_Del_Bien,
                b.Marca, b.Modelo, b.Numero_De_Serie,
                a.nombre AS Area_Nombre
            FROM 
                resguardos r 
            JOIN 
                bienes b ON r.id_bien = b.id 
            JOIN 
                areas a ON r.id_area = a.id
            WHERE 
                r.id = %s
        """
        
        # --- 3. Ejecución de la Consulta ---
        cursor.execute(sql_query, (id_resguardo,))
        resguardo_data = cursor.fetchone()

        # --- 4. Manejo de Errores (Si no se encuentra el resguardo) ---
        if not resguardo_data:
            # Si no se encuentra un resguardo con ese ID, devuelve un error 404.
            abort(404, description="Resguardo no encontrado")

        # --- 5. Preparar Datos Adicionales (Responsables) ---
        # Estos datos son fijos y se pueden gestionar aquí o en un archivo de config.
        responsables = {
        }

        # --- 6. Renderizado de la Plantilla de Impresión ---
        # Se pasa el diccionario 'resguardo_data' como 'resguardo' a la plantilla
        # y se desempaquetan los responsables como variables individuales.
        return render_template(
            'imprimir_resguardo.html', 
            resguardo=resguardo_data,
            **responsables
        )

    except Exception as e:
        traceback.print_exc()
        flash(f"Ocurrió un error al generar el resguardo para impresión: {e}", "error")
        # Puedes redirigir o mostrar una página de error genérica
        return "Error al generar el documento.", 500
    finally:
        if conn:
            conn.close()





@resguardos_bp.route('/carga_masiva')
@login_required
def carga_masiva():
    """Muestra la página de ayuda para la importación masiva con Excel."""
    # Esta función simplemente renderiza la plantilla estática de ayuda.
    return render_template('resguardos/carga_masiva.html')
