from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import uuid
import os
import traceback
import math
import mysql.connector

# Se importan las funciones y variables de tus otros archivos
from database import get_db_connection
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from decorators import permission_required
from log_activity import log_activity

bienes_bp = Blueprint('bienes', __name__)

def allowed_file(filename):
    """Función para verificar si la extensión del archivo es permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bienes_bp.route('/bienes')
@login_required
@permission_required('bienes.listar_bienes')
def listar_bienes():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        page = request.args.get('page', 1, type=int)
        items_per_page = 100
        offset = (page - 1) * items_per_page
        search_query = request.args.get('search_query', '').strip()
        
        # La consulta ahora solo se une con el resguardo ACTIVO para evitar duplicados
        count_base_query = "FROM bienes b LEFT JOIN resguardos r ON b.id = r.id_bien AND r.Activo = 1 LEFT JOIN areas a ON r.id_area = a.id"
        
        where_clause = ""
        params = []
        if search_query:
            where_clause = " WHERE b.No_Inventario LIKE %s OR b.Descripcion_Corta_Del_Bien LIKE %s OR r.Nombre_Del_Resguardante LIKE %s"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
            
        count_query = "SELECT COUNT(DISTINCT b.id) AS total " + count_base_query + where_clause
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()['total']
        total_pages = math.ceil(total_items / items_per_page)

        sql_query = f"""
            SELECT 
                b.id, b.No_Inventario, b.Descripcion_Corta_Del_Bien, b.Estado_Del_Bien,
                r.id AS resguardo_id, a.nombre AS Area_Nombre,
                (CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END) AS tiene_resguardo
            {count_base_query}
            {where_clause}
            GROUP BY b.id
            ORDER BY b.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([items_per_page, offset])
        cursor.execute(sql_query, tuple(params))
        bienes_data = cursor.fetchall()
        
        # CORRECCIÓN: Se pasa 'page' en lugar de 'current_page' para que coincida con la plantilla.
        return render_template(
            'bienes/listar_bienes.html', 
            bienes=bienes_data, 
            page=page, 
            total_pages=total_pages,
            search_query=search_query
        )
        
    except Exception as err:
        flash(f"Error al obtener los bienes: {err}", 'danger')
        traceback.print_exc()
        # CORRECCIÓN: Se pasan todas las variables que la plantilla necesita, incluso en caso de error.
        return render_template(
            'bienes/listar_bienes.html', 
            bienes=[], 
            page=1, 
            total_pages=1,
            search_query=""
        )
    finally:
        if conn and conn.is_connected():
            conn.close()

