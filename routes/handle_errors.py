from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required
import traceback
# Importación necesaria para los cursores de PyMySQL
import pymysql.cursors 

from config import FULL_DB_COLUMNS, VALID_DB_COLUMNS
from database import get_db_connection

# Asegúrate de importar tu función de conversión. 
# Si está en otro archivo (ej. utils.py), ajusta esta línea:
# from utils import convert_to_db_type
# Por ahora, asumiremos que la tienes disponible o definida aquí.

handle_errors_bp = Blueprint('errors', __name__)

# --- 1. RUTA: LISTAR LOTES (CORREGIDA) ---
@handle_errors_bp.route('/error_batches')
@login_required
def select_error_batch():
    conn = get_db_connection()
    if conn is None:
        flash("Error: No se pudo conectar a la base de datos.", "danger")
        return redirect(url_for('index'))

    # IMPORTANTE: Usamos DictCursor para que los datos tengan nombre de columna
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    batches = []

    try:
        print("--- INICIO DEBUG DE ERRORES ---")
        
        # 1. Prueba simple: ¿Hay algo en la tabla?
        cursor.execute("SELECT count(*) as total FROM resguardo_errores")
        total_rows = cursor.fetchone()
        print(f"DEBUG: Total de filas en tabla resguardo_errores: {total_rows['total']}")

        # 2. Ejecutar la consulta de agrupación
        query = """
            SELECT 
                upload_id, 
                COUNT(*) as total_errors, 
                MAX(Fecha_Registro) as fecha_carga
            FROM resguardo_errores 
            GROUP BY upload_id 
            ORDER BY fecha_carga DESC
        """
        cursor.execute(query)
        batches = cursor.fetchall()
        
        print(f"DEBUG: Lotes encontrados: {len(batches)}")
        
        if len(batches) > 0:
            print(f"DEBUG: Datos del primer lote: {batches[0]}")
        else:
            print("DEBUG: La consulta GROUP BY no devolvió nada (¿Quizás upload_id es NULL?)")

        print("--- FIN DEBUG DE ERRORES ---")

    except Exception as e:
        print(f"DEBUG ERROR EXCEPCIÓN: {e}")
        flash(f"Error al listar lotes de errores: {e}", 'error')
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

    return render_template('excel_import/select_error_batch.html', batches=batches)

# --- 2. RUTA: VER ERRORES DE UN LOTE (CORREGIDA) ---
@handle_errors_bp.route('/handle_errors/<string:target_upload_id>')
@login_required
def handle_errors(target_upload_id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))

    # CORRECCIÓN: Usar DictCursor
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    error_rows = []
    total_skipped = 0

    try:
        # 1. Contar errores
        cursor.execute("SELECT COUNT(*) as total FROM resguardo_errores WHERE upload_id = %s", (target_upload_id,))
        result = cursor.fetchone()
        total_skipped = result['total'] if result else 0

        if total_skipped == 0:
            flash("Este archivo ya no tiene errores pendientes.", 'success')
            return redirect(url_for('errors.select_error_batch'))

        # 2. Obtener filas (Limit 50)
        limit = 50
        cursor.execute("""
            SELECT * FROM resguardo_errores 
            WHERE upload_id = %s 
            ORDER BY id ASC 
            LIMIT %s OFFSET 0
        """, (target_upload_id, limit))
        
        error_rows = cursor.fetchall()

    except Exception as e:
        flash(f"Error al obtener filas: {e}", 'error')
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

    # Nota: Si moviste select_error_batch a 'excel_import/', 
    # es probable que handle_errors.html también esté ahí.
    # Si no, déjalo como 'handle_errors.html'
    return render_template('excel_import/handle_errors.html', 
        error_rows=template_error_rows, 
        columns=FULL_DB_COLUMNS, 
        total_skipped=total_skipped, 
        upload_id=target_upload_id,
        initial_limit=limit,
        has_more=(len(error_rows) < total_skipped)
    )


