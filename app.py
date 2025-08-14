from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import mysql.connector
from datetime import date
from pypdf import PdfReader, PdfWriter
import os
import re
import traceback
import pandas as pd
import openpyxl
import uuid
from datetime import datetime
from io import BytesIO

# The `temp_error_storage` is no longer used, but kept as a reminder of the old logic.
# The new logic uses the `resguardo_errores` table.
# temp_error_storage = {}

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'
PDF_TEMPLATE_PATH = os.path.join(app.root_path, 'templates', 'PlantillaPrueba.pdf')

# --- Configuración de la Base de Datos ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Pescadoroot',
    'database': 'inventario'
}

def get_db_connection():
    """Establece conexión con la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        flash(f"Error de Conexión a la Base de Datos: {err}. Verifica las credenciales y que MariaDB esté corriendo.", 'error')
        return None

def get_table_columns():
    """
    Retrieves column names from the 'resguardo' table to ensure consistency.
    This is useful for dynamic form generation and validation.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    cursor = conn.cursor()
    columns = []
    try:
        cursor.execute("DESCRIBE resguardo")
        columns = [column[0] for column in cursor.fetchall()]
    except mysql.connector.Error as err:
        print(f"Error getting table columns: {err}")
    finally:
        cursor.close()
        conn.close()
    return columns

# Global list of valid column names from your DB schema for validation and mapping
# This should be exactly as they appear in your database table 'resguardo'
VALID_DB_COLUMNS = get_table_columns()

# Mapping for common Excel column names to actual DB column names
# Excel column names (keys) should be the exact headers in your Excel file
# DB column names (values) should be the exact column names in your database
COLUMN_MAPPING = {
    "NO.POLIZA": "Poliza",
    "FECHA POLIZA": "Fecha_Poliza",
    "SUB-CTA. ARMONIZADORA": "Sub_Cuenta_Armonizadora",
    "FECHA RESGUARDO":"Fecha_Resguardo",
    "NO. DE CUENTA": "No_Cuenta",
    "NO. DE INVENTARIO": "No_Inventario",
    "NO. DE RESGUARDO": "No_Resguardo",
    "PROVEEDOR": "Proveedor",
    "FACTURA": "No_Factura", # Assuming this is 'No_Factura'
    "FECHA FACTURA": "Fecha_Factura",
    "COSTO INICIAL": "Costo_Inicial",
    "DEPRECIACION ACUMULADA": "Depreciacion_Acumulada", # Ensure spelling matches DB (Depreciacion_Acumulada)
    "COSTO FINAL": "Costo_Final_Cantidad", # Assuming this maps to Costo_Final_Cantidad
    "CANTIDAD": "Cantidad",
    "DESCRIPCION FISICAS DEL BIEN": "Descripcion_Del_Bien", # Assuming this maps to Descripcion_Del_Bien
    "DESCRIPCION FISICA": "Descripcion_Fisica", # Assuming this maps to Descripcion_Fisica
    "AREA": "Area",
    "RUBRO": "Rubro",
    "NOMBRE DEL USUARIO": "Nombre_Del_Usuario", # Assuming this maps to Nombre_Del_Usuario
    "PUESTO": "Puesto",
    "NO. DE TRABAJADOR": "No_Trabajador",
    "NOMBRE DIRECTOR/JEFE AREA": "Nombre_Director_Jefe_Area", # Assuming this maps
    "TIPO DE RESGUARDO": "Tipo_De_Resguardo", # Assuming this maps
    "ADSCRIPCION DIRECCION AREA": "Adscripcion_Direccion_Area",
    "NOMBRE DEL RESGUARDANTE": "Nombre_Del_Resguardante",
    "ESTADO DEL BIEN": "Estado_Del_Bien",
    "MARCA": "Marca",
    "MODELO": "Modelo",
    "NUMERO DE SERIE": "Numero_De_Serie",
    # Add any other mappings where Excel header differs from DB column name
}


