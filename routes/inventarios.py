# inventario_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, make_response, Response
from flask_login import login_required, current_user
import traceback
import math
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import Response
from weasyprint import HTML

from config import ALLOWED_EXTENSIONS
# Se importan las funciones y variables de tus otros archivos
from database import get_db_connection
from decorators import permission_required
from log_activity import log_activity
from flask import jsonify

inventarios_bp = Blueprint('inventarios', __name__, url_prefix='/inventarios')


def allowed_file(filename):
    """Función para verificar si la extensión del archivo es permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# --- RUTA 1: VISTA PRINCIPAL DEL MÓDULO ---
@inventarios_bp.route('/')
@login_required
@permission_required('inventarios.listar_inventarios')
def listar_inventarios():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # --- CONSULTA ACTUALIZADA ---
        # Ahora usamos subconsultas para contar las áreas y los bienes de cada inventario.
        sql_query = """
            SELECT 
                i.*,
                (SELECT COUNT(ia.area_id) FROM inventario_areas ia WHERE ia.inventario_id = i.id) AS num_areas,
                (SELECT COUNT(idet.id) FROM inventario_detalle idet WHERE idet.id_inventario = i.id) AS num_bienes
            FROM inventarios i
            ORDER BY i.fecha_inicio DESC
        """
        cursor.execute(sql_query)
        todos_los_inventarios = cursor.fetchall()
        
        return render_template(
            'inventarios/lista_inventarios.html', 
            inventarios=todos_los_inventarios
        )

    except Exception as e:
        flash(f"Error al cargar los inventarios: {e}", 'danger')
        traceback.print_exc()
        return render_template('inventarios/lista_inventarios.html', inventarios=[])
    finally:
        if conn and conn.is_connected():
            conn.close()

# inventarios_routes.py

@inventarios_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@permission_required('inventarios.crear_inventario')
def crear_inventario():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # --- LÓGICA POST: PROCESAR EL FORMULARIO ---
            form_data = request.form
            nombre = form_data.get('nombre')
            tipo = form_data.get('tipo')
            area_ids = request.form.getlist('area_ids')
            user_ids = request.form.getlist('user_ids')

            if not all([nombre, tipo, area_ids, user_ids]):
                flash('Todos los campos son obligatorios.', 'warning')
                # Si la validación falla, debemos recargar los datos para volver a mostrar el formulario
                # Esta consulta es idéntica a la de la lógica GET
                sql_areas_con_detalle = """
                    SELECT a.id, a.nombre, COUNT(DISTINCT r.id_bien) AS num_bienes,
                           (SELECT r2.Nombre_Director_Jefe_De_Area FROM resguardos r2 WHERE r2.id_area = a.id AND r2.Nombre_Director_Jefe_De_Area IS NOT NULL LIMIT 1) AS jefe_de_area
                    FROM areas a
                    LEFT JOIN resguardos r ON a.id = r.id_area AND r.Activo = 1
                    GROUP BY a.id, a.nombre ORDER BY a.nombre
                """
                cursor.execute(sql_areas_con_detalle)
                areas = cursor.fetchall()
                cursor.execute("SELECT id, username FROM user ORDER BY username")
                users = cursor.fetchall()
                return render_template('inventarios/crear_inventario.html', areas=areas, users=users, form_data=form_data)

            # --- INICIO DE LA TRANSACCIÓN ---
            
            # 1. Crear el registro principal en la tabla 'inventarios'
            sql_inventario = "INSERT INTO inventarios (nombre, tipo, estatus, id_usuario_creador) VALUES (%s, %s, 'Planificado', %s)"
            cursor.execute(sql_inventario, (nombre, tipo, current_user.id))
            inventario_id = cursor.lastrowid

            # 2. Vincular las áreas seleccionadas
            sql_areas = "INSERT INTO inventario_areas (inventario_id, area_id) VALUES (%s, %s)"
            area_values = [(inventario_id, int(area_id)) for area_id in area_ids]
            cursor.executemany(sql_areas, area_values)

            # 3. Vincular los usuarios (brigada)
            sql_brigada = "INSERT INTO inventario_brigadas (inventario_id, user_id) VALUES (%s, %s)"
            user_values = [(inventario_id, int(user_id)) for user_id in user_ids]
            cursor.executemany(sql_brigada, user_values)
            
            # 4. Generar la "Cédula de Levantamiento" (los registros en 'inventario_detalle')
            format_strings = ','.join(['%s'] * len(area_ids))
            sql_bienes_a_inventariar = f"""
                SELECT b.id, r.id AS resguardo_id, r.id_area, r.Nombre_Del_Resguardante
                FROM bienes b
                JOIN resguardos r ON b.id = r.id_bien
                WHERE r.Activo = 1 AND r.id_area IN ({format_strings})
            """
            cursor.execute(sql_bienes_a_inventariar, tuple(area_ids))
            bienes_en_areas = cursor.fetchall()
            
            if bienes_en_areas:
                sql_detalle = """
                    INSERT INTO inventario_detalle (
                        id_inventario, id_bien, id_resguardo_esperado, id_area_esperada, 
                        nombre_resguardante_esperado, estatus_hallazgo
                    ) VALUES (%s, %s, %s, %s, %s, 'Pendiente')
                """
                detalle_values = [
                    (inventario_id, bien['id'], bien['resguardo_id'], bien['id_area'], bien['Nombre_Del_Resguardante'])
                    for bien in bienes_en_areas
                ]
                cursor.executemany(sql_detalle, detalle_values)

            conn.commit()
            log_activity("Creación de Inventario", "Inventarios", inventario_id, f"Se creó el inventario '{nombre}' con {len(bienes_en_areas)} bienes a verificar.")
            flash(f'Inventario "{nombre}" creado exitosamente.', 'success')
            return redirect(url_for('inventarios.listar_inventarios'))

        # --- LÓGICA GET: MOSTRAR EL FORMULARIO CON DATOS ENRIQUECIDOS ---
        sql_areas_con_detalle = """
            SELECT 
                a.id, 
                a.nombre,
                COUNT(DISTINCT r.id_bien) AS num_bienes,
                (SELECT r2.Nombre_Director_Jefe_De_Area 
                 FROM resguardos r2 
                 WHERE r2.id_area = a.id AND r2.Nombre_Director_Jefe_De_Area IS NOT NULL 
                 LIMIT 1) AS jefe_de_area
            FROM areas a
            LEFT JOIN resguardos r ON a.id = r.id_area AND r.Activo = 1
            GROUP BY a.id, a.nombre
            ORDER BY a.nombre
        """
        cursor.execute(sql_areas_con_detalle)
        areas = cursor.fetchall()
        
        cursor.execute("SELECT id, username FROM user ORDER BY username")
        users = cursor.fetchall()
        
        return render_template('inventarios/crear_inventario.html', areas=areas, users=users, form_data={})

    except Exception as e:
        if conn and conn.rollback: conn.rollback()
        flash(f"Error al procesar la solicitud de inventario: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('inventarios.listar_inventarios'))
    finally:
        if conn and conn.is_connected():
            conn.close()

@inventarios_bp.route('/gestionar/<int:inventario_id>')
@login_required
@permission_required('inventarios.gestionar_inventario') # Permiso para gestionar inventarios
def gestionar_inventario(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id, nombre FROM areas ORDER BY nombre ASC")
        todas_las_areas = cursor.fetchall()

        cursor.execute("SELECT * FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        if not inventario:
            flash("El inventario no existe.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))
            
        # --- ¡CAMBIO IMPORTANTE EN LA CONSULTA SQL! ---
        # Se une con 'resguardos' para obtener el Nombre_Director_Jefe_De_Area
        sql_detalles = """
            SELECT 
                d.*, 
                b.No_Inventario, b.Descripcion_Del_Bien,
                a.nombre AS nombre_area,
                r.Nombre_Director_Jefe_De_Area  -- <-- Se añade este campo
            FROM inventario_detalle d
            JOIN bienes b ON d.id_bien = b.id
            JOIN areas a ON d.id_area_esperada = a.id
            LEFT JOIN resguardos r ON d.id_resguardo_esperado = r.id -- <-- Se añade este JOIN
            WHERE d.id_inventario = %s
            ORDER BY a.nombre, b.No_Inventario
        """
        cursor.execute(sql_detalles, (inventario_id,))
        detalles_list = cursor.fetchall()

        # El resto de la función no necesita cambios
        detalles_agrupados = {}
        for detalle in detalles_list:
            nombre_area = detalle['nombre_area']
            if nombre_area not in detalles_agrupados:
                detalles_agrupados[nombre_area] = []
            detalles_agrupados[nombre_area].append(detalle)
        
        cursor.execute("SELECT * FROM inventario_sobrantes WHERE id_inventario = %s", (inventario_id,))
        sobrantes = cursor.fetchall()

        return render_template(
            'inventarios/gestionar_inventario.html',
            inventario=inventario,
            detalles_agrupados=detalles_agrupados, 
            sobrantes=sobrantes,
            todas_las_areas=todas_las_areas
        )

    except Exception as e:
        flash(f"Error al cargar el inventario: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('inventarios.listar_inventarios'))
    finally:
        if conn and conn.is_connected():
            conn.close()

# inventarios_routes.py
# NUEVO ENDPOINT: Para obtener los datos de un detalle y sus fotos
@inventarios_bp.route('/detalle/<int:detalle_id>', methods=['GET'])
@login_required
@permission_required('inventarios.obtener_detalle') # Se recomienda un permiso de 'ver'
def obtener_detalle(detalle_id):
    """
    Devuelve los datos de un bien específico en formato JSON para ser usados
    por el frontend al momento de editar.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Obtener datos principales del detalle
        cursor.execute("""
            SELECT estatus_hallazgo, condicion_fisica_reportada, observaciones 
            FROM inventario_detalle WHERE id = %s
        """, (detalle_id,))
        detalle = cursor.fetchone()

        if not detalle:
            return jsonify({'error': 'Detalle no encontrado'}), 404

        # 2. Obtener las fotos asociadas
        cursor.execute("""
            SELECT id, ruta_archivo 
            FROM inventario_fotos WHERE id_inventario_detalle = %s
        """, (detalle_id,))
        fotos = cursor.fetchall()
        
        # 3. Combinar y devolver como JSON
        detalle['fotos'] = fotos
        print(detalle)  # Para depuración
        return jsonify(detalle)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error de servidor: {e}'}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@inventarios_bp.route('/detalle/actualizar/<int:detalle_id>', methods=['POST'])
