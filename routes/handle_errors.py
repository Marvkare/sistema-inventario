# your_flask_app/routes/resguardos.py
# app.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file,jsonify
from flask_login import login_required, current_user 
import mysql.connector
import os
import traceback
from pypdf import PdfReader, PdfWriter
import pypdf.generic
from werkzeug.utils import secure_filename

from database import get_db, get_db_connection, get_table_columns

handle_errors_bp = Blueprint('errors', __name__)


@handle_errors_bp.route('/handle_errors')
@login_required
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
    total_skipped = 0
    try:
        # Get total count first
        cursor.execute("SELECT COUNT(*) FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        total_skipped = cursor.fetchone()['COUNT(*)']

        # Get the first 50 rows for initial load
        limit = 50
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s ORDER BY id ASC LIMIT %s OFFSET 0", (upload_id, limit))
        error_rows = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Error al obtener filas de error: {err}", 'error')
    finally:
        cursor.close()
        conn.close()
    
    if not error_rows:
        session.pop('upload_id', None)
        flash("No hay filas con errores para revisar.", 'info')
        return redirect(url_for('index'))

    template_error_rows = []
    for row in error_rows:
        original_row = {col: row.get(col, '') for col in FULL_DB_COLUMNS}
        template_error_rows.append({
            'id': row.get('id'),
            'original_row': original_row,
            'error': row.get('error_message', 'Error desconocido')
        })

    return render_template('handle_errors.html', 
        error_rows=template_error_rows, 
        columns=FULL_DB_COLUMNS, 
        total_skipped=total_skipped, 
        upload_id=upload_id,
        initial_limit=limit,
        has_more=(len(error_rows) < total_skipped)
    )

@handle_errors_bp.route('/get_error_rows_paginated/<string:upload_id>')
@login_required
def get_error_rows_paginated(upload_id):
    """Fetches paginated error rows via AJAX."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    offset = request.args.get('offset', type=int, default=0)
    limit = request.args.get('limit', type=int, default=20)
    
    cursor = conn.cursor(dictionary=True)
    error_rows = []
    try:
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s ORDER BY id ASC LIMIT %s OFFSET %s", (upload_id, limit, offset))
        error_rows = cursor.fetchall()
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

    template_error_rows = []
    for row in error_rows:
        original_row = {col: row.get(col, '') for col in FULL_DB_COLUMNS}
        template_error_rows.append({
            'id': row.get('id'),
            'original_row': original_row,
            'error': row.get('error_message', 'Error desconocido')
        })

    # Check if there are more rows to fetch
    has_more = len(template_error_rows) == limit
    
    return jsonify({
        'success': True, 
        'rows': template_error_rows, 
        'has_more': has_more,
        'next_offset': offset + len(template_error_rows)
    })


@handle_errors_bp.route('/save_error_row/<string:upload_id>/<int:row_id>', methods=['POST'])
@login_required
def save_error_row(upload_id, row_id):
    """Saves a single row with errors after being manually corrected."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor()
    try:
        row_to_save = request.form.to_dict()
        
        insert_data = {}
        for db_col in VALID_DB_COLUMNS:
            value = row_to_save.get(db_col)
            try:
                insert_data[db_col] = convert_to_db_type(db_col, value)
            except ValueError as ve:
                conn.rollback()
                return jsonify({'success': False, 'message': f'Error de conversión en campo "{db_col}": {ve}'}), 400

        if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
            conn.rollback()
            return jsonify({'success': False, 'message': "'No_Inventario' o 'No_Resguardo' son obligatorios."}), 400
        
        cols = ', '.join(f"`{col}`" for col in insert_data.keys())
        placeholders = ', '.join(['%s'] * len(insert_data))
        query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
        cursor.execute(query, tuple(insert_data.values()))
        
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


@handle_errors_bp.route('/save_all_error_rows/<string:upload_id>', methods=['POST'])
@login_required
def save_all_error_rows(upload_id):
    """Saves all error rows that have been corrected."""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error de conexión a la base de datos.'}), 500

    cursor = conn.cursor(dictionary=True)
    saved_count = 0
    errors = []
    
    all_form_data = request.form.to_dict()

    try:
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        error_rows_from_db = cursor.fetchall()
        
        for index, db_error_row in enumerate(error_rows_from_db):
            try:
                insert_data = {}
                for db_col in VALID_DB_COLUMNS:
                    form_key = f"{db_col}-{index}"
                    value = all_form_data.get(form_key, db_error_row.get(db_col))
                    
                    if value is None:
                        continue
                    
                    insert_data[db_col] = convert_to_db_type(db_col, value)

                if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
                    raise ValueError("'No_Inventario' o 'No_Resguardo' son obligatorios.")

                cols = ', '.join(f"`{col}`" for col in insert_data.keys())
                placeholders = ', '.join(['%s'] * len(insert_data))
                query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
                cursor.execute(query, tuple(insert_data.values()))
                
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