@app.route('/')
def index():
    """Ruta principal: Muestra el formulario para agregar/editar y la opción de carga masiva."""
    empty_resguardo = {col: '' for col in get_table_columns()}
    empty_resguardo['No_Folio'] = ''
    # Ensure correct keys for rendering select option in 'Tipo_De_Resguardo'
    empty_resguardo['Tipo_De_Resguardo'] = '' 
    return render_template('index.html', form_data=empty_resguardo)

@app.route('/resguardos_list')
def resguardos_list():
    """Nueva ruta: Muestra solo la lista de resguardos."""
    conn = get_db_connection()
    if conn is None:
        return render_template('resguardos_list.html', resguardos=[]) # Renderiza la plantilla sin datos

    cursor = conn.cursor(dictionary=True) # dictionary=True para obtener resultados como diccionarios
    resguardos = []
    try:
        cursor.execute("SELECT * FROM resguardo ORDER BY No_Folio DESC")
        resguardos = cursor.fetchall()
        print(resguardos)
    except mysql.connector.Error as err:
        flash(f"Error al cargar datos: {err}", 'error')
    finally:
        cursor.close()
        conn.close()
    
    return render_template('resguardos_list.html', resguardos=resguardos)


@app.route('/generate_resguardo_pdf/<int:folio_id>')
def generate_resguardo_pdf(folio_id):
    conn = get_db_connection()
    if conn is None:
        flash("No se pudo conectar a la base de datos.", 'error')
        return redirect(url_for('resguardos_list'))

    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM resguardo WHERE No_Folio = %s", (folio_id,))
            resguardo_data = cursor.fetchone()
            if not resguardo_data:
                flash("Resguardo no encontrado.", 'error')
                return redirect(url_for('resguardos_list'))
    except mysql.connector.Error as err:
        flash(f"Error al obtener datos: {err}", 'error')
        return redirect(url_for('resguardos_list'))
    finally:
        conn.close()

    try:
        # Load template PDF
        reader = PdfReader(PDF_TEMPLATE_PATH)
        
        # Verify the PDF has form fields
        if not reader.get_form_text_fields():
            flash("La plantilla PDF no contiene campos de formulario.", 'error')
            return redirect(url_for('resguardos_list'))

        # Prepare field data
        field_data = {
            "No_Folio_Field": str(resguardo_data.get('No_Folio', '')),
            "No_Inventario_Field": resguardo_data.get('No_Inventario', ''),
            "No_Factura_Field": resguardo_data.get('No_Factura', ''),
            "No_Cuenta_Field": resguardo_data.get('No_Cuenta', ''),
        }

        # Create writer and clone document
        writer = PdfWriter()
        writer.clone_reader_document_root(reader)

        # Update fields
        for page in writer.pages:
            if '/Annots' in page:
                annotations = page['/Annots']
                for annotation in annotations:
                    annot_obj = annotation.get_object()
                    if '/T' in annot_obj:
                        field_name = annot_obj['/T']
                        if field_name in field_data:
                            annot_obj.update({
                                pypdf.generic.NameObject("/V"): pypdf.generic.TextStringObject(field_data[field_name]),
                                pypdf.generic.NameObject("/Ff"): pypdf.generic.NumberObject(1)
                            })


        # Save to templates folder
        output_path = os.path.join('resguardos', f'resguardo_{folio_id}.pdf')
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)

        flash(f"PDF guardado correctamente en: {output_path}", 'success')
        return redirect(url_for('resguardos_list'))

    except FileNotFoundError:
        flash("Plantilla PDF no encontrada.", 'error')
    except PermissionError:
        flash("No tienes permisos para escribir en la carpeta templates.", 'error')
    except Exception as e:
        flash(f"Error al generar PDF: {str(e)}", 'error')
        print(f"Error detallado:\n{traceback.format_exc()}")
    
    return redirect(url_for('resguardos_list'))


