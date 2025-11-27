from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import uuid
import os
import traceback
import math
import pymysql
import pymysql.cursors

# Se importan las funciones y variables de tus otros archivos
from database import get_db_connection
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from decorators import permission_required
from log_activity import log_activity
from drive_service import (
    drive_service, 
    BIENES_FOLDER_ID, 
)

bienes_bp = Blueprint('bienes', __name__)

def allowed_file(filename):
    """Función para verificar si la extensión del archivo es permitida."""
    # Se obtiene la extensión desde la configuración de la app
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS')
    if not allowed_extensions:
        # Fallback por si no está en config
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
        
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@bienes_bp.route('/bienes')
@login_required
@permission_required('bienes.listar_bienes')
def listar_bienes():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        # CORRECCIÓN: PyMySQL usa DictCursor, no dictionary=True
        cursor = conn.cursor(pymysql.cursors.DictCursor)

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
        # CORRECCIÓN: PyMySQL no tiene is_connected, solo verifica si existe
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@bienes_bp.route('/bienes/agregar', methods=['GET', 'POST'])
@login_required
@permission_required('bienes.agregar_bien')
def agregar_bien():
    if request.method == 'POST':
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor) 
            form_data = request.form

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
                1 
            )
            cursor.execute(sql, values)
            id_bien = cursor.lastrowid

            # --- 📸 LÓGICA DE IMÁGENES (ACTUALIZADA A LOCAL) ---
            
            # 1. Definir la carpeta base de subidas desde la config
            base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if not base_upload_folder:
                raise Exception("UPLOAD_FOLDER no está configurado en la app.")

            # 2. Crear la subcarpeta específica para 'bienes'
            bienes_upload_dir = os.path.join(base_upload_folder, 'bienes')
            os.makedirs(bienes_upload_dir, exist_ok=True)

            for file in request.files.getlist('imagenes_bien'):
                if file and file.filename and allowed_file(file.filename):
                    
                    # 3. Crear un nombre de archivo único
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # 4. Crear la ruta de guardado absoluta
                    save_path = os.path.join(bienes_upload_dir, unique_filename)
                    
                    # 5. Guardar el archivo en el disco
                    file.save(save_path)
                    
                    # 6. Crear la ruta relativa para la base de datos
                    # (ej: 'bienes/mi-archivo-uuid.jpg')
                    db_path = os.path.join('bienes', unique_filename)
                    
                    # 7. Guardar la ruta relativa en la DB
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", 
                                   (id_bien, db_path))

            conn.commit()
            log_activity(
                action="Creación de Bien", 
                category="Bienes", 
                resource_id=id_bien, 
                details=f"Usuario '{current_user.username}' creó el bien: {form_data.get('No_Inventario')}"
            )
            flash('Bien agregado exitosamente.', 'success')
            return redirect(url_for('bienes.listar_bienes'))

        except Exception as e:
            if conn: conn.rollback()
            flash(f'Error al agregar el bien: {e}', 'danger')
            traceback.print_exc()
            return render_template('bienes/bien_form.html', is_edit=False, form_data=request.form)
        finally:
            if conn : conn.close()
            
    return render_template('bienes/bien_form.html', is_edit=False, form_data={})

