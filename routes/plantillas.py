from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user # Asume que tienes Flask-Login configurado
import mysql.connector
import os
import traceback
import json
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO
from PIL import Image
from config import UPLOAD_FOLDER, AVAILABLE_COLUMNS # Asegúrate de que estos archivos existan
from database import get_db_connection # Asegúrate de que este archivo exista
from helpers import map_operator_to_sql
from log_activity import log_activity # Asegúrate de que este archivo exista
from decorators import permission_required # Asume que este decorador existe

plantillas_bp = Blueprint('plantillas', __name__)

# =================================================================
# FUNCIÓN CENTRALIZADA PARA OBTENER DATOS CON FILTROS E IMÁGENES
# =================================================================
def get_filtered_resguardo_data(selected_columns, filters, limit=None):
    """
    Función que construye y ejecuta una consulta SQL dinámica
    basada en columnas y filtros seleccionados.
    
    Retorna: una lista de diccionarios con los resultados y el número 
             máximo de imágenes por bien y resguardo.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Mapeo de columnas a sus tablas para construir la consulta
        column_map = {
            'id': 'r', 'No_Resguardo': 'r', 'Tipo_De_Resguardo': 'r', 'Fecha_Resguardo': 'r',
            'No_Trabajador': 'r', 'Puesto_Trabajador': 'r', 'No_Nomina_Trabajador': 'r',
            'Nombre_Del_Resguardante': 'r', 'Nombre_Director_Jefe_De_Area': 'r', 'Activo': 'r',
            'No_Inventario': 'b', 'No_Factura': 'b', 'No_Cuenta': 'b', 'Proveedor': 'b',
            'Descripcion_Del_Bien': 'b', 'Descripcion_Corta_Del_Bien': 'b', 'Rubro': 'b',
            'Poliza': 'b', 'Fecha_Poliza': 'b', 'Sub_Cuenta_Armonizadora': 'b',
            'Fecha_Factura': 'b', 'Costo_Inicial': 'b', 'Depreciacion_Acumulada': 'b',
            'Costo_Final_Cantidad': 'b', 'Cantidad': 'b', 'Estado_Del_Bien': 'b',
            'Marca': 'b', 'Modelo': 'b', 'Numero_De_Serie': 'b', 'Tipo_De_Alta': 'b',
            'Area_Nombre': 'a'
        }
        
        # Separar columnas de datos de columnas de imágenes
        data_columns = [col for col in selected_columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
        image_columns = [col for col in selected_columns if col in ['imagenPath_bien', 'imagenPath_resguardo']]
        
        # Construir la cláusula SELECT
        select_clause = []
        for col in data_columns:
            table_alias = column_map.get(col)
            if col == 'Area_Nombre':
                select_clause.append('a.nombre AS Area_Nombre')
            elif table_alias:
                select_clause.append(f'{table_alias}.`{col}`')
        
        # Incluir IDs para las uniones si se necesitan imágenes
        if image_columns:
            select_clause.append('r.id AS resguardo_id')
            select_clause.append('b.id AS bien_id')
            
        select_string = ", ".join(select_clause)

        # Construir la cláusula FROM con los JOINs
        from_clause = """
            FROM resguardos r
            JOIN bienes b ON r.id_bien = b.id
            JOIN areas a ON r.id_area = a.id
        """
        
        # Construir la cláusula WHERE con los filtros
        where_clauses = []
        sql_params = []
        
        for f in filters:
            field = f.get('field')
            operator = f.get('operator')
            value = f.get('value')
            
            if not field or value is None or value == '':
                continue

            table_alias = column_map.get(field)
            if not table_alias:
                continue

            sql_operator = map_operator_to_sql(operator)
            if not sql_operator:
                continue
                
            if operator == 'contains':
                where_clauses.append(f"{table_alias}.`{field}` LIKE %s")
                sql_params.append(f"%{value}%")
            elif operator == 'not_contains':
                where_clauses.append(f"{table_alias}.`{field}` NOT LIKE %s")
                sql_params.append(f"%{value}%")
            elif operator == 'starts_with':
                where_clauses.append(f"{table_alias}.`{field}` LIKE %s")
                sql_params.append(f"{value}%")
            elif operator == 'ends_with':
                where_clauses.append(f"{table_alias}.`{field}` LIKE %s")
                sql_params.append(f"%{value}")
            elif field == 'Area_Nombre':
                where_clauses.append(f"a.nombre {sql_operator} %s")
                sql_params.append(value)
            else:
                where_clauses.append(f"{table_alias}.`{field}` {sql_operator} %s")
                sql_params.append(value)

        # Consulta final
        final_query = f"SELECT {select_string} {from_clause}"
        if where_clauses:
            final_query += " WHERE " + " AND ".join(where_clauses)
        
        final_query += " ORDER BY r.id DESC"
        if limit:
            final_query += f" LIMIT {limit}"

        cursor.execute(final_query, sql_params)
        results = cursor.fetchall()
        
        if not results:
            return [], 0, 0

        # Obtener imágenes si se solicitaron
        max_bien_images, max_resguardo_images = 0, 0
        
        if 'imagenPath_bien' in image_columns:
            bien_ids = [str(row['bien_id']) for row in results]
            if bien_ids:
                placeholders = ','.join(['%s'] * len(bien_ids))
                cursor.execute(f"SELECT id_bien, GROUP_CONCAT(ruta_imagen) as imagenes FROM imagenes_bien WHERE id_bien IN ({placeholders}) GROUP BY id_bien", bien_ids)
                bien_images = {row['id_bien']: row['imagenes'].split(',') for row in cursor.fetchall()}
                max_bien_images = max(len(v) for v in bien_images.values()) if bien_images else 0
                for row in results:
                    row['imagenPath_bien'] = bien_images.get(row['bien_id'], [])
                    for i, img_path in enumerate(row['imagenPath_bien']):
                        row[f'imagen_bien_{i+1}'] = img_path

        if 'imagenPath_resguardo' in image_columns:
            resguardo_ids = [str(row['resguardo_id']) for row in results]
            if resguardo_ids:
                placeholders = ','.join(['%s'] * len(resguardo_ids))
                cursor.execute(f"SELECT id_resguardo, GROUP_CONCAT(ruta_imagen) as imagenes FROM imagenes_resguardo WHERE id_resguardo IN ({placeholders}) GROUP BY id_resguardo", resguardo_ids)
                resguardo_images = {row['id_resguardo']: row['imagenes'].split(',') for row in cursor.fetchall()}
                max_resguardo_images = max(len(v) for v in resguardo_images.values()) if resguardo_images else 0
                for row in results:
                    row['imagenPath_resguardo'] = resguardo_images.get(row['resguardo_id'], [])
                    for i, img_path in enumerate(row['imagenPath_resguardo']):
                        row[f'imagen_resguardo_{i+1}'] = img_path

        # Limpiar resultados de campos temporales
        for row in results:
            row.pop('resguardo_id', None)
            row.pop('bien_id', None)

        return results, max_bien_images, max_resguardo_images
        
    except Exception as e:
        traceback.print_exc()
        raise e
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


@plantillas_bp.route('/crear_plantilla', methods=['GET', 'POST'])
@login_required
def crear_plantilla():
    """Ruta para crear y guardar una plantilla de consulta."""
    if request.method == 'POST':
        template_name = request.form.get('template_name')
        template_description = request.form.get('template_description')
        selected_columns = request.form.getlist('columns')
        
        filters = []
        filter_fields = request.form.getlist('filter_field[]')
        filter_operators = request.form.getlist('filter_operator[]')
        filter_values = request.form.getlist('filter_value[]')

        for i in range(len(filter_fields)):
            if filter_fields[i] and filter_operators[i] and filter_values[i]:
                filters.append({'field': filter_fields[i], 'operator': filter_operators[i], 'value': filter_values[i]})
        
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            columns_json = json.dumps(selected_columns)
            filters_json = json.dumps(filters)

            sql = "INSERT INTO query_templates (name, description, columns, filters) VALUES (%s, %s, %s, %s)"
            data_to_save = (template_name, template_description, columns_json, filters_json)

            cursor.execute(sql, data_to_save)
            conn.commit()

            flash(f"Plantilla '{template_name}' guardada exitosamente.", 'success')
            return redirect(url_for('plantillas.ver_plantillas'))

        except mysql.connector.IntegrityError:
            flash(f"Error: Ya existe una plantilla con el nombre '{template_name}'.", 'danger')
        except Exception as e:
            flash(f"Error al guardar la plantilla: {e}", 'danger')
        finally:
            if conn:
                conn.close()

    return render_template('crear_plantilla.html', columns=AVAILABLE_COLUMNS)


@plantillas_bp.route('/ver_plantillas')
@login_required
@permission_required('resguardos.crear_resguardo')
def ver_plantillas():
    """Ruta para ver todas las plantillas de consulta guardadas."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, description FROM query_templates ORDER BY name")
        templates = cursor.fetchall()
        return render_template('ver_plantillas.html', templates=templates)
    except Exception as e:
        flash(f"Error al cargar las plantillas: {e}", 'danger')
        return redirect(url_for('index'))
    finally:
        if conn:
            conn.close()