@login_required
@permission_required('inventarios.actualizar_detalle')
def actualizar_detalle(detalle_id):
    inventario_id_str = request.form.get('inventario_id')
    
    # --- Validación del ID para redirección (sin cambios) ---
    if not inventario_id_str:
        flash('Error crítico: No se pudo identificar el inventario para la redirección.', 'danger')
        return redirect(url_for('inventarios.listar_inventarios'))
    inventario_id = int(inventario_id_str)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # --- Validación de estatus del inventario (sin cambios) ---
        cursor.execute("SELECT estatus FROM inventarios WHERE id = %s", (inventario_id,))
        inventario_actual = cursor.fetchone()
        if not inventario_actual or inventario_actual['estatus'] != 'En Progreso':
            flash('Acción no permitida. El inventario no está en la fase de "Levantamiento Físico".', 'warning')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # --- LÓGICA DE ACTUALIZACIÓN ---
        form_data = request.form
        cursor = conn.cursor()

        # ✅ 1. (NUEVO) PROCESAR FOTOS MARCADAS PARA ELIMINAR
        fotos_a_eliminar_ids = request.form.getlist('fotos_a_eliminar')
        if fotos_a_eliminar_ids:
            # Creamos placeholders (%s) de forma segura
            placeholders = ','.join(['%s'] * len(fotos_a_eliminar_ids))
            
            # Obtenemos las rutas de los archivos para borrarlos del disco
            cursor_dict = conn.cursor(dictionary=True)
            sql_get_filenames = f"SELECT ruta_archivo FROM inventario_fotos WHERE id IN ({placeholders}) AND id_inventario_detalle = %s"
            cursor_dict.execute(sql_get_filenames, (*fotos_a_eliminar_ids, detalle_id))
            
            for row in cursor_dict.fetchall():
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], row['ruta_archivo']))
                except OSError as e:
                    print(f"Error al eliminar archivo físico: {e}") # Idealmente, usar logging

            # Eliminamos los registros de la base de datos
            sql_delete_fotos = f"DELETE FROM inventario_fotos WHERE id IN ({placeholders})"
            cursor.execute(sql_delete_fotos, fotos_a_eliminar_ids)

        # 2. Actualizar la tabla 'inventario_detalle' (sin cambios, ya funciona para editar)
        sql_update = """
            UPDATE inventario_detalle SET
                estatus_hallazgo = %s, condicion_fisica_reportada = %s, observaciones = %s,
                id_usuario_verificador = %s, fecha_verificacion = %s
            WHERE id = %s
        """
        values = (
            form_data.get('estatus_hallazgo'), form_data.get('condicion_fisica'),
            form_data.get('observaciones'), current_user.id, datetime.now(), detalle_id
        )
        cursor.execute(sql_update, values)

        # 3. Procesar y guardar las nuevas fotos (sin cambios)
        fotos = request.files.getlist('fotos')
        for foto in fotos:
            if foto and foto.filename and allowed_file(foto.filename):
                filename = secure_filename(foto.filename)
                unique_filename = f"{uuid.uuid4()}-{filename}"
                foto.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))
                
                sql_foto = "INSERT INTO inventario_fotos (id_inventario_detalle, ruta_archivo) VALUES (%s, %s)"
                cursor.execute(sql_foto, (detalle_id, unique_filename))

        conn.commit()
        # Mensaje más genérico que aplica para revisión y edición
        flash("El detalle del bien ha sido actualizado correctamente.", "success")
        log_activity("Actualización de Bien", "Inventarios", detalle_id, f"Se actualizó el detalle del bien en el inventario ID: {inventario_id}")

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al actualizar el bien: {e}", "danger")
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            conn.close()
            
    return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
