# your_flask_app/routes/resguardos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file,jsonify
from flask_login import login_required, current_user
import mysql.connector
import os
import traceback
from pypdf import PdfReader, PdfWriter
import pypdf.generic
from werkzeug.utils import secure_filename
import json
from config import AVAILABLE_COLUMNS
from database import get_db, get_db_connection, get_table_columns, get_filtered_resguardo_data
import pandas as pd
from io import BytesIO
plantillas_bp = Blueprint('plantillas', __name__)
from helpers import map_operator_to_sql
from decorators import permission_required
from config import UPLOAD_FOLDER
from PIL import Image
@plantillas_bp.route('/crear_plantilla', methods=['GET', 'POST'])
@login_required
def crear_plantilla():
    """
    Ruta para crear y guardar una plantilla de consulta.
    """
    if request.method == 'POST':
        # Obtener los datos del formulario
        template_name = request.form.get('template_name')
        template_description = request.form.get('template_description')
        selected_columns = request.form.getlist('columns')
        
        # Obtener los datos de los filtros dinámicos
        filters = []
        filter_fields = request.form.getlist('filter_field[]')
        filter_operators = request.form.getlist('filter_operator[]')
        filter_values = request.form.getlist('filter_value[]')

        for i in range(len(filter_fields)):
            if filter_fields[i] and filter_operators[i] and filter_values[i]:
                filters.append({
                    'field': filter_fields[i],
                    'operator': filter_operators[i],
                    'value': filter_values[i]
                })
        
        conn = None # Initialize conn to None for finally block
        try:
            conn = get_db_connection()
            cursor = conn.cursor() # <--- ¡Crea un cursor para ejecutar consultas!

            # Convertir las listas de Python a cadenas JSON para guardarlas en la base de datos
            columns_json = json.dumps(selected_columns)
            filters_json = json.dumps(filters)

            sql = """
                INSERT INTO query_templates (name, description, columns, filters)
                VALUES (%s, %s, %s, %s)
            """
            data_to_save = (template_name, template_description, columns_json, filters_json)

            cursor.execute(sql, data_to_save)
            conn.commit() # <--- ¡Confirma la transacción!

            flash(f"Plantilla '{template_name}' guardada exitosamente.", 'success')
            return redirect(url_for('plantillas.ver_plantillas'))

        except mysql.connector.IntegrityError:
            # Este error ocurre si intentas guardar un nombre de plantilla que ya existe
            flash(f"Error: Ya existe una plantilla con el nombre '{template_name}'.", 'danger')
        except Exception as e:
            # Captura cualquier otro error de la base de datos
            flash(f"Error al guardar la plantilla: {e}", 'danger')
        finally:
            if conn:
                conn.close() # <--- ¡Asegúrate de que la conexión se cierre!

    # Para una solicitud GET, renderizar el formulario
    return render_template('crear_plantilla.html', columns=AVAILABLE_COLUMNS)



# --- New Route: View All Templates (Corrected to use cursor) ---
@plantillas_bp.route('/ver_plantillas')
@login_required
@permission_required('resguardos.crear_resguardo')
def ver_plantillas():
    """
    Ruta para ver todas las plantillas de consulta guardadas.
    """
    conn = None # Initialize conn to None for finally block
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # <--- Create a cursor here! Use dictionary=True for named access
        cursor.execute("SELECT id, name, description FROM query_templates ORDER BY name")
        templates = cursor.fetchall() # <--- Call fetchall() on the cursor!
        return render_template('ver_plantillas.html', templates=templates)
    except Exception as e:
        flash(f"Error al cargar las plantillas: {e}", 'danger')
        return redirect(url_for('index')) # Or render an error page
    finally:
        if conn:
            conn.close() # Ensure connection is closed


