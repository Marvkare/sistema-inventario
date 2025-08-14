from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
import mysql.connector
from datetime import date
from io import BytesIO
from pypdf import PdfReader, PdfWriter # Ensure this import is present!
from pypdf.generic import NameObject, TextStringObject, NumberObject
from weasyprint import HTML, CSS
import os
import re
import traceback
import sys
import pypdf
import pandas as pd
import openpyxl
import uuid


print(f"--- Diagnóstico del Entorno Python ---")
print(f"Proceso ID: {os.getpid()}")
print(f"Ruta del ejecutable de Python: {sys.executable}")
print(f"Ruta del módulo pypdf: {pypdf.__file__}")
print(f"Versión de pypdf: {pypdf.__version__}")
print(f"--- Fin del Diagnóstico ---")

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui' # ¡CAMBIA ESTO! Es crucial para sesiones y mensajes flash.
PDF_TEMPLATE_PATH = os.path.join(app.root_path, 'templates', 'PlantillaPrueba.pdf')

# --- Configuración de la Base de Datos ---
DB_CONFIG = {
    'host': 'localhost', # O la IP de tu servidor de base de datos
    'user': 'root', # ¡Cambia esto por tu usuario de MariaDB/MySQL!
    'password': 'Pescadoroot', # ¡Cambia esto por tu contraseña de MariaDB/MySQL!
    'database': 'inventario'
}

temp_error_storage = {}