# ... (tus otras importaciones y rutas) ...

@inventarios_bp.route('/<int:inventario_id>/finalizar', methods=['POST'])
@login_required
@permission_required('inventarios.finalizar_inventario') # Un nuevo permiso para esta acción
def finalizar_inventario(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # --- LÓGICA DE CIERRE ---
        # 1. Encontrar todos los bienes que quedaron como 'Pendiente' en este inventario.
        cursor.execute("""
            SELECT id_bien FROM inventario_detalle
            WHERE id_inventario = %s AND estatus_hallazgo = 'Pendiente'
        """, (inventario_id,))
        
        # Obtenemos solo los IDs de los bienes
        bienes_pendientes = [row['id_bien'] for row in cursor.fetchall()]

        if bienes_pendientes:
            # 2. Actualizar el estatus de esos bienes a 'Faltante' en la tabla principal 'bienes'.
            # Se usa 'IN (%s, %s, ...)' para actualizar múltiples filas a la vez.
            format_strings = ','.join(['%s'] * len(bienes_pendientes))
            cursor.execute(f"""
                UPDATE bienes SET estatus_actual = 'Faltante'
                WHERE id IN ({format_strings})
            """, tuple(bienes_pendientes))

        # 3. Actualizar el estatus del inventario a 'Finalizado' y registrar la fecha de cierre.
        cursor.execute("""
            UPDATE inventarios SET 
                estatus = 'Finalizado',
                fecha_cierre = %s
            WHERE id = %s
        """, (datetime.now(), inventario_id))

        conn.commit()
        log_activity("Finalización de Inventario", "Inventarios", inventario_id, f"Se finalizó el inventario. {len(bienes_pendientes)} bienes marcados como faltantes.")
        flash('El inventario ha sido finalizado exitosamente.', 'success')

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al finalizar el inventario: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            conn.close()
            
    return redirect(url_for('inventarios.listar_inventarios'))

# inventarios_routes.py

# inventarios_routes.py

@inventarios_bp.route('/<int:inventario_id>/cambiar_estatus/<string:accion>', methods=['POST'])
@login_required
@permission_required('inventarios.cambiar_estatus_inventario') # Permiso para cambiar estatus del inventario
def cambiar_estatus_inventario(inventario_id, accion):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Obtenemos el estado actual ANTES de hacer nada.
        cursor.execute("SELECT estatus FROM inventarios WHERE id = %s", (inventario_id,))
        inventario_actual = cursor.fetchone()
        if not inventario_actual:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))
        
        current_status = inventario_actual['estatus']
        nuevo_estatus = None
        mensaje_log = ""
        
        # 2. VALIDACIÓN DE TRANSICIÓN DE ESTADO
        if accion == 'comenzar' and current_status == 'Planificado':
            nuevo_estatus = 'En Progreso'
            mensaje_log = 'El inventario ha cambiado a: En Progreso.'
        elif accion == 'conciliar' and current_status == 'En Progreso':
            nuevo_estatus = 'En Conciliación'
            mensaje_log = 'El inventario ha cambiado a: En Conciliación.'
        elif accion == 'finalizar' and current_status == 'En Conciliación':
            nuevo_estatus = 'Finalizado'
            mensaje_log = 'El inventario ha sido finalizado.'
            
            # Lógica especial para 'finalizar': Marcar bienes pendientes como faltantes
            cursor.execute("SELECT id_bien FROM inventario_detalle WHERE id_inventario = %s AND estatus_hallazgo = 'Pendiente'", (inventario_id,))
            bienes_pendientes = [row['id_bien'] for row in cursor.fetchall()]
            if bienes_pendientes:
                format_strings = ','.join(['%s'] * len(bienes_pendientes))
                cursor.execute(f"UPDATE bienes SET estatus_actual = 'Faltante' WHERE id IN ({format_strings})", tuple(bienes_pendientes))
                mensaje_log += f" {len(bienes_pendientes)} bienes marcados como faltantes."
        
        # 3. Si la transición no fue válida, mostramos un error.
        if not nuevo_estatus:
            flash(f"Acción '{accion}' no permitida para un inventario en estado '{current_status}'.", 'warning')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 4. Ejecutar la actualización en la BD
        if nuevo_estatus == 'Finalizado':
            cursor.execute("UPDATE inventarios SET estatus = %s, fecha_cierre = %s WHERE id = %s", (nuevo_estatus, datetime.now(), inventario_id))
        else:
            cursor.execute("UPDATE inventarios SET estatus = %s WHERE id = %s", (nuevo_estatus, inventario_id))

        conn.commit()
        log_activity("Cambio de Estatus", "Inventarios", inventario_id, mensaje_log)
        flash(f'El estatus del inventario se ha actualizado a "{nuevo_estatus}".', 'success')

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al cambiar el estatus del inventario: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            conn.close()

    if accion == 'finalizar':
        return redirect(url_for('inventarios.listar_inventarios'))
    else:
        return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))