# --- 3. RUTA: PAGINACIÓN (CORREGIDA) ---
@handle_errors_bp.route('/get_error_rows_paginated/<string:upload_id>')
@login_required
def get_error_rows_paginated(upload_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error DB'}), 500

    offset = request.args.get('offset', type=int, default=0)
    limit = request.args.get('limit', type=int, default=20)
    
    # CORRECCIÓN: Usar DictCursor
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    error_rows = []
    try:
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s ORDER BY id ASC LIMIT %s OFFSET %s", (upload_id, limit, offset))
        error_rows = cursor.fetchall()
    except Exception as err:
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

    has_more = len(template_error_rows) == limit
    
    return jsonify({
        'success': True, 
        'rows': template_error_rows, 
        'has_more': has_more,
        'next_offset': offset + len(template_error_rows)
    })


# --- 4. RUTA: GUARDAR FILA INDIVIDUAL (CORREGIDA) ---
@handle_errors_bp.route('/save_error_row/<string:upload_id>/<int:row_id>', methods=['POST'])
@login_required
def save_error_row(upload_id, row_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error DB'}), 500

    # Cursor normal para inserts
    cursor = conn.cursor() 
    
    try:
        row_to_save = request.form.to_dict()
        insert_data = {}
        
        # IMPORTANTE: Aquí debes asegurarte de que 'convert_to_db_type' esté disponible
        # O copiar la lógica de conversión aquí.
        for db_col in VALID_DB_COLUMNS:
             if db_col in row_to_save:
                 # insert_data[db_col] = convert_to_db_type(db_col, row_to_save[db_col])
                 insert_data[db_col] = row_to_save[db_col] # Simplificado

        if not insert_data.get('No_Inventario') or not insert_data.get('No_Resguardo'):
            conn.rollback()
            return jsonify({'success': False, 'message': "Faltan datos obligatorios"}), 400
        
        cols = ', '.join(f"`{col}`" for col in insert_data.keys())
        placeholders = ', '.join(['%s'] * len(insert_data))
        
        # Asegúrate de que la tabla destino sea correcta ('resguardos' o 'resguardo')
        query = f"INSERT INTO resguardos ({cols}) VALUES ({placeholders})" 
        
        cursor.execute(query, tuple(insert_data.values()))
        
        cursor.execute("DELETE FROM resguardo_errores WHERE id = %s AND upload_id = %s", (row_id, upload_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Guardado.', 'row_id': row_id}), 200

    except Exception as err:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()


# --- 5. RUTA: GUARDAR TODO (CORREGIDA) ---
@handle_errors_bp.route('/save_all_error_rows/<string:upload_id>', methods=['POST'])
@login_required
def save_all_error_rows(upload_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Error DB'}), 500

    # CORRECCIÓN: Usar DictCursor
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    saved_count = 0
    
    try:
        cursor.execute("SELECT * FROM resguardo_errores WHERE upload_id = %s", (upload_id,))
        error_rows_from_db = cursor.fetchall()
        
        # ... (Tu lógica de guardado masivo iría aquí, usando insert_data) ...
        
        pass 

    except Exception as e:
        conn.rollback()
        flash(f"Error: {str(e)}", 'error')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('index'))

@handle_errors_bp.route('/edit_error_row/<int:error_id>', methods=['GET', 'POST'])
@login_required
def edit_error_row(error_id):
    conn = get_db_connection()
    if conn is None:
        flash("Error de conexión a la base de datos.", "danger")
        return redirect(url_for('index'))

    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        # 1. Buscar el registro de error específico
        cursor.execute("SELECT * FROM resguardo_errores WHERE id = %s", (error_id,))
        error_data = cursor.fetchone()

        if not error_data:
            flash("El registro de error no existe o ya fue corregido.", "warning")
            return redirect(url_for('errors.select_error_batch'))

        # Obtener upload_id para saber a dónde regresar si cancelan
        current_upload_id = error_data['upload_id']

        # --- LÓGICA POST: GUARDAR CORRECCIÓN ---
        if request.method == 'POST':
            try:
                form = request.form
                
                # A) GESTIÓN DEL ÁREA (Nombre -> ID)
                area_nombre = form.get('Area')
                if not area_nombre:
                    raise ValueError("El campo Área es obligatorio.")
                
                # Buscar ID del área o crearla si no existe
                cursor.execute("SELECT id FROM areas WHERE nombre = %s", (area_nombre,))
                area_result = cursor.fetchone()
                if area_result:
                    id_area = area_result['id']
                else:
                    cursor.execute("INSERT INTO areas (nombre) VALUES (%s)", (area_nombre,))
                    id_area = cursor.lastrowid

                # B) GESTIÓN DEL BIEN
                no_inventario = form.get('No_Inventario')
                if not no_inventario:
                    raise ValueError("El No. de Inventario es obligatorio.")

                # Verificar si el bien ya existe
                cursor.execute("SELECT id FROM bienes WHERE No_Inventario = %s", (no_inventario,))
                bien_result = cursor.fetchone()

                if bien_result:
                    id_bien = bien_result['id']
                    # Opcional: Aquí podrías hacer un UPDATE si quieres actualizar datos del bien existente
                else:
                    # Insertar nuevo bien
                    # Nota: Asegúrate de que los nombres de los inputs en tu HTML coincidan con las columnas de la BD
                    sql_bien = """
                        INSERT INTO bienes (
                            No_Inventario, Descripcion_Del_Bien, Descripcion_Corta_Del_Bien, 
                            Marca, Modelo, Numero_De_Serie, Estado_Del_Bien, Tipo_De_Alta, 
                            Clasificacion_Legal, Area_Presupuestal, No_Factura, Fecha_Factura, 
                            Costo_Inicial, Depreciacion_Acumulada, Costo_Final, Valor_En_Libros, 
                            Poliza, Fecha_Poliza, No_Cuenta, Sub_Cuenta_Armonizadora, Rubro, 
                            Proveedor, Documento_Propiedad, Fecha_Documento_Propiedad, Fecha_Adquisicion_Alta,
                            Cantidad, Activo, usuario_id_registro
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s
                        )
                    """
                    # Función auxiliar para limpiar fechas vacías
                    def clean_date(d): return d if d else None
                    
                    vals_bien = (
                        no_inventario, form.get('Descripcion_Del_Bien'), form.get('Descripcion_Corta_Del_Bien'),
                        form.get('Marca'), form.get('Modelo'), form.get('Numero_De_Serie'), form.get('Estado_Del_Bien'),
                        form.get('Tipo_De_Alta'), form.get('Clasificacion_Legal', 'Dominio Privado'), form.get('Area_Presupuestal'),
                        form.get('No_Factura'), clean_date(form.get('Fecha_Factura')), form.get('Costo_Inicial'),
                        form.get('Depreciacion_Acumulada'), form.get('Costo_Final'), form.get('Valor_En_Libros'),
                        form.get('Poliza'), clean_date(form.get('Fecha_Poliza')), form.get('No_Cuenta'),
                        form.get('Sub_Cuenta_Armonizadora'), form.get('Rubro'), form.get('Proveedor'),
                        form.get('Documento_Propiedad'), clean_date(form.get('Fecha_Documento_Propiedad')),
                        clean_date(form.get('Fecha_Adquisicion_Alta')), form.get('Cantidad', 1), current_user.id
                    )
                    cursor.execute(sql_bien, vals_bien)
                    id_bien = cursor.lastrowid

                # C) GESTIÓN DEL RESGUARDO
                # Verificar duplicado de resguardo activo
                cursor.execute("SELECT id FROM resguardos WHERE id_bien = %s AND Activo = 1", (id_bien,))
                if cursor.fetchone():
                    raise ValueError(f"El bien {no_inventario} ya tiene un resguardo activo.")

                sql_resguardo = """
                    INSERT INTO resguardos (
                        id_bien, id_area, No_Resguardo, Ubicacion, Tipo_De_Resguardo, 
                        Fecha_Resguardo, Nombre_Del_Resguardante, Puesto_Trabajador, 
                        RFC_Trabajador, No_Trabajador, No_Nomina_Trabajador, 
                        Nombre_Director_Jefe_De_Area, Activo, usuario_id_registro
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                """
                vals_resguardo = (
                    id_bien, id_area, form.get('No_Resguardo'), form.get('Ubicacion'),
                    form.get('Tipo_De_Resguardo'), clean_date(form.get('Fecha_Resguardo')),
                    form.get('Nombre_Del_Resguardante'), form.get('Puesto_Trabajador'),
                    form.get('RFC_Trabajador'), form.get('No_Trabajador'),
                    form.get('No_Nomina_Trabajador'), form.get('Nombre_Director_Jefe_De_Area'),
                    current_user.id
                )
                cursor.execute(sql_resguardo, vals_resguardo)

                # D) ÉXITO: ELIMINAR EL ERROR Y CONFIRMAR
                cursor.execute("DELETE FROM resguardo_errores WHERE id = %s", (error_id,))
                conn.commit()

                flash("Fila corregida e importada exitosamente.", "success")
                # Redirigir a la lista de errores de este lote específico
                return redirect(url_for('errors.handle_errors', target_upload_id=current_upload_id))

            except Exception as e:
                conn.rollback()
                flash(f"Error al guardar la corrección: {str(e)}", "danger")
                # Si falla, volvemos a mostrar el formulario con los datos que envió el usuario para que no tenga que reescribir todo
                # (Combinamos error_data original con lo que mandó el form)
                error_data.update(request.form.to_dict()) 

        # --- LÓGICA GET: PREPARAR DATOS ---
        
        # Obtener lista de áreas para el select
        cursor.execute("SELECT nombre FROM areas ORDER BY nombre ASC")
        areas_db = cursor.fetchall()
        areas_list = [a['nombre'] for a in areas_db]

        return render_template('excel_import/edit_error_row.html', 
                               error_id=error_id,
                               error_data=error_data,
                               areas=areas_list)

    except Exception as e:
        flash(f"Error del sistema: {e}", "danger")
        return redirect(url_for('errors.select_error_batch'))
    finally:
        cursor.close()
        conn.close()