def get_db_connection():
    """Establece conexión con la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        flash(f"Error de Conexión a la Base de Datos: {err}. Verifica las credenciales y que MariaDB esté corriendo.", 'error')
        return None

# Global list of valid column names from your DB schema for validation and mapping
# This should be exactly as they appear in your database table 'resguardo'
VALID_DB_COLUMNS = [
    "No_Folio", "No_Inventario", "No_Factura", "No_Cuenta", "No_Resguardo",
    "No_Trabajador", "Proveedor", "Fecha_Resguardo",
    "Descripcion_Del_Bien", "Descripcion_Fisica", "Area", "Rubro", "Poliza",
    "Fecha_Poliza", "Sub_Cuenta_Armonizadora", "Fecha_Factura", "Costo_Inicial",
    "Depreciacion_Acumulada", "Costo_Final_Cantidad", "Cantidad",
    "Nombre_Del_Usuario", "Puesto", "Nombre_Director_Jefe_Area",
    "Tipo_De_Resguardo", "Adscripcion_Direccion_Area", "Nombre_Del_Resguardante",
    "Estado_Del_Bien", "Marca", "Modelo", "Numero_De_Serie"
]

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
                                NameObject("/V"): TextStringObject(field_data[field_name]),
                                NameObject("/Ff"): NumberObject(1)
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
            error_rows = [] # New list to store the full rows with errors
            
            # Get cleaned column names from the Excel file
            excel_columns = {str(col).upper().strip(): str(col) for col in df.columns}
            
            # Process each row
            for index, row in df.iterrows():
                print(f"--- Procesando Fila {index + 2} del Excel ---")
                insert_data = {}
                row_data_for_errors = {}
                try:
                    for db_col in VALID_DB_COLUMNS:
                        excel_header_match = None
                        
                        # Check for direct match first
                        if db_col in excel_columns.values():
                            excel_header_match = db_col
                        # Check for mapped match
                        elif db_col in COLUMN_MAPPING.values():
                            for excel_header_key, mapped_db_col_name in COLUMN_MAPPING.items():
                                if mapped_db_col_name == db_col and excel_header_key.upper().strip() in excel_columns:
                                    excel_header_match = excel_columns[excel_header_key.upper().strip()]
                                    break

                        if excel_header_match:
                            value = row[excel_header_match]
                            row_data_for_errors[db_col] = str(value) if pd.notna(value) else ''
                            insert_data[db_col] = convert_to_db_type(db_col, value)
                        else:
                            insert_data[db_col] = None
                            row_data_for_errors[db_col] = ''

                    # Handle mandatory fields
                    if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
                        error_msg = f"'No_Inventario' o 'No_Resguardo' son obligatorios y no se encontraron o estaban vacíos."
                        error_rows.append({'original_row': row_data_for_errors, 'error': error_msg})
                        print(f"   -> OMITIDO: {error_msg}")
                        skipped_count += 1
                        continue

                    # No_Folio is usually auto-increment, so we remove it
                    if 'No_Folio' in insert_data:
                        del insert_data['No_Folio']
                    
                    # Construct INSERT query dynamically
                    cols = ', '.join(f"`{col}`" for col in insert_data.keys())
                    placeholders = ', '.join(['%s'] * len(insert_data))
                    query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"

                    # Execute the query
                    cursor.execute(query, tuple(insert_data.values()))
                    inserted_count += 1
                    print(f"   -> Éxito: Fila {index + 2} insertada correctamente.")

                except mysql.connector.Error as err:
                    if err.errno == 1062:
                        error_msg = f"Error de duplicado para No_Inventario/No_Resguardo: {err}. Se omitió la fila."
                    else:
                        error_msg = f"Error de base de datos: {err}. Se omitió la fila."
                    error_rows.append({'original_row': row_data_for_errors, 'error': error_msg})
                    print(f"   -> OMITIDO: {error_msg}")
                    skipped_count += 1
                except ValueError as ve:
                    error_msg = f"Error de conversión de datos: {ve}. Se omitió la fila."
                    error_rows.append({'original_row': row_data_for_errors, 'error': error_msg})
                    print(f"   -> OMITIDO: {error_msg}")
                    skipped_count += 1
                except Exception as e:
                    error_msg = f"Error de procesamiento inesperado: {e}. Se omitió la fila."
                    error_rows.append({'original_row': row_data_for_errors, 'error': error_msg})
                    print(f"   -> OMITIDO: {error_msg}")
                    skipped_count += 1
            
            # Handle commit or rollback
            if inserted_count > 0:
                conn.commit()
                flash(f"Se importaron {inserted_count} resguardos correctamente.", 'success')
                print(f"\n--- COMMIT EXITOSO: Se insertaron {inserted_count} filas. ---")
            else:
                conn.rollback() # Rollback if no rows were inserted
                print(f"\n--- ROLLBACK: No se insertaron filas. ---")
            
            # If there are errors, store them in the server-side temporary storage and session
            if error_rows:
                upload_id = str(uuid.uuid4())
                temp_error_storage[upload_id] = {'rows': error_rows, 'total_skipped': skipped_count}
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
    error_data = temp_error_storage.get(upload_id, {'rows': [], 'total_skipped': 0})
    error_rows = error_data['rows']
    total_skipped = error_data['total_skipped']
    
    # Get all possible column names to display headers
    columns = VALID_DB_COLUMNS
    if not error_rows:
        flash("No hay filas con errores para revisar.", 'info')
        return redirect(url_for('index'))
    return render_template('handle_errors.html', error_rows=error_rows, columns=columns, total_skipped=total_skipped, upload_id=upload_id)

@app.route('/save_error_row/<string:upload_id>/<int:row_index>', methods=['POST'])
def save_error_row(upload_id, row_index):
    """Saves a single row with errors after being manually corrected."""
    if upload_id not in temp_error_storage or row_index >= len(temp_error_storage[upload_id]['rows']):
        return jsonify({'success': False, 'message': 'Fila no encontrada o sesión expirada.'}), 404

    row_to_save = request.form.to_dict()
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor()
    try:
        # Perform validation and type conversion for the corrected data
        insert_data = {}
        for db_col in VALID_DB_COLUMNS:
            value = row_to_save.get(db_col)
            try:
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
        conn.commit()

        # Remove the successfully saved row from the temporary storage
        temp_error_storage[upload_id]['rows'].pop(row_index)
        temp_error_storage[upload_id]['total_skipped'] -= 1
        
        return jsonify({'success': True, 'message': 'Fila guardada correctamente.'}), 200

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
    if upload_id not in temp_error_storage or not temp_error_storage[upload_id]['rows']:
        return jsonify({'success': False, 'message': 'No hay filas con errores para guardar.'}), 404

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor()
    saved_count = 0
    errors = []
    
    # Get all form data from the request, which is a dictionary of dictionaries
    all_form_data = request.form.to_dict()
    
    error_indices_to_remove = []

    for index, error_row in enumerate(temp_error_storage[upload_id]['rows']):
        try:
            insert_data = {}
            for db_col in VALID_DB_COLUMNS:
                # The form data comes in with a key like 'Nombre_Del_Usuario-0', so we need to rebuild
                form_key = f"{db_col}-{index}"
                value = all_form_data.get(form_key)
                if value is None:
                    continue
                
                insert_data[db_col] = convert_to_db_type(db_col, value)

            if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
                raise ValueError("'No_Inventario' o 'No_Resguardo' son obligatorios.")

            if 'No_Folio' in insert_data:
                del insert_data['No_Folio']
            
            cols = ', '.join(f"`{col}`" for col in insert_data.keys())
            placeholders = ', '.join(['%s'] * len(insert_data))
            query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
            cursor.execute(query, tuple(insert_data.values()))
            
            saved_count += 1
            error_indices_to_remove.append(index)

        except (mysql.connector.Error, ValueError) as err:
            errors.append(f"Fila {index + 1}: {err}")
            continue

    if saved_count > 0:
        conn.commit()
        # Clean up the session by removing the saved rows
        for index in sorted(error_indices_to_remove, reverse=True):
            temp_error_storage[upload_id]['rows'].pop(index)
            temp_error_storage[upload_id]['total_skipped'] -= 1
        
        message = f"Se guardaron {saved_count} filas correctamente."
        flash(message, 'success')
    else:
        conn.rollback()
        message = "No se pudo guardar ninguna fila."
        flash(message, 'warning')
        
    if errors:
        for err_msg in errors:
            flash(err_msg, 'warning')

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

            set_clause = ', '.join([f"`{col}` = %s" for col in update_data.keys()])
            query = f"UPDATE resguardo SET {set_clause} WHERE `No_Folio` = %s"
            
            params = list(update_data.values()) + [folio_id]
            
            cursor.execute(query, tuple(params))
            conn.commit()
            flash("Resguardo actualizado correctamente.", 'success')
        except mysql.connector.Error as err:
            flash(f"Error al actualizar resguardo: {err}", 'error')
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:folio_id>', methods=['POST'])
def delete_resguardo(folio_id):
    """Elimina un registro de la base de datos."""
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))

    cursor = conn.cursor()
    try:
        query = "DELETE FROM resguardo WHERE No_Folio = %s"
        cursor.execute(query, (folio_id,))
        conn.commit()
        flash("Resguardo eliminado correctamente.", 'success')
    except mysql.connector.Error as err:
        flash(f"Error al eliminar resguardo: {err}", 'error')
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('index'))

def get_table_columns():
    """Retorna una lista de los nombres de las columnas de la tabla resguardo."""
    return [
        "No_Folio", "No_Inventario", "No_Factura", "No_Cuenta", "No_Resguardo",
        "No_Trabajador", "Proveedor", "Fecha_Resguardo",
        "Descripcion_Del_Bien", "Descripcion_Fisica", "Area", "Rubro", "Poliza",
        "Fecha_Poliza", "Sub_Cuenta_Armonizadora", "Fecha_Factura", "Costo_Inicial",
        "Depreciacion_Acumulada", "Costo_Final_Cantidad", "Cantidad",
        "Nombre_Del_Usuario", "Puesto", "Nombre_Director_Jefe_Area",
        "Tipo_De_Resguardo", "Adscripcion_Direccion_Area", "Nombre_Del_Resguardante",
        "Estado_Del_Bien", "Marca", "Modelo", "Numero_De_Serie"
    ]

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')