# inventarios_routes.py

@inventarios_bp.route('/<int:inventario_id>/sobrantes/agregar', methods=['POST'])
@login_required
@permission_required('inventarios.agregar_sobrante')
def agregar_sobrante(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Validación de estatus: no se pueden agregar sobrantes a un inventario 'Planificado'
        cursor.execute("SELECT estatus, id_area_encontrado FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        if not inventario or inventario['estatus'] == 'Planificado':
            flash('Acción no permitida en el estado actual del inventario.', 'warning')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        form_data = request.form
        cursor = conn.cursor() # Cursor normal para inserts

        # Insertar en la tabla 'inventario_sobrantes'
        sql_sobrante = """
            INSERT INTO inventario_sobrantes (
                id_inventario, id_area_encontrado, descripcion_bien, marca, modelo, 
                numero_serie, condicion_fisica, estatus_resolucion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendiente de Identificación')
        """
        # Asumimos que se encontró en la primera área del inventario, esto podría mejorarse
        # pidiendo al usuario que seleccione el área donde lo encontró.
        cursor.execute("SELECT area_id FROM inventario_areas WHERE inventario_id = %s LIMIT 1", (inventario_id,))
        area_encontrado_id = cursor.fetchone()[0]

        values = (
            inventario_id, area_encontrado_id, form_data.get('descripcion_bien'), form_data.get('marca'),
            form_data.get('modelo'), form_data.get('numero_serie'), form_data.get('condicion_fisica')
        )
        cursor.execute(sql_sobrante, values)
        sobrante_id = cursor.lastrowid
        
        # Procesar y guardar fotos (si las hay)
        fotos = request.files.getlist('fotos_sobrante')
        for foto in fotos:
            if foto and foto.filename and allowed_file(foto.filename):
                filename = secure_filename(foto.filename)
                unique_filename = f"{uuid.uuid4()}-{filename}"
                foto.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))
                
                sql_foto = "INSERT INTO inventario_sobrante_fotos (id_inventario_sobrante, ruta_archivo) VALUES (%s, %s)"
                cursor.execute(sql_foto, (sobrante_id, unique_filename))

        conn.commit()
        log_activity("Registro de Sobrante", "Inventarios", sobrante_id, f"Se registró un bien sobrante en el inventario ID: {inventario_id}")
        flash('Bien sobrante registrado exitosamente.', 'success')

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al registrar el bien sobrante: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))