@bienes_bp.route('/bienes/editar/<int:bien_id>', methods=['GET', 'POST'])
@login_required
@permission_required('bienes.editar_bien')
def editar_bien(bien_id):
    conn = None
    cursor = None  
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # --- PREPARACIÓN DE CARPETAS LOCALES ---
        # 1. Obtener la carpeta base de subidas desde la config
        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            raise Exception("UPLOAD_FOLDER no está configurado en la app.")
        
        # 2. Definir y crear la subcarpeta 'bienes' si no existe
        bienes_upload_dir = os.path.join(base_upload_folder, 'bienes')
        os.makedirs(bienes_upload_dir, exist_ok=True)

        # ==================================
        # LÓGICA POST
        # ==================================
        if request.method == 'POST':
            form_data = request.form
            
            # --- UPDATE DATOS DEL BIEN (Sin cambios) ---
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
            values = (
                form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), 
                form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'), 
                form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'), 
                form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), 
                form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final'), form_data.get('Cantidad'), 
                form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'), 
                form_data.get('Numero_De_Serie'), form_data.get('Tipo_De_Alta'),
                form_data.get('Clasificacion_Legal'),
                form_data.get('Area_Presupuestal'),
                form_data.get('Documento_Propiedad'),
                form_data.get('Fecha_Documento_Propiedad') or None,
                form_data.get('Valor_En_Libros'),
                form_data.get('Fecha_Adquisicion_Alta') or None,
                bien_id
            )
            cursor.execute(sql, values)
            
            # --- Lógica para ELIMINAR imágenes (LOCAL) ---
            for img_id in request.form.getlist('eliminar_imagen_bien[]'):
                cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id = %s AND id_bien = %s", (img_id, bien_id))
                imagen = cursor.fetchone()
                
                if imagen and imagen['ruta_imagen']:
                    # Construir la ruta absoluta del archivo a borrar
                    # imagen['ruta_imagen'] trae algo como "bienes/foto.jpg"
                    full_path_to_delete = os.path.join(base_upload_folder, imagen['ruta_imagen'])
                    
                    try:
                        # 1. Borrar el archivo físico si existe
                        if os.path.exists(full_path_to_delete):
                            os.remove(full_path_to_delete)
                        
                        # 2. Borrar registro de la BD
                        cursor.execute("DELETE FROM imagenes_bien WHERE id = %s", (img_id,))
                    
                    except Exception as e:
                        flash(f"Error al borrar archivo físico: {e}", "warning")
                else:
                    flash(f"No se encontró el registro de imagen {img_id}.", "warning")

            # --- Lógica para AÑADIR nuevas imágenes (LOCAL) ---
            for file in request.files.getlist('imagenes_bien'):
                if file and file.filename and allowed_file(file.filename):
                    
                    # 1. Generar nombre único
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # 2. Definir ruta absoluta para guardar
                    save_path = os.path.join(bienes_upload_dir, unique_filename)
                    
                    # 3. Guardar archivo
                    file.save(save_path)
                    
                    # 4. Definir ruta relativa para la BD (ej: 'bienes/foto.jpg')
                    db_path = os.path.join('bienes', unique_filename)
                    
                    # 5. Insertar en BD
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", 
                                   (bien_id, db_path))

            conn.commit()
            log_activity(
                action="Edición de Bien", 
                category="Bienes", 
                resource_id=bien_id, 
                details=f"Usuario '{current_user.username}' editó el bien: {form_data.get('No_Inventario')}"
            )
            flash('Bien actualizado exitosamente.', 'success')
            return redirect(url_for('bienes.listar_bienes'))

        # ==================================
        # LÓGICA GET
        # ==================================
        
        cursor.execute("SELECT * FROM bienes WHERE id = %s", (bien_id,))
        bien = cursor.fetchone()
        
        if not bien:
            abort(404)
        
        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (bien_id,))
        bien['imagenes'] = cursor.fetchall()
        
        cursor.execute("SELECT * FROM resguardos WHERE id_bien = %s ORDER BY Fecha_Registro DESC", (bien_id,))
        bien['resguardos'] = cursor.fetchall()
        
        return render_template('bienes/bien_form.html', is_edit=True, bien=bien)
        
    except Exception as e:
        if conn: 
            conn.rollback() 
        flash(f'Error al procesar la solicitud: {e}', 'danger')
        traceback.print_exc() 
        return redirect(url_for('bienes.listar_bienes'))
    
    finally:
        if cursor:
            cursor.close()
        if conn: 
            conn.close()

