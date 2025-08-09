from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
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
    "No_Trabajador", "No_Nomina", "Proveedor", "Fecha_Elaboracion",
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
    "SUB-CTA ARMONIZADORA": "Sub_Cuenta_Armonizadora",
    "NO. DE CUENTA": "No_Cuenta",
    "No. De Inventario": "No_Inventario",
    "No. De Resguardo": "No_Resguardo",
    "PROVEEDOR": "Proveedor",
    "FACTURA": "No_Factura", # Assuming this is 'No_Factura'
    "FECHA FACTURA": "Fecha_Factura",
    "COSTO INICIAL": "Costo_Inicial",
    "DEPRECIACION ACUMULADA": "Depreciacion_Acumulada", # Ensure spelling matches DB (Depreciacion_Acumulada)
    "COSTO FINAL": "Costo_Final_Cantidad", # Assuming this maps to Costo_Final_Cantidad
    "CANTIDAD": "Cantidad",
    "DESCRIPCION DEL BIEN": "Descripcion_Del_Bien", # Assuming this maps to Descripcion_Del_Bien
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

# --- Data Type Conversion Helper ---
def convert_to_db_type(column_name, value):
    """Converts a value to the appropriate Python type for database insertion based on column name."""
    if pd.isna(value) or value is None or str(value).strip() == '':
        return None

    # Dates
    if column_name in ["Fecha_Elaboracion", "Fecha_Poliza", "Fecha_Factura"]:
        try:
            # Handle various date formats including Excel's numerical date format
            if isinstance(value, (int, float)):
                return pd.to_datetime(value, unit='D', origin='1899-12-30').date() # Excel date to datetime.date
            elif isinstance(value, str):
                # Try common date formats
                for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y'):
                    try:
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        pass
                raise ValueError(f"Unknown date format for '{value}'")
            elif isinstance(value, datetime):
                return value.date()
            elif isinstance(value, date):
                return value
        except Exception as e:
            print(f"Warning: Could not convert date '{value}' for column '{column_name}': {e}")
            return None # Return None or raise error depending on strictness

    # Numbers (Decimal/Float)
    elif column_name in ["Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final_Cantidad"]:
        try:
            return float(value)
        except ValueError:
            print(f"Warning: Could not convert '{value}' to float for column '{column_name}'")
            return None # Or default to 0.0

    # Integers
    elif column_name == "Cantidad":
        try:
            return int(float(value)) # Convert to float first to handle decimals like "1.0"
        except ValueError:
            print(f"Warning: Could not convert '{value}' to int for column '{column_name}'")
            return None # Or default to 0

    # Strings (default)
    return str(value)

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

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    if 'excel_file' not in request.files:
        flash("No se encontró ningún archivo.", 'error')
        return redirect(url_for('index'))

    file = request.files['excel_file']
    if file.filename == '':
        flash("No se seleccionó ningún archivo.", 'error')
        return redirect(url_for('index'))

    if file and file.filename.endswith(('.xlsx', '.xls')):
        try:
            # Read Excel into a pandas DataFrame
            df = pd.read_excel(file)

            conn = get_db_connection()
            if conn is None:
                return redirect(url_for('index'))

            cursor = conn.cursor()
            inserted_count = 0
            skipped_count = 0
            errors = []

            # Prepare for insertion
            db_columns_sanitized = [col.lower().replace(' ', '_') for col in VALID_DB_COLUMNS]

            for index, row in df.iterrows():
                insert_data = {}
                try:
                    # Map Excel columns to DB columns
                    # Clean Excel column names for mapping (remove spaces, convert to lowercase)
                    excel_column_map = {col.replace(' ', '_').upper(): col for col in df.columns}

                    for db_col in VALID_DB_COLUMNS:
                        # Try exact match first
                        excel_header_match = None
                        if db_col in df.columns: # Check if DB column name exists directly in Excel header
                            excel_header_match = db_col
                        else: # Try mapping
                            for excel_header_key, mapped_db_col_name in COLUMN_MAPPING.items():
                                if mapped_db_col_name == db_col and excel_header_key in df.columns:
                                    excel_header_match = excel_header_key
                                    break

                        if excel_header_match is not None:
                            insert_data[db_col] = convert_to_db_type(db_col, row[excel_header_match])
                        else:
                            insert_data[db_col] = None # Or a default value if column is missing

                    # Handle mandatory fields
                    if insert_data.get('No_Inventario') is None:
                        errors.append(f"Fila {index + 2}: 'No_Inventario' es obligatorio y no se encontró o estaba vacío.")
                        skipped_count += 1
                        continue
                    if insert_data.get('No_Resguardo') is None:
                        errors.append(f"Fila {index + 2}: 'No_Resguardo' es obligatorio y no se encontró o estaba vacío.")
                        skipped_count += 1
                        continue

                    # Remove No_Folio if it's auto-incremented
                    insert_data.pop('No_Folio', None)
                    
                    # Construct INSERT query dynamically
                    cols = ', '.join(f"`{col}`" for col in insert_data.keys())
                    placeholders = ', '.join(['%s'] * len(insert_data))
                    query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"

                    cursor.execute(query, tuple(insert_data.values()))
                    inserted_count += 1

                except mysql.connector.Error as err:
                    # Specific error for duplicate entry (No_Inventario or No_Resguardo being UNIQUE)
                    if err.errno == 1062: # MySQL error code for Duplicate entry for key 'X'
                        errors.append(f"Fila {index + 2}: Error de duplicado para No_Inventario/No_Resguardo: {err}. Se omitió la fila.")
                    else:
                        errors.append(f"Fila {index + 2}: Error de base de datos: {err}. Se omitió la fila.")
                    skipped_count += 1
                    conn.rollback() # Rollback current row if error
                except Exception as e:
                    errors.append(f"Fila {index + 2}: Error de procesamiento: {e}. Se omitió la fila.")
                    skipped_count += 1
            
            conn.commit() # Commit all successful insertions
            if inserted_count > 0:
                flash(f"Se importaron {inserted_count} resguardos correctamente.", 'success')
            if skipped_count > 0:
                flash(f"Se omitieron {skipped_count} filas debido a errores.", 'warning')
                for err_msg in errors:
                    flash(err_msg, 'warning') # Flash each specific error
            
        except Exception as e:
            flash(f"Error al procesar el archivo Excel: {str(e)}", 'error')
            print(f"Error processing Excel: {traceback.format_exc()}")
            if 'conn' in locals() and conn:
                conn.rollback() # Rollback if a global error occurred before loop
        finally:
            if 'conn' in locals() and conn:
                cursor.close()
                conn.close()
    else:
        flash("Formato de archivo no soportado. Por favor, sube un archivo .xlsx o .xls", 'error')

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
                    elif key in ["Fecha_Elaboracion", "Fecha_Poliza", "Fecha_Factura"]:
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
    for key in ["Fecha_Elaboracion", "Fecha_Poliza", "Fecha_Factura"]:
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
                    elif key in ["Fecha_Elaboracion", "Fecha_Poliza", "Fecha_Factura"]:
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
        "No_Trabajador", "No_Nomina", "Proveedor", "Fecha_Elaboracion",
        "Descripcion_Del_Bien", "Descripcion_Fisica", "Area", "Rubro", "Poliza",
        "Fecha_Poliza", "Sub_Cuenta_Armonizadora", "Fecha_Factura", "Costo_Inicial",
        "Depreciacion_Acumulada", "Costo_Final_Cantidad", "Cantidad",
        "Nombre_Del_Usuario", "Puesto", "Nombre_Director_Jefe_Area",
        "Tipo_De_Resguardo", "Adscripcion_Direccion_Area", "Nombre_Del_Resguardante",
        "Estado_Del_Bien", "Marca", "Modelo", "Numero_De_Serie"
    ]

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')