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
    Función completa que construye y ejecuta una consulta SQL dinámica,
    incluyendo la lógica para obtener y formatear las URLs de las imágenes.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        column_map = {
            'id': 'r', 'No_Resguardo': 'r', 'Tipo_De_Resguardo': 'r', 'Fecha_Resguardo': 'r',
            'No_Trabajador': 'r', 'Puesto_Trabajador': 'r', 'No_Nomina_Trabajador': 'r',
            'Nombre_Del_Resguardante': 'r', 'Nombre_Director_Jefe_De_Area': 'r', 'Activo': 'r',
            'No_Inventario': 'b', 'No_Factura': 'b', 'No_Cuenta': 'b', 'Proveedor': 'b',
            'Descripcion_Del_Bien': 'b', 'Descripcion_Corta_Del_Bien': 'b', 'Rubro': 'b',
            'Poliza': 'b', 'Fecha_Poliza': 'b', 'Sub_Cuenta_Armonizadora': 'b',
            'Fecha_Factura': 'b', 'Costo_Inicial': 'b', 'Depreciacion_Acumulada': 'b',
            'Costo_Final': 'b', 'Cantidad': 'b', 'Estado_Del_Bien': 'b',
            'Marca': 'b', 'Modelo': 'b', 'Numero_De_Serie': 'b', 'Tipo_De_Alta': 'b',
            'Area': 'a'
        }
        
        data_columns = [col for col in selected_columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
        image_columns = [col for col in selected_columns if col in ['imagenPath_bien', 'imagenPath_resguardo']]
        
        select_clause = set()
        select_clause.add('r.id AS resguardo_id')
        select_clause.add('b.id AS bien_id')

        for col in data_columns:
            table_alias = column_map.get(col)
            if col == 'Area':
                select_clause.add('a.nombre AS Area')
            elif table_alias:
                select_clause.add(f'{table_alias}.`{col}`')
        
        if any(f.get('field') == 'Area' for f in filters):
            select_clause.add('a.nombre AS Area')
            
        select_string = ", ".join(list(select_clause))

        from_clause = "FROM resguardos r JOIN bienes b ON r.id_bien = b.id JOIN areas a ON r.id_area = a.id"
        
        where_clauses = []
        sql_params = []
        
        for f in filters:
            field, operator, value = f.get('field'), f.get('operator'), f.get('value')
            if not all([field, operator, value]): 
                continue
            
            sql_operator = map_operator_to_sql(operator)
            if not sql_operator: 
                continue

            if field == 'Area':
                where_clauses.append(f"(a.id = %s OR a.nombre LIKE %s OR a.numero LIKE %s)")
                sql_params.extend([value, f"%{value}%", f"%{value}%"])
            else:
                table_alias = column_map.get(field)
                if not table_alias: 
                    continue
                
                where_clauses.append(f"{table_alias}.`{field}` {sql_operator} %s")
                if operator == 'contains':
                    sql_params.append(f"%{value}%")
                else:
                    sql_params.append(value)

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

        # --- LÓGICA DE IMÁGENES (RESTAURADA Y COMPLETA) ---
        if 'imagenPath_bien' in image_columns:
            bien_ids = [str(row['bien_id']) for row in results if row.get('bien_id')]
            if bien_ids:
                placeholders = ','.join(['%s'] * len(bien_ids))
                cursor.execute(f"SELECT id_bien, GROUP_CONCAT(ruta_imagen) as imagenes FROM imagenes_bien WHERE id_bien IN ({placeholders}) GROUP BY id_bien", bien_ids)
                bien_images = {row['id_bien']: row['imagenes'].split(',') for row in cursor.fetchall() if row['imagenes']}
                for row in results:
                    filenames = bien_images.get(row.get('bien_id'), [])
                    row['imagenPath_bien'] = [url_for('serve_uploaded_file', filename=f) for f in filenames]

        if 'imagenPath_resguardo' in image_columns:
            resguardo_ids = [str(row['resguardo_id']) for row in results if row.get('resguardo_id')]
            if resguardo_ids:
                placeholders = ','.join(['%s'] * len(resguardo_ids))
                cursor.execute(f"SELECT id_resguardo, GROUP_CONCAT(ruta_imagen) as imagenes FROM imagenes_resguardo WHERE id_resguardo IN ({placeholders}) GROUP BY id_resguardo", resguardo_ids)
                resguardo_images = {row['id_resguardo']: row['imagenes'].split(',') for row in cursor.fetchall() if row['imagenes']}
                for row in results:
                    filenames = resguardo_images.get(row.get('resguardo_id'), [])
                    row['imagenPath_resguardo'] = [url_for('serve_uploaded_file', filename=f) for f in filenames]

        return results, len(results), len(results)
        
    except Exception as e:
        traceback.print_exc()
        return [], 0, 0
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
            if conn: conn.close()

    # Renderiza la nueva plantilla unificada en modo "crear"
    return render_template('plantillas/plantilla_form.html', 
                           is_edit=False, 
                           template={},
                           columns=AVAILABLE_COLUMNS,
                           template_columns=[],
                           template_filters=[])


@plantillas_bp.route('/editar_plantilla/<int:template_id>', methods=['GET', 'POST'])
@login_required
@permission_required('plantillas.editar_plantilla')
def editar_plantilla(template_id):
    """Ruta para editar una plantilla de consulta existente."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,))
        template = cursor.fetchone()

        if not template:
            flash("Plantilla no encontrada.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))
        
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
        
        # Renderiza la nueva plantilla unificada en modo "editar"
        return render_template('plantillas/plantilla_form.html',
                               is_edit=True,
                               template=template,
                               columns=AVAILABLE_COLUMNS,
                               template_columns=template_columns,
                               template_filters=template_filters)

    except Exception as e:
        flash(f"Error al cargar/editar la plantilla: {e}", 'danger')
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn and conn.is_connected():
            conn.close()

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

        # --- BLOQUE DE CORRECCIÓN: TRANSFORMA LAS LISTAS DE IMÁGENES ---
        for row in filtered_data:
            if 'imagenPath_bien' in row and row['imagenPath_bien']:
                for i, path in enumerate(row['imagenPath_bien']):
                    row[f'imagen_bien_{i+1}'] = path
            if 'imagenPath_resguardo' in row and row['imagenPath_resguardo']:
                for i, path in enumerate(row['imagenPath_resguardo']):
                    row[f'imagen_resguardo_{i+1}'] = path
        # --- FIN DEL BLOQUE DE CORRECCIÓN ---

        df = pd.DataFrame(filtered_data)
        
        excel_file_buffer = BytesIO()

        with pd.ExcelWriter(excel_file_buffer, engine='xlsxwriter') as writer:
            # ... (el resto de tu código para generar el Excel no necesita cambios)
            # Ahora funcionará porque encontrará las columnas 'imagen_resguardo_1', etc.
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
                                # Corrección para construir la ruta de la imagen de forma segura
                                filename = os.path.basename(str(value))
                                # La ruta en la BD puede tener '/uploads/', lo quitamos si UPLOAD_FOLDER ya lo tiene.
                                relative_path = str(value).lstrip('/uploads').lstrip('/')
                                image_path = os.path.join(UPLOAD_FOLDER, relative_path)
                                
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

            # ... resto del código para ajustar ancho de columnas
            for col_num, col_name in enumerate(all_columns_in_order):
                if col_name.startswith('imagen_'):
                    worksheet.set_column(col_num, col_num, 25)
                else:
                    max_len = 0
                    if col_name in df.columns:
                        # Asegurar que no haya valores nulos que causen error en .map(len)
                        max_len = max(len(str(col_name)), df[col_name].dropna().astype(str).map(len).max()) if not df[col_name].dropna().empty else len(str(col_name))
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
        results, _, _ = get_filtered_resguardo_data(columns, filters, limit=100)
        return jsonify(results)
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Ocurrió un error inesperado. Detalle: {e}"}), 500