@bienes_bp.route('/bienes/agregar', methods=['GET', 'POST'])
@login_required
@permission_required('bienes.agregar_bien')
def agregar_bien():
    if request.method == 'POST':
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            form_data = request.form

            sql = """INSERT INTO bienes (No_Inventario, No_Factura, No_Cuenta, Proveedor, Descripcion_Del_Bien, Descripcion_Corta_Del_Bien, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora, Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final_Cantidad, Cantidad, Estado_Del_Bien, Marca, Modelo, Numero_De_Serie, Tipo_De_Alta) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            values = (form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'), form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'), form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final_Cantidad'), form_data.get('Cantidad'), form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'), form_data.get('Numero_De_Serie'), form_data.get('Tipo_De_Alta'))
            cursor.execute(sql, values)
            id_bien = cursor.lastrowid

            for file in request.files.getlist('imagenes_bien'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", (id_bien, unique_filename))

            conn.commit()
            log_activity(action="Creación de Bien", category="Bienes", resource_id=id_bien, details=f"Se creó el bien: {form_data.get('No_Inventario')}")
            flash('Bien agregado exitosamente.', 'success')
            return redirect(url_for('bienes.listar_bienes'))

        except Exception as e:
            if conn: conn.rollback()
            flash(f'Error al agregar el bien: {e}', 'danger')
            traceback.print_exc()
            # Se devuelve el formulario con los datos que el usuario ya había ingresado
            return render_template('bienes/bien_form.html', is_edit=False, form_data=request.form)
        finally:
            if conn and conn.is_connected(): conn.close()
            
    # Para el método GET, se muestra el formulario vacío
    return render_template('bienes/bien_form.html', is_edit=False, form_data={})

@bienes_bp.route('/bienes/editar/<int:bien_id>', methods=['GET', 'POST'])
@login_required
@permission_required('bienes.editar_bien')
def editar_bien(bien_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            form_data = request.form
            sql = """UPDATE bienes SET No_Inventario=%s, No_Factura=%s, No_Cuenta=%s, Proveedor=%s, Descripcion_Del_Bien=%s, Descripcion_Corta_Del_Bien=%s, Rubro=%s, Poliza=%s, Fecha_Poliza=%s, Sub_Cuenta_Armonizadora=%s, Fecha_Factura=%s, Costo_Inicial=%s, Depreciacion_Acumulada=%s, Costo_Final_Cantidad=%s, Cantidad=%s, Estado_Del_Bien=%s, Marca=%s, Modelo=%s, Numero_De_Serie=%s, Tipo_De_Alta=%s WHERE id=%s"""
            values = (form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'), form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'), form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final_Cantidad'), form_data.get('Cantidad'), form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'), form_data.get('Numero_De_Serie'), form_data.get('Tipo_De_Alta'), bien_id)
            cursor.execute(sql, values)
            
            for img_id in request.form.getlist('eliminar_imagen_bien[]'):
                cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id = %s AND id_bien = %s", (img_id, bien_id))
                imagen = cursor.fetchone()
                if imagen:
                    try:
                        os.remove(os.path.join(UPLOAD_FOLDER, imagen['ruta_imagen']))
                    except OSError:
                        pass
                    cursor.execute("DELETE FROM imagenes_bien WHERE id = %s", (img_id,))

            for file in request.files.getlist('imagenes_bien'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", (bien_id, unique_filename))

            conn.commit()
            log_activity(action="Edición de Bien", category="Bienes", resource_id=bien_id, details=f"Se editó el bien: {form_data.get('No_Inventario')}")
            flash('Bien actualizado exitosamente.', 'success')
            return redirect(url_for('bienes.listar_bienes'))

        # Lógica GET para mostrar el formulario con datos existentes
        cursor.execute("SELECT * FROM bienes WHERE id = %s", (bien_id,))
        bien = cursor.fetchone()
        if not bien:
            abort(404)
        
        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (bien_id,))
        bien['imagenes'] = cursor.fetchall()

        # --- CORRECCIÓN CLAVE ---
        # Se añade la consulta para obtener los resguardos asociados al bien.
        cursor.execute("SELECT * FROM resguardos WHERE id_bien = %s ORDER BY Fecha_Registro DESC", (bien_id,))
        bien['resguardos'] = cursor.fetchall()

        return render_template('bienes/bien_form.html', is_edit=True, form_data=bien)
        
    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al actualizar el bien: {e}', 'danger')
        traceback.print_exc()
        return redirect(url_for('bienes.listar_bienes'))
    finally:
        if conn and conn.is_connected(): conn.close()


@bienes_bp.route('/bienes/eliminar/<int:bien_id>', methods=['POST'])
@login_required
@permission_required('bienes.eliminar_bien')
def eliminar_bien(bien_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT No_Inventario FROM bienes WHERE id = %s", (bien_id,))
        bien = cursor.fetchone()
        
        cursor.execute("DELETE FROM bienes WHERE id = %s", (bien_id,))
        conn.commit()
        
        if bien:
            log_activity(action="Eliminación de Bien", category="Bienes", resource_id=bien_id, details=f"Se eliminó el bien: {bien['No_Inventario']}")
        
        flash('Bien eliminado exitosamente.', 'success')
    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al eliminar el bien: {e}', 'danger')
    finally:
        if conn and conn.is_connected(): conn.close()
        
    return redirect(url_for('bienes.listar_bienes'))

@bienes_bp.route('/bienes/detalles/<int:bien_id>')
@login_required
@permission_required('bienes.ver_detalles_bien')
def ver_detalles_bien(bien_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM bienes WHERE id = %s", (bien_id,))
        bien = cursor.fetchone()
        if not bien:
            abort(404)
        
        cursor.execute("SELECT r.*, a.nombre as Area_Nombre FROM resguardos r JOIN areas a ON r.id_area = a.id WHERE r.id_bien = %s", (bien_id,))
        resguardos = cursor.fetchall()
        
        cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (bien_id,))
        imagenes = [row['ruta_imagen'] for row in cursor.fetchall()]

        return render_template('bienes/detalles_bien.html', bien=bien, resguardos=resguardos, imagenes=imagenes)
        
    except Exception as e:
        flash(f'Error al ver los detalles del bien: {e}', 'danger')
        return redirect(url_for('bienes.listar_bienes'))
    finally:
        if conn and conn.is_connected():
            conn.close()

# Ruta para servir imágenes (necesaria para mostrarlas en las plantillas)
@bienes_bp.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