@bienes_bp.route('/bienes/eliminar/<int:bien_id>', methods=['POST'])
@login_required
@permission_required('bienes.eliminar_bien')
def eliminar_bien(bien_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # 1. Obtener el nombre del bien para los mensajes y verificar que existe
        cursor.execute("SELECT No_Inventario FROM bienes WHERE id = %s", (bien_id,))
        bien = cursor.fetchone()
        
        if not bien:
            flash("Error: El bien que intenta eliminar no existe.", 'danger')
            return redirect(url_for('bienes.listar_bienes'))

        # --- ¡NUEVA VALIDACIÓN AÑADIDA! ---
        # 2. Contar cuántos resguardos (activos o inactivos) están ligados a este bien
        cursor.execute("SELECT COUNT(*) AS total FROM resguardos WHERE id_bien = %s", (bien_id,))
        resguardo_count = cursor.fetchone()['total']

        # 3. Si el conteo es mayor a 0, bloquear la eliminación
        if resguardo_count > 0:
            flash(f"Error: No se puede eliminar el bien '{bien['No_Inventario']}'. Tiene {resguardo_count} resguardo(s) históricos asociados.", 'danger')
            return redirect(url_for('bienes.listar_bienes'))
        # --- FIN DE LA VALIDACIÓN ---

        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (bien_id,))
        imagenes = cursor.fetchall()
        
        if imagenes:
            print(f"Eliminando {len(imagenes)} imágenes de Drive para el bien {bien_id}...")
            for img in imagenes:
                if img['ruta_imagen']:
                    # 4a. Borrar de Google Drive
                    drive_service.delete(img['ruta_imagen'])
                
                # 4b. Borrar de la tabla 'imagenes_bien'
                cursor.execute("DELETE FROM imagenes_bien WHERE id = %s", (img['id'],))

        # 5. Ahora sí, proceder con la eliminación del 'bien'
        cursor.execute("DELETE FROM bienes WHERE id = %s", (bien_id,))
        conn.commit()
        
        # 5. Registrar la eliminación exitosa
        log_activity(
            action="Eliminación de Bien", 
            category="Bienes", 
            resource_id=bien_id, 
            details=f"Usuario '{current_user.username}' eliminó el bien sin resguardo: {bien['No_Inventario']}"
        )
        flash('Bien eliminado exitosamente (no tenía resguardos asociados).', 'success')

    except Exception as e:
        if conn: conn.rollback()
        # Captura genérica por si otra tabla (ej. inventarios, bajas) tiene una FK
        if '1451' in str(e): # Error 1451 es "Cannot delete or update a parent row: a foreign key constraint fails"
             flash(f"Error: No se puede eliminar el bien '{bien['No_Inventario']}', está referenciado en otro módulo (ej. inventarios, procesos de baja).", 'danger')
        else:
            flash(f'Error al eliminar el bien: {e}', 'danger')
    finally:
        if conn: conn.close()
        
    return redirect(url_for('bienes.listar_bienes'))

@bienes_bp.route('/bienes/detalles/<int:bien_id>')
@login_required
@permission_required('bienes.ver_detalles_bien')
def ver_detalles_bien(bien_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        
        # --- CAMBIO: Se une con la tabla 'user' para obtener el nombre del usuario ---
        sql_bien = """
            SELECT 
                b.*, 
                u.username AS registrado_por_username,
                u.nombres AS registrado_por_nombres
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
                i.tipo AS inventario_tipo,          -- ✅ LÍNEA AÑADIDA
                i.fecha_inicio,
                uc.username AS creador_username,
                uc.nombres AS creador_nombres,
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
                SELECT ib.inventario_id, u.username, u.nombres
                FROM inventario_brigadas ib JOIN user u ON ib.user_id = u.id 
                WHERE ib.inventario_id IN ({format_strings})
            """
            cursor.execute(sql_brigadas, tuple(inventario_ids))
            for row in cursor.fetchall():
                inv_id = row['inventario_id']
                if inv_id not in brigadas_por_inventario:
                    brigadas_por_inventario[inv_id] = []
                # Guardamos un diccionario con ambos datos para usarlo en la plantilla
                brigadas_por_inventario[inv_id].append({
                    'username': row['username'],
                    'nombres': row['nombres']
                })
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
        if conn:
            conn.close()

