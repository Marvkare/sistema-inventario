from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify, send_file
import pandas as pd
import uuid
import traceback
from datetime import datetime
from io import BytesIO
import re
from decimal import Decimal, InvalidOperation
# Se importan las funciones y variables de tus otros archivos
from database import get_db_connection
from config import COLUMN_MAPPING, BIENES_COLUMNS, RESGUARDOS_COLUMNS, EXCEL_AREA_COL_NAME, FULL_DB_COLUMNS
from decorators import permission_required
from log_activity import log_activity
# CORRECCIÓN: Se añaden las importaciones que faltaban
from flask_login import login_required, current_user

excel_import_bp = Blueprint('excel_import', __name__)

# Columnas que se convertirán a FECHA (formato YYYY-MM-DD)
# Columnas que se convertirán a FECHA (formato YYYY-MM-DD)
# --- Definición de Tipos de Columna ---
# IMPORTANTE: Estos son los nombres de las columnas de la BASE DE DATOS
# (los 'values' de tu COLUMN_MAPPING)

# Columnas que se convertirán a FECHA (formato YYYY-MM-DD)
DATE_COLS = [
    "Fecha_Poliza",
    "Fecha_Factura",
    "Fecha_Documento_Propiedad",
    "Fecha_Adquisicion_Alta",
    "Fecha_Resguardo"
]

# Columnas que se convertirán a NÚMERO DECIMAL (para dinero)
DECIMAL_COLS = [
    "Costo_Inicial",
    "Depreciacion_Acumulada",
    "Costo_Final",
    "Valor_En_Libros"
]

# Columnas que se convertirán a NÚMERO ENTERO
INT_COLS = [
    "Cantidad",
    "Tipo_De_Resguardo",
    "No_Nomina_Trabajador"
]


