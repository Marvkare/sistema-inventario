from flask import current_app, Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user # Asume que tienes Flask-Login configurado
import os
import traceback
import json
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO
from PIL import Image
from config import UPLOAD_FOLDER # Asegúrate de que estos archivos existan
from database import get_db_connection # Asegúrate de que este archivo exista
from helpers import map_operator_to_sql
from log_activity import log_activity # Asegúrate de que este archivo exista
from decorators import permission_required # Asume que este decorador existe
import pymysql
import io
from drive_service import drive_service, get_cached_image, save_to_cache
plantillas_bp = Blueprint('plantillas', __name__)
import urllib.parse

# EL CÓDIGO NUEVO (CORRECTO)
# REEMPLAZA tu diccionario AVAILABLE_COLUMNS con este:

AVAILABLE_COLUMNS = {
    # --- Columnas de Bienes (bienes) ---
    'id_bien': 'bienes.id',
    'No_Inventario': 'bienes.No_Inventario',
    'No_Factura': 'bienes.No_Factura',
    'No_Cuenta': 'bienes.No_Cuenta',
    'Proveedor': 'bienes.Proveedor',
    'Descripcion_Del_Bien': 'bienes.Descripcion_Del_Bien',
    'Descripcion_Corta_Del_Bien': 'bienes.Descripcion_Corta_Del_Bien',
    'Rubro': 'bienes.Rubro',
    'Poliza': 'bienes.Poliza',
    'Fecha_Poliza': 'bienes.Fecha_Poliza',
    'Sub_Cuenta_Armonizadora': 'bienes.Sub_Cuenta_Armonizadora',
    'Fecha_Factura': 'bienes.Fecha_Factura',
    'Costo_Inicial': 'bienes.Costo_Inicial',
    'Depreciacion_Acumulada': 'bienes.Depreciacion_Acumulada',
    'Costo_Final': 'bienes.Costo_Final',
    'Cantidad': 'bienes.Cantidad',
    'Estado_Del_Bien': 'bienes.Estado_Del_Bien',
    'Marca': 'bienes.Marca',
    'Modelo': 'bienes.Modelo',
    'Numero_De_Serie': 'bienes.Numero_De_Serie',
    'Tipo_De_Alta': 'bienes.Tipo_De_Alta',
    'Clasificacion_Legal': 'bienes.Clasificacion_Legal',
    'Area_Presupuestal': 'bienes.Area_Presupuestal',
    'Documento_Propiedad': 'bienes.Documento_Propiedad',
    'Fecha_Documento_Propiedad': 'bienes.Fecha_Documento_Propiedad',
    'Valor_En_Libros': 'bienes.Valor_En_Libros',
    'Fecha_Adquisicion_Alta': 'bienes.Fecha_Adquisicion_Alta',
    'Fecha_Registro_Bien': 'bienes.Fecha_Registro',
    'estatus_actual': 'bienes.estatus_actual',
    
    # --- Columnas de Resguardo (resguardos) ---
    'id_resguardo': 'resguardos.id',
    'No_Resguardo': 'resguardos.No_Resguardo',
    'Ubicacion': 'resguardos.Ubicacion',
    'Tipo_De_Resguardo': 'resguardos.Tipo_De_Resguardo',
    'Fecha_Resguardo': 'resguardos.Fecha_Resguardo',
    'No_Trabajador': 'resguardos.No_Trabajador',
    'Puesto_Trabajador': 'resguardos.Puesto_Trabajador',
    'RFC_Trabajador': 'resguardos.RFC_Trabajador',
    'No_Nomina_Trabajador': 'resguardos.No_Nomina_Trabajador',
    'Nombre_Del_Resguardante': 'resguardos.Nombre_Del_Resguardante',
    'Nombre_Director_Jefe_De_Area': 'resguardos.Nombre_Director_Jefe_De_Area',
    'Resguardo_Activo': 'resguardos.Activo',

    # --- Columnas de Area (areas) ---
    'id_area': 'areas.id',
    'Area_Nombre': 'areas.nombre', 
    'Area_Numero': 'areas.numero',
    # --- Columnas de Estado y Virtuales ---

    'imagenPath_bien': None,
    'imagenPath_resguardo': None,
}


