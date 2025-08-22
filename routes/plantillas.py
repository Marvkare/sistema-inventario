# your_flask_app/routes/resguardos.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file,jsonify
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


@plantillas_bp.route('/crear_plantilla', methods=['GET', 'POST'])
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


# --- New Route: Edit Template (Modified to use cursor and correct placeholder) ---
@plantillas_bp.route('/editar_plantilla/<int:template_id>', methods=['GET', 'POST'])
def editar_plantilla(template_id):
    """
    Ruta para editar una plantilla de consulta existente.
    """
    conn = None # Initialize conn to None for finally block
    template = None # Initialize template to None

    try:
        conn = get_db_connection()
        # Create a cursor object for executing queries
        cursor = conn.cursor(dictionary=True) # Use dictionary=True for dict-like rows
        
        # --- FIX: Execute query on the cursor and use %s placeholder ---
        cursor.execute("SELECT * FROM query_templates WHERE id = %s", (template_id,)) 
        template = cursor.fetchone() # Fetch the result from the cursor
        # --- END FIX ---
        
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
                    filters.append({
                        'field': filter_fields[i],
                        'operator': filter_operators[i],
                        'value': filter_values[i]
                    })
            
            # Convert Python lists to JSON strings for database storage
            columns_json = json.dumps(selected_columns)
            filters_json = json.dumps(filters)

            try:
                # --- FIX: Execute UPDATE query on the cursor and use %s placeholder ---
                cursor.execute(
                    """UPDATE query_templates
                       SET name = %s, description = %s, columns = %s, filters = %s
                       WHERE id = %s""",
                    (template_name, template_description, columns_json, filters_json, template_id)
                )
                conn.commit()
                # --- END FIX ---
                
                flash(f"Plantilla '{template_name}' actualizada exitosamente.", 'success')
                return redirect(url_for('plantillas.ver_plantillas'))
            except mysql.connector.IntegrityError:
                flash(f"Error: Ya existe otra plantilla con el nombre '{template_name}'.", 'danger')
            except Exception as e:
                flash(f"Error al actualizar la plantilla: {e}", 'danger')
        
        # For GET request (and if POST failed before redirect)
        # --- FIX: Parse JSON strings from the database back into Python objects ---
        template_columns = json.loads(template['columns']) if template['columns'] else []
        template_filters = json.loads(template['filters']) if template['filters'] else []
        # --- END FIX ---

        return render_template('editar_plantilla.html', 
                               template=template, 
                               columns=AVAILABLE_COLUMNS,
                               template_columns=template_columns,
                               template_filters=template_filters)
    except Exception as e:
        flash(f"Error al cargar/editar la plantilla: {e}", 'danger')
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close() # Ensure connection is closed

# --- New Route: Delete Template (Optional but recommended) ---
@plantillas_bp.route('/eliminar_plantilla/<int:template_id>', methods=['POST'])
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
def exportar_excel(template_id):
    """
    Ruta para exportar los datos de una plantilla a Excel con estilo.
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

        filtered_data = get_filtered_resguardo_data(selected_columns, filters)

        if not filtered_data:
            df = pd.DataFrame(columns=selected_columns)
        else:
            df = pd.DataFrame(filtered_data)
            df = df[selected_columns] # Ensure correct column order and selection

        excel_file_buffer = BytesIO()

        # Create a Pandas ExcelWriter object using the 'xlsxwriter' engine
        with pd.ExcelWriter(excel_file_buffer, engine='xlsxwriter') as writer:
            # Write the DataFrame to a specific sheet
            sheet_name = template['name'] if template['name'] else 'Reporte'
            df.to_excel(writer, index=False, sheet_name=sheet_name)

            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # --- Define formats ---
            # Header format (Blue background, bold, white text, centered)
            header_format = workbook.add_format({
                'bg_color': '#4A90E2', # A shade of blue (you can choose any hex color)
                'font_color': 'white',
                'bold': True,
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })

            # Data format (Centered)
            data_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })

            # --- Apply header format ---
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format) # Row 0 is the header row

            # --- Apply data format to all cells below header ---
            # Loop through rows (starting from 1 for data) and columns
            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    worksheet.write(row_num, col_num, df.iloc[row_num - 1, col_num], data_format)

            # Optional: Adjust column widths for better readability
            for col_num, column_name in enumerate(df.columns):
                max_len = max(len(str(column_name)), df[column_name].astype(str).map(len).max())
                worksheet.set_column(col_num, col_num, max_len + 2) # Add a little extra padding

        excel_file_buffer.seek(0)

        filename = f"reporte_{template['name'].replace(' ', '_')}.xlsx"

        return send_file(excel_file_buffer,
                         download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True)

    except Exception as e:
        flash(f"Error al generar el archivo Excel: {e}", 'danger')
        # Log the full traceback for debugging in your development environment
        import traceback
        traceback.print_exc()
        return redirect(url_for('plantillas.ver_plantillas'))
    finally:
        if conn:
            conn.close()

@plantillas_bp.route('/preview_query', methods=['POST'])
def preview_query():
    """
    Executes a query based on the filters and columns passed from the frontend
    and returns the real data from the database.
    """
    data = request.get_json()
    columns = data.get('columns', [])
    filters = data.get('filters', [])

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "No se pudo conectar a la base de datos."}), 499
    cursor = conn.cursor(dictionary=True)
    
    try:
        if not columns:
            return jsonify({"error": "No se han seleccionado columnas para la vista previa."}), 399

        select_clause = ", ".join([f"`{col}`" for col in columns])
        sql_query = f"SELECT {select_clause} FROM resguardo"
        
        where_clauses = []
        values = []
        
        for f in filters:
            field = f.get('field')
            operator = f.get('operator')
            value = f.get('value')
            
            if not field or not value:
                continue

            if operator == 'contains':
                where_clauses.append(f"`{field}` LIKE %s")
                values.append(f"%{value}%")
            elif operator in ['==', '!=', '>', '<']:
                sql_op = '=' if operator == '==' else operator
                where_clauses.append(f"`{field}` {sql_op} %s")
                values.append(value)
            # You can add other operators here as needed
        
        if where_clauses:
            sql_query += " WHERE " + " AND ".join(where_clauses)
        print(where_clauses) 
        cursor.execute(sql_query, values)
        results = cursor.fetchall()
        
        return jsonify(results)
    
    except mysql.connector.Error as e:
        print(f"Error executing preview query: {e}")
        return jsonify({"error": "Error al ejecutar la consulta de vista previa."}), 499
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Ocurrió un error inesperado."}), 499
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

