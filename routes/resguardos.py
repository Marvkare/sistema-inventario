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
resguardos_bp = Blueprint('resguardos', __name__)

def get_areas_data():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, Nombre FROM areas ORDER BY Nombre")
        areas = cursor.fetchall()
        return {area['Nombre']: area['id'] for area in areas}
    except mysql.connector.Error as err:
        print(f"Error al obtener áreas: {err}")
        return {}
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()




@resguardos_bp.route('/crear_resguardo', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def crear_resguardo():
    conn = None
    cursor = None
    
    # Obtiene los datos de las áreas para el formulario, mapeando nombre a ID.
    areas_data = get_areas_data()
    areas_list = list(areas_data.keys())
    
    form_data = {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if request.method == 'POST':
            form_data = request.form.to_dict()

            area_name = form_data.get('Area')
            area_id = areas_data.get(area_name)
            
            if not area_id:
                return jsonify({"message": "Área seleccionada no válida.", "category": "danger"}), 400

            # 1. Insertar los datos del bien en la tabla 'bienes'
            sql_insert_bien = """
                INSERT INTO bienes (No_Inventario, No_Factura, No_Cuenta, No_Resguardo, Proveedor, Descripcion_Del_Bien, 
                                    Descripcion_Corta_Del_Bien, Area, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora, 
                                    Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final_Cantidad, Cantidad, 
                                    Estado_Del_Bien, Marca, Modelo, Numero_De_Serie)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            bien_values = (
                form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), 
                form_data.get('No_Resguardo'), form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'),
                form_data.get('Descripcion_Corta_Del_Bien'), area_name, form_data.get('Rubro'),
                form_data.get('Poliza'), form_data.get('Fecha_Poliza'), form_data.get('Sub_Cuenta_Armonizadora'),
                form_data.get('Fecha_Factura'), form_data.get('Costo_Inicial'), form_data.get('Depreciacion_Acumulada'),
                form_data.get('Costo_Final_Cantidad'), form_data.get('Cantidad'), form_data.get('Estado_Del_Bien'), 
                form_data.get('Marca'), form_data.get('Modelo'), form_data.get('Numero_De_Serie')
            )
            
            cursor.execute(sql_insert_bien, bien_values)
            id_bien = cursor.lastrowid
            
            # 2. Insertar los datos del resguardo en la tabla 'resguardos'
            sql_insert_resguardo = """
                INSERT INTO resguardos (id_bien, id_area, No_Resguardo, Tipo_De_Resguardo, Fecha_Resguardo, 
                                        No_Trabajador, Puesto, Nombre_Director_Jefe_De_Area, Nombre_Del_Resguardante)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            resguardo_values = (
                id_bien, area_id, form_data.get('No_Resguardo'), form_data.get('Tipo_De_Resguardo'), 
                form_data.get('Fecha_Resguardo'), form_data.get('No_Trabajador'), form_data.get('Puesto'), 
                form_data.get('Nombre_Director_Jefe_De_Area'), form_data.get('Nombre_Del_Resguardante')
            )
            
            cursor.execute(sql_insert_resguardo, resguardo_values)
            id_resguardo = cursor.lastrowid
            
            # 3. Manejar las imágenes del bien y guardarlas en la base de datos
            imagenes_bien = request.files.getlist('imagenes_bien')
            sql_insert_bien_img = "INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)"

            for file in imagenes_bien:
                if file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                    print("File path")
                    print(file_path)
                    file.save(file_path)
                    
                    cursor.execute(sql_insert_bien_img, (id_bien, unique_filename))

            # 4. Manejar las imágenes del resguardo y guardarlas en la base de datos
            imagenes_resguardo = request.files.getlist('imagenes_resguardo')
            sql_insert_resguardo_img = "INSERT INTO imagenes_resguardo (id_resguardo, ruta_imagen) VALUES (%s, %s)"

            for file in imagenes_resguardo:
                if file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                    file.save(file_path)

                    cursor.execute(sql_insert_resguardo_img, (id_resguardo, unique_filename))
            
            conn.commit()
            log_activity(action='Resguardos', resource='Resguardo', resource_id=id_resguardo, details=f'Se registró un nuevo resguardo y bien, ID: {id_resguardo}')
            return jsonify({
                "message": "Resguardo y bien creado exitosamente.",
                "category": "success",
                "redirect_url": url_for('resguardos.ver_resguardos')
            }), 200
           
        return render_template('crear_resguardo.html', areas=areas_list, form_data=form_data, available_columns=AVAILABLE_COLUMNS)

    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            conn.rollback()
        return jsonify({"message": f"Error de base de datos: {err}", "category": "danger"}), 500
        
    except Exception as e:
        if conn and conn.is_connected():
            conn.rollback()
        return jsonify({"message": f"Ocurrió un error inesperado: {e}", "category": "danger"}), 500
        
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@resguardos_bp.route('/editar_resguardo/<int:id_resguardo>', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def editar_resguardo(id_resguardo):
    conn = None
    cursor = None
    
    areas_data = get_areas_data()
    areas_list = list(areas_data.keys())

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            form_data = request.form.to_dict()
            cursor.execute("SELECT id_bien FROM resguardos WHERE id = %s", (id_resguardo,))
            resguardo = cursor.fetchone()
            if not resguardo:
                return jsonify({"message": "Resguardo no encontrado.", "category": "danger"}), 404
            
            id_bien = resguardo['id_bien']
            area_name = form_data.get('Area')
            area_id = areas_data.get(area_name)
            
            if not area_id:
                return jsonify({"message": "Área seleccionada no válida.", "category": "danger"}), 400

            # FUNCIONES AUXILIARES PARA MANEJAR CAMPOS
            def parse_decimal(value):
                if value is None or value == '':
                    return None
                try:
                    cleaned_value = str(value).replace(',', '').strip()
                    return float(cleaned_value) if cleaned_value else None
                except (ValueError, TypeError):
                    return None

            def parse_int(value):
                if value is None or value == '':
                    return None
                try:
                    return int(value) if value else None
                except (ValueError, TypeError):
                    return None

            def parse_string(value):
                return value if value else None

            # CONVERTIR TODOS LOS CAMPOS NUMÉRICOS Y FECHAS
            fecha_poliza = parse_string(form_data.get('Fecha_Poliza'))
            fecha_factura = parse_string(form_data.get('Fecha_Factura'))
            fecha_resguardo = parse_string(form_data.get('Fecha_Resguardo'))
            
            costo_inicial = parse_decimal(form_data.get('Costo_Inicial'))
            depreciacion_acumulada = parse_decimal(form_data.get('Depreciacion_Acumulada'))
            costo_final_cantidad = parse_decimal(form_data.get('Costo_Final_Cantidad'))
            cantidad = parse_int(form_data.get('Cantidad'))
            tipo_resguardo = parse_int(form_data.get('Tipo_De_Resguardo'))

            # 1. Actualizar los datos del bien
            sql_update_bien = """
                UPDATE bienes SET No_Inventario=%s, No_Factura=%s, No_Cuenta=%s, Proveedor=%s, 
                Descripcion_Del_Bien=%s, Descripcion_Corta_Del_Bien=%s, Rubro=%s, Poliza=%s, 
                Fecha_Poliza=%s, Sub_Cuenta_Armonizadora=%s, Fecha_Factura=%s, Costo_Inicial=%s, 
                Depreciacion_Acumulada=%s, Costo_Final_Cantidad=%s, Cantidad=%s, Estado_Del_Bien=%s, 
                Marca=%s, Modelo=%s, Numero_De_Serie=%s WHERE id=%s
            """
            
            bien_values = (
                parse_string(form_data.get('No_Inventario')),
                parse_string(form_data.get('No_Factura')),
                parse_string(form_data.get('No_Cuenta')),
                parse_string(form_data.get('Proveedor')),
                parse_string(form_data.get('Descripcion_Del_Bien')),
                parse_string(form_data.get('Descripcion_Corta_Del_Bien')),
                parse_string(form_data.get('Rubro')),
                parse_string(form_data.get('Poliza')),
                fecha_poliza,
                parse_string(form_data.get('Sub_Cuenta_Armonizadora')),
                fecha_factura,
                costo_inicial,
                depreciacion_acumulada,
                costo_final_cantidad,
                cantidad,
                parse_string(form_data.get('Estado_Del_Bien')),
                parse_string(form_data.get('Marca')),
                parse_string(form_data.get('Modelo')),
                parse_string(form_data.get('Numero_De_Serie')),
                id_bien
            )
            
            cursor.execute(sql_update_bien, bien_values)
            
            # 2. Actualizar los datos del resguardo
            sql_update_resguardo = """
                UPDATE resguardos SET id_area=%s, No_Resguardo=%s, Tipo_De_Resguardo=%s, Fecha_Resguardo=%s, 
                No_Trabajador=%s, Puesto=%s, Nombre_Director_Jefe_De_Area=%s, Nombre_Del_Resguardante=%s 
                WHERE id=%s
            """
            
            resguardo_values = (
                area_id,
                parse_string(form_data.get('No_Resguardo')),
                tipo_resguardo,
                fecha_resguardo,
                parse_string(form_data.get('No_Trabajador')),
                parse_string(form_data.get('Puesto')),
                parse_string(form_data.get('Nombre_Director_Jefe_De_Area')),
                parse_string(form_data.get('Nombre_Del_Resguardante')),
                id_resguardo
            )
            
            cursor.execute(sql_update_resguardo, resguardo_values)


                        # 3. Procesar eliminación de imágenes
            eliminar_imagenes_bien = request.form.getlist('eliminar_imagen_bien[]')
            eliminar_imagenes_resguardo = request.form.getlist('eliminar_imagen_resguardo[]')

            print(f"Imágenes bien a eliminar: {eliminar_imagenes_bien}")
            print(f"Imágenes resguardo a eliminar: {eliminar_imagenes_resguardo}")

            # Eliminar imágenes del bien
            for img_id in eliminar_imagenes_bien:
                if img_id:
                    try:
                        # Primero obtener la ruta para eliminar el archivo físico
                        cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id = %s", (img_id,))
                        imagen = cursor.fetchone()
                        if imagen:
                            # Eliminar archivo físico
                            file_path = os.path.join(UPLOAD_FOLDER, imagen['ruta_imagen'])
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                print(f"Archivo eliminado: {file_path}")
                            
                            # Eliminar registro de la base de datos
                            cursor.execute("DELETE FROM imagenes_bien WHERE id = %s", (img_id,))
                            print(f"Imagen de bien eliminada de BD: {img_id}")
                    except Exception as e:
                        print(f"Error al eliminar imagen de bien {img_id}: {e}")

            # Eliminar imágenes del resguardo
            for img_id in eliminar_imagenes_resguardo:
                if img_id:
                    try:
                        # Primero obtener la ruta para eliminar el archivo físico
                        cursor.execute("SELECT ruta_imagen FROM imagenes_resguardo WHERE id = %s", (img_id,))
                        imagen = cursor.fetchone()
                        if imagen:
                            # Eliminar archivo físico
                            file_path = os.path.join(UPLOAD_FOLDER, imagen['ruta_imagen'])
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                print(f"Archivo eliminado: {file_path}")
                            
                            # Eliminar registro de la base de datos
                            cursor.execute("DELETE FROM imagenes_resguardo WHERE id = %s", (img_id,))
                            print(f"Imagen de resguardo eliminada de BD: {img_id}")
                    except Exception as e:
                        print(f"Error al eliminar imagen de resguardo {img_id}: {e}")

            # 4. Procesar nuevas imágenes del bien - SOLO SI HAY ARCHIVOS CON CONTENIDO
            imagenes_bien = request.files.getlist('imagenes_bien')
            print(f"Imágenes bien recibidas: {[img.filename for img in imagenes_bien]}")

            for file in imagenes_bien:
                # VERIFICAR QUE EL ARCHIVO TENGA NOMBRE Y CONTENIDO
                if file and file.filename and file.filename != '':
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # Guardar en la nueva ubicación (UPLOAD_FOLDER)
                    file_save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                    file.save(file_save_path)
                    
                    # Guardar solo el nombre del archivo en la base de datos
                    cursor.execute("INSERT INTO imagenes_bien (id_bien, ruta_imagen) VALUES (%s, %s)", 
                                (id_bien, unique_filename))
                    print(f"Imagen de bien guardada: {unique_filename}")

            # 5. Procesar nuevas imágenes del resguardo - SOLO SI HAY ARCHIVOS CON CONTENIDO
            imagenes_resguardo = request.files.getlist('imagenes_resguardo')
            print(f"Imágenes resguardo recibidas: {[img.filename for img in imagenes_resguardo]}")

            for file in imagenes_resguardo:
                # VERIFICAR QUE EL ARCHIVO TENGA NOMBRE Y CONTENIDO
                if file and file.filename and file.filename != '':
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    
                    # Guardar en la nueva ubicación (UPLOAD_FOLDER)
                    file_save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                    file.save(file_save_path)
                    
                    # Guardar solo el nombre del archivo en la base de datos
                    cursor.execute("INSERT INTO imagenes_resguardo (id_resguardo, ruta_imagen) VALUES (%s, %s)", 
                                (id_resguardo, unique_filename))
                    print(f"Imagen de resguardo guardada: {unique_filename}")
        
            conn.commit()
            log_activity(action='Resguardos', resource='Resguardo', resource_id=id_resguardo, details=f'Se Actualizo un nuevo resguardo y bien, ID: {id_resguardo}')
            return jsonify({
                "message": "Resguardo actualizado exitosamente.",
                "category": "success",
                "redirect_url": url_for('resguardos.ver_resguardo', id_resguardo=id_resguardo) # REDIRECCIÓN CORREGIDA
            }), 200

        else:
            sql_select = """
                SELECT r.id AS resguardo_id, b.id AS bien_id, r.*, b.*, a.Nombre as Area_Nombre
                FROM resguardos r
                JOIN bienes b ON r.id_bien = b.id
                JOIN areas a ON r.id_area = a.id
                WHERE r.id = %s
            """
            cursor.execute(sql_select, (id_resguardo,))
            resguardo_data = cursor.fetchone()

            if not resguardo_data:
                flash('Resguardo no encontrado.', 'danger')
                return redirect(url_for('resguardos.ver_resguardos'))

            cursor.execute("SELECT id, ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (resguardo_data['bien_id'],))
            imagenes_bien_db = cursor.fetchall()
            
            cursor.execute("SELECT id, ruta_imagen FROM imagenes_resguardo WHERE id_resguardo = %s", (resguardo_data['resguardo_id'],))
            imagenes_resguardo_db = cursor.fetchall()
            
            resguardo_data['Area'] = resguardo_data['Area_Nombre']

            return render_template('editar_resguardo.html', 
                                 areas=areas_list, 
                                 resguardo_data=resguardo_data, 
                                 imagenes_bien_db=imagenes_bien_db, 
                                 imagenes_resguardo_db=imagenes_resguardo_db)

    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            conn.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "message": f"Error de base de datos: {err}",
            "category": "danger"
        }), 500
    except Exception as e:
        if conn and conn.is_connected():
            conn.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            "message": f"Ocurrió un error inesperado: {e}",
            "category": "danger"
        }), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


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
        # El cursor de diccionario es útil para acceder a los datos por nombre de columna.
        cursor = conn.cursor(dictionary=True)

        # 1. Obtener los datos principales del resguardo y el bien
        # Corrección: Se añaden alias para los IDs de las tablas para evitar conflictos.
        sql_select_resguardo = """
            SELECT 
                r.id AS id_resguardo,
                b.id AS id_bien,
                r.No_Resguardo,
                r.Tipo_De_Resguardo,
                r.Fecha_Resguardo,
                r.No_Trabajador,
                r.Puesto,
                r.Nombre_Director_Jefe_De_Area,
                r.Nombre_Del_Resguardante,
                b.No_Inventario,
                b.No_Factura,
                b.No_Cuenta,
                b.Proveedor,
                b.Descripcion_Del_Bien,
                b.Descripcion_Corta_Del_Bien,
                b.Rubro,
                b.Poliza,
                b.Fecha_Poliza,
                b.Sub_Cuenta_Armonizadora,
                b.Fecha_Factura,
                b.Costo_Inicial,
                b.Depreciacion_Acumulada,
                b.Costo_Final_Cantidad,
                b.Cantidad,
                b.Estado_Del_Bien,
                b.Marca,
                b.Modelo,
                b.Numero_De_Serie,
                a.nombre AS Area_Nombre
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
            WHERE r.id = %s
        """
        cursor.execute(sql_select_resguardo, (id_resguardo,))
        resguardo = cursor.fetchone()
        print(resguardo)
        if not resguardo:
            flash('Resguardo no encontrado.', 'danger')
            return redirect(url_for('resguardos.ver_resguardos'))

        # 2. Obtener las rutas de las imágenes del bien
        # Se usa el alias 'bien_id' para obtener el ID del bien correctamente.
        cursor.execute("SELECT ruta_imagen FROM imagenes_bien WHERE id_bien = %s", (resguardo['id_bien'],))
        imagenes_bien = [row['ruta_imagen'] for row in cursor.fetchall()]
        
        # 3. Obtener las rutas de las imágenes del resguardo
        # Se usa el alias 'resguardo_id' para obtener el ID del resguardo correctamente.
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
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@resguardos_bp.route('/resguardos_sujeto_control')
@login_required
@permission_required('resguardos.ver_resguardo')
def ver_resguardos_sujeto_control():
    conn = None
    resguardos_data = []
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 100, type=int)
    offset = (page - 1) * limit

    # Search parameters
    search_column = request.args.get('search_column', 'all')
    search_query = request.args.get('search_query', '').strip()
    
    # Check if this is an AJAX request for infinite scroll
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql_select_columns = """
            r.id,
            b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Descripcion_Del_Bien,
            b.Descripcion_Corta_Del_Bien, a.nombre AS Area_Nombre,
            b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
            b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada,
            b.Costo_Final_Cantidad, b.Cantidad, b.Estado_Del_Bien, b.Marca,
            b.Modelo, b.Numero_De_Serie,
            r.No_Resguardo, r.Tipo_De_Resguardo, r.Fecha_Resguardo, r.No_Trabajador,
            r.Puesto, r.Nombre_Director_Jefe_De_Area,
            r.Nombre_Del_Resguardante,
            b.Proveedor
        """
        
        sql_query = f"""
            SELECT {sql_select_columns}
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
        """
        
        where_clauses = ["r.Tipo_De_Resguardo = 1"] # Filtro clave
        sql_params = []

        if search_query:
            if search_column == 'all':
                all_columns_search_clauses = []
                searchable_cols = [
                    'b.No_Inventario', 'b.No_Factura', 'b.No_Cuenta', 'b.Descripcion_Del_Bien',
                    'a.nombre', 'b.Proveedor', 'b.Rubro', 'r.No_Resguardo',
                    'r.Nombre_Del_Resguardante'
                ]
                for col in searchable_cols:
                    all_columns_search_clauses.append(f"{col} LIKE %s")
                    sql_params.append(f"%{search_query}%")
                where_clauses.append("(" + " OR ".join(all_columns_search_clauses) + ")")
            else:
                col_mapping = {
                    'Area': 'a.nombre',
                    'No_Inventario': 'b.No_Inventario',
                    'No_Factura': 'b.No_Factura',
                    'No_Cuenta': 'b.No_Cuenta',
                    'Descripcion_Del_Bien': 'b.Descripcion_Del_Bien',
                    'Descripcion_Corta_Del_Bien': 'b.Descripcion_Corta_Del_Bien',
                    'Rubro': 'b.Rubro',
                    'Poliza': 'b.Poliza',
                    'Fecha_Poliza': 'b.Fecha_Poliza',
                    'Sub_Cuenta_Armonizadora': 'b.Sub_Cuenta_Armonizadora',
                    'Fecha_Factura': 'b.Fecha_Factura',
                    'Costo_Inicial': 'b.Costo_Inicial',
                    'Depreciacion_Acumulada': 'b.Depreciacion_Acumulada',
                    'Costo_Final_Cantidad': 'b.Costo_Final_Cantidad',
                    'Cantidad': 'b.Cantidad',
                    'Estado_Del_Bien': 'b.Estado_Del_Bien',
                    'Marca': 'b.Marca',
                    'Modelo': 'b.Modelo',
                    'Numero_De_Serie': 'b.Numero_De_Serie',
                    'No_Resguardo': 'r.No_Resguardo',
                    'No_Trabajador': 'r.No_Trabajador',
                    'Fecha_Resguardo': 'r.Fecha_Resguardo',
                    'Puesto': 'r.Puesto',
                    'Nombre_Director_Jefe_De_Area': 'r.Nombre_Director_Jefe_De_Area',
                    'Tipo_De_Resguardo': 'r.Tipo_De_Resguardo',
                    'Nombre_Del_Resguardante': 'r.Nombre_Del_Resguardante',
                    'Proveedor': 'b.Proveedor'
                }

                db_col = col_mapping.get(search_column)
                if db_col:
                    where_clauses.append(f"{db_col} LIKE %s")
                    sql_params.append(f"%{search_query}%")
                else:
                    flash("Columna de búsqueda inválida.", 'error')
                    search_column = 'all'

        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)

        sql_query += f" ORDER BY r.id DESC LIMIT %s OFFSET %s"
        sql_params.extend([limit, offset])

        cursor.execute(sql_query, sql_params)
        resguardos_data = cursor.fetchall()
        
        available_columns_for_search = [col for col in AVAILABLE_COLUMNS if col not in [
            'Descripcion_Del_Bien', 'Descripcion_Corta_Del_Bien', 'Puesto', 'Tipo_De_Resguardo', 'Estado_Del_Bien'
        ]]

        if is_ajax:
            for row in resguardos_data:
                for key, value in row.items():
                    if isinstance(value, (date, datetime)):
                        row[key] = value.isoformat()
            
            return jsonify(resguardos_data)
        else:
            return render_template(
                'resguardos_sujeto_control.html',
                resguardos=resguardos_data,
                search_column=search_column,
                search_query=search_query,
                available_columns_for_search=available_columns_for_search,
                current_page=page,
                limit=limit
            )

    except mysql.connector.Error as err:
        flash(f"Error al obtener resguardos: {err}", 'error')
        print(f"Error: {err}")
        return render_template('resguardos_sujeto_control.html', resguardos=[], search_column=search_column, search_query=search_query, available_columns_for_search=AVAILABLE_COLUMNS, current_page=page, limit=limit)
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", 'error')
        print(f"Unexpected error: {e}")
        return render_template('resguardos_sujeto_control.html', resguardos=[], search_column=search_column, search_query=search_query, available_columns_for_search=AVAILABLE_COLUMNS, current_page=page, limit=limit)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@resguardos_bp.route('/generate_resguardo_pdf/<int:id_resguardo>')