# =================================================================
# FUNCIÓN CENTRALIZADA PARA OBTENER DATOS CON FILTROS E IMÁGENES
# =================================================================
def map_operator_to_sql(operator):
    """Mapea operadores del frontend a operadores SQL."""
    operator_map = {
        '==': '=',
        '!=': '!=',
        '>': '>',
        '<': '<',
        '>=': '>=',
        '<=': '<=',
        'contains': 'LIKE'
    }
    return operator_map.get(operator)

def get_filtered_resguardo_data(selected_columns, filters, limit=None):
    """
    Versión corregida para almacenamiento local.
    1. Usa build_where_clause para filtros complejos.
    2. Genera URLs apuntando a 'serve_uploaded_file'.
    3. Evita el error 'Unknown column Imagen_Path'.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # --- 1. Construcción segura del SELECT ---
        safe_columns_clauses = []
        special_columns = [] # Aquí guardaremos 'imagenPath_bien', etc.

        # Siempre traemos los IDs ocultos para poder buscar las imágenes después
        safe_columns_clauses.append("bienes.id AS `id_bien_hidden`")
        safe_columns_clauses.append("resguardos.id AS `id_resguardo_hidden`")

        for col in selected_columns:
            if col in AVAILABLE_COLUMNS:
                sql_name = AVAILABLE_COLUMNS[col]
                
                if sql_name is None:
                    # Es una columna especial (imagen), NO la agregamos al SQL
                    special_columns.append(col)
                else:
                    # Es una columna normal de la BD
                    safe_columns_clauses.append(f"{sql_name} AS `{col}`")
        
        if not safe_columns_clauses:
             return [], 0, 0

        select_clause = ", ".join(safe_columns_clauses)

        # --- 2. Construcción del WHERE (Usando la función recursiva) ---
        # Asegúrate de que 'build_where_clause' esté definida antes en tu archivo
        where_sql, where_params = build_where_clause(filters)

        # --- 3. Construcción del Query Principal ---
        query = f"SELECT {select_clause} FROM bienes"
        query += " LEFT JOIN resguardos ON bienes.id = resguardos.id_bien"
        query += " LEFT JOIN areas ON resguardos.id_area = areas.id"

        if where_sql:
            query += f" WHERE {where_sql}"
        
        query += " ORDER BY bienes.id DESC"

        if limit:
            query += f" LIMIT {limit}"

        # Ejecución
        cursor.execute(query, where_params)
        results = cursor.fetchall()

        if not results:
            return [], 0, 0

        # --- 4. Inyección de Imágenes (LÓGICA LOCAL CORREGIDA) ---
        max_bien_images = 0
        max_resguardo_images = 0

        # A) Imágenes de Bienes
        if 'imagenPath_bien' in special_columns:
            bien_ids = set()
            for row in results:
                bid = row.get('id_bien_hidden')
                if bid: bien_ids.add(str(bid))
            
            if bien_ids:
                format_strings = ','.join(['%s'] * len(bien_ids))
                sql_img = f"""
                    SELECT id_bien, GROUP_CONCAT(ruta_imagen) as rutas 
                    FROM imagenes_bien 
                    WHERE id_bien IN ({format_strings}) 
                    GROUP BY id_bien
                """
                cursor.execute(sql_img, tuple(bien_ids))
                
                mapa_img = {}
                for row_img in cursor.fetchall():
                    rutas = row_img['rutas'].split(',') if row_img['rutas'] else []
                    
                    # --- CAMBIO CLAVE AQUÍ ---
                    # Usamos 'serve_uploaded_file' en lugar de 'serve_drive_image'
                    urls = [url_for('serve_uploaded_file', filename=r) for r in rutas]
                    
                    mapa_img[row_img['id_bien']] = urls
                    if len(urls) > max_bien_images:
                        max_bien_images = len(urls)

                # Asignar a los resultados
                for row in results:
                    bid = row.get('id_bien_hidden')
                    row['imagenPath_bien'] = mapa_img.get(bid, [])

        # B) Imágenes de Resguardos
        if 'imagenPath_resguardo' in special_columns:
            res_ids = set()
            for row in results:
                rid = row.get('id_resguardo_hidden')
                if rid: res_ids.add(str(rid))
            
            if res_ids:
                format_strings = ','.join(['%s'] * len(res_ids))
                sql_img = f"""
                    SELECT id_resguardo, GROUP_CONCAT(ruta_imagen) as rutas 
                    FROM imagenes_resguardo 
                    WHERE id_resguardo IN ({format_strings}) 
                    GROUP BY id_resguardo
                """
                cursor.execute(sql_img, tuple(res_ids))
                
                mapa_img = {}
                for row_img in cursor.fetchall():
                    rutas = row_img['rutas'].split(',') if row_img['rutas'] else []
                    
                    # --- CAMBIO CLAVE AQUÍ ---
                    urls = [url_for('serve_uploaded_file', filename=r) for r in rutas]
                    
                    mapa_img[row_img['id_resguardo']] = urls
                    if len(urls) > max_resguardo_images:
                        max_resguardo_images = len(urls)

                for row in results:
                    rid = row.get('id_resguardo_hidden')
                    row['imagenPath_resguardo'] = mapa_img.get(rid, [])

        # --- 5. Limpieza final (Opcional) ---
        for row in results:
            row.pop('id_bien_hidden', None)
            row.pop('id_resguardo_hidden', None)

        return results, max_bien_images, max_resguardo_images

    except Exception as e:
        print("Error CRÍTICO en get_filtered_resguardo_data:")
        traceback.print_exc() 
        return [], 0, 0
    finally:
        if conn :
            cursor.close()
            conn.close()

def build_where_clause(group_data):
    """
    Construye recursivamente la cláusula WHERE y los parámetros
    a partir de la estructura de datos anidada.
    Usa el diccionario AVAILABLE_COLUMNS para la seguridad.
    """
    if not group_data or not group_data.get('rules'):
        return "", []

    condition = f" {group_data.get('condition', 'AND').upper()} "
    params = []
    clauses = []

    for rule in group_data['rules']:
        if 'condition' in rule:
            # Es un sub-grupo
            sub_clause, sub_params = build_where_clause(rule)
            if sub_clause:
                clauses.append(f"({sub_clause})")
                params.extend(sub_params)
        else:
            # Es una regla simple
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            
            # 1. Validación (contra las claves del diccionario)
            if not (field and operator and field in AVAILABLE_COLUMNS):
                continue
                
            # 2. Búsqueda del nombre real (ej: 'bienes.No_Inventario')
            sql_field_name = AVAILABLE_COLUMNS[field] 
            
            sql_op_map = {'==': '=', '!=': '!=', '>': '>', '<': '<'}
            
            if operator in sql_op_map:
                clauses.append(f"{sql_field_name} {sql_op_map[operator]} %s")
                params.append(value)
            elif operator == 'contains':
                clauses.append(f"{sql_field_name} LIKE %s")
                params.append(f"%{value}%")
            elif operator == 'in':
                values_list = [v.strip() for v in value.split(',') if v.strip()]
                if not values_list:
                    continue
                placeholders = ', '.join(['%s'] * len(values_list))
                clauses.append(f"{sql_field_name} IN ({placeholders})")
                params.extend(values_list)

    if not clauses:
        return "", []
        
    return condition.join(clauses), params


# --- 3. RUTA PARA CREAR PLANTILLA (CORREGIDA) ---
@plantillas_bp.route('/crear_plantilla', methods=['GET', 'POST'])
@login_required
def crear_plantilla():
    """Ruta para crear y guardar una plantilla de consulta."""
    
    if request.method == 'POST':
        template_name = request.form.get('template_name')
        template_description = request.form.get('template_description')
        selected_columns = request.form.getlist('columns')
        
        # Lee el JSON directamente del input oculto
        filters_json = request.form.get('filters_json')
        
        if not filters_json:
            filters_json = "{}" # Guardar un objeto vacío por defecto
            
        try:
            json.loads(filters_json) 
        except json.JSONDecodeError:
            flash("Error: El formato de los filtros es inválido.", 'danger')
            return render_template('plantillas/plantilla_form.html', 
                                   is_edit=False, 
                                   template={'name': template_name, 'description': template_description},
                                   columns=list(AVAILABLE_COLUMNS.keys()),
                                   template_columns=selected_columns,
                                   template_filters=None)

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                columns_json = json.dumps(selected_columns)
                
                sql = "INSERT INTO query_templates (name, description, columns, filters) VALUES (%s, %s, %s, %s)"
                data_to_save = (template_name, template_description, columns_json, filters_json)
                
                cursor.execute(sql, data_to_save)
                new_template_id = cursor.lastrowid
            conn.commit()
            
            log_activity(
                action="Creación de Plantilla",
                category="Plantillas",
                resource_id=new_template_id,
                details=f"Usuario '{current_user.username}' creó la plantilla: {template_name}"
            )
            flash(f"Plantilla '{template_name}' guardada exitosamente.", 'success')
            return redirect(url_for('plantillas.ver_plantillas'))
        
        except (mysql.connector.IntegrityError, pymysql.err.IntegrityError):
            flash(f"Error: Ya existe una plantilla con el nombre '{template_name}'.", 'danger')
        except Exception as e:
            flash(f"Error al guardar la plantilla: {e}", 'danger')
        finally:
            if conn: 
                conn.close()

    # Renderiza la nueva plantilla unificada en modo "crear" (para GET)
    return render_template('plantillas/plantilla_form.html', 
                           is_edit=False, 
                           template={},
                           columns=list(AVAILABLE_COLUMNS.keys()), # <-- CORREGIDO
                           template_columns=[],
                           template_filters=None) # <-- CORREGIDO


# --- 4. RUTA PARA EDITAR PLANTILLA (CORREGIDA) ---
@plantillas_bp.route('/editar_plantilla/<int:template_id>', methods=['GET', 'POST'])
@login_required
@permission_required('plantillas.editar_plantilla')
def editar_plantilla(template_id):
    """Ruta para editar una plantilla de consulta existente."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,))
            template = cursor.fetchone()

        if not template:
            flash("Plantilla no encontrada.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))
        
        if request.method == 'POST':
            template_name = request.form.get('template_name')
            template_description = request.form.get('template_description')
            selected_columns = request.form.getlist('columns')
            filters_json = request.form.get('filters_json')

            if not filters_json:
                filters_json = "{}"
            
            try:
                json.loads(filters_json)
            except json.JSONDecodeError:
                flash("Error: El formato de los filtros es inválido y no se pudo guardar.", 'danger')
                return render_template('plantillas/plantilla_form.html',
                                       is_edit=True,
                                       template=template,
                                       columns=list(AVAILABLE_COLUMNS.keys()),
                                       template_columns=selected_columns,
                                       template_filters=None)
            
            columns_json = json.dumps(selected_columns)

            try:
                with conn.cursor() as write_cursor:
                    sql = "UPDATE query_templates SET name = %s, description = %s, columns = %s, filters = %s WHERE id = %s"
                    data = (template_name, template_description, columns_json, filters_json, template_id)
                    write_cursor.execute(sql, data)
                conn.commit()

                log_activity(
                    action="Edición de Plantilla",
                    category="Plantillas",
                    resource_id=template_id,
                    details=f"Usuario '{current_user.username}' actualizó la plantilla: {template_name}"
                )
                flash(f"Plantilla '{template_name}' actualizada exitosamente.", 'success')
                return redirect(url_for('plantillas.ver_plantillas'))
            
            except (mysql.connector.IntegrityError, pymysql.err.IntegrityError):
                flash(f"Error: Ya existe otra plantilla con el nombre '{template_name}'.", 'danger')
            except Exception as e:
                flash(f"Error al actualizar la plantilla: {e}", 'danger')

        # --- Lógica para GET (o si el POST falla y re-renderiza) ---
        template_columns = json.loads(template['columns']) if template.get('columns') else []
        
        # --- LÓGICA CORREGIDA PARA CARGAR FILTROS ---
        template_filters_raw = template.get('filters')
        if not template_filters_raw or template_filters_raw == '{}':
            template_filters = None # Pasa None para que JS use el default
        else:
            try:
                template_filters = json.loads(template_filters_raw)
            except json.JSONDecodeError:
                template_filters = None # Si el JSON está corrupto, usa el default
        
        return render_template('plantillas/plantilla_form.html',
                               is_edit=True,
                               template=template,
                               columns=list(AVAILABLE_COLUMNS.keys()), # <-- CORREGIDO
                               template_columns=template_columns,
                               template_filters=template_filters)

    except Exception as e:
        flash(f"Error al cargar/editar la plantilla: {e}", 'danger')
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close()


# --- 5. RUTA DE VISTA PREVIA (CORREGIDA) ---
@plantillas_bp.route('/preview_query', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def preview_query():
    """
    Genera una vista previa de la consulta uniendo Bienes, Resguardos y Areas.
    Maneja la carga de imágenes de almacenamiento local.
    """
    data = request.get_json()
    columns = data.get('columns', []) 
    filters_data = data.get('filters', {}) 

    conn = None
    try:
        # --- 1. Separar Columnas SQL de Columnas Especiales (Imágenes) ---
        safe_columns_clauses = []
        special_columns = [] # Aquí guardaremos si piden 'imagenPath_bien' o 'resguardo'

        # Aseguramos que siempre traemos los IDs para poder buscar las imágenes después
        if 'id_bien' not in columns:
            safe_columns_clauses.append("bienes.id AS `id_bien_hidden`")
        if 'id_resguardo' not in columns:
            safe_columns_clauses.append("resguardos.id AS `id_resguardo_hidden`")

        for user_name in columns:
            if user_name in AVAILABLE_COLUMNS:
                sql_name = AVAILABLE_COLUMNS[user_name]
                
                if sql_name is None:
                    # Es una columna especial (imagen), no la ponemos en el SQL
                    special_columns.append(user_name)
                else:
                    # Es una columna normal de la BD
                    safe_columns_clauses.append(f"{sql_name} AS `{user_name}`")

        if not safe_columns_clauses:
            return jsonify([])

        safe_columns_str = ", ".join(safe_columns_clauses)

        # --- 2. Construir Cláusula WHERE (tu función existente) ---
        where_sql, where_params = build_where_clause(filters_data)
        
        # --- 3. Construir Consulta SQL Principal ---
        query = f"SELECT {safe_columns_str} FROM bienes"
        query += " LEFT JOIN resguardos ON bienes.id = resguardos.id_bien"
        query += " LEFT JOIN areas ON resguardos.id_area = areas.id"
        
        if where_sql:
            query += f" WHERE {where_sql}"
        
        query += " LIMIT 50" 

        # --- 4. Ejecutar Consulta Principal ---
        conn = get_db_connection()
        # Usamos DictCursor para poder manipular el diccionario de resultados
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(query, where_params)
        results = cursor.fetchall()

        if not results:
            return jsonify([])

        # --- 5. POST-PROCESAMIENTO: Inyectar Imágenes Locales ---
        
        # A) Imágenes de Bienes
        if 'imagenPath_bien' in special_columns:
            # Recolectar IDs de bienes de los resultados (usando el alias o el hidden)
            bien_ids = set()
            for row in results:
                # Intentar obtener ID de la columna seleccionada o de la oculta
                bid = row.get('id_bien') or row.get('id_bien_hidden')
                if bid:
                    bien_ids.add(str(bid))
            
            if bien_ids:
                format_strings = ','.join(['%s'] * len(bien_ids))
                # Usamos GROUP_CONCAT para traer todas las rutas separadas por coma
                sql_img = f"""
                    SELECT id_bien, GROUP_CONCAT(ruta_imagen) as rutas 
                    FROM imagenes_bien 
                    WHERE id_bien IN ({format_strings}) 
                    GROUP BY id_bien
                """
                cursor.execute(sql_img, tuple(bien_ids))
                
                # Crear mapa: { id_bien: ['url1', 'url2'] }
                mapa_imagenes_bien = {}
                for row in cursor.fetchall():
                    rutas = row['rutas'].split(',') if row['rutas'] else []
                    # Convertir rutas físicas en URLs usando la función universal 'serve_uploaded_file'
                    # Nota: 'serve_uploaded_file' debe estar definida en app.py y accesible via 'url_for'
                    urls = [url_for('serve_uploaded_file', filename=r) for r in rutas]
                    mapa_imagenes_bien[row['id_bien']] = urls

                # Asignar al resultado final
                for row in results:
                    bid = row.get('id_bien') or row.get('id_bien_hidden')
                    # Insertamos la lista de URLs o una lista vacía
                    row['imagenPath_bien'] = mapa_imagenes_bien.get(bid, [])

        # B) Imágenes de Resguardos
        if 'imagenPath_resguardo' in special_columns:
            res_ids = set()
            for row in results:
                rid = row.get('id_resguardo') or row.get('id_resguardo_hidden')
                if rid:
                    res_ids.add(str(rid))
            
            if res_ids:
                format_strings = ','.join(['%s'] * len(res_ids))
                sql_img = f"""
                    SELECT id_resguardo, GROUP_CONCAT(ruta_imagen) as rutas 
                    FROM imagenes_resguardo 
                    WHERE id_resguardo IN ({format_strings}) 
                    GROUP BY id_resguardo
                """
                cursor.execute(sql_img, tuple(res_ids))
                
                mapa_imagenes_res = {}
                for row in cursor.fetchall():
                    rutas = row['rutas'].split(',') if row['rutas'] else []
                    urls = [url_for('serve_uploaded_file', filename=r) for r in rutas]
                    mapa_imagenes_res[row['id_resguardo']] = urls

                for row in results:
                    rid = row.get('id_resguardo') or row.get('id_resguardo_hidden')
                    row['imagenPath_resguardo'] = mapa_imagenes_res.get(rid, [])

        # --- 6. Limpieza (Opcional): Quitar columnas hidden ---
        for row in results:
            row.pop('id_bien_hidden', None)
            row.pop('id_resguardo_hidden', None)
        return jsonify(results)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error al construir la consulta: {str(e)}"}), 500
    finally:
        if conn:
            cursor.close()
            conn.close()

@plantillas_bp.route('/ver_plantillas')
@login_required
@permission_required('resguardos.crear_resguardo')
def ver_plantillas():
    """Ruta para ver todas las plantillas de consulta guardadas."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("SELECT id, name, description FROM query_templates ORDER BY name")
        templates = cursor.fetchall()
        return render_template('ver_plantillas.html', templates=templates)
    except Exception as e:
        flash(f"Error al cargar las plantillas: {e}", 'danger')
        return redirect(url_for('index'))
    finally:
        if conn:
            conn.close()

@plantillas_bp.route('/eliminar_plantilla/<int:template_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def eliminar_plantilla(template_id):
    """Ruta para eliminar una plantilla de consulta."""
    conn = None
    template_name = f"ID {template_id}" # Valor por defecto por si falla la consulta
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # --- AÑADIDO: Obtener el nombre ANTES de borrar ---
        cursor.execute("SELECT name FROM query_templates WHERE id = %s", (template_id,))
        template = cursor.fetchone()
        if template:
            template_name = template['name']
        # --- FIN AÑADIDO ---

        # Cambiar a cursor normal para DELETE
        cursor = conn.cursor() 
        cursor.execute("DELETE FROM query_templates WHERE id = %s", (template_id,))
        conn.commit()

        # --- AÑADIDO: Log de actividad ---
        log_activity(
            action="Eliminación de Plantilla",
            category="Plantillas",
            resource_id=template_id,
            details=f"Usuario '{current_user.username}' eliminó la plantilla: {template_name}"
        )
        # --- FIN AÑADIDO ---

        flash("Plantilla eliminada exitosamente.", 'success')
    except Exception as e:
        flash(f"Error al eliminar la plantilla: {e}", 'danger')
    finally:
        if conn:
            conn.close()
    return redirect(url_for('plantillas.ver_plantillas'))

@plantillas_bp.route('/exportar_excel/<int:template_id>')
@login_required
@permission_required('resguardos.crear_resguardo')
def exportar_excel(template_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 1. Obtener la plantilla
        cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,))
        template = cursor.fetchone()
        
        if not template:
            flash("Plantilla no encontrada.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))

        # 2. Obtener carpeta base local (Donde están guardadas las fotos realmente)
        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            flash("Error de configuración: UPLOAD_FOLDER no definido.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))

        # 3. Obtener configuración de columnas y filtros
        selected_columns = json.loads(template['columns']) if template['columns'] else []
        filters = json.loads(template['filters']) if template['filters'] else []

        # 4. Obtener los datos (Esta función devuelve URLs relativas, ej: /uploads/bienes/foto.jpg)
        filtered_data, max_bien_images, max_resguardo_images = get_filtered_resguardo_data(selected_columns, filters)

        if not filtered_data:
            flash("No hay datos para exportar con esos filtros.", 'warning')
            return redirect(url_for('plantillas.ver_plantillas'))

        # 5. Aplanar las listas de imágenes en columnas individuales para el DataFrame
        for row in filtered_data:
            if 'imagenPath_bien' in row and row['imagenPath_bien']:
                for i, path in enumerate(row['imagenPath_bien']):
                    if i < max_bien_images:
                        row[f'imagen_bien_{i+1}'] = path
            if 'imagenPath_resguardo' in row and row['imagenPath_resguardo']:
                for i, path in enumerate(row['imagenPath_resguardo']):
                    if i < max_resguardo_images:
                        row[f'imagen_resguardo_{i+1}'] = path
        
        # Crear DataFrame y Buffer de Excel
        df = pd.DataFrame(filtered_data)
        excel_file_buffer = BytesIO()

        with pd.ExcelWriter(excel_file_buffer, engine='xlsxwriter') as writer:
            sheet_name = template['name'][:30] if template['name'] else 'Reporte' # Excel limita nombre a 31 chars
            workbook = writer.book
            worksheet = workbook.add_worksheet(sheet_name) 

            # Formatos
            header_format = workbook.add_format({'bg_color': '#4A90E2', 'font_color': 'white', 'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
            data_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
            image_cell_format = workbook.add_format({'align': 'center', 'valign': 'top', 'border': 1})

            # Definir orden de columnas
            all_columns_in_order = [col for col in selected_columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
            for i in range(max_bien_images):
                all_columns_in_order.append(f'imagen_bien_{i+1}')
            for i in range(max_resguardo_images):
                all_columns_in_order.append(f'imagen_resguardo_{i+1}')
            
            # Escribir Encabezados
            for col_num, column_name in enumerate(all_columns_in_order):
                display_name = column_name.replace('_', ' ').title()
                if column_name.startswith('imagen_bien_'):
                    display_name = f'Img Bien {column_name.split("_")[2]}'
                elif column_name.startswith('imagen_resguardo_'):
                    display_name = f'Img Resguardo {column_name.split("_")[2]}'
                worksheet.write(0, col_num, display_name, header_format)

            # Configuración de altura de filas para imágenes
            image_row_height = 120
            worksheet.set_default_row(30) # Altura por defecto para filas de texto

            # --- BUCLE PRINCIPAL DE FILAS ---
            for row_num, row_data in enumerate(filtered_data):
                excel_row = row_num + 1
                
                # Verificar si esta fila tiene imágenes para ajustar altura
                has_images = any(row_data.get(col) for col in [f'imagen_bien_{i+1}' for i in range(max_bien_images)] + [f'imagen_resguardo_{i+1}' for i in range(max_resguardo_images)])
                if has_images:
                    worksheet.set_row(excel_row, image_row_height)

                # --- BUCLE DE COLUMNAS ---
                for col_num, col_name in enumerate(all_columns_in_order):
                    value = row_data.get(col_name, '')
                    
                    # ==========================================================
                    # 📸 LÓGICA DE INSERCIÓN DE IMÁGENES LOCALES
                    # ==========================================================
                    if col_name.startswith('imagen_'):
                        if value: 
                            try:
                                # 1. Limpiar la URL para obtener la ruta relativa
                                # El valor viene como: "/uploads/bienes/foto.jpg" -> queremos "bienes/foto.jpg"
                                url_str = str(value)
                                if '/uploads/' in url_str:
                                    relative_path = url_str.split('/uploads/')[-1]
                                else:
                                    relative_path = url_str.lstrip('/')

                                # Decodificar caracteres raros (%20 -> espacio)
                                relative_path = urllib.parse.unquote(relative_path)

                                # 2. Construir la ruta absoluta en el servidor
                                full_path = os.path.join(base_upload_folder, relative_path)
                                
                                # 3. Verificar extensión (Excel no soporta incrustar PDF)
                                _, ext = os.path.splitext(full_path)
                                if ext.lower() == '.pdf':
                                    worksheet.write(excel_row, col_num, 'Archivo PDF (No visualizable)', data_format)
                                    continue 

                                # 4. Verificar existencia física
                                if os.path.exists(full_path):
                                    
                                    # Abrir imagen en bytes para procesar
                                    with open(full_path, 'rb') as f:
                                        image_data = f.read()
                                    
                                    image_buffer = io.BytesIO(image_data)
                                    
                                    # Usar Pillow para obtener dimensiones y evitar errores de formato
                                    try:
                                        img = Image.open(image_buffer)
                                        width, height = img.size
                                    except Exception:
                                        worksheet.write(excel_row, col_num, 'Formato img inválido', data_format)
                                        continue

                                    # Calcular escala para que quepa en la celda (aprox 200x120 px)
                                    # Unidades de excel aprox: width 25 ~ 180px, height 120 ~ 160px
                                    x_scale = 180 / width
                                    y_scale = 150 / height
                                    scale = min(x_scale, y_scale, 1.0) # Mantener proporción y no agrandar

                                    # Insertar en Excel
                                    worksheet.insert_image(
                                        excel_row, col_num, 
                                        full_path, 
                                        {
                                            'image_data': image_buffer, 
                                            'x_scale': scale, 
                                            'y_scale': scale, 
                                            'x_offset': 5, 
                                            'y_offset': 5,
                                            'object_position': 1 # Mover y cambiar tamaño con celdas
                                        }
                                    )
                                    worksheet.write(excel_row, col_num, '', image_cell_format) # Celda vacía formateada
                                
                                else:
                                    # El archivo está en BD pero no en disco
                                    print(f"EXCEL DEBUG: No encontrado -> {full_path}")
                                    worksheet.write(excel_row, col_num, 'Archivo no encontrado', data_format)

                            except Exception as e:
                                print(f"EXCEL ERROR en fila {excel_row}: {e}")
                                worksheet.write(excel_row, col_num, 'Error al procesar', data_format)
                        else:
                            worksheet.write(excel_row, col_num, 'Sin imagen', data_format)
                    
                    # ==========================================================
                    # 📝 LÓGICA PARA DATOS NORMALES (TEXTO/NÚMEROS)
                    # ==========================================================
                    else:
                        worksheet.write(excel_row, col_num, value, data_format)

            # Ajustar ancho de columnas
            for col_num, col_name in enumerate(all_columns_in_order):
                if col_name.startswith('imagen_'):
                    worksheet.set_column(col_num, col_num, 25) # Ancho fijo para imágenes
                else:
                    worksheet.set_column(col_num, col_num, 20) # Ancho estándar para texto
        
        excel_file_buffer.seek(0)
        filename = f"reporte_{template['name'].replace(' ', '_')}.xlsx"
        
        log_activity("Exportación Excel", "Plantillas", resource_id=template_id, details=f"Exportada: {template['name']}")

        return send_file(
            excel_file_buffer, 
            download_name=filename, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            as_attachment=True
        )

    except Exception as e:
        flash(f"Error crítico al generar Excel: {str(e)}", 'danger')
        traceback.print_exc()
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close()