@inventarios_bp.route('/<int:inventario_id>/reporte')
@login_required
@permission_required('inventarios.generar_reporte')
def generar_reporte(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Obtener datos principales (inventario, brigada)
        cursor.execute("SELECT * FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        if not inventario:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))
        cursor.execute("SELECT u.username FROM user u JOIN inventario_brigadas ib ON u.id = ib.user_id WHERE ib.inventario_id = %s ORDER BY u.username", (inventario_id,))
        brigada = [row['username'] for row in cursor.fetchall()]

        # 2. Obtener todos los detalles de bienes
        sql_detalles = """
            SELECT d.*, b.No_Inventario, b.Descripcion_Del_Bien, b.Valor_En_Libros,
                r.Nombre_Director_Jefe_De_Area, a.nombre as nombre_area,
                u.username as nombre_verificador -- <--- LÍNEA AÑADIDA
            FROM inventario_detalle d
            JOIN bienes b ON d.id_bien = b.id
            LEFT JOIN resguardos r ON d.id_resguardo_esperado = r.id
            LEFT JOIN areas a ON d.id_area_esperada = a.id
            LEFT JOIN user u ON d.id_usuario_verificador = u.id -- <--- JOIN AÑADIDO
            WHERE d.id_inventario = %s
        """
        cursor.execute(sql_detalles, (inventario_id,))
        todos_los_detalles = cursor.fetchall()
        
        # 3. Obtener todas las fotos
        detalle_ids = [d['id'] for d in todos_los_detalles]
        fotos_por_detalle = {}
        if detalle_ids:
            format_strings = ','.join(['%s'] * len(detalle_ids))
            cursor.execute(f"SELECT id_inventario_detalle, ruta_archivo FROM inventario_fotos WHERE id_inventario_detalle IN ({format_strings})", tuple(detalle_ids))
            fotos = cursor.fetchall()
            for foto in fotos:
                detalle_id = foto['id_inventario_detalle']
                if detalle_id not in fotos_por_detalle: fotos_por_detalle[detalle_id] = []
                fotos_por_detalle[detalle_id].append(foto['ruta_archivo'])

        # 4. Procesar y clasificar los datos en TODAS las categorías
        faltantes_por_area, discrepancias_por_area, correctos_por_area = {}, {}, {}
        bienes_revisados = []
        area_jefe_map = {}

        for detalle in todos_los_detalles:
            area = detalle['nombre_area'] or 'Sin Área Asignada'
            jefe = detalle.get('Nombre_Director_Jefe_De_Area') or 'No Asignado'
            if area not in area_jefe_map: area_jefe_map[area] = jefe
            
            if detalle['estatus_hallazgo'] != 'Pendiente':
                bienes_revisados.append(detalle)

            es_faltante = (detalle['estatus_hallazgo'] == 'No Localizado') or \
                          (inventario['estatus'] == 'Finalizado' and detalle['estatus_hallazgo'] == 'Pendiente')
            
            if es_faltante:
                if area not in faltantes_por_area: faltantes_por_area[area] = []
                faltantes_por_area[area].append(detalle)
            elif detalle['estatus_hallazgo'] == 'Localizado con Discrepancia':
                if area not in discrepancias_por_area: discrepancias_por_area[area] = []
                discrepancias_por_area[area].append(detalle)
            elif detalle['estatus_hallazgo'] == 'Localizado':
                if area not in correctos_por_area: correctos_por_area[area] = []
                correctos_por_area[area].append(detalle)
        
        # 5. Obtener los bienes sobrantes
        cursor.execute("""
            SELECT s.*, u.username as nombre_capturador
            FROM inventario_sobrantes s
            LEFT JOIN user u ON s.id_usuario_captura = u.id
            WHERE s.id_inventario = %s
        """, (inventario_id,))
        bienes_sobrantes = cursor.fetchall()

        # 6. Renderizar la plantilla con todos los datos
        return render_template(
            'inventarios/reporte_inventario.html',
            inventario=inventario,
            area_jefe_map=area_jefe_map,
            brigada=brigada,
            total_registrado=len(todos_los_detalles),
            faltantes_por_area=faltantes_por_area,
            discrepancias_por_area=discrepancias_por_area,
            correctos_por_area=correctos_por_area,
            bienes_sobrantes=bienes_sobrantes,
            bienes_revisados=bienes_revisados,
            fotos_por_detalle=fotos_por_detalle
        )

    except Exception as e:
        flash(f'Error al generar el reporte: {e}', 'danger')
        traceback.print_exc()
        if 'inventario_id' in locals():
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
        else:
            return redirect(url_for('inventarios.listar_inventarios'))
    finally:
        if conn and conn.is_connected():
            conn.close()


@inventarios_bp.route('/<int:inventario_id>/reporte/pdf')
@login_required
@permission_required('inventarios.descargar_reporte_pdf') # o el permiso que corresponda
def descargar_reporte_pdf(inventario_id):
    """
    Genera un reporte en PDF de un inventario y lo muestra en el navegador para previsualización.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        fecha_generacion_reporte = datetime.now()

        # --- SECCIÓN 1: RECOPILACIÓN DE DATOS ---

        # 1a. Obtener datos del inventario principal y brigada
        cursor.execute("SELECT * FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        if not inventario:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))

        cursor.execute("""
            SELECT u.username FROM user u
            JOIN inventario_brigadas ib ON u.id = ib.user_id
            WHERE ib.inventario_id = %s ORDER BY u.username
        """, (inventario_id,))
        brigada = [row['username'] for row in cursor.fetchall()]

        # 1b. Obtener todos los detalles de bienes y nombre del verificador
        sql_detalles = """
            SELECT
                d.*, b.No_Inventario, b.Descripcion_Del_Bien, b.Valor_En_Libros,
                r.Nombre_Director_Jefe_De_Area, a.nombre as nombre_area,
                u.username as nombre_verificador
            FROM inventario_detalle d
            JOIN bienes b ON d.id_bien = b.id
            LEFT JOIN resguardos r ON d.id_resguardo_esperado = r.id
            LEFT JOIN areas a ON d.id_area_esperada = a.id
            LEFT JOIN user u ON d.id_usuario_verificador = u.id
            WHERE d.id_inventario = %s
        """
        cursor.execute(sql_detalles, (inventario_id,))
        todos_los_detalles = cursor.fetchall()

        # 1c. Obtener todas las fotos de los detalles
        detalle_ids = [d['id'] for d in todos_los_detalles]
        fotos_por_detalle = {}
        if detalle_ids:
            format_strings = ','.join(['%s'] * len(detalle_ids))
            cursor.execute(f"SELECT id_inventario_detalle, ruta_archivo FROM inventario_fotos WHERE id_inventario_detalle IN ({format_strings})", tuple(detalle_ids))
            fotos = cursor.fetchall()
            for foto in fotos:
                detalle_id = foto['id_inventario_detalle']
                if detalle_id not in fotos_por_detalle:
                    fotos_por_detalle[detalle_id] = []
                fotos_por_detalle[detalle_id].append(foto['ruta_archivo'])

        # 1d. Procesar y clasificar los datos
        faltantes_por_area, discrepancias_por_area, correctos_por_area = {}, {}, {}
        bienes_revisados = []
        area_jefe_map = {}
        for detalle in todos_los_detalles:
            area = detalle['nombre_area'] or 'Sin Área Asignada'
            jefe = detalle.get('Nombre_Director_Jefe_De_Area') or 'No Asignado'
            if area not in area_jefe_map: area_jefe_map[area] = jefe

            if detalle['estatus_hallazgo'] != 'Pendiente':
                bienes_revisados.append(detalle)

            es_faltante = (detalle['estatus_hallazgo'] == 'No Localizado') or \
                          (inventario['estatus'] == 'Finalizado' and detalle['estatus_hallazgo'] == 'Pendiente')
            if es_faltante:
                if area not in faltantes_por_area: faltantes_por_area[area] = []
                faltantes_por_area[area].append(detalle)
            elif detalle['estatus_hallazgo'] == 'Localizado con Discrepancia':
                if area not in discrepancias_por_area: discrepancias_por_area[area] = []
                discrepancias_por_area[area].append(detalle)
            elif detalle['estatus_hallazgo'] == 'Localizado':
                if area not in correctos_por_area: correctos_por_area[area] = []
                correctos_por_area[area].append(detalle)

        # 1e. Obtener los bienes sobrantes
        cursor.execute("""
            SELECT s.*, u.username as nombre_capturador FROM inventario_sobrantes s
            LEFT JOIN user u ON s.id_usuario_captura = u.id
            WHERE s.id_inventario = %s
        """, (inventario_id,))
        bienes_sobrantes = cursor.fetchall()


        # --- SECCIÓN 2: GENERACIÓN DEL PDF ---

        # 2a. Renderizar la plantilla HTML a una cadena de texto
        html_string = render_template(
            'inventarios/reporte_inventario_pdf.html',
            fecha_generacion=fecha_generacion_reporte,
            inventario=inventario,
            area_jefe_map=area_jefe_map,
            brigada=brigada,
            total_registrado=len(todos_los_detalles),
            faltantes_por_area=faltantes_por_area,
            discrepancias_por_area=discrepancias_por_area,
            correctos_por_area=correctos_por_area,
            bienes_sobrantes=bienes_sobrantes,
            bienes_revisados=bienes_revisados,
            fotos_por_detalle=fotos_por_detalle
        )

        # 2b. Convertir la cadena HTML a PDF en memoria
        pdf_file = HTML(string=html_string, base_url=request.base_url).write_pdf()

        # 2c. Crear la respuesta y configurarla para VISTA PREVIA
        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=reporte_{inventario.get("nombre", "inventario")}.pdf'
        
        return response

    except Exception as e:
        flash(f'Error al generar el PDF: {e}', 'danger')
        traceback.print_exc()
        return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
    finally:
        if conn and conn.is_connected():
            conn.close()