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
        
        # --- CAMBIO: Se añaden más columnas para mostrar en la lista ---
        select_base = """
            SELECT 
                b.id, b.No_Inventario, b.Descripcion_Corta_Del_Bien, b.Estado_Del_Bien,
                b.Marca, b.Modelo, b.Clasificacion_Legal, b.Valor_En_Libros,
                r.id AS resguardo_id, a.nombre AS Area_Nombre, r.Nombre_Del_Resguardante,
                (CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END) AS tiene_resguardo
        """
        from_base = "FROM bienes b LEFT JOIN resguardos r ON b.id = r.id_bien AND r.Activo = 1 LEFT JOIN areas a ON r.id_area = a.id"
        
        where_clause = ""
        params = []
        if search_query:
            # --- CAMBIO: Se amplía la búsqueda a más campos útiles ---
            searchable_fields = [
                'b.No_Inventario', 'b.Descripcion_Corta_Del_Bien', 'b.Marca', 
                'b.Modelo', 'b.Numero_De_Serie', 'b.Clasificacion_Legal', 
                'r.Nombre_Del_Resguardante', 'a.nombre'
            ]
            where_clause = " WHERE " + " OR ".join([f"{field} LIKE %s" for field in searchable_fields])
            params.extend([f"%{search_query}%"] * len(searchable_fields))
            
        count_query = f"SELECT COUNT(DISTINCT b.id) AS total {from_base} {where_clause}"
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()['total']
        total_pages = math.ceil(total_items / items_per_page)

        # Se añaden los parámetros de paginación después del conteo
        final_params = params + [items_per_page, offset]

        sql_query = f"""
            {select_base}
            {from_base}
            {where_clause}
            GROUP BY b.id
            ORDER BY b.id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(sql_query, tuple(final_params))
        bienes_data = cursor.fetchall()
        
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

            # --- CAMBIO: Se añade 'Activo' a la lista de columnas ---
            sql = """
                INSERT INTO bienes (
                    No_Inventario, No_Factura, No_Cuenta, Proveedor, Descripcion_Del_Bien,
                    Descripcion_Corta_Del_Bien, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora,
                    Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final, Cantidad,
                    Estado_Del_Bien, Marca, Modelo, Numero_De_Serie, Tipo_De_Alta,
                    Clasificacion_Legal, usuario_id_registro, Area_Presupuestal, Documento_Propiedad,
                    Fecha_Documento_Propiedad, Valor_En_Libros, Fecha_Adquisicion_Alta, Activo
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'),
                form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'),
                form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'),
                form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'),
                form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final'), form_data.get('Cantidad'),
                form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'),
                form_data.get('Numero_De_Serie'), form_data.get('Tipo_De_Alta'),
                form_data.get('Clasificacion_Legal'),
                current_user.id,
                form_data.get('Area_Presupuestal'),
                form_data.get('Documento_Propiedad'),
                form_data.get('Fecha_Documento_Propiedad') or None,
                form_data.get('Valor_En_Libros'),
                form_data.get('Fecha_Adquisicion_Alta') or None,
                1  # Se añade el valor 1 (TRUE) para el campo Activo
            )
            cursor.execute(sql, values)
            id_bien = cursor.lastrowid

            # --- 📸 LÓGICA DE IMÁGENES (INTACTA) ---
            # Esta parte del código no se modificó y sigue funcionando.
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
            return render_template('bienes/bien_form.html', is_edit=False, form_data=request.form)
        finally:
            if conn and conn.is_connected(): conn.close()
            
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
            print(form_data)
            # --- CAMBIO: Se añaden los nuevos campos a la consulta UPDATE ---
            sql = """
                UPDATE bienes SET 
                    No_Inventario=%s, No_Factura=%s, No_Cuenta=%s, Proveedor=%s, Descripcion_Del_Bien=%s, 
                    Descripcion_Corta_Del_Bien=%s, Rubro=%s, Poliza=%s, Fecha_Poliza=%s, 
                    Sub_Cuenta_Armonizadora=%s, Fecha_Factura=%s, Costo_Inicial=%s, Depreciacion_Acumulada=%s, 
                    Costo_Final=%s, Cantidad=%s, Estado_Del_Bien=%s, Marca=%s, Modelo=%s, 
                    Numero_De_Serie=%s, Tipo_De_Alta=%s, Clasificacion_Legal=%s, Area_Presupuestal=%s, 
                    Documento_Propiedad=%s, Fecha_Documento_Propiedad=%s, Valor_En_Libros=%s, 
                    Fecha_Adquisicion_Alta=%s 
                WHERE id=%s
            """
            
            # --- CAMBIO: Se añaden los valores de los nuevos campos al tuple ---
            values = (
                form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), 
                form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'), 
                form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'), 
                form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), 
                form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final'), form_data.get('Cantidad'), 
                form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'), 
                form_data.get('Numero_De_Serie'), form_data.get('Tipo_De_Alta'),
                # Nuevos campos
                form_data.get('Clasificacion_Legal'),
                form_data.get('Area_Presupuestal'),
                form_data.get('Documento_Propiedad'),
                form_data.get('Fecha_Documento_Propiedad') or None,
                form_data.get('Valor_En_Libros'),
                form_data.get('Fecha_Adquisicion_Alta') or None,
                # ID del bien al final para el WHERE
                bien_id
            )
            cursor.execute(sql, values)
            print(request.form.getlist('imagenes_bien'))
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

        # Lógica GET (sin cambios necesarios aquí, SELECT * ya trae los nuevos campos)
        cursor.execute("SELECT * FROM bienes WHERE id = %s", (bien_id,))
        bien = cursor.fetchone()
        if not bien:
            abort(404)
        
        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (bien_id,))
        bien['imagenes'] = cursor.fetchall()
        print(bien['imagenes'])
        cursor.execute("SELECT * FROM resguardos WHERE id_bien = %s ORDER BY Fecha_Registro DESC", (bien_id,))
        bien['resguardos'] = cursor.fetchall()
        print(bien)
        return render_template('bienes/bien_form.html', is_edit=True, bien=bien)
        
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
        
        # --- CAMBIO: Se une con la tabla 'user' para obtener el nombre del usuario ---
        sql_bien = """
            SELECT 
                b.*, 
                u.username AS registrado_por_nombre 
            FROM bienes b
            JOIN user u ON b.usuario_id_registro = u.id
            WHERE b.id = %s
        """
        cursor.execute(sql_bien, (bien_id,))
        bien = cursor.fetchone()
        
        if not bien:
            abort(404)
        
        # El resto de la función sigue exactamente igual
        cursor.execute("SELECT r.*, a.nombre as Area_Nombre FROM resguardos r JOIN areas a ON r.id_area = a.id WHERE r.id_bien = %s", (bien_id,))
        resguardos = cursor.fetchall()
        
        cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (bien_id,))
        imagenes = [row['ruta_imagen'] for row in cursor.fetchall()]
   

        sql_historial = """
            SELECT 
                d.id AS detalle_id,
                i.id AS inventario_id,
                i.nombre AS inventario_nombre,
                i.fecha_inicio,
                uc.username AS creador_nombre,
                r.Nombre_Del_Resguardante,
                r.Nombre_Director_Jefe_De_Area
            FROM inventario_detalle d
            JOIN inventarios i ON d.id_inventario = i.id
            JOIN user uc ON i.id_usuario_creador = uc.id
            LEFT JOIN resguardos r ON d.id_resguardo_esperado = r.id
            WHERE d.id_bien = %s
            ORDER BY i.fecha_inicio DESC
        """
        cursor.execute(sql_historial, (bien_id,))
        historial_inventarios = cursor.fetchall()
        print(historial_inventarios)
        brigadas_por_inventario = {}
        fotos_por_detalle = {}

        if historial_inventarios:
            # Obtener todos los IDs necesarios para consultas secundarias eficientes
            inventario_ids = list({h['inventario_id'] for h in historial_inventarios})
            detalle_ids = [h['detalle_id'] for h in historial_inventarios]
            
            # 1. Obtener todas las brigadas de los inventarios involucrados
            format_strings = ','.join(['%s'] * len(inventario_ids))
            sql_brigadas = f"""
                SELECT ib.inventario_id, u.username 
                FROM inventario_brigadas ib JOIN user u ON ib.user_id = u.id 
                WHERE ib.inventario_id IN ({format_strings})
            """
            cursor.execute(sql_brigadas, tuple(inventario_ids))
            for row in cursor.fetchall():
                inv_id = row['inventario_id']
                if inv_id not in brigadas_por_inventario:
                    brigadas_por_inventario[inv_id] = []
                brigadas_por_inventario[inv_id].append(row['username'])

            # 2. Obtener todas las fotos de los detalles de inventario involucrados
            format_strings = ','.join(['%s'] * len(detalle_ids))
            sql_fotos = f"SELECT id_inventario_detalle, ruta_archivo FROM inventario_fotos WHERE id_inventario_detalle IN ({format_strings})"
            cursor.execute(sql_fotos, tuple(detalle_ids))
            for row in cursor.fetchall():
                det_id = row['id_inventario_detalle']
                if det_id not in fotos_por_detalle:
                    fotos_por_detalle[det_id] = []
                fotos_por_detalle[det_id].append(row['ruta_archivo'])
            print(historial_inventarios)
        return render_template('bienes/detalles_bien.html', bien=bien, 
            resguardos=resguardos, 
            imagenes=imagenes,
            historial_inventarios=historial_inventarios,
            brigadas_por_inventario=brigadas_por_inventario,
            fotos_por_detalle=fotos_por_detalle)
        
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