@plantillas_bp.route('/editar_plantilla/<int:template_id>', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def editar_plantilla(template_id):
    """Ruta para editar una plantilla de consulta existente."""
    conn = None
    template = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,))
        template = cursor.fetchone()

        if not template:
            flash("Plantilla no encontrada.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))

        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre")
        areas = cursor.fetchall()

        if request.method == 'POST':
            template_name = request.form.get('template_name')
            template_description = request.form.get('template_description')
            selected_columns = request.form.getlist('columns')
            filters = []
            filter_fields = request.form.getlist('filter_field[]')
            filter_operators = request.form.getlist('filter_operator[]')
            filter_values = request.form.getlist('filter_value[]')

            for i in range(len(filter_fields)):
                if filter_fields[i] and filter_operators[i] and filter_values[i]:
                    filters.append({'field': filter_fields[i], 'operator': filter_operators[i], 'value': filter_values[i]})

            columns_json = json.dumps(selected_columns)
            filters_json = json.dumps(filters)

            try:
                cursor.execute("UPDATE query_templates SET name = %s, description = %s, columns = %s, filters = %s WHERE id = %s", (template_name, template_description, columns_json, filters_json, template_id))
                conn.commit()
                flash(f"Plantilla '{template_name}' actualizada exitosamente.", 'success')
                return redirect(url_for('plantillas.ver_plantillas'))
            except mysql.connector.IntegrityError:
                flash(f"Error: Ya existe otra plantilla con el nombre '{template_name}'.", 'danger')
            except Exception as e:
                flash(f"Error al actualizar la plantilla: {e}", 'danger')

        template_columns = json.loads(template['columns']) if template['columns'] else []
        template_filters = json.loads(template['filters']) if template['filters'] else []
        
        # Generar datos de vista previa
        preview_data, _, _ = get_filtered_resguardo_data(template_columns, template_filters, limit=5)
        
        return render_template('editar_plantilla.html',
                               template=template,
                               columns=AVAILABLE_COLUMNS,
                               template_columns=template_columns,
                               template_filters=template_filters,
                               areas=areas,
                               preview_data=preview_data)

    except Exception as e:
        flash(f"Error al cargar/editar la plantilla: {e}", 'danger')
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close()

@plantillas_bp.route('/eliminar_plantilla/<int:template_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def eliminar_plantilla(template_id):
    """Ruta para eliminar una plantilla de consulta."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM query_templates WHERE id = %s", (template_id,))
        conn.commit()
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
    """Ruta para exportar los datos de una plantilla a Excel, incluyendo imágenes."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,))
        template = cursor.fetchone()
        
        if not template:
            flash("Plantilla no encontrada para exportar a Excel.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))

        selected_columns = json.loads(template['columns']) if template['columns'] else []
        filters = json.loads(template['filters']) if template['filters'] else []

        filtered_data, max_bien_images, max_resguardo_images = get_filtered_resguardo_data(selected_columns, filters)

        if not filtered_data:
            flash("No se encontraron datos para los filtros seleccionados.", 'warning')
            return redirect(url_for('plantillas.ver_plantillas'))
            
        # Crear DataFrame ANTES del bloque de escritura
        df = pd.DataFrame(filtered_data)
        
        excel_file_buffer = BytesIO()

        with pd.ExcelWriter(excel_file_buffer, engine='xlsxwriter') as writer:
            sheet_name = template['name'][:31] if template['name'] else 'Reporte'
            workbook = writer.book
            worksheet = workbook.add_worksheet(sheet_name) 

            # Formatos
            header_format = workbook.add_format({'bg_color': '#4A90E2', 'font_color': 'white', 'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
            data_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
            image_cell_format = workbook.add_format({'align': 'center', 'valign': 'top', 'border': 1})

            # Crear lista de todas las columnas para el Excel
            all_columns_in_order = [col for col in selected_columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
            for i in range(max_bien_images):
                all_columns_in_order.append(f'imagen_bien_{i+1}')
            for i in range(max_resguardo_images):
                all_columns_in_order.append(f'imagen_resguardo_{i+1}')
            
            # Escribir headers
            for col_num, column_name in enumerate(all_columns_in_order):
                display_name = column_name.replace('_', ' ').title()
                if column_name.startswith('imagen_bien_'):
                    display_name = f'Imagen Bien {column_name.split("_")[2]}'
                elif column_name.startswith('imagen_resguardo_'):
                    display_name = f'Imagen Resguardo {column_name.split("_")[2]}'
                worksheet.write(0, col_num, display_name, header_format)

            # Escribir datos e insertar imágenes
            image_row_height = 120
            worksheet.set_default_row(20)

            for row_num, row_data in enumerate(filtered_data):
                excel_row = row_num + 1
                has_images = any(row_data.get(col) for col in [f'imagen_bien_{i+1}' for i in range(max_bien_images)] + [f'imagen_resguardo_{i+1}' for i in range(max_resguardo_images)])
                if has_images:
                    worksheet.set_row(excel_row, image_row_height)

                for col_num, col_name in enumerate(all_columns_in_order):
                    value = row_data.get(col_name, '')
                    
                    if col_name.startswith('imagen_'):
                        if value:
                            try:
                                filename = os.path.basename(str(value))
                                image_path = os.path.join(UPLOAD_FOLDER, filename)
                                
                                if os.path.exists(image_path):
                                    img = Image.open(image_path)
                                    img_width, img_height = img.size
                                    cell_width_excel_units = 25
                                    cell_width_pixels = cell_width_excel_units * 7.5
                                    cell_height_pixels = 120 * 96/72
                                    x_scale = cell_width_pixels / img_width
                                    y_scale = cell_height_pixels / img_height
                                    scale_factor = min(x_scale, y_scale)

                                    worksheet.insert_image(
                                        excel_row, col_num, image_path,
                                        {'x_scale': scale_factor, 'y_scale': scale_factor, 'x_offset': 5, 'y_offset': 5}
                                    )
                                    worksheet.write(excel_row, col_num, '', image_cell_format)
                                else:
                                    worksheet.write(excel_row, col_num, f'No encontrada: {filename}', data_format)
                            except Exception as e:
                                print(f"Error inserting image {value}: {e}")
                                worksheet.write(excel_row, col_num, f'Error: {os.path.basename(str(value))}', data_format)
                        else:
                            worksheet.write(excel_row, col_num, 'Sin imagen', data_format)
                    else:
                        worksheet.write(excel_row, col_num, value, data_format)

            for col_num, col_name in enumerate(all_columns_in_order):
                if col_name.startswith('imagen_'):
                    worksheet.set_column(col_num, col_num, 25)
                else:
                    max_len = 0
                    if col_name in df.columns:
                        max_len = max(len(str(col_name)), df[col_name].astype(str).map(len).max())
                    else:
                        max_len = len(str(col_name))
                    worksheet.set_column(col_num, col_num, min(max_len + 2, 50))
        
        excel_file_buffer.seek(0)
        filename = f"reporte_{template['name'].replace(' ', '_')}.xlsx"
        log_activity("Se exporto una plantilla","Plantillas",details="Se exporto una plantilla excell",resource_id=template_id)
        return send_file(excel_file_buffer, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True)

    except Exception as e:
        flash(f"Error al generar el archivo Excel: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close()

@plantillas_bp.route('/preview_query', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def preview_query():
    data = request.get_json()
    columns = data.get('columns', [])
    filters = data.get('filters', [])

    try:
        results, _, _ = get_filtered_resguardo_data(columns, filters, limit=5)
        return jsonify(results)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Ocurrió un error inesperado. Detalle: {e}"}), 500