@login_required
@permission_required('resguardos.crear_resguardo')
def generate_resguardo_pdf(id_resguardo):
    conn, cursor = get_db() # Using get_db for dictionary cursor
    if not conn:
        flash("No se pudo conectar a la base de datos.", 'error')
        return redirect(url_for('main.resguardos_list'))

    try:
        cursor.execute("SELECT * FROM resguardo WHERE id = %s", (id_resguardo,))
        resguardo_data = cursor.fetchone()
        if not resguardo_data:
            flash("Resguardo no encontrado.", 'error')
            return redirect(url_for('main.resguardos_list'))
    except mysql.connector.Error as err:
        flash(f"Error al obtener datos: {err}", 'error')
        return redirect(url_for('main.resguardos_list'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    try:
        reader = PdfReader(current_app.config['PDF_TEMPLATE_PATH'])
        
        if not reader.get_form_text_fields():
            flash("La plantilla PDF no contiene campos de formulario.", 'error')
            return redirect(url_for('main.resguardos_list'))

        # Map your DB data to PDF fields
        # This is a critical part, ensure field names in PDF match these keys
        field_data = {
            "No_Inventario_Field": resguardo_data.get('No_Inventario', ''),
            "No_Factura_Field": resguardo_data.get('No_Factura', ''),
            "No_Cuenta_Field": resguardo_data.get('No_Cuenta', ''),
            # Add all other fields you want to populate
            "No_Resguardo_Field": resguardo_data.get('No_Resguardo', ''),
            "Proveedor_Field": resguardo_data.get('Proveedor', ''),
            "Fecha_Resguardo_Field": str(resguardo_data.get('Fecha_Resguardo', '')) if resguardo_data.get('Fecha_Resguardo') else '',
            "Descripcion_Del_Bien_Field": resguardo_data.get('Descripcion_Del_Bien', ''),
            "Descripcion_Fisica_Field": resguardo_data.get('Descripcion_Fisica', ''),
            "Area_Field": resguardo_data.get('Area', ''),
            "Rubro_Field": resguardo_data.get('Rubro', ''),
            "Poliza_Field": resguardo_data.get('Poliza', ''),
            "Fecha_Poliza_Field": str(resguardo_data.get('Fecha_Poliza', '')) if resguardo_data.get('Fecha_Poliza') else '',
            "Sub_Cuenta_Armonizadora_Field": resguardo_data.get('Sub_Cuenta_Armonizadora', ''),
            "Fecha_Factura_Field": str(resguardo_data.get('Fecha_Factura', '')) if resguardo_data.get('Fecha_Factura') else '',
            "Costo_Inicial_Field": str(resguardo_data.get('Costo_Inicial', '')),
            "Depreciacion_Acumulada_Field": str(resguardo_data.get('Depreciacion_Acumulada', '')),
            "Costo_Final_Cantidad_Field": str(resguardo_data.get('Costo_Final_Cantidad', '')),
            "Cantidad_Field": str(resguardo_data.get('Cantidad', '')),
            
            "Puesto_Field": resguardo_data.get('Puesto', ''),
            "Nombre_Director_Jefe_De_Area_Field": resguardo_data.get('Nombre_Director_Jefe_De_Area', ''),
            "Numero_De_Serie_Field": resguardo_data.get('Numero_De_Serie', '')
        }

        writer = PdfWriter()
        writer.clone_reader_document_root(reader)
        
        # Fill the form fields
        writer.update_page_form_field_values(writer.pages[0], field_data) # Assuming fields are on the first page

        # Flatten the form fields so they are not editable in the final PDF
        writer.flatten_form()

        # Save to BytesIO to send as file
        output_pdf_buffer = BytesIO()
        writer.write(output_pdf_buffer)
        output_pdf_buffer.seek(0)

        return send_file(
            output_pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'resguardo_{id_resguardo}.pdf'
        )

    except FileNotFoundError:
        flash("Plantilla PDF no encontrada en " + current_app.config['PDF_TEMPLATE_PATH'], 'error')
    except Exception as e:
        flash(f"Error al generar PDF: {str(e)}", 'error')
        print(f"Error detallado:\n{traceback.format_exc()}")
        
    return redirect(url_for('main.resguardos_list'))


@resguardos_bp.route('/ver_resguardos')
@login_required
@permission_required('resguardos.ver_resguardo')
def ver_resguardos():
    conn = None
    resguardos_data = []
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 100, type=int)
    offset = (page - 1) * limit

    # Search parameters
    search_column = request.args.get('search_column', 'all')
    search_query = request.args.get('search_query', '').strip()
    
    # Check if this is an AJAX request for infinite scroll
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        sql_select_columns = """
            r.id,
            b.No_Inventario, b.No_Factura, b.No_Cuenta, b.Descripcion_Del_Bien,
            b.Descripcion_Corta_Del_Bien, a.nombre AS Area_Nombre,
            b.Rubro, b.Poliza, b.Fecha_Poliza, b.Sub_Cuenta_Armonizadora,
            b.Fecha_Factura, b.Costo_Inicial, b.Depreciacion_Acumulada,
            b.Costo_Final_Cantidad, b.Cantidad, b.Estado_Del_Bien, b.Marca,
            b.Modelo, b.Numero_De_Serie,
            r.No_Resguardo, r.Tipo_De_Resguardo, r.Fecha_Resguardo, r.No_Trabajador,
            r.Puesto, r.Nombre_Director_Jefe_De_Area,
            r.Nombre_Del_Resguardante,
            b.Proveedor
        """
        
        sql_query = f"""
            SELECT {sql_select_columns}
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
        """
        
        where_clauses = []
        sql_params = []

        if search_query:
            print(search_query)
            if search_column == 'all':
                
                all_columns_search_clauses = []
                # Use a specific list of columns for "all" search for better performance
                searchable_cols = [
                    'b.No_Inventario', 'b.No_Factura', 'b.No_Cuenta', 'b.Descripcion_Del_Bien',
                    'a.nombre', 'b.Proveedor', 'b.Rubro', 'r.No_Resguardo',
                    'r.Nombre_Del_Resguardante'
                ]
                for col in searchable_cols:
                    all_columns_search_clauses.append(f"{col} LIKE %s")
                    sql_params.append(f"%{search_query}%")
                where_clauses.append("(" + " OR ".join(all_columns_search_clauses) + ")")
            else:
                # Find the correct table prefix for the search column
                col_mapping = {
                    'Area': 'a.nombre',
                    'No_Inventario': 'b.No_Inventario',
                    'No_Factura': 'b.No_Factura',
                    'No_Cuenta': 'b.No_Cuenta',
                    'Descripcion_Del_Bien': 'b.Descripcion_Del_Bien',
                    'Descripcion_Corta_Del_Bien': 'b.Descripcion_Corta_Del_Bien',
                    'Rubro': 'b.Rubro',
                    'Poliza': 'b.Poliza',
                    'Fecha_Poliza': 'b.Fecha_Poliza',
                    'Sub_Cuenta_Armonizadora': 'b.Sub_Cuenta_Armonizadora',
                    'Fecha_Factura': 'b.Fecha_Factura',
                    'Costo_Inicial': 'b.Costo_Inicial',
                    'Depreciacion_Acumulada': 'b.Depreciacion_Acumulada',
                    'Costo_Final_Cantidad': 'b.Costo_Final_Cantidad',
                    'Cantidad': 'b.Cantidad',
                    'Estado_Del_Bien': 'b.Estado_Del_Bien',
                    'Marca': 'b.Marca',
                    'Modelo': 'b.Modelo',
                    'Numero_De_Serie': 'b.Numero_De_Serie',
                    'No_Resguardo': 'r.No_Resguardo',
                    'No_Trabajador': 'r.No_Trabajador',
                    'Fecha_Resguardo': 'r.Fecha_Resguardo',
                    'Puesto': 'r.Puesto',
                    'Nombre_Director_Jefe_De_Area': 'r.Nombre_Director_Jefe_De_Area',
                    'Tipo_De_Resguardo': 'r.Tipo_De_Resguardo',
                    'Nombre_Del_Resguardante': 'r.Nombre_Del_Resguardante',
                    'Proveedor': 'b.Proveedor'
                }

                db_col = col_mapping.get(search_column)
                if db_col:
                    where_clauses.append(f"{db_col} LIKE %s")
                    sql_params.append(f"%{search_query}%")
                else:
                    flash("Columna de búsqueda inválida.", 'error')
                    search_column = 'all'

        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)

        sql_query += f" ORDER BY r.id DESC LIMIT %s OFFSET %s"
        sql_params.extend([limit, offset])

        cursor.execute(sql_query, sql_params)
        resguardos_data = cursor.fetchall()
        
        # Prepare a list of user-friendly column names for the search dropdown
        available_columns_for_search = [col for col in AVAILABLE_COLUMNS if col not in [
            'Descripcion_Del_Bien', 'Descripcion_Corta_Del_Bien', 'Puesto', 'Tipo_De_Resguardo', 'Estado_Del_Bien'
        ]]

        if is_ajax:
            # Format dates to string for JSON serialization
           
            for row in resguardos_data:
                for key, value in row.items():
                    if isinstance(value, (date, datetime)):
                        row[key] = value.isoformat()
            
            # Use 'Area_Nombre' key instead of 'Area' as defined in the query
            
            return jsonify(resguardos_data)
        else:
            return render_template(
                'resguardos_list.html',
                resguardos=resguardos_data,
                search_column=search_column,
                search_query=search_query,
                available_columns_for_search=available_columns_for_search,
                current_page=page,
                limit=limit
            )

    except mysql.connector.Error as err:
        flash(f"Error al obtener resguardos: {err}", 'error')
        print(f"Error: {err}")
        return render_template('resguardos_list.html', resguardos=[], search_column=search_column, search_query=search_query, available_columns_for_search=AVAILABLE_COLUMNS, current_page=page, limit=limit)
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", 'error')
        print(f"Unexpected error: {e}")
        return render_template('resguardos_list.html', resguardos=[], search_column=search_column, search_query=search_query, available_columns_for_search=AVAILABLE_COLUMNS, current_page=page, limit=limit)
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@resguardos_bp.route('/resguardos_clasificados')
@login_required
@permission_required('resguardos.crear_resguardo')
def resguardos_clasificados():
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos", 'error')
        return redirect(url_for('index'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
     SELECT r.*,
                   CASE
                       WHEN r.Tipo_De_Resguardo LIKE '%Control%' THEN 'Sujeto de Control'
                       ELSE 'Resguardo Normal'
                   END AS Tipo_De_Resguardo
            FROM resguardo r
            ORDER BY
                CASE
                    WHEN r.Tipo_De_Resguardo LIKE '%Control%' THEN 0
                    ELSE 1
                END,
                r.id
""")
        resguardos = cursor.fetchall()
        
        column_names = [desc[0] for desc in cursor.description]
        
        return render_template('resguardos_clasificados.html', 
                            resguardos=resguardos,
                            column_names=column_names)
    except Exception as e:
        flash(f"Error al obtener resguardos: {str(e)}", 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

        
@resguardos_bp.route('/exportar_resguardos_excel', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def exportar_resguardos_excel():
    try:
        selected_columns = request.form.getlist('columns')
        
        if not selected_columns:
            return jsonify({'error': 'No se seleccionaron columnas'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
            
        try:
            cursor = conn.cursor(dictionary=True)
            columns_str = ', '.join(selected_columns)
            cursor.execute(f"""
                SELECT {columns_str}, 
                       CASE 
                           WHEN Tipo_De_Resguardo  = 1 THEN 'Sujeto de Control'
                           ELSE 'Resguardo Normal'
                       END AS Tipo_de_resguardo
                FROM resguardo
                ORDER BY Tipo_De_Resguardo  DESC, id
            """)
            data = cursor.fetchall()
            
            df = pd.DataFrame(data)
            
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df.to_excel(writer, sheet_name='Resguardos', index=False)
            writer.close()
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='resguardos_clasificados.xlsx'
            )
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500



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

