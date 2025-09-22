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
            # Se ha eliminado la columna 'Area' de esta inserción para reflejar el cambio en la base de datos.
            sql_insert_bien = """
                INSERT INTO bienes (No_Inventario, No_Factura, No_Cuenta, Proveedor, Descripcion_Del_Bien, 
                                    Descripcion_Corta_Del_Bien, Rubro, Poliza, Fecha_Poliza, Sub_Cuenta_Armonizadora, 
                                    Fecha_Factura, Costo_Inicial, Depreciacion_Acumulada, Costo_Final_Cantidad, Cantidad, 
                                    Estado_Del_Bien, Marca, Modelo, Numero_De_Serie)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Se ha eliminado el valor 'area_name' de los valores de la inserción de bienes.
            bien_values = (
                form_data.get('No_Inventario'), form_data.get('No_Factura'), form_data.get('No_Cuenta'), 
                form_data.get('Proveedor'), form_data.get('Descripcion_Del_Bien'),
                form_data.get('Descripcion_Corta_Del_Bien'), form_data.get('Rubro'),
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
                                        No_Trabajador, No_Nomina_Trabajador, Puesto_Trabajador, Nombre_Director_Jefe_De_Area, Nombre_Del_Resguardante)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            resguardo_values = (
                id_bien, area_id, form_data.get('No_Resguardo'), form_data.get('Tipo_De_Resguardo'), 
                form_data.get('Fecha_Resguardo'), form_data.get('No_Trabajador'), form_data.get('No_Nomina_Trabajador'), form_data.get('Puesto_Trabajador'), 
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
        print(f"Error de base de datos: {err}")
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
                No_Trabajador=%s, No_Nomina_Trabajador=%s, Puesto_trabajador=%s, Nombre_Director_Jefe_De_Area=%s, Nombre_Del_Resguardante=%s 
                WHERE id=%s
            """
            
            resguardo_values = (
                area_id,
                parse_string(form_data.get('No_Resguardo')),
                tipo_resguardo,
                fecha_resguardo,
                parse_string(form_data.get('No_Trabajador')),
                parse_string(form_data.get('No_Nomina_Trabajador')),
                parse_string(form_data.get('Puesto_Trabajador')),
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
                r.Puesto_Trabajador AS Puesto,
                r.Nombre_Director_Jefe_De_Area,
                r.Nombre_Del_Resguardante,
                r.No_Nomina_Trabajador,
                r.Activo,
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


@resguardos_bp.route('/crear_resguardo_de_bien/<int:id_bien>', methods=['GET'])
@login_required
@permission_required('resguardos.crear_resguardo')
def crear_resguardo_de_bien(id_bien):
    conn = None
    cursor = None
    areas_list = list(get_areas_data().keys())
    form_data = {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Obtener los datos del bien usando su ID
        sql_select_bien = "SELECT * FROM bienes WHERE id = %s"
        cursor.execute(sql_select_bien, (id_bien,))
        bien_data = cursor.fetchone()

        if not bien_data:
            flash("Bien no encontrado.", "danger")
            return redirect(url_for('bienes.listar_bienes'))

        # 2. Pasa los datos del bien al diccionario form_data
        form_data = bien_data
        
        # 3. Formatea las fechas si existen, para que el formulario las muestre correctamente
        if 'Fecha_Poliza' in form_data and form_data['Fecha_Poliza']:
            form_data['Fecha_Poliza'] = form_data['Fecha_Poliza'].isoformat()
        if 'Fecha_Factura' in form_data and form_data['Fecha_Factura']:
            form_data['Fecha_Factura'] = form_data['Fecha_Factura'].isoformat()
        
        # 4. Renderiza el formulario, pero ahora con los datos precargados
        return render_template(
            'crear_resguardo.html', 
            areas=areas_list, 
            form_data=form_data, 
            available_columns=AVAILABLE_COLUMNS,
            bien_precargado=True # Una variable para controlar la lógica en la plantilla si es necesario
        )

    except mysql.connector.Error as err:
        flash(f"Error de base de datos: {err}", "danger")
        return redirect(url_for('bienes.listar_bienes'))
        
    except Exception as e:
        flash(f"Ocurrió un error inesperado: {e}", "danger")
        return redirect(url_for('bienes.listar_bienes'))
        
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# En tu archivo routes/resguardos.py

# ... (tus otras importaciones como Flask, render_template, request, etc.)

# =================================================================
# VISTAS DE RESGUARDOS (RUTAS)
# =================================================================

@resguardos_bp.route('/resguardos')
# Probablemente quieras añadir @login_required aquí también
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
                b.Costo_Final_Cantidad, b.Cantidad, b.Estado_Del_Bien,
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
                b.Costo_Final_Cantidad, b.Cantidad, b.Estado_Del_Bien,
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