# your_flask_app/routes/resguardos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify, abort
from flask_login import login_required, current_user
import os
import traceback
from database import get_db_connection, get_db_connection, AVAILABLE_COLUMNS
from decorators import permission_required
from log_activity import log_activity
import math
from pymysql.err import MySQLError
import pymysql
import pymysql.cursors
from drive_service import drive_service, BIENES_FOLDER_ID, RESGUARDOS_FOLDER_ID
import traceback
from werkzeug.utils import secure_filename
import uuid

resguardos_bp = Blueprint('resguardos', __name__)

def allowed_file(filename):
    """Función para verificar si la extensión del archivo es permitida."""
    # Se obtiene la extensión desde la configuración de la app
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS')
    if not allowed_extensions:
        # Fallback por si no está en config
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
        
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_areas_for_form():
    """Obtiene una lista de objetos de área [{id, nombre}] desde la BD."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn: return []
        cursor = cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre")
        return cursor.fetchall()
    except MySQLError as err:
        print(f"Error al obtener áreas: {err}")
        return []
    finally:
        if conn :
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

@resguardos_bp.route('/crear_resguardo', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def crear_resguardo():
    conn = None
    # Asumo que esta función existe y obtiene las áreas
    areas = get_areas_for_form() 
    
    # --- LÓGICA PARA EL MÉTODO POST (ENVIAR FORMULARIO) ---
    if request.method == 'POST':
        try:
            conn = get_db_connection()
            if not conn: 
                raise Exception("No se pudo conectar a la base de datos.")
            
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # --- CONFIGURACIÓN DE CARPETAS LOCALES ---
            base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if not base_upload_folder:
                raise Exception("UPLOAD_FOLDER no está configurado en la app.")
            
            # Definir rutas de carpetas (se crearán si no existen)
            bienes_upload_dir = os.path.join(base_upload_folder, 'bienes')
            resguardos_upload_dir = os.path.join(base_upload_folder, 'resguardos')
            os.makedirs(bienes_upload_dir, exist_ok=True)
            os.makedirs(resguardos_upload_dir, exist_ok=True)
            
            form_data = request.form
            id_bien_existente = form_data.get('id_bien_existente')
            id_bien = None
            
            if id_bien_existente:
                id_bien = id_bien_existente
            else:
                # --- 1. Crear nuevo bien ---
                sql_bien = """INSERT INTO bienes (No_Inventario, Tipo_De_Alta, No_Factura, No_Cuenta, Proveedor, Descripcion_Del_Bien, Descripcion_Corta_Del_Bien, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora, Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final, Cantidad, Estado_Del_Bien, Marca, Modelo, Numero_De_Serie, Clasificacion_Legal, usuario_id_registro, Area_Presupuestal, Documento_Propiedad, Fecha_Documento_Propiedad, Valor_En_Libros, Fecha_Adquisicion_Alta, Activo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                bien_values = (form_data.get('No_Inventario'), form_data.get('Tipo_De_Alta'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'), form_data.get('Descripcion_Corta_Del_Bien'), form_data.get('Rubro'), form_data.get('Poliza'), form_data.get('Fecha_Poliza'), form_data.get('Sub_Cuenta_Armonizadora'), form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), form_data.get('Depreciacion_Acumulada'), form_data.get('Costo_Final'), form_data.get('Cantidad'), form_data.get('Estado_Del_Bien'), form_data.get('Marca'), form_data.get('Modelo'), form_data.get('Numero_De_Serie'), form_data.get('Clasificacion_Legal'), current_user.id, form_data.get('Area_Presupuestal'), form_data.get('Documento_Propiedad'), form_data.get('Fecha_Documento_Propiedad'), form_data.get('Valor_En_Libros'), form_data.get('Fecha_Adquisicion_Alta'), 1)
                
                cursor.execute(sql_bien, bien_values)
                id_bien = cursor.lastrowid
                
                # --- 2. Guardar imágenes del bien (LOCAL) ---
                for file in request.files.getlist('imagenes_bien'):
                    # Nota: Asegúrate de tener la función 'allowed_file' importada o definida en este archivo
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}-{filename}"
                        
                        # Guardar físico
                        save_path = os.path.join(bienes_upload_dir, unique_filename)
                        file.save(save_path)
                        
                        # Guardar ruta relativa en BD
                        db_path = os.path.join('bienes', unique_filename)
                        cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", (id_bien, db_path))

            # --- 3. Crear el resguardo ---
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

            # --- 4. Guardar imágenes del resguardo (LOCAL) ---
            for file in request.files.getlist('imagenes_resguardo'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # Guardar físico en carpeta 'resguardos'
                    save_path = os.path.join(resguardos_upload_dir, unique_filename)
                    file.save(save_path)
                    
                    # Guardar ruta relativa en BD
                    db_path = os.path.join('resguardos', unique_filename)
                    # Asumiendo que tu tabla tiene 'fecha_subida'
                    cursor.execute("INSERT INTO imagenes_resguardo (id_resguardo, ruta_imagen, fecha_subida) VALUES (%s, %s, NOW())", (id_resguardo, db_path))
            
            # --- 5. Si todo salió bien, confirmar cambios ---
            conn.commit()
            log_activity(
                action='Creación de Resguardo', 
                category='Resguardos', 
                resource_id=id_resguardo, 
                details=f"Usuario '{current_user.username}' creó el resguardo No. Resguardo: {form_data.get('No_Resguardo')}"
            )
            
            # --- 6. Enviar respuesta JSON de ÉXITO ---
            return jsonify({
                "message": "Resguardo creado exitosamente.", 
                "category": "success", 
                "redirect_url": url_for('resguardos.ver_resguardos') 
            }), 200

        # --- MANEJO DE ERRORES ---
        except pymysql.MySQLError as e:
            if conn: conn.rollback()
            
            # Revisa si 'e' tiene 'args' y si el primer argumento es 1062 (Duplicate Entry)
            if e.args and e.args[0] == 1062:
                error_message = str(e)
                field = "un campo" 

                if "No_Inventario" in error_message:
                    field = f"El Número de Inventario '{form_data.get('No_Inventario')}'"
                elif "Numero_De_Serie" in error_message:
                     field = f"El Número de Serie '{form_data.get('Numero_De_Serie')}'"
                
                return jsonify({
                    "message": f"Error al guardar: {field} ya existe en la base de datos."
                }), 409 # 409 Conflict
            
            else:
                traceback.print_exc() 
                return jsonify({"message": f"Ocurrió un error de base de datos: {e}", "category": "danger"}), 500
        
        except Exception as e:
            if conn: conn.rollback()
            traceback.print_exc() 
            return jsonify({"message": f"Ocurrió un error inesperado: {e}", "category": "danger"}), 500

        finally:
            if conn : conn.close()
            
    # --- LÓGICA PARA EL MÉTODO GET ---
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
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Se obtienen los datos del bien
        cursor.execute("SELECT * FROM bienes WHERE id = %s", (id_bien,))
        bien_data = cursor.fetchone()

        if not bien_data:
            flash("Bien no encontrado.", "danger")
            return redirect(url_for('bienes.listar_bienes'))
        
        log_activity(
            action="Carga de Formulario Resguardo",
            category="Resguardos",
            resource_id=id_bien,
            details=f"Usuario '{current_user.username}' cargó el formulario para crear un resguardo para el bien No. Inventario: {bien_data.get('No_Inventario')}"
        )
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
        if conn : conn.close()


@resguardos_bp.route('/editar_resguardo/<int:id_resguardo>', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.editar_resguardo')
def editar_resguardo(id_resguardo):
    conn = None
    areas = get_areas_for_form()
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # --- 1. PREPARAR CARPETAS LOCALES ---
        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            raise Exception("UPLOAD_FOLDER no está configurado en la app.")
            
        bienes_upload_dir = os.path.join(base_upload_folder, 'bienes')
        resguardos_upload_dir = os.path.join(base_upload_folder, 'resguardos')
        
        # Crear carpetas si no existen
        os.makedirs(bienes_upload_dir, exist_ok=True)
        os.makedirs(resguardos_upload_dir, exist_ok=True)

        # --- VALIDACIÓN INICIAL ---
        sql_select_val = """
            SELECT r.*, b.*, r.id AS resguardo_id, b.id AS bien_id, a.id as Area_id 
            FROM resguardos r 
            JOIN bienes b ON r.id_bien = b.id 
            JOIN areas a ON r.id_area = a.id 
            WHERE r.id = %s AND r.Activo = 1
        """
        cursor.execute(sql_select_val, (id_resguardo,))
        resguardo_data_val = cursor.fetchone()

        if not resguardo_data_val:
            flash("El resguardo no existe o está inactivo y no puede ser editado.", "warning")
            return redirect(url_for('resguardos.ver_resguardos'))

        id_bien_val = resguardo_data_val['bien_id']

        if request.method == 'POST':
            form_data = request.form
            
            # --- VALIDACIÓN DE CONSISTENCIA ---
            id_bien_form = form_data.get('id_bien')
            if not id_bien_form or int(id_bien_form) != id_bien_val:
                flash("Error de inconsistencia de datos. No se pudo actualizar.", "danger")
                return redirect(url_for('resguardos.ver_resguardos'))

            area_id = form_data.get('Area')

            def to_null(value):
                return None if value == '' else value

            # --- Actualización del Bien ---
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
                form_data.get('Modelo'), form_data.get('Numero_De_Serie'), id_bien_val
            )
            cursor.execute(sql_update_bien, bien_values)
            
            # --- Actualización del Resguardo ---
            sql_update_resguardo = "UPDATE resguardos SET id_area=%s, No_Resguardo=%s, Tipo_De_Resguardo=%s, Fecha_Resguardo=%s, No_Trabajador=%s, No_Nomina_Trabajador=%s, Puesto_trabajador=%s, Nombre_Director_Jefe_De_Area=%s, Nombre_Del_Resguardante=%s WHERE id=%s"
            resguardo_values = (
                area_id, form_data.get('No_Resguardo'), 
                form_data.get('Tipo_De_Resguardo'), to_null(form_data.get('Fecha_Resguardo')),
                form_data.get('No_Trabajador'), to_null(form_data.get('No_Nomina_Trabajador')),
                form_data.get('Puesto_Trabajador'), form_data.get('Nombre_Director_Jefe_De_Area'),
                form_data.get('Nombre_Del_Resguardante'), id_resguardo
            )
            cursor.execute(sql_update_resguardo, resguardo_values)
            
            # --- MANEJO DE IMÁGENES LOCAL ---

            # A) Eliminar imágenes de BIENES
            for img_id in request.form.getlist('eliminar_imagen_bien[]'):
                cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id = %s", (img_id,))
                imagen = cursor.fetchone()
                if imagen and imagen['ruta_imagen']:
                    # Construir ruta física
                    full_path = os.path.join(base_upload_folder, imagen['ruta_imagen'])
                    try:
                        if os.path.exists(full_path):
                            os.remove(full_path)
                        cursor.execute("DELETE FROM imagenes_bien WHERE id = %s", (img_id,))
                    except Exception as e:
                        # Loguear error pero no detener transacción crítica
                        print(f"Error borrando imagen local bien: {e}")

            # B) Eliminar imágenes de RESGUARDOS
            for img_id in request.form.getlist('eliminar_imagen_resguardo[]'):
                cursor.execute("SELECT ruta_imagen FROM imagenes_resguardo WHERE id = %s", (img_id,))
                imagen = cursor.fetchone()
                if imagen and imagen['ruta_imagen']:
                    full_path = os.path.join(base_upload_folder, imagen['ruta_imagen'])
                    try:
                        if os.path.exists(full_path):
                            os.remove(full_path)
                        cursor.execute("DELETE FROM imagenes_resguardo WHERE id = %s", (img_id,))
                    except Exception as e:
                        print(f"Error borrando imagen local resguardo: {e}")
            
            # C) Subir nuevas imágenes de BIENES
            for file in request.files.getlist('imagenes_bien'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # Guardar físico
                    save_path = os.path.join(bienes_upload_dir, unique_filename)
                    file.save(save_path)
                    
                    # Guardar ruta relativa en BD
                    db_path = os.path.join('bienes', unique_filename)
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", (id_bien_val, db_path))

            # D) Subir nuevas imágenes de RESGUARDOS
            for file in request.files.getlist('imagenes_resguardo'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # Guardar físico
                    save_path = os.path.join(resguardos_upload_dir, unique_filename)
                    file.save(save_path)
                    
                    # Guardar ruta relativa en BD
                    db_path = os.path.join('resguardos', unique_filename)
                    cursor.execute("INSERT INTO imagenes_resguardo (id_resguardo, ruta_imagen) VALUES (%s, %s)", (id_resguardo, db_path))

            conn.commit()
            log_activity(
                action='Edición de Resguardo', 
                category='Resguardos', 
                resource_id=id_resguardo, 
                details=f"Usuario '{current_user.username}' editó el resguardo No. Resguardo {form_data.get('No_Resguardo')}"
            )
            flash('Resguardo actualizado exitosamente.', 'success')

            return jsonify({
                'success': True,
                'redirect_url': url_for('resguardos.ver_resguardos')
            })

        # --- Lógica GET ---
        if not resguardo_data_val: abort(404)

        cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (resguardo_data_val['bien_id'],))
        imagenes_bien_db = cursor.fetchall()
        cursor.execute("SELECT id, ruta_imagen FROM imagenes_resguardo WHERE id_resguardo = %s", (resguardo_data_val['resguardo_id'],))
        imagenes_resguardo_db = cursor.fetchall()
        
        return render_template('resguardos/resguardo_form.html', is_edit=True, form_data=resguardo_data_val, areas=areas, imagenes_bien_db=imagenes_bien_db, imagenes_resguardo_db=imagenes_resguardo_db)

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al editar el resguardo: {e}", 'danger')
        traceback.print_exc()
        
        # Fallback data on error
        form_data_on_error = request.form.to_dict()
        form_data_on_error['resguardo_id'] = id_resguardo
        form_data_on_error['bien_id'] = request.form.get('id_bien', id_bien_val)
        
        imagenes_bien_db, imagenes_resguardo_db = [], []
        
        # Intento de recuperación de imágenes para no mostrar vacío en caso de error
        try:
            # Reconexión si se perdió
            if not conn or not conn.open:
                conn = get_db_connection()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (id_bien_val,))
            imagenes_bien_db = cursor.fetchall()
            cursor.execute("SELECT id, ruta_imagen FROM imagenes_resguardo WHERE id_resguardo = %s", (id_resguardo,))
            imagenes_resguardo_db = cursor.fetchall()
        except:
            pass

        return render_template('resguardos/resguardo_form.html', 
                               is_edit=True, 
                               form_data=form_data_on_error, 
                               areas=areas,
                               imagenes_bien_db=imagenes_bien_db,
                               imagenes_resguardo_db=imagenes_resguardo_db)
    finally:
        if conn : conn.close()

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
        cursor = conn.cursor(pymysql.cursors.DictCursor) 
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
    except pymysql.MySQLError as err:
        flash(f"Error de base de datos: {err}", "danger")
        return redirect(url_for('resguardos.ver_resguardos'))
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", "danger")
        traceback.print_exc()
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn:
            cursor.close()
            conn.close()

# It's good practice to have a helper function to get areas
def get_areas_list_from_db():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT DISTINCT nombre FROM areas ORDER BY nombre")
        areas = [row['nombre'] for row in cursor.fetchall()]
        return areas
    except Exception as e:
        print(f"Error fetching areas from DB: {e}")
        return []
    finally:
        if conn:
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
        log_activity(
            action='Eliminación de Resguardo', 
            category='Resguardos', 
            resource_id=id, 
            details=f"Usuario '{current_user.username}' eliminó el resguardo y bien asociado, ID resguardo: {id}"
        )
        flash("Resguardo eliminado correctamente.", 'success')
    except MySQLError as err:
        flash(f"Error al eliminar resguardo: {err}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index'))

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
        cursor = conn.cursor(pymysql.cursors.DictCursor)

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
        cursor = conn.cursor(pymysql.cursors.DictCursor)
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