@plantillas_bp.route('/editar_plantilla/<int:template_id>', methods=['GET', 'POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def editar_plantilla(template_id):
    """
    Ruta para editar una plantilla de consulta existente.
    """
    conn = None
    template = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Fetch template data
        cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,))
        template = cursor.fetchone()

        if not template:
            flash("Plantilla no encontrada.", 'danger')
            return redirect(url_for('plantillas.ver_plantillas'))

        # Fetch areas
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
                    filters.append({
                        'field': filter_fields[i],
                        'operator': filter_operators[i],
                        'value': filter_values[i]
                    })

            columns_json = json.dumps(selected_columns)
            filters_json = json.dumps(filters)

            try:
                cursor.execute(
                    """UPDATE query_templates
                       SET name = %s, description = %s, columns = %s, filters = %s
                       WHERE id = %s""",
                    (template_name, template_description, columns_json, filters_json, template_id)
                )
                conn.commit()

                flash(f"Plantilla '{template_name}' actualizada exitosamente.", 'success')
                return redirect(url_for('plantillas.ver_plantillas'))
            except mysql.connector.IntegrityError:
                flash(f"Error: Ya existe otra plantilla con el nombre '{template_name}'.", 'danger')
            except Exception as e:
                flash(f"Error al actualizar la plantilla: {e}", 'danger')

        template_columns = json.loads(template['columns']) if template['columns'] else []
        template_filters = json.loads(template['filters']) if template['filters'] else []
        print(template_columns)
        # Generar datos de vista previa para mostrar imágenes
        preview_data = []
        if template_columns:
            try:
                # Obtener datos de muestra para la vista previa
                cursor.execute("SELECT * FROM resguardos WHERE activo = TRUE LIMIT 5")
                sample_resguardos = cursor.fetchall()
                
                if sample_resguardos:
                    resguardo_ids = [str(r['id']) for r in sample_resguardos]
                    bien_ids = [str(r['id_bien']) for r in sample_resguardos]

                    # Obtener imágenes de bienes
                    bien_images = {}
                    if 'imagenPath_bien' in template_columns and bien_ids:
                        placeholders = ','.join(['%s'] * len(bien_ids))
                        cursor.execute(f"""
                            SELECT id_bien, GROUP_CONCAT(ruta_imagen) as imagenes 
                            FROM imagenes_bien 
                            WHERE id_bien IN ({placeholders})
                            GROUP BY id_bien
                        """, bien_ids)
                        for row in cursor.fetchall():
                            bien_images[row['id_bien']] = row['imagenes'].split(',') if row['imagenes'] else []

                    # Obtener imágenes de resguardos
                    resguardo_images = {}
                    if 'imagenPath_resguardo' in template_columns and resguardo_ids:
                        placeholders = ','.join(['%s'] * len(resguardo_ids))
                        cursor.execute(f"""
                            SELECT id_resguardo, GROUP_CONCAT(ruta_imagen) as imagenes 
                            FROM imagenes_resguardo 
                            WHERE id_resguardo IN ({placeholders})
                            GROUP BY id_resguardo
                        """, resguardo_ids)
                        for row in cursor.fetchall():
                            resguardo_images[row['id_resguardo']] = row['imagenes'].split(',') if row['imagenes'] else []

                    # Crear datos de vista previa
                    for resguardo in sample_resguardos:
                        item = {}
                        for col in template_columns:
                            if col == 'imagenPath_bien':
                                item[col] = bien_images.get(resguardo['id_bien'], [])
                            elif col == 'imagenPath_resguardo':
                                item[col] = resguardo_images.get(resguardo['id'], [])
                            else:
                                item[col] = resguardo.get(col, '')
                        preview_data.append(item)

            except Exception as e:
                print(f"Error generating preview data: {e}")
                # Datos de ejemplo si hay error
                preview_data = [{'imagenPath_bien': ['uploads/example-bien.jpg'], 
                               'imagenPath_resguardo': ['uploads/example-resguardo.jpg']}]

        return render_template('editar_plantilla.html',
                               template=template,
                               columns=AVAILABLE_COLUMNS,
                               template_columns=template_columns,
                               template_filters=template_filters,
                               areas=areas,
                               preview_data=preview_data,  # Pasar datos de vista previa
                               imagenes_bien_db=[],
                               imagenes_resguardo_db=[])

    except Exception as e:
        flash(f"Error al cargar/editar la plantilla: {e}", 'danger')
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close()