@app.route('/resguardos_clasificados')
def resguardos_clasificados():
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos", 'error')
        return redirect(url_for('index'))
    
    try:
        # Obtener todos los resguardos
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
                r.No_Folio
""")
        resguardos = cursor.fetchall()
        
        # Obtener nombres de columnas
        column_names = [desc[0] for desc in cursor.description]
        
        return render_template('resguardos_clasificados.html', 
                            resguardos=resguardos,
                            column_names=column_names)
    except Exception as e:
        flash(f"Error al obtener resguardos: {str(e)}", 'error')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/exportar_resguardos_excel', methods=['POST'])
def exportar_resguardos_excel():
    try:
        # Obtener columnas seleccionadas del formulario
        selected_columns = request.form.getlist('columns')
        
        if not selected_columns:
            return jsonify({'error': 'No se seleccionaron columnas'}), 400
        
        conn = get_db_connection()
        if conn is None:
            return jsonify({'error': 'Error de conexión a la base de datos'}), 500
            
        try:
            # Obtener datos con las columnas seleccionadas
            cursor = conn.cursor(dictionary=True)
            columns_str = ', '.join(selected_columns)
            cursor.execute(f"""
                SELECT {columns_str}, 
                       CASE 
                           WHEN Tipo_De_Resguardo  = 1 THEN 'Sujeto de Control'
                           ELSE 'Resguardo Normal'
                       END AS Tipo_de_resguardo
                FROM resguardo
                ORDER BY Tipo_De_Resguardo  DESC, No_Folio
            """)
            data = cursor.fetchall()
            
            # Crear DataFrame de pandas
            df = pd.DataFrame(data)
            
            # Crear archivo Excel en memoria
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
# --- Data Type Conversion Helper ---
def convert_to_db_type(column_name, value):
    """
    Converts a value from Excel to the appropriate Python type for the database.
    Handles dates, numbers, and cleans up special characters.
    """
    # Handle NULL values from Excel (e.g., NaN from pandas)
    if pd.isna(value) or value is None or str(value).strip() == '':
        return None

    # Dates
    if column_name in ["Fecha_Resguardo", "Fecha_Poliza", "Fecha_Factura"]:
        try:
            # Handle various date formats including Excel's numerical date format
            if isinstance(value, (int, float)):
                # Excel dates are days since '1899-12-30'
                return (pd.to_datetime('1899-12-30') + pd.to_timedelta(value, unit='D')).date()
            elif isinstance(value, str):
                # Try common date formats
                for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%m-%d-%Y'):
                    try:
                        # Use datetime from the import to avoid NameError
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        pass
                raise ValueError(f"Unknown date format for '{value}'")
            elif isinstance(value, datetime):
                return value.date()
            elif isinstance(value, date):
                return value
        except Exception as e:
            # We raise a ValueError here to catch it in the main loop and skip the row
            raise ValueError(f"No se pudo convertir la fecha '{value}': {e}")

    # Numbers (Decimal/Float)
    elif column_name in ["Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final_Cantidad"]:
        try:
            if isinstance(value, str):
                # Clean up the string by removing non-numeric characters before conversion
                value = re.sub(r'[^\d.]', '', value).strip()
                if value == '':
                    return None
            return float(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"No se pudo convertir '{value}' a un número decimal: {e}")

    # Integers
    elif column_name == "Cantidad":
        try:
            if isinstance(value, str):
                value = re.sub(r'[^\d]', '', value).strip()
                if value == '':
                    return None
            return int(float(value)) # Convert to float first to handle decimals like "1.0"
        except (ValueError, TypeError) as e:
            raise ValueError(f"No se pudo convertir '{value}' a un número entero: {e}")

    # Strings (default)
    return str(value)


@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    print("\n--- INICIANDO PROCESO DE CARGA DE EXCEL ---")
    if 'excel_file' not in request.files:
        flash("No se encontró ningún archivo.", 'error')
        return redirect(url_for('index'))

    file = request.files['excel_file']
    if file.filename == '':
        flash("No se seleccionó ningún archivo.", 'error')
        return redirect(url_for('index'))

    if file and file.filename.endswith(('.xlsx', '.xls')):
        conn = None
        cursor = None
        try:
            df = pd.read_excel(file)
            print(f"Archivo Excel leído. Total de filas a procesar: {len(df)}")

            conn = get_db_connection()
            if conn is None:
                return redirect(url_for('index'))

            cursor = conn.cursor()
            inserted_count = 0
            skipped_count = 0
            error_rows = []
            upload_id = str(uuid.uuid4())
            
            # Get cleaned column names from the Excel file
            excel_columns_map = {str(col).upper().strip(): str(col) for col in df.columns}
            
            # Process each row
            for index, row in df.iterrows():
                print(f"--- Procesando Fila {index + 2} del Excel ---")
                insert_data = {}
                raw_row_data = {'upload_id': upload_id}
                error_msg = None

                # First, extract all data as text, and prepare for insertion into resguardo_errores
                for db_col in VALID_DB_COLUMNS:
                    excel_header_match = None
                    # Check for direct match first
                    if db_col in excel_columns_map.values():
                        excel_header_match = db_col
                    # Check for mapped match
                    elif db_col in COLUMN_MAPPING.values():
                        for excel_header_key, mapped_db_col_name in COLUMN_MAPPING.items():
                            if mapped_db_col_name == db_col and excel_header_key.upper().strip() in excel_columns_map:
                                excel_header_match = excel_columns_map[excel_header_key.upper().strip()]
                                break
                    
                    value = row.get(excel_header_match, '')
                    raw_row_data[db_col] = str(value) if pd.notna(value) else ''
                
                try:
                    # Now, try to convert types for the main table insertion
                    temp_insert_data = {}
                    for db_col, value in raw_row_data.items():
                        if db_col not in ['id', 'upload_id', 'error_message']: # Skip error table specific columns
                            temp_insert_data[db_col] = convert_to_db_type(db_col, value)

                    # Handle mandatory fields
                    if not temp_insert_data.get('No_Inventario') or not temp_insert_data.get('No_Resguardo'):
                        error_msg = f"'No_Inventario' o 'No_Resguardo' son obligatorios y no se encontraron o estaban vacíos."
                        raise ValueError(error_msg)
                    
                    # No_Folio is usually auto-increment, so we remove it
                    if 'No_Folio' in temp_insert_data:
                        del temp_insert_data['No_Folio']
                    
                    # Construct INSERT query dynamically for the main table
                    cols = ', '.join(f"`{col}`" for col in temp_insert_data.keys())
                    placeholders = ', '.join(['%s'] * len(temp_insert_data))
                    query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"

                    # Execute the query
                    cursor.execute(query, tuple(temp_insert_data.values()))
                    inserted_count += 1
                    print(f"   -> Éxito: Fila {index + 2} insertada correctamente.")

                except (mysql.connector.Error, ValueError, Exception) as err:
                    if isinstance(err, mysql.connector.Error) and err.errno == 1062:
                        error_msg = f"Error de duplicado para No_Inventario/No_Resguardo. Se omitió la fila."
                    elif error_msg is None: # If error_msg was not set by mandatory field check
                        error_msg = f"Error de procesamiento: {err}. Se omitió la fila."

                    raw_row_data['error_message'] = error_msg
                    error_rows.append(raw_row_data)
                    skipped_count += 1
                    print(f"   -> OMITIDO: {error_msg}")

            # Handle commit or rollback
            if inserted_count > 0:
                conn.commit()
                flash(f"Se importaron {inserted_count} resguardos correctamente.", 'success')
                print(f"\n--- COMMIT EXITOSO: Se insertaron {inserted_count} filas. ---")
            else:
                conn.rollback()
                print(f"\n--- ROLLBACK: No se insertaron filas. ---")
            
            # If there are errors, insert them into the new table
            if error_rows:
                cols = ', '.join(f"`{col}`" for col in error_rows[0].keys())
                placeholders = ', '.join(['%s'] * len(error_rows[0]))
                query = f"INSERT INTO resguardo_errores ({cols}) VALUES ({placeholders})"
                
                values = [tuple(row.values()) for row in error_rows]
                cursor.executemany(query, values)
                conn.commit()
                session['upload_id'] = upload_id
                
                flash(f"Se importaron {inserted_count} resguardos correctamente. Se omitieron {skipped_count} filas debido a errores. Por favor, revisa y corrige las filas a continuación.", 'warning')
                return redirect(url_for('handle_errors'))
            
        except Exception as e:
            flash(f"Error al procesar el archivo Excel: {str(e)}", 'error')
            print(f"--- ERROR FATAL AL PROCESAR EL ARCHIVO ---")
            print(f"Error: {e}")
            print(f"Stack Trace: {traceback.format_exc()}")
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            print("--- PROCESO DE CARGA DE EXCEL FINALIZADO ---\n")
    else:
        flash("Formato de archivo no soportado. Por favor, sube un archivo .xlsx o .xls", 'error')

    return redirect(url_for('index'))


@app.route('/handle_errors')
def handle_errors():
    """Displays a page with rows that had import errors for manual editing."""
    upload_id = session.get('upload_id')
    if not upload_id:
        flash("No hay filas con errores para revisar.", 'info')
        return redirect(url_for('index'))

    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)
    error_rows = []
    try:
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        error_rows = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Error al obtener filas de error: {err}", 'error')
    finally:
        cursor.close()
        conn.close()
    
    total_skipped = len(error_rows)
    columns = VALID_DB_COLUMNS
    if not error_rows:
        # If there are no rows, remove the upload_id from the session
        session.pop('upload_id', None)
        flash("No hay filas con errores para revisar.", 'info')
        return redirect(url_for('index'))

    # Prepare a dictionary for the template to have a similar structure
    template_error_rows = []
    for row in error_rows:
        original_row = {col: row.get(col, '') for col in columns}
        template_error_rows.append({
            'id': row.get('id'), # Pass the ID of the error row for saving
            'original_row': original_row,
            'error': row.get('error_message', 'Error desconocido')
        })

    return render_template('handle_errors.html', error_rows=template_error_rows, columns=columns, total_skipped=total_skipped, upload_id=upload_id)


@app.route('/save_error_row/<string:upload_id>/<int:row_id>', methods=['POST'])
def save_error_row(upload_id, row_id):
    """Saves a single row with errors after being manually corrected."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor()
    try:
        row_to_save = request.form.to_dict()
        
        # Perform validation and type conversion for the corrected data
        insert_data = {}
        for db_col in VALID_DB_COLUMNS:
            value = row_to_save.get(db_col)
            try:
                # Use the helper function to convert the cleaned data
                insert_data[db_col] = convert_to_db_type(db_col, value)
            except ValueError as ve:
                conn.rollback()
                return jsonify({'success': False, 'message': f'Error de conversión en campo "{db_col}": {ve}'}), 400

        # Check for mandatory fields again
        if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
            conn.rollback()
            return jsonify({'success': False, 'message': "'No_Inventario' o 'No_Resguardo' son obligatorios."}), 400

        # Construct and execute the INSERT query
        if 'No_Folio' in insert_data:
            del insert_data['No_Folio']
        cols = ', '.join(f"`{col}`" for col in insert_data.keys())
        placeholders = ', '.join(['%s'] * len(insert_data))
        query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
        cursor.execute(query, tuple(insert_data.values()))
        
        # If successful, delete the row from the errors table
        cursor.execute("DELETE FROM resguardo_errores WHERE id = %s AND upload_id = %s", (row_id, upload_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Fila guardada correctamente.', 'row_id': row_id}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1062:
            return jsonify({'success': False, 'message': f'Error de duplicado para No_Inventario/No_Resguardo.'}), 409
        else:
            return jsonify({'success': False, 'message': f'Error de base de datos: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/save_all_error_rows/<string:upload_id>', methods=['POST'])
def save_all_error_rows(upload_id):
    """Saves all error rows that have been corrected."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor(dictionary=True)
    saved_count = 0
    errors = []
    
    # Get all form data from the request
    all_form_data = request.form.to_dict()

    try:
        # Fetch all error rows for this upload ID
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        error_rows_from_db = cursor.fetchall()
        
        # Iterate over the original error rows from the DB
        for index, db_error_row in enumerate(error_rows_from_db):
            try:
                insert_data = {}
                for db_col in VALID_DB_COLUMNS:
                    # The form data uses keys like 'No_Inventario-0', so we build the key
                    form_key = f"{db_col}-{index}"
                    # Use the corrected value from the form if it exists, otherwise use the original from the DB
                    value = all_form_data.get(form_key, db_error_row.get(db_col))
                    
                    if value is None:
                        continue
                    
                    # Convert the corrected value
                    insert_data[db_col] = convert_to_db_type(db_col, value)

                if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
                    raise ValueError("'No_Inventario' o 'No_Resguardo' son obligatorios.")

                if 'No_Folio' in insert_data:
                    del insert_data['No_Folio']
                
                cols = ', '.join(f"`{col}`" for col in insert_data.keys())
                placeholders = ', '.join(['%s'] * len(insert_data))
                query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
                cursor.execute(query, tuple(insert_data.values()))
                
                # If insertion is successful, delete from the errors table
                cursor.execute("DELETE FROM resguardo_errores WHERE id = %s", (db_error_row['id'],))
                saved_count += 1

            except (mysql.connector.Error, ValueError) as err:
                errors.append(f"Fila {index + 1}: {err}")
                continue
        
        if saved_count > 0:
            conn.commit()
            message = f"Se guardaron {saved_count} filas correctamente."
            flash(message, 'success')
        else:
            conn.rollback()
            message = "No se pudo guardar ninguna fila."
            flash(message, 'warning')
            
        if errors:
            for err_msg in errors:
                flash(err_msg, 'warning')
        
    except Exception as e:
        conn.rollback()
        flash(f"Ocurrió un error inesperado al guardar todas las filas: {str(e)}", 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('index'))


@app.route('/add', methods=['POST'])
def add_resguardo():
    """Agrega un nuevo resguardo a la base de datos."""
    if request.method == 'POST':
        form_values = request.form.to_dict()
        form_values.pop('No_Folio', None) # Eliminar No_Folio si está presente

        if not form_values.get("No_Inventario") or not form_values.get("No_Resguardo"):
            flash("Los campos 'No. Inventario' y 'No. Resguardo' son obligatorios.", 'warning')
            return redirect(url_for('index'))

        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))

        cursor = conn.cursor()
        try:
            insert_data = {}
            for key, value in form_values.items():
                if value == '':
                    insert_data[key] = None
                else:
                    if key in ["Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final_Cantidad"]:
                        try:
                            insert_data[key] = float(value)
                        except ValueError:
                            flash(f"El campo '{key.replace('_', ' ')}' debe ser numérico.", 'error')
                            return redirect(url_for('index'))
                    elif key == "Cantidad":
                        try:
                            insert_data[key] = int(value)
                        except ValueError:
                            flash(f"El campo 'Cantidad' debe ser un número entero.", 'error')
                            return redirect(url_for('index'))
                    elif key in ["Fecha_Resguardo", "Fecha_Poliza", "Fecha_Factura"]:
                        try:
                            insert_data[key] = date.fromisoformat(value)
                        except ValueError:
                            flash(f"El campo '{key.replace('_', ' ')}' debe tener el formato YYYY-MM-DD.", 'error')
                            return redirect(url_for('index'))
                    else:
                        insert_data[key] = value

            cols = ', '.join(f"`{col}`" for col in insert_data.keys())
            placeholders = ', '.join(['%s'] * len(insert_data))
            query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
            
            cursor.execute(query, tuple(insert_data.values()))
            conn.commit()
            flash("Resguardo agregado correctamente.", 'success')
        except mysql.connector.Error as err:
            flash(f"Error al agregar resguardo: {err}", 'error')
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:folio_id>')
def edit_resguardo(folio_id):
    """Muestra el formulario para editar un resguardo existente."""
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))

    cursor = conn.cursor(dictionary=True)
    resguardo_data = {}
    try:
        cursor.execute("SELECT * FROM resguardo WHERE No_Folio = %s", (folio_id,))
        resguardo_data = cursor.fetchone()
        if not resguardo_data:
            flash("Resguardo no encontrado.", 'error')
            return redirect(url_for('index'))
    except mysql.connector.Error as err:
        flash(f"Error al obtener datos para edición: {err}", 'error')
    finally:
        cursor.close()
        conn.close()
    
    # Formatea los campos de fecha a YYYY-MM-DD para el formulario
    for key in ["Fecha_Resguardo", "Fecha_Poliza", "Fecha_Factura"]:
        if key in resguardo_data and resguardo_data[key]:
            resguardo_data[key] = resguardo_data[key].isoformat()

    return render_template('index.html', form_data=resguardo_data)

@app.route('/update/<int:folio_id>', methods=['POST'])
def update_resguardo(folio_id):
    """Actualiza un registro existente en la base de datos."""
    if request.method == 'POST':
        form_values = request.form.to_dict()
        
        if not form_values.get("No_Inventario") or not form_values.get("No_Resguardo"):
            flash("Los campos 'No. Inventario' y 'No. Resguardo' son obligatorios para la actualización.", 'warning')
            return redirect(url_for('edit', folio_id=folio_id))

        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))

        cursor = conn.cursor()
        try:
            update_data = {}
            for key, value in form_values.items():
                if value == '':
                    update_data[key] = None
                else:
                    if key in ["Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final_Cantidad"]:
                        try:
                            update_data[key] = float(value)
                        except ValueError:
                            flash(f"El campo '{key.replace('_', ' ')}' debe ser numérico.", 'error')
                            return redirect(url_for('edit', folio_id=folio_id))
                    elif key == "Cantidad":
                        try:
                            update_data[key] = int(value)
                        except ValueError:
                            flash(f"El campo 'Cantidad' debe ser un número entero.", 'error')
                            return redirect(url_for('edit', folio_id=folio_id))
                    elif key in ["Fecha_Resguardo", "Fecha_Poliza", "Fecha_Factura"]:
                        try:
                            update_data[key] = date.fromisoformat(value)
                        except ValueError:
                            flash(f"El campo '{key.replace('_', ' ')}' debe tener el formato YYYY-MM-DD.", 'error')
                            return redirect(url_for('edit', folio_id=folio_id))
                    else:
                        update_data[key] = value

            # No_Folio should not be updated as it's the primary key
            if 'No_Folio' in update_data:
                del update_data['No_Folio']
            
            set_clauses = ', '.join([f"`{col}` = %s" for col in update_data.keys()])
            query = f"UPDATE resguardo SET {set_clauses} WHERE No_Folio = %s"
            
            values = list(update_data.values())
            values.append(folio_id)
            
            cursor.execute(query, tuple(values))
            conn.commit()
            flash("Resguardo actualizado correctamente.", 'success')
        except mysql.connector.Error as err:
            flash(f"Error al actualizar resguardo: {err}", 'error')
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('index'))