def convert_to_db_type(db_col, value):
    """
    Limpia y convierte un valor de Excel al tipo de dato correcto 
    para la base de datos (como string, Decimal, int, o None).
    
    :param db_col: El nombre de la columna (del encabezado de Excel).
    :param value: El valor de la celda.
    :return: El valor limpio y tipado.
    """
    
    # 1. FILTRO UNIVERSAL DE NULOS
    if pd.isna(value) or value is None or str(value).strip() == '':
        return None

    str_value = str(value).strip()

    # 2. FILTRO DE FECHAS
    if db_col in DATE_COLS:
        
        # Corrección para el error '1970-01-01'
        if str_value == '0' or value == 0:
            return None
        
        # --- ¡ESTA ES LA PARTE QUE SOLUCIONA TU ERROR! ---
        # Primero: Intenta ver si es un número (serial de Excel como 45789)
        if isinstance(value, (int, float)):
            try:
                # Convertir número de serie de Excel
                return pd.to_datetime(value, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                raise ValueError(f"Número de serie de fecha no válido: '{value}' en '{db_col}'")
        
        # Segundo: Si no es un número, intenta parsearlo como texto (ej. "24/10/2025")
        try:
            return pd.to_datetime(str_value, dayfirst=True).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            raise ValueError(f"Formato de fecha no válido: '{value}' en columna '{db_col}'")
        # --- FIN DE LA CORRECCIÓN ---
            
    # 3. FILTRO DE NÚMEROS DECIMALES (Costos, Valores)
    elif db_col in DECIMAL_COLS:
        
        cleaned_value = str_value.replace('$', '').replace(',', '').strip()
        
        if cleaned_value == '':
            return None
            
        try:
            return Decimal(cleaned_value)
        except InvalidOperation:
            raise ValueError(f"Formato de número decimal no válido: '{value}' en columna '{db_col}'")

    # 4. FILTRO DE NÚMEROS ENTEROS (Cantidad, etc.)
    elif db_col in INT_COLS:
        
        cleaned_value = str_value.replace(',', '').strip()
        
        if cleaned_value.endswith('.0'):
            cleaned_value = cleaned_value[:-2]

        if cleaned_value == '':
            return None

        try:
            return int(cleaned_value)
        except (ValueError, TypeError):
            raise ValueError(f"Formato de número entero no válido: '{value}' en columna '{db_col}'")

    # 5. FILTRO PARA TODO LO DEMÁS (Texto)
    else:
        # Devuelve el string limpio
        return str_value


def get_or_create_bien(cursor, bien_data):
    no_inventario = bien_data.get('No_Inventario')
    if not no_inventario:
        raise ValueError("La columna 'No_Inventario' es obligatoria.")
    
    cursor.execute("SELECT id FROM bienes WHERE No_Inventario = %s", (no_inventario,))
    result = cursor.fetchone()
    if result: 
        return result['id']
    
    # --- CORRECCIÓN: Asegurar campos obligatorios ---
    # Campos obligatorios según el modelo Bienes
    required_fields = {
        'Clasificacion_Legal': 'Dominio Privado',  # Valor por defecto
        'Activo': 1,  # Valor por defecto
        'usuario_id_registro': current_user.id  # Usuario actual
    }
    
    print("Required fields:", required_fields)
    print("Bien data antes:", bien_data)
    
    # Agregar campos obligatorios que no estén en bien_data
    for field, default_value in required_fields.items():
        if field not in bien_data or bien_data[field] is None:
            bien_data[field] = default_value
    
    print("Bien data después:", bien_data)  # <-- Agregar este print para verificar
    
    # Preparar la consulta de inserción
    cols = ', '.join(f"`{col}`" for col in bien_data.keys())
    placeholders = ', '.join(['%s'] * len(bien_data))
    query = f"INSERT INTO bienes ({cols}) VALUES ({placeholders})"
    
    try:
        print("Query:", query)  # <-- Ver la consulta SQL
        print("Values:", tuple(bien_data.values()))  # <-- Ver los valores
        cursor.execute(query, tuple(bien_data.values()))
        return cursor.lastrowid
    except Exception as e:
        # Si hay error de duplicado, intentar obtener el ID existente
        if "Duplicate entry" in str(e) and "No_Inventario" in str(e):
            cursor.execute("SELECT id FROM bienes WHERE No_Inventario = %s", (no_inventario,))
            result = cursor.fetchone()
            if result:
                return result['id']
        raise e
    
def get_or_create_area(cursor, area_name):
    if not area_name or pd.isna(area_name): return None
    cursor.execute("SELECT id FROM areas WHERE nombre = %s", (area_name,))
    result = cursor.fetchone()
    if result: return result['id']
    
    cursor.execute("INSERT INTO areas (nombre) VALUES (%s)", (area_name,))
    return cursor.lastrowid

def try_format_date_for_html(date_string):
    """Intenta convertir un string de fecha a formato YYYY-MM-DD para inputs HTML."""
    if not date_string:
        return ""
    try:
        # Intenta parsear la fecha (siendo flexible con el formato) y la convierte
        return pd.to_datetime(date_string, dayfirst=True).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        # Si falla, devuelve el string original para que el usuario pueda ver qué estaba mal
        return date_string

@excel_import_bp.route('/upload_excel', methods=['POST'])
@login_required
@permission_required('excel_import.upload_excel')
def upload_excel():
    if 'excel_file' not in request.files or not request.files['excel_file'].filename:
        flash("No se seleccionó ningún archivo.", 'danger')
        return redirect(url_for('resguardos.crear_resguardo'))

    file = request.files['excel_file']
    conn = None
    inserted_count = 0
    error_rows = []
    upload_id = str(uuid.uuid4())
    
    # Registrar inicio de la actividad (SOLO si db está disponible)
    try:
        from app import db  # Importar aquí para evitar errores
        log_activity(
            action='INICIO_IMPORTACION_EXCEL',
            category='IMPORTACION',
            details=f"Usuario '{current_user.username}' inició importación desde archivo: {file.filename}",
            resource_id=upload_id
        ) 
        db.session.commit()
    except Exception as log_error:
        print(f"Error inicial en log: {log_error}")

    try:
        df = pd.read_excel(file)
        excel_headers_map = {str(col).upper().strip(): str(col) for col in df.columns}
        conn = get_db_connection()  # ← MANTIENES tu conexión actual
        cursor = conn.cursor(dictionary=True)
        
        # Registrar lectura exitosa del archivo
        try:
            log_activity(
                action='ARCHIVO_LEIDO',
                category='IMPORTACION',
                details=f"Usuario '{current_user.username}' leyó un archivo. Filas: {len(df)}, Columnas: {len(df.columns)}",
                resource_id=upload_id
            )
            db.session.commit()
        except Exception as log_error:
            print(f"Error en log de archivo leído: {log_error}")
        
        for index, row in df.iterrows():
            try:
                bien_data = {}
                resguardo_data = {}
                
                for excel_header, db_col in COLUMN_MAPPING.items():
                    excel_col_name = excel_headers_map.get(excel_header.upper().strip())
                    if excel_col_name and excel_col_name in row:
                        value = row[excel_col_name]
                        cleaned_value = convert_to_db_type(db_col, value)
                        if db_col in BIENES_COLUMNS: bien_data[db_col] = cleaned_value
                        elif db_col in RESGUARDOS_COLUMNS: resguardo_data[db_col] = cleaned_value
                
                id_bien = get_or_create_bien(cursor, bien_data)
                
                area_name = row.get(excel_headers_map.get(EXCEL_AREA_COL_NAME.upper().strip()))
                id_area = get_or_create_area(cursor, area_name)
                if not id_area: raise ValueError("El campo 'Area' es obligatorio.")
                
                resguardo_data.update({'id_bien': id_bien, 'id_area': id_area, 'Activo': 1, 'usuario_id_registro': current_user.id})

                cols = ', '.join(f"`{col}`" for col in resguardo_data.keys())
                placeholders = ', '.join(['%s'] * len(resguardo_data))
                query = f"INSERT INTO resguardos ({cols}) VALUES ({placeholders})"
                
                cursor.execute(query, tuple(resguardo_data.values()))
                inserted_count += 1

            except Exception as err:
                error_msg = f"Error en fila {index + 2}: {err}"
                error_row_data = {'upload_id': upload_id, 'error_message': error_msg}
                
                cursor.execute("DESCRIBE resguardo_errores")
                error_table_cols = {col['Field'] for col in cursor.fetchall()}
                
                for excel_header, db_col in COLUMN_MAPPING.items():
                    if db_col in error_table_cols:
                        excel_col_name = excel_headers_map.get(excel_header.upper().strip())
                        if excel_col_name and excel_col_name in row:
                            value = row[excel_col_name]
                            error_row_data[db_col] = str(value) if pd.notna(value) else None
                
                error_rows.append(error_row_data)
                traceback.print_exc()

        if inserted_count > 0: 
            conn.commit()
            # Registrar éxito en la inserción de datos
            try:
                log_activity(
                    action='DATOS_INSERTADOS',
                    category='IMPORTACION',
                    details=f"Usuario '{current_user.username}': {inserted_count} resguardos insertados exitosamente.",
                    resource_id=upload_id
                )
                db.session.commit()
            except Exception as log_error:
                print(f"Error en log de datos insertados: {log_error}")
        
        if error_rows:
            error_cols_to_insert = list(error_rows[0].keys())
            error_cols_sql = ', '.join(f"`{col}`" for col in error_cols_to_insert)
            error_placeholders = ', '.join(['%s'] * len(error_cols_to_insert))
            error_query = f"INSERT INTO resguardo_errores ({error_cols_sql}) VALUES ({error_placeholders})"
            
            error_values = [tuple(row.get(key) for key in error_cols_to_insert) for row in error_rows]
            
            cursor.executemany(error_query, error_values)
            conn.commit()
            session['upload_id'] = upload_id
            
            # Registrar errores encontrados
            try:
                log_activity(
                    action='ERRORES_REGISTRADOS',
                    category='IMPORTACION',
                    details=f"Usuario '{current_user.username}': Se registraron {len(error_rows)} filas con problemas.",
                    resource_id=upload_id
                )
                
                log_activity(
                    action='IMPORTACION_COMPLETADA_CON_ERRORES',
                    category='IMPORTACION',
                    details=f"Usuario '{current_user.username}': Importación completada. Exitosos: {inserted_count}, Errores: {len(error_rows)}",
                    resource_id=upload_id
                )
                db.session.commit()
            except Exception as log_error:
                print(f"Error en log de errores: {log_error}")
            
            flash(f"Se importaron {inserted_count} resguardos y se omitieron {len(error_rows)} filas con errores. Por favor, revísalas.", 'warning')
            return redirect(url_for('excel_import.handle_errors'))
            
        elif inserted_count > 0:
            flash(f"Se importaron {inserted_count} resguardos exitosamente.", 'success')
            # Registrar finalización exitosa
            try:
                log_activity(
                    action='IMPORTACION_COMPLETADA_EXITOSA',
                    category='IMPORTACION',
                    details=f"Usuario '{current_user.username}': Importación completada exitosamente. Total resguardos: {inserted_count}",
                    resource_id=upload_id
                )
                db.session.commit()
            except Exception as log_error:
                print(f"Error en log de éxito: {log_error}")
            
        else:
            flash("No se encontraron filas válidas para importar en el archivo.", 'info')
            # Registrar que no había datos válidos
            try:
                log_activity(
                    action='IMPORTACION_SIN_DATOS_VALIDOS',
                    category='IMPORTACION',
                    details=f"Usuario '{current_user.username}': El archivo no contenía filas válidas para importar.",
                    resource_id=upload_id
                )
                db.session.commit()
            except Exception as log_error:
                print(f"Error en log sin datos: {log_error}")

    except Exception as e:
        if conn: 
            conn.rollback()
        
        # Registrar error fatal
        try:
            log_activity(
                action='ERROR_FATAL_IMPORTACION',
                category='IMPORTACION',
                details=f"Usuario '{current_user.username}': Error fatal al procesar archivo: {str(e)}",
                resource_id=upload_id
            )
            db.session.commit()
        except Exception as log_error:
            print(f"Error en log fatal: {log_error}")
        
        flash(f"Error fatal al procesar el archivo: {e}", 'danger')
        traceback.print_exc()
        
    finally:
        if conn and conn.is_connected(): 
            conn.close()
    
    return redirect(url_for('resguardos.crear_resguardo'))


@excel_import_bp.route('/handle_errors')
@login_required
@permission_required('excel_import.handle_errors')
def handle_errors():
    upload_id = session.get('upload_id')
    if not upload_id:
        flash("No se encontró un ID de carga de errores.", 'info')
        return redirect(url_for('resguardos.crear_resguardo'))

    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            flash("No se pudo conectar a la base de datos.", 'danger')
            return redirect(url_for('resguardos.crear_resguardo'))
        
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        errors = cursor.fetchall()

        return render_template('excel_import/handle_errors.html', errors=errors, upload_id=upload_id)
    except Exception as e:
        flash(f"Error al recuperar los detalles de la carga: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('resguardos.crear_resguardo'))
    finally:
        if conn and conn.is_connected():
            conn.close()



@excel_import_bp.route('/delete_error_row/<int:row_id>', methods=['POST'])
@login_required
@permission_required('excel_import.delete_error_row')
def delete_error_row(row_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM resguardo_errores WHERE id = %s", (row_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Fila de error eliminada.'}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f"Error al eliminar: {e}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@excel_import_bp.route('/exportar_resguardos_excel', methods=['POST'])
@login_required
@permission_required('excel_import.exportar_resguardos_excel')
def exportar_resguardos_excel():
    conn = None
    try:
        selected_columns = request.form.getlist('columns')
        if not selected_columns:
            return jsonify({'error': 'No se seleccionaron columnas'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        columns_str = ', '.join(f"`{col}`" for col in selected_columns)
        query = f"SELECT {columns_str} FROM resguardos ORDER BY id"
        cursor.execute(query)
        data = cursor.fetchall()
        
        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name='Resguardos')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='resguardos_exportados.xlsx'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@excel_import_bp.route('/edit_error/<int:error_id>', methods=['GET', 'POST'])
@login_required
@permission_required('excel_import.edit_error_row')
def edit_error_row(error_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            form_data = request.form.to_dict()
            try:
                bien_data = {}
                resguardo_data = {}
                
                for excel_header, db_col in COLUMN_MAPPING.items():
                    if db_col in form_data:
                        value = form_data[db_col]
                        cleaned_value = convert_to_db_type(db_col, value)
                        if db_col in BIENES_COLUMNS:
                            bien_data[db_col] = cleaned_value
                        elif db_col in RESGUARDOS_COLUMNS:
                            resguardo_data[db_col] = cleaned_value
                
                # --- CORRECCIÓN: Asegurar que Clasificacion_Legal tenga un valor ---
                if 'Clasificacion_Legal' not in bien_data or not bien_data['Clasificacion_Legal']:
                    bien_data['Clasificacion_Legal'] = 'Dominio Público'  # Valor por defecto
                
                id_bien = get_or_create_bien(cursor, bien_data)

                area_name = form_data.get("Area")
                id_area = get_or_create_area(cursor, area_name)
                if not id_area:
                    raise ValueError(f"El área '{area_name}' no es válida.")
                
                resguardo_data.update({'id_bien': id_bien, 'id_area': id_area, 'Activo': 1, 'usuario_id_registro': current_user.id})

                cols = ', '.join(f"`{col}`" for col in resguardo_data.keys())
                placeholders = ', '.join(['%s'] * len(resguardo_data))
                query = f"INSERT INTO resguardos ({cols}) VALUES ({placeholders})"
                
                cursor.execute(query, tuple(resguardo_data.values()))
                
                cursor.execute("DELETE FROM resguardo_errores WHERE id = %s", (error_id,))
                
                conn.commit()
                flash('Fila corregida y guardada exitosamente.', 'success')
                return redirect(url_for('excel_import.handle_errors'))

            except Exception as err:
                conn.rollback()
                flash(f"Error al guardar la corrección: {err}", 'danger')
                cursor.execute("SELECT nombre FROM areas ORDER BY nombre")
                areas = [row['nombre'] for row in cursor.fetchall()]
                return render_template('excel_import/edit_error_row.html', error_data=form_data, error_id=error_id, areas=areas)

        # Lógica para mostrar el formulario (GET)
        cursor.execute("SELECT * FROM resguardo_errores WHERE id = %s", (error_id,))
        error_data = cursor.fetchone()
        if not error_data:
            flash("Fila de error no encontrada.", "warning")
            return redirect(url_for('excel_import.handle_errors'))

        # Pre-formatear las fechas para la plantilla
        error_data['Fecha_Resguardo'] = try_format_date_for_html(error_data.get('Fecha_Resguardo'))
        error_data['Fecha_Poliza'] = try_format_date_for_html(error_data.get('Fecha_Poliza'))
        error_data['Fecha_Factura'] = try_format_date_for_html(error_data.get('Fecha_Factura'))

        cursor.execute("SELECT nombre FROM areas ORDER BY nombre")
        areas = [row['nombre'] for row in cursor.fetchall()]
        
        return render_template('excel_import/edit_error_row.html', error_data=error_data, error_id=error_id, areas=areas)

    except Exception as e:
        flash(f"Ocurrió un error: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('excel_import.handle_errors'))
    finally:
        if conn and conn.is_connected():
            conn.close()