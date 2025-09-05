# your_flask_app/routes/excel_import.py
from flask import Blueprint, request, redirect, url_for, flash, jsonify, session, current_app, send_file
import pandas as pd
import mysql.connector
import os
import re
import uuid
import traceback
from datetime import datetime, date
from io import BytesIO
from flask_login import login_required, current_user
from database import get_db_connection, get_full_db_columns
from config import VALID_DB_COLUMNS, COLUMN_MAPPING, FULL_DB_COLUMNS, BIENES_COLUMNS, RESGUARDOS_COLUMNS, EXCEL_AREA_COL_NAME # Import VALID_DB_COLUMNS and COLUMN_MAPPING
from decorators import permission_required
excel_import_bp = Blueprint('excel_import', __name__)

# --- Data Type Conversion Helper (moved from app.py) ---
def convert_to_db_type(column_name, value):
    if pd.isna(value) or value is None or str(value).strip() == '':
        return None

    if column_name in ["Fecha_Resguardo", "Fecha_Poliza", "Fecha_Factura"]:
        try:
            if isinstance(value, (datetime, date, pd.Timestamp)):
                return value.date()
                
            if isinstance(value, (int, float)):
                fecha = pd.to_datetime(value, unit='D', origin='1899-12-30', errors='coerce').date()
                return fecha
            else:
                return pd.to_datetime(value, errors='raise').date()
        except Exception as e:
            raise ValueError(f"No se pudo convertir el valor de fecha '{value}' para la columna '{column_name}': {e}")
    
    elif column_name in ["Costo_Inicial", "Depreciacion_Acumulada", "Costo_Final_Cantidad"]:
        try:
            if isinstance(value, str):
                value = re.sub(r'[^\d.]', '', value).strip()
                if value == '':
                    return None
            return float(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"No se pudo convertir '{value}' a un número decimal para la columna '{column_name}': {e}")

    elif column_name == "Cantidad":
        try:
            if isinstance(value, str):
                value = re.sub(r'[^\d]', '', value).strip()
                if value == '':
                    return None
            return int(float(value)) # Convert to float first, then int to handle cases like "5.0"
        except (ValueError, TypeError) as e:
            raise ValueError(f"No se pudo convertir '{value}' a un número entero para la columna '{column_name}': {e}")
    
    return str(value) # Default to string for other types

def get_or_create_bien(cursor, bien_data):
    """
    Siempre inserta un nuevo bien en la base de datos y devuelve su ID.
    """
    try:
        bien_cols = ', '.join([f"`{col}`" for col in bien_data.keys()])
        placeholders = ', '.join(['%s'] * len(bien_data))
        query_insert = f"INSERT INTO bienes ({bien_cols}) VALUES ({placeholders})"
        cursor.execute(query_insert, tuple(bien_data.values()))
        return cursor.lastrowid
    except mysql.connector.Error as err:
        raise Exception(f"Error al procesar el bien: {err}")