# --- New Route: Delete Template (Optional but recommended) ---
@plantillas_bp.route('/eliminar_plantilla/<int:template_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def eliminar_plantilla(template_id):
    """
    Ruta para eliminar una plantilla de consulta.
    """
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM query_templates WHERE id = ?", (template_id,)) # Use %s for MySQL
        conn.commit()
        flash("Plantilla eliminada exitosamente.", 'success')
    except Exception as e:
        flash(f"Error al eliminar la plantilla: {e}", 'danger')
    finally:
        conn.close()
    return redirect(url_for('plantillas.ver_plantillas'))


@plantillas_bp.route('/exportar_excel/<int:template_id>')
@login_required
@permission_required('resguardos.crear_resguardo')
def exportar_excel(template_id):
    """
    Ruta para exportar los datos de una plantilla a Excel, incluyendo imágenes.
    """
    conn = None
    template = None

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

        print(f"Selected columns: {selected_columns}")
        print(f"Filters: {filters}")

        # Obtener datos con información de imágenes
        filtered_data, max_bien_images, max_resguardo_images = get_filtered_resguardo_data(selected_columns, filters)

        if not filtered_data:
            flash("No se encontraron datos para los filtros seleccionados.", 'warning')
            return redirect(url_for('plantillas.ver_plantillas'))

        # Configurar la ruta de uploads (la misma que usas en toda la aplicación)
        
        
        # Crear lista de todas las columnas para el Excel
        all_columns = []
        
        # Columnas de datos normales
        data_columns = [col for col in selected_columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
        all_columns.extend(data_columns)
        
        # Columnas de imágenes de bienes
        image_bien_columns = []
        for i in range(max_bien_images):
            col_name = f'imagen_bien_{i+1}'
            image_bien_columns.append(col_name)
        all_columns.extend(image_bien_columns)
        
        # Columnas de imágenes de resguardos
        image_resguardo_columns = []
        for i in range(max_resguardo_images):
            col_name = f'imagen_resguardo_{i+1}'
            image_resguardo_columns.append(col_name)
        all_columns.extend(image_resguardo_columns)

        # Crear DataFrame
        df_data = []
        for row in filtered_data:
            row_dict = {}
            for col in all_columns:
                row_dict[col] = row.get(col, '')
            df_data.append(row_dict)
        
        df = pd.DataFrame(df_data)

        excel_file_buffer = BytesIO()

        with pd.ExcelWriter(excel_file_buffer, engine='xlsxwriter') as writer:
            sheet_name = template['name'][:31] if template['name'] else 'Reporte'
            workbook = writer.book
            worksheet = workbook.add_worksheet(sheet_name) 

            # Formatos
            header_format = workbook.add_format({
                'bg_color': '#4A90E2', 
                'font_color': 'white',
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            data_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            image_cell_format = workbook.add_format({
                'align': 'center',
                'valign': 'top', 
                'border': 1
            })

            # Escribir headers
            for col_num, column_name in enumerate(all_columns):
                display_name = column_name.replace('_', ' ').title()
                if column_name.startswith('imagen_bien_'):
                    display_name = f'Imagen Bien {column_name.split("_")[2]}'
                elif column_name.startswith('imagen_resguardo_'):
                    display_name = f'Imagen Resguardo {column_name.split("_")[2]}'
                worksheet.write(0, col_num, display_name, header_format)

            # Configurar altura de filas para imágenes
            image_row_height = 120
            worksheet.set_default_row(20)

            # Escribir datos e insertar imágenes
            for row_num, row_data in enumerate(filtered_data):
                excel_row = row_num + 1

                # Ajustar altura de fila si hay imágenes
                has_images = any(row_data.get(col) for col in image_bien_columns + image_resguardo_columns)
                if has_images:
                    worksheet.set_row(excel_row, image_row_height)

                # Escribir datos e insertar imágenes
                for col_num, col_name in enumerate(all_columns):
                    value = row_data.get(col_name, '')
                    
                    if col_name in image_bien_columns or col_name in image_resguardo_columns:
                        if value:
                            try:
                                filename = os.path.basename(str(value))
                                image_path = os.path.join(UPLOAD_FOLDER, filename)
                                
                                if os.path.exists(image_path):
                                    # 1. Obtener dimensiones de la imagen
                                    img = Image.open(image_path)
                                    img_width, img_height = img.size

                                    # 2. Definir las dimensiones máximas de la celda
                                    # Ancho de la columna 25 (en unidades de Excel)
                                    cell_width_excel_units = 25 
                                    cell_width_pixels = cell_width_excel_units * 7.5 # Conversión aproximada
                                    
                                    # Altura de la fila 120 (en puntos)
                                    cell_height_pixels = 120 * 96/72 # Conversión a píxeles (72 ppp es el estándar para puntos)

                                    # 3. Calcular los factores de escala para ancho y alto
                                    x_scale = cell_width_pixels / img_width
                                    y_scale = cell_height_pixels / img_height
                                    
                                    # Usar el factor de escala más pequeño para que la imagen quepa dentro de la celda
                                    scale_factor = min(x_scale, y_scale)

                                    # 4. Insertar la imagen con las escalas calculadas
                                    worksheet.insert_image(
                                        excel_row, col_num, image_path,
                                        {
                                            'x_scale': scale_factor,
                                            'y_scale': scale_factor,
                                            'x_offset': 5,
                                            'y_offset': 5
                                        }
                                    )
                                    
                                    # Escribir nombre del archivo como texto también
                                    worksheet.write(excel_row, col_num, filename, image_cell_format)
                                else:
                                    worksheet.write(excel_row, col_num, f'No encontrada: {filename}', data_format)
                            except Exception as e:
                                print(f"Error inserting image {value}: {e}")
                                worksheet.write(excel_row, col_num, f'Error: {os.path.basename(str(value))}', data_format)
                        else:
                            worksheet.write(excel_row, col_num, 'Sin imagen', data_format)
                    else:
                        # Es una columna de datos normal
                        worksheet.write(excel_row, col_num, value, data_format)

            # Ajustar anchos de columnas
            for col_num, col_name in enumerate(all_columns):
                if col_name in image_bien_columns or col_name in image_resguardo_columns:
                    worksheet.set_column(col_num, col_num, 25)  # Ancho para columnas de imágenes
                else:
                    max_len = max(
                        len(str(col_name)),
                        df[col_name].astype(str).map(len).max() if col_name in df.columns else len(str(col_name))
                    )
                    worksheet.set_column(col_num, col_num, min(max_len + 2, 50))

        excel_file_buffer.seek(0)
        filename = f"reporte_{template['name'].replace(' ', '_')}.xlsx"
        return send_file(
            excel_file_buffer,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True
        )

    except Exception as e:
        flash(f"Error al generar el archivo Excel: {e}", 'danger')
        import traceback
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

    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "No se pudo conectar a la base de datos."}), 500
        
        cursor = conn.cursor(dictionary=True)
        
        if not columns:
            return jsonify({"error": "No se han seleccionado columnas para la vista previa."}), 400

        # Mapeo de columnas actualizado
        column_to_table = {
            # Columnas de la tabla 'resguardos'
            'id': 'r', 'id_bien': 'r', 'id_area': 'r', 'No_Resguardo': 'r',
            'Tipo_De_Resguardo': 'r', 'Fecha_Resguardo': 'r', 'No_Trabajador': 'r',
            'Puesto': 'r', 'Nombre_Director_Jefe_De_Area': 'r', 'Nombre_Del_Resguardante': 'r',
            'Fecha_Registro': 'r', 'Fecha_Ultima_Modificacion': 'r', 'Activo': 'r',
            # Columnas de la tabla 'bienes'
            'id_bien_b': 'b', 'No_Inventario': 'b', 'No_Factura': 'b', 'No_Cuenta': 'b',
            'Proveedor': 'b', 'Descripcion_Del_Bien': 'b', 'Descripcion_Corta_Del_Bien': 'b',
            'Rubro': 'b', 'Poliza': 'b', 'Fecha_Poliza': 'b',
            'Sub_Cuenta_Armonizadora': 'b', 'Fecha_Factura': 'b', 'Costo_Inicial': 'b',
            'Depreciacion_Acumulada': 'b', 'Costo_Final_Cantidad': 'b', 'Cantidad': 'b',
            'Estado_Del_Bien': 'b', 'Marca': 'b', 'Modelo': 'b', 'Numero_De_Serie': 'b',
            # Columnas de la tabla 'areas'
            'Area': 'a',
            'nombre_area': 'a', 'numero_area': 'a',
            # Columnas de imágenes
            'imagenPath_bien': 'special',
            'imagenPath_resguardo': 'special'
        }

        # Separar columnas normales de columnas de imágenes
        normal_columns = [col for col in columns if col not in ['imagenPath_bien', 'imagenPath_resguardo']]
        image_columns = [col for col in columns if col in ['imagenPath_bien', 'imagenPath_resguardo']]

        # DEBUG: Verificar qué columnas se están procesando
        print(f"Columnas normales: {normal_columns}")
        print(f"Columnas de imágenes: {image_columns}")

        # Renombrar columnas normales
        selected_columns = []
        for col in normal_columns:
            table_alias = column_to_table.get(col)
            if table_alias:
                if col == 'Area':
                    selected_columns.append(f"`a`.`nombre` AS `Area`")
                else:
                    selected_columns.append(f"`{table_alias}`.`{col}` AS `{col}`")
        print(selected_columns)
                
        # Asegurarse de incluir IDs necesarios para las imágenes
        if image_columns:
            selected_columns.append("r.id AS resguardo_id")
            selected_columns.append("b.id AS bien_id")

        if not selected_columns and not image_columns:
            return jsonify({"error": "No se han seleccionado columnas válidas."}), 400

        select_clause = ", ".join(selected_columns)
        
        # Consulta base con JOINs
        sql_query = f"""
            SELECT {select_clause}
            FROM resguardos AS r
            JOIN bienes AS b ON r.id_bien = b.id
            JOIN areas AS a ON r.id_area = a.id
        """
        
        where_clauses = []
        values = []
        
        for f in filters:
            field = f.get('field')
            operator = f.get('operator')
            value = f.get('value')
            
            if not field or value is None or value == '':
                continue

            # No aplicar filtros a columnas de imágenes especiales
            if field in ['imagenPath_bien', 'imagenPath_resguardo']:
                continue

            table_alias = column_to_table.get(field)
            if not table_alias:
                print(f"Advertencia: Campo de filtro '{field}' no mapeado.")
                continue
            
            # LÓGICA DE FILTRADO - USAR LA FUNCIÓN map_operator_to_sql
            sql_operator = map_operator_to_sql(operator)
            if not sql_operator:
                continue
                
            # Manejar diferentes tipos de operadores
            if operator == 'contains':
                where_clauses.append(f"`{table_alias}`.`{field}` LIKE %s")
                values.append(f"%{value}%")
            elif operator == 'not_contains':
                where_clauses.append(f"`{table_alias}`.`{field}` NOT LIKE %s")
                values.append(f"%{value}%")
            elif operator == 'starts_with':
                where_clauses.append(f"`{table_alias}`.`{field}` LIKE %s")
                values.append(f"{value}%")
            elif operator == 'ends_with':
                where_clauses.append(f"`{table_alias}`.`{field}` LIKE %s")
                values.append(f"%{value}")
            elif field == 'Area':
                try:
                    value = int(value)
                except ValueError:
                    return jsonify({"error": f"El valor para el filtro de Área no es un número válido: {value}"}), 400
                
                where_clauses.append(f"`a`.`id` {sql_operator} %s")
                values.append(value)
            else:
                where_clauses.append(f"`{table_alias}`.`{field}` {sql_operator} %s")
                values.append(value)
        
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
            
        sql_query += " LIMIT 100"

        print(f"Consulta SQL: {sql_query}")  # DEBUG
        print(f"Valores: {values}")  # DEBUG

        cursor.execute(sql_query, values)
        results = cursor.fetchall()

        # DEBUG: Verificar resultados iniciales
        print(f"Resultados iniciales: {results}")

        # Obtener imágenes si se solicitaron columnas de imágenes
        if image_columns and results:
            resguardo_ids = [str(row['resguardo_id']) for row in results]
            bien_ids = [str(row['bien_id']) for row in results]

            print(f"Resguardo IDs: {resguardo_ids}")  # DEBUG
            print(f"Bien IDs: {bien_ids}")  # DEBUG

            # Obtener imágenes de bienes
            bien_images = {}
            if 'imagenPath_bien' in image_columns and bien_ids:
                placeholders = ','.join(['%s'] * len(bien_ids))
                cursor.execute(f"""
                    SELECT id_bien, GROUP_CONCAT(ruta_imagen) as imagenes 
                    FROM imagenes_bien 
                    WHERE id_bien IN ({placeholders})
                    GROUP BY id_bien
                """, bien_ids)
                for row in cursor.fetchall():
                    bien_images[row['id_bien']] = row['imagenes'].split(',') if row['imagenes'] else []
                print(f"Imágenes de bienes: {bien_images}")  # DEBUG

            # Obtener imágenes de resguardos
            resguardo_images = {}
            if 'imagenPath_resguardo' in image_columns and resguardo_ids:
                placeholders = ','.join(['%s'] * len(resguardo_ids))
                cursor.execute(f"""
                    SELECT id_resguardo, GROUP_CONCAT(ruta_imagen) as imagenes 
                    FROM imagenes_resguardo 
                    WHERE id_resguardo IN ({placeholders})
                    GROUP BY id_resguardo
                """, resguardo_ids)
                for row in cursor.fetchall():
                    resguardo_images[row['id_resguardo']] = row['imagenes'].split(',') if row['imagenes'] else []
                print(f"Imágenes de resguardos: {resguardo_images}")  # DEBUG

            # Agregar imágenes a los resultados
            for row in results:
                if 'imagenPath_bien' in image_columns:
                    row['imagenPath_bien'] = bien_images.get(row['bien_id'], [])
                if 'imagenPath_resguardo' in image_columns:
                    row['imagenPath_resguardo'] = resguardo_images.get(row['resguardo_id'], [])

        # Eliminar campos temporales
        for row in results:
            row.pop('resguardo_id', None)
            row.pop('bien_id', None)

        print(f"Resultados finales: {results}")  # DEBUG
        return jsonify(results)
    
    except mysql.connector.Error as e:
        print(f"Error al ejecutar la consulta de vista previa: {e}")
        return jsonify({"error": f"Error al ejecutar la consulta de vista previa. Detalle: {e}"}), 500
    except Exception as e:
        print(f"Error inesperado: {e}")
        return jsonify({"error": f"Ocurrió un error inesperado. Detalle: {e}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()