def get_or_create_area(cursor, area_name):
    """
    Busca un área por su nombre. Si existe, devuelve su ID.
    Si no existe, la inserta y devuelve el nuevo ID.
    """
    if not area_name:
        return None
    try:
        query_select = "SELECT id FROM areas WHERE nombre = %s"
        cursor.execute(query_select, (area_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            query_insert = "INSERT INTO areas (nombre) VALUES (%s)"
            cursor.execute(query_insert, (area_name,))
            return cursor.lastrowid
    except mysql.connector.Error as err:
        raise Exception(f"Error al procesar el área: {err}")

@excel_import_bp.route('/upload_excel', methods=['POST'])
@login_required
@permission_required('excel_import.upload_excel')
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
        inserted_count = 0
        skipped_count = 0
        error_rows = []
        upload_id = str(uuid.uuid4())

        try:
            df = pd.read_excel(file)
            
            # Use a dictionary comprehension to create case-insensitive and stripped headers
            excel_headers_map = {str(col).upper().strip(): str(col) for col in df.columns}
            print("Nombres de columnas del Excel:", excel_headers_map)

            conn = get_db_connection()
            if conn is None:
                return redirect(url_for('index'))

            cursor = conn.cursor()
            
            # Iterate through each row of the DataFrame
            for index, row in df.iterrows():
                print(f"--- Procesando Fila {index + 2} del Excel ---")
                
                # Use a try...except block to process each row independently
                try:
                    bien_data = {}
                    resguardo_data = {}
                    
                    # 1. Map columns from the single mapping dictionary to the correct database tables
                    for excel_header, db_col in COLUMN_MAPPING.items():
                        # Get the value from the Excel row, using the case-insensitive header map
                        excel_col_name = excel_headers_map.get(excel_header.upper().strip())
                        if excel_col_name:
                            value = row.get(excel_col_name)
                            cleaned_value = convert_to_db_type(db_col, value)

                            if db_col in BIENES_COLUMNS:
                                bien_data[db_col] = cleaned_value
                            elif db_col in RESGUARDOS_COLUMNS:
                                resguardo_data[db_col] = cleaned_value
                    
                    # 2. Get or create the Bien record and get its ID
                    id_bien = get_or_create_bien(cursor, bien_data)

                    # 3. Process Areas Data
                    area_name = None
                    if EXCEL_AREA_COL_NAME.upper().strip() in excel_headers_map:
                        area_name = row.get(excel_headers_map[EXCEL_AREA_COL_NAME.upper().strip()])
                    
                    id_area = get_or_create_area(cursor, area_name)
                    if not id_area:
                        raise ValueError("El campo 'Area' es obligatorio y no se encontró o estaba vacío.")
                    
                   
                    resguardo_data['id_bien'] = id_bien
                    resguardo_data['id_area'] = id_area

                    # 5. Insert the Resguardo record
                    cols = ', '.join(f"`{col}`" for col in resguardo_data.keys())
                    placeholders = ', '.join(['%s'] * len(resguardo_data))
                    query = f"INSERT INTO resguardos ({cols}) VALUES ({placeholders})"
                    
                    cursor.execute(query, tuple(resguardo_data.values()))
                    inserted_count += 1
                    print(f"    -> Éxito: Fila {index + 2} insertada correctamente.")

                except (mysql.connector.Error, ValueError, Exception) as err:
                    error_msg = f"Error de procesamiento: {err}"
                    if isinstance(err, mysql.connector.Error) and err.errno == 1062:
                        error_msg = f"Error de duplicado para No_Inventario/No_Resguardo. Se omitió la fila. Error: {err}"
                    
                    # Prepare the row for the error table, including all possible columns
                    error_row_data = {'upload_id': upload_id}
                    for db_col in FULL_DB_COLUMNS:
                        excel_col_name = None
                        # Find the original Excel column name from the single mapping
                        for excel_header, mapped_db_col in COLUMN_MAPPING.items():
                            if mapped_db_col == db_col:
                                excel_col_name = excel_headers_map.get(excel_header.upper().strip())
                                break
                        
                        if excel_col_name:
                            value = row.get(excel_col_name)
                            error_row_data[db_col] = str(value) if pd.notna(value) else ''
                        else:
                            error_row_data[db_col] = ''
                    
                    error_row_data['error_message'] = error_msg
                    error_rows.append(error_row_data)
                    skipped_count += 1
                    print(f"    -> OMITIDO: {error_msg} ")
                    traceback.print_exc()

            if inserted_count > 0:
                conn.commit()
                flash(f"Se importaron {inserted_count} resguardos correctamente.", 'success')
                print(f"\n--- COMMIT EXITOSO: Se insertaron {inserted_count} filas. ---")
            else:
                conn.rollback()
                print(f"\n--- ROLLBACK: No se insertaron filas. ---")
                if not error_rows:
                    flash("El archivo Excel estaba vacío o no contenía datos válidos para importar.", 'info')

            if error_rows:
                # Insert the collected error rows into the `resguardo_errores` table in a separate step
                try:
                    error_cols_to_insert = [key for key in error_rows[0].keys()]
                    error_cols = ', '.join(f"`{col}`" for col in error_cols_to_insert)
                    error_placeholders = ', '.join(['%s'] * len(error_cols_to_insert))
                    error_query = f"INSERT INTO resguardo_errores ({error_cols}) VALUES ({error_placeholders})"
                    
                    error_values = [tuple(row[key] for key in error_cols_to_insert) for row in error_rows]

                    cursor.executemany(error_query, error_values)
                    conn.commit()
                    session['upload_id'] = upload_id
                    
                    flash(f"Se importaron {inserted_count} resguardos correctamente. Se omitieron {skipped_count} filas debido a errores. Por favor, revisa y corrige las filas a continuación.", 'warning')
                    return redirect(url_for('excel_import.handle_errors'))
                except Exception as e:
                    print(f"Error al insertar filas de error: {e}")
                    traceback.print_exc()
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

@excel_import_bp.route('/handle_errors')
@login_required
@permission_required('resguardos.crear_resguardo')
def handle_errors():
    """Displays a page with rows that had import errors for manual editing."""
    upload_id = session.get('upload_id')
    if not upload_id:
        flash("No hay filas con errores para revisar.", 'info')
        return redirect(url_for('index')) # Use blueprint prefix

    conn, cursor = get_db() # Use dictionary cursor
    if not conn:
        return redirect(url_for('index')) # Use blueprint prefix

    error_rows = []
    total_skipped = 0
    try:
        cursor.execute("SELECT COUNT(*) FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        total_skipped = cursor.fetchone()['COUNT(*)']

        limit = 50
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s ORDER BY id ASC LIMIT %s OFFSET 0", (upload_id, limit))
        error_rows = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Error al obtener filas de error: {err}", 'error')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            
    if not error_rows:
        session.pop('upload_id', None)
        flash("No hay filas con errores para revisar.", 'info')
        return redirect(url_for('index')) # Use blueprint prefix

    template_error_rows = []
    # FULL_DB_COLUMNS needs to be correctly populated for error table display
    # This might need to be retrieved dynamically if resguardo_errores has different cols
    for row in error_rows:
        original_row = {col: row.get(col, '') for col in FULL_DB_COLUMNS}
        template_error_rows.append({
            'id': row.get('id'),
            'original_row': original_row,
            'error': row.get('error_message', 'Error desconocido')
        })

    return render_template('handle_errors.html', 
        error_rows=template_error_rows, 
        columns=FULL_DB_COLUMNS, # Pass FULL_DB_COLUMNS from config or dynamic
        total_skipped=total_skipped, 
        upload_id=upload_id,
        initial_limit=limit,
        has_more=(len(error_rows) < total_skipped)
    )

@excel_import_bp.route('/get_error_rows_paginated/<string:upload_id>')
@login_required
@permission_required('resguardos.crear_resguardo')
def get_error_rows_paginated(upload_id):
    """Fetches paginated error rows via AJAX."""
    conn, cursor = get_db() # Use dictionary cursor
    if not conn:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    offset = request.args.get('offset', type=int, default=0)
    limit = request.args.get('limit', type=int, default=20)
    
    error_rows = []
    try:
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s ORDER BY id ASC LIMIT %s OFFSET %s", (upload_id, limit, offset))
        error_rows = cursor.fetchall()
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    template_error_rows = []
    for row in error_rows:
        original_row = {col: row.get(col, '') for col in FULL_DB_COLUMNS} # Use FULL_DB_COLUMNS
        template_error_rows.append({
            'id': row.get('id'),
            'original_row': original_row,
            'error': row.get('error_message', 'Error desconocido')
        })

    has_more = len(template_error_rows) == limit
    
    return jsonify({
        'success': True, 
        'rows': template_error_rows, 
        'has_more': has_more,
        'next_offset': offset + len(template_error_rows)
    })

@excel_import_bp.route('/save_error_row/<string:upload_id>/<int:row_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def save_error_row(upload_id, row_id):
    """Saves a single row with errors after being manually corrected."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor()
    try:
        row_to_save = request.form.to_dict()
        
        insert_data = {}
        # VALID_DB_COLUMNS must include ALL columns you want to insert into 'resguardo' table
        # Make sure `Imagen_Path` and `Fecha_Registro` are handled correctly
        # If 'Fecha_Registro' is auto-generated by DB, don't include it here
        for db_col in VALID_DB_COLUMNS: 
            value = row_to_save.get(db_col)
            try:
                # Convert the value using the same logic as upload_excel
                converted_value = convert_to_db_type(db_col, value)
                insert_data[db_col] = converted_value
            except ValueError as ve:
                conn.rollback()
                return jsonify({'success': False, 'message': f"Error de formato en '{db_col}': {str(ve)}"}), 400

        # Validate mandatory fields again before final insert
        if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
            conn.rollback()
            return jsonify({'success': False, 'message': "Los campos 'No_Inventario' y 'No_Resguardo' son obligatorios."}), 400

        cols = ', '.join(f"`{col}`" for col in insert_data.keys())
        placeholders = ', '.join(['%s'] * len(insert_data))
        query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"

        cursor.execute(query, tuple(insert_data.values()))
        
        # Delete the row from the error table if insertion is successful
        cursor.execute("DELETE FROM resguardo_errores WHERE id = %s AND upload_id = %s", (row_id, upload_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Fila corregida y guardada exitosamente.'}), 200

    except mysql.connector.Error as e:
        conn.rollback()
        print(f"Database error saving error row: {type(e).__name__}: {e}")
        if e.errno == 1062: # Duplicate entry error
            return jsonify({'success': False, 'message': "Error: Un resguardo con el mismo 'No_Inventario' o 'No_Resguardo' ya existe."}), 409
        return jsonify({'success': False, 'message': f"Error de base de datos: {e}"}), 500
    except Exception as e:
        conn.rollback()
        print(f"Unexpected error saving error row: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'message': f"Ocurrió un error inesperado al guardar: {e}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Add a route to delete an error row
@excel_import_bp.route('/delete_error_row/<string:upload_id>/<int:row_id>', methods=['POST'])
@login_required
@permission_required('resguardos.crear_resguardo')
def delete_error_row(upload_id, row_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM resguardo_errores WHERE id = %s AND upload_id = %s", (row_id, upload_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Fila de error eliminada exitosamente.'}), 200
    except Exception as e:
        conn.rollback()
        print(f"Error deleting error row: {type(e).__name__}: {e}")
        return jsonify({'success': False, 'message': f"Error al eliminar la fila de error: {e}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@excel_import_bp.route('/exportar_resguardos_excel', methods=['POST'])
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
            # Ensure Tipo_De_Resguardo is handled correctly in SELECT
            # If Tipo_De_Resguardo is actually a string like 'Sujeto de Control' or 'Resguardo Normal' in your DB
            # then the CASE statement might be redundant or needs to match string values.
            # Assuming Tipo_De_Resguardo is indeed 1 for Sujeto de Control and something else for Normal.
            # If it's a string in the DB, just select it directly.
            
            # Adjust this query based on how 'Tipo_De_Resguardo' is stored (int or string)
            # Example if Tipo_De_Resguardo is stored as string:
            # columns_str = ', '.join(selected_columns)
            # cursor.execute(f"SELECT {columns_str} FROM resguardo ORDER BY Tipo_De_Resguardo DESC, id")

            # Example if Tipo_De_Resguardo is stored as int/boolean (as your original CASE implies)
            columns_str = ', '.join(selected_columns)
            cursor.execute(f"""
                SELECT {columns_str}, 
                        CASE 
                            WHEN Tipo_De_Resguardo = 1 THEN 'Sujeto de Control'
                            ELSE 'Resguardo Normal'
                        END AS Tipo_De_Resguardo_Export
                FROM resguardo
                ORDER BY Tipo_De_Resguardo DESC, id
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