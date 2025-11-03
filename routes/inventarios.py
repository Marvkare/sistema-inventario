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
from PIL import Image # Para detectar el tipo de imagen
import base64
import io
from config import ALLOWED_EXTENSIONS
# Se importan las funciones y variables de tus otros archivos
from database import get_db_connection
from decorators import permission_required
from log_activity import log_activity
from flask import jsonify
import pymysql
from drive_service import drive_service, INVENTARIOS_FOLDER_ID, get_cached_image, save_to_cache


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
        cursor = conn.cursor(pymysql.cursors.DictCursor) 
        
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
        if conn :
            conn.close()

# inventarios_routes.py

@inventarios_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@permission_required('inventarios.crear_inventario')
def crear_inventario():
    """
    Gestiona la creación de un nuevo proceso de inventario.
    
    GET: Muestra el formulario con las áreas y usuarios disponibles.
    POST: Procesa los datos del formulario, crea el inventario, asigna áreas y
          brigada, y genera la cédula de levantamiento inicial.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # --- LÓGICA POST: PROCESAR EL FORMULARIO ---
        if request.method == 'POST':
            form_data = request.form
            
            # 1. Recolección de datos del formulario
            nombre = form_data.get('nombre')
            tipo = form_data.get('tipo')
            tipo_resguardo_val = form_data.get('Tipo_De_Resguardo') # Recibe '0' o '1'
            area_ids = request.form.getlist('area_ids')
            user_ids = request.form.getlist('user_ids')

            # 2. Validación de datos de entrada
            if not all([nombre, tipo, area_ids, user_ids]) or tipo_resguardo_val is None:
                flash('Todos los campos son obligatorios. Por favor, complete toda la información.', 'warning')
                # Si la validación falla, debemos recargar los datos para volver a mostrar el formulario
                # Esta lógica es idéntica a la de la petición GET
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
                # Devolvemos el formulario con los datos que el usuario ya había ingresado
                return render_template('inventarios/crear_inventario.html', areas=areas, users=users, form_data=form_data)

            tipo_resguardo_int = int(tipo_resguardo_val)

            # --- INICIO DE LA TRANSACCIÓN DE BASE DE DATOS ---
            
            # 3. Crear el registro principal en la tabla 'inventarios'
            sql_inventario = """
                INSERT INTO inventarios (nombre, tipo, tipo_resguardo_inventariado, estatus, id_usuario_creador) 
                VALUES (%s, %s, %s, 'Planificado', %s)
            """
            cursor.execute(sql_inventario, (nombre, tipo, tipo_resguardo_int, current_user.id))
            inventario_id = cursor.lastrowid

            # 4. Vincular las áreas seleccionadas en la tabla pivote
            sql_areas = "INSERT INTO inventario_areas (inventario_id, area_id) VALUES (%s, %s)"
            area_values = [(inventario_id, int(area_id)) for area_id in area_ids]
            cursor.executemany(sql_areas, area_values)

            # 5. Vincular los usuarios (brigada) en la tabla pivote
            sql_brigada = "INSERT INTO inventario_brigadas (inventario_id, user_id) VALUES (%s, %s)"
            user_values = [(inventario_id, int(user_id)) for user_id in user_ids]
            cursor.executemany(sql_brigada, user_values)
            
            # 6. Generar la "Cédula de Levantamiento" inicial (registros en 'inventario_detalle')
            format_strings = ','.join(['%s'] * len(area_ids))
            sql_bienes_a_inventariar = f"""
                SELECT b.id, r.id AS resguardo_id, r.id_area, r.Nombre_Del_Resguardante
                FROM bienes b
                JOIN resguardos r ON b.id = r.id_bien
                WHERE r.Activo = 1 
                  AND r.id_area IN ({format_strings})
                  AND r.Tipo_De_Resguardo = %s
            """
            query_params = tuple(area_ids) + (tipo_resguardo_int,)
            cursor.execute(sql_bienes_a_inventariar, query_params)
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

            # 7. Confirmar todos los cambios en la base de datos
            conn.commit()
            
            log_activity(
                    action="Creación de Inventario", 
                    category="Inventarios", 
                    resource_id=inventario_id, 
                    details=f"Usuario '{current_user.username}' creó el inventario '{nombre}' con {len(bienes_en_areas)} bienes a verificar."
                ) 
            flash(f'Inventario "{nombre}" creado exitosamente.', 'success')
            return redirect(url_for('inventarios.listar_inventarios'))

        # --- LÓGICA GET: MOSTRAR EL FORMULARIO INICIAL ---
        sql_areas_con_detalle = """
                    SELECT 
                        a.id, 
                        a.nombre,
                        (SELECT r2.Nombre_Director_Jefe_De_Area 
                        FROM resguardos r2 
                        WHERE r2.id_area = a.id AND r2.Nombre_Director_Jefe_De_Area IS NOT NULL 
                        LIMIT 1) AS jefe_de_area,
                        
                        -- Contar bienes de resguardo normal (Tipo_De_Resguardo = 0)
                        COUNT(DISTINCT CASE WHEN r.Tipo_De_Resguardo = 0 THEN r.id_bien END) AS num_bienes_normal,
                        
                        -- Contar bienes sujetos a control (Tipo_De_Resguardo = 1)
                        COUNT(DISTINCT CASE WHEN r.Tipo_De_Resguardo = 1 THEN r.id_bien END) AS num_bienes_control
                        
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
        # Si ocurre cualquier error, deshacer todos los cambios de la transacción
        if conn :
            conn.rollback()
        
        flash(f"Error crítico al procesar la solicitud de inventario: {e}", 'danger')
        traceback.print_exc() # Imprime el error detallado en la consola del servidor para depuración
        
        # Redirigir a una página segura para evitar estados inconsistentes
        return redirect(url_for('inventarios.listar_inventarios'))
    
    finally:
        # Asegurarse de que la conexión a la base de datos siempre se cierre
        if conn:
            conn.close()

@inventarios_bp.route('/gestionar/<int:inventario_id>')
@login_required
@permission_required('inventarios.gestionar_inventario') # Permiso para gestionar inventarios
def gestionar_inventario(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 
        
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

        # 1. Obtener la brigada actual (asumiendo que ya lo haces para tu plantilla)
        cursor.execute("""
            SELECT u.id, u.username, u.nombres AS full_name
            FROM user u
            JOIN inventario_brigadas ib ON u.id = ib.user_id
            WHERE ib.inventario_id = %s
            ORDER BY u.nombres
        """, (inventario_id,))
        brigada_actual = cursor.fetchall()
        
        # 2. Obtener usuarios que NO están en la brigada
        cursor.execute("""
            SELECT u.id, u.username, u.nombres AS full_name
            FROM user u
            WHERE u.id NOT IN (
                SELECT ib.user_id FROM inventario_brigadas ib
                WHERE ib.inventario_id = %s
            )
            ORDER BY u.nombres
        """, (inventario_id,))
        usuarios_disponibles = cursor.fetchall()

        return render_template(
            'inventarios/gestionar_inventario.html',
            inventario=inventario,
            detalles_agrupados=detalles_agrupados, 
            sobrantes=sobrantes,
            todas_las_areas=todas_las_areas,
            brigada=brigada_actual,
            usuarios_disponibles=usuarios_disponibles
        )

    except Exception as e:
        flash(f"Error al cargar el inventario: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('inventarios.listar_inventarios'))
    finally:
        if conn :
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
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

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
        if conn :
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

        # --- ✅ NUEVO: VALIDAR SERVICIO DE DRIVE ---
        if not drive_service or not INVENTARIOS_FOLDER_ID:
            flash("Error crítico: El servicio de almacenamiento (Google Drive) no está configurado.", "danger")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # --- VALIDACIÓN DE PERTENENCIA A LA BRIGADA (sin cambios) ---
        cursor.execute("""
            SELECT 1 FROM inventario_brigadas 
            WHERE inventario_id = %s AND user_id = %s
        """, (inventario_id, current_user.id))
        
        is_member = cursor.fetchone()
        if not is_member:
            flash('Acceso prohibido. No eres parte de la brigada asignada a este inventario.', 'danger')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # --- Validación de estatus del inventario (sin cambios) ---
        cursor.execute("SELECT estatus FROM inventarios WHERE id = %s", (inventario_id,))
        inventario_actual = cursor.fetchone()
        if not inventario_actual or inventario_actual['estatus'] != 'En Progreso':
            flash('Acción no permitida. El inventario no está en la fase de "Levantamiento Físico".', 'warning')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # --- LÓGICA DE ACTUALIZACIÓN ---
        form_data = request.form
        cursor = conn.cursor() # Cambiamos a cursor estándar para DML

        # --- ✅ 1. (MODIFICADO) PROCESAR FOTOS MARCADAS PARA ELIMINAR ---
        fotos_a_eliminar_ids = request.form.getlist('fotos_a_eliminar')
        if fotos_a_eliminar_ids:
            placeholders = ','.join(['%s'] * len(fotos_a_eliminar_ids))
            
            # Obtenemos los Drive IDs (ruta_archivo) para borrarlos de Drive
            cursor_dict = conn.cursor(pymysql.cursors.DictCursor)
            sql_get_filenames = f"SELECT id, ruta_archivo FROM inventario_fotos WHERE id IN ({placeholders}) AND id_inventario_detalle = %s"
            cursor_dict.execute(sql_get_filenames, (*fotos_a_eliminar_ids, detalle_id))
            
            archivos_a_borrar = cursor_dict.fetchall()
            
            for row in archivos_a_borrar:
                try:
                    # --- REEMPLAZO DE os.remove CON drive_service.delete ---
                    drive_file_id = row['ruta_archivo']
                    if drive_file_id:
                        print(f"Eliminando de Drive: {drive_file_id}")
                        drive_service.delete(drive_file_id)
                    else:
                        print(f"No hay Drive ID para el registro de foto {row['id']}")
                except Exception as e:
                    # No detenemos la transacción, solo registramos el error
                    current_app.logger.error(f"Error al eliminar archivo físico de Drive: {e}") 

            # Eliminamos los registros de la base de datos (sin cambios)
            sql_delete_fotos = f"DELETE FROM inventario_fotos WHERE id IN ({placeholders})"
            cursor.execute(sql_delete_fotos, fotos_a_eliminar_ids)

        # 2. Actualizar la tabla 'inventario_detalle' (sin cambios)
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

        # --- ✅ 3. (MODIFICADO) PROCESAR Y GUARDAR LAS NUEVAS FOTOS ---
        fotos = request.files.getlist('fotos')
        for foto in fotos:
            if foto and foto.filename and allowed_file(foto.filename):
                
                # --- REEMPLAZO DE foto.save CON drive_service.upload ---
                drive_id = drive_service.upload(
                    file_storage=foto,
                    model_type="inventario-detalle", # Nombre descriptivo
                    target_folder_id=INVENTARIOS_FOLDER_ID
                )
                
                if drive_id:
                    # Guardamos el Drive ID en la base de datos
                    sql_foto = "INSERT INTO inventario_fotos (id_inventario_detalle, ruta_archivo) VALUES (%s, %s)"
                    cursor.execute(sql_foto, (detalle_id, drive_id))
                else:
                    # Si la subida falla, forzamos un rollback de toda la transacción
                    raise Exception(f"Fallo al subir la imagen '{foto.filename}' a Google Drive.")

        conn.commit()
        flash("El detalle del bien ha sido actualizado correctamente.", "success")
        log_activity(
            action="Actualización de Bien (Drive)", 
            category="Inventarios", 
            resource_id=detalle_id, 
            details=f"Usuario '{current_user.username}' actualizó el detalle del bien en el inventario ID: {inventario_id}"
        )

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al actualizar el bien: {e}", "danger")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            
    return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

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
        log_activity(
            action="Finalización de Inventario", 
            category="Inventarios", 
            resource_id=inventario_id, 
            details=f"Usuario '{current_user.username}' finalizó el inventario. {len(bienes_pendientes)} bienes marcados como faltantes."
        )
        flash('El inventario ha sido finalizado exitosamente.', 'success')

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al finalizar el inventario: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn :
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
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # 1. Obtenemos el estado actual ANTES de hacer nada.
        cursor.execute("SELECT estatus, id_usuario_creador FROM inventarios WHERE id = %s", (inventario_id,))
        inventario_actual = cursor.fetchone()
        if not inventario_actual:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))
        
        # Comparamos el ID del creador del inventario con el del usuario actual.
        if inventario_actual['id_usuario_creador'] != current_user.id:
            flash('Acción no permitida. Solo el usuario que creó el inventario puede cambiar su estatus.', 'danger')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
        
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
        log_activity(
            action="Cambio de Estatus", 
            category="Inventarios", 
            resource_id=inventario_id, 
            details=f"Usuario '{current_user.username}' cambió el estatus: {mensaje_log}"
        )
        flash(f'El estatus del inventario se ha actualizado a "{nuevo_estatus}".', 'success')

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al cambiar el estatus del inventario: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn :
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

        # --- ✅ NUEVO: VALIDAR SERVICIO DE DRIVE ---
        if not drive_service or not INVENTARIOS_FOLDER_ID:
            flash("Error crítico: El servicio de almacenamiento (Google Drive) no está configurado.", "danger")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
            
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # Verificación de pertenencia a la brigada (Sin cambios)
        cursor.execute("""
            SELECT 1 FROM inventario_brigadas 
            WHERE inventario_id = %s AND user_id = %s
        """, (inventario_id, current_user.id))
        
        is_member = cursor.fetchone()
        if not is_member:
            flash('Acceso prohibido. No eres parte de la brigada asignada a este inventario.', 'danger')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # Validación de estatus (Sin cambios)
        cursor.execute("SELECT estatus FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        
        if not inventario or inventario['estatus'] == 'Planificado':
            flash('Acción no permitida en el estado actual del inventario.', 'warning')
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        form_data = request.form
        
        # Validación de área (Sin cambios)
        area_encontrado_id = form_data.get('id_area_encontrado') 
        if not area_encontrado_id:
             flash('Debe seleccionar el área donde se encontró el bien sobrante.', 'warning')
             return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # Insertar en la tabla 'inventario_sobrantes' (Sin cambios)
        sql_sobrante = """
            INSERT INTO inventario_sobrantes (
                id_inventario, id_area_encontrado, descripcion_bien, marca, modelo, 
                numero_serie, condicion_fisica, estatus_resolucion, id_usuario_captura, fecha_captura
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendiente de Identificación', %s, %s)
        """
        values = (
            inventario_id, area_encontrado_id, form_data.get('descripcion_bien'), 
            form_data.get('marca'), form_data.get('modelo'), form_data.get('numero_serie'), 
            form_data.get('condicion_fisica'), current_user.id, datetime.now()
        )
        
        write_cursor = conn.cursor()
        write_cursor.execute(sql_sobrante, values)
        sobrante_id = write_cursor.lastrowid
        
        # --- ✅ (MODIFICADO) PROCESAR Y GUARDAR FOTOS ---
        fotos = request.files.getlist('fotos_sobrante')
        for foto in fotos:
            if foto and foto.filename and allowed_file(foto.filename):
                
                # --- Subir a Google Drive ---
                drive_id = drive_service.upload(
                    file_storage=foto,
                    model_type="inventario-sobrante", # Nombre descriptivo
                    target_folder_id=INVENTARIOS_FOLDER_ID
                )
                
                if drive_id:
                    # --- Guardar el Drive ID en la BD ---
                    sql_foto = "INSERT INTO inventario_sobrante_fotos (id_inventario_sobrante, ruta_archivo) VALUES (%s, %s)"
                    write_cursor.execute(sql_foto, (sobrante_id, drive_id))
                else:
                    # Si la subida falla, forzar rollback de toda la transacción
                    raise Exception(f"Fallo al subir la imagen '{foto.filename}' a Google Drive.")

        conn.commit()
        log_activity(
            action="Registro de Sobrante (Drive)", 
            category="Inventarios", 
            resource_id=sobrante_id, 
            details=f"Usuario '{current_user.username}' registró un bien sobrante en el inventario ID: {inventario_id}"
        )
        flash('Bien sobrante registrado exitosamente.', 'success')

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al registrar el bien sobrante: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

    return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))


@inventarios_bp.route('/<int:inventario_id>/reporte')
@login_required
@permission_required('inventarios.generar_reporte')
def generar_reporte(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # 1. Obtener datos principales (inventario, brigada) - (Sin cambios)
        cursor.execute("SELECT * FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        if not inventario:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))
        
        sql_brigada = """
            SELECT u.username, u.nombres AS full_name, u.id
            FROM user u 
            JOIN inventario_brigadas ib ON u.id = ib.user_id 
            WHERE ib.inventario_id = %s 
            ORDER BY u.nombres
        """
        cursor.execute(sql_brigada, (inventario_id,))
        brigada = cursor.fetchall()

        # 2. Obtener todos los detalles de bienes (Sin cambios)
        sql_detalles = """
            SELECT d.*, b.No_Inventario, b.Descripcion_Del_Bien, b.Valor_En_Libros,
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
        
        # --- ✅ 3. (MODIFICADO) Obtener todas las fotos y CONVERTIR a URLs ---
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
                
                # Convertimos el ID de Drive (ruta_archivo) en una URL servible
                file_id = foto['ruta_archivo']
                if file_id:
                    # Usamos la ruta global 'serve_drive_image' (sin prefijo de blueprint)
                    url_imagen = url_for('serve_drive_image', file_id=file_id)
                    fotos_por_detalle[detalle_id].append(url_imagen)

        # 4. Procesar y clasificar los datos (Sin cambios)
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
        
        # 5. Obtener los bienes sobrantes (Sin cambios)
        cursor.execute("""
            SELECT s.*, u.username as nombre_capturador
            FROM inventario_sobrantes s
            LEFT JOIN user u ON s.id_usuario_captura = u.id
            WHERE s.id_inventario = %s
        """, (inventario_id,))
        bienes_sobrantes = cursor.fetchall()

        # --- ✅ 5b. (NUEVO) Obtener fotos de los bienes sobrantes ---
        sobrante_ids = [s['id'] for s in bienes_sobrantes]
        fotos_por_sobrante = {}
        if sobrante_ids:
            format_strings_sobrantes = ','.join(['%s'] * len(sobrante_ids))
            cursor.execute(f"SELECT id_inventario_sobrante, ruta_archivo FROM inventario_sobrante_fotos WHERE id_inventario_sobrante IN ({format_strings_sobrantes})", tuple(sobrante_ids))
            fotos_s = cursor.fetchall()
            for foto in fotos_s:
                sobrante_id = foto['id_inventario_sobrante']
                if sobrante_id not in fotos_por_sobrante: 
                    fotos_por_sobrante[sobrante_id] = []
                
                file_id = foto['ruta_archivo']
                if file_id:
                    url_imagen = url_for('serve_drive_image', file_id=file_id)
                    fotos_por_sobrante[sobrante_id].append(url_imagen)

        # --- ✅ 6. (MODIFICADO) Renderizar la plantilla con todos los datos ---
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
            fotos_por_detalle=fotos_por_detalle,
            fotos_por_sobrante=fotos_por_sobrante # <-- Variable añadida
        )

    except Exception as e:
        flash(f'Error al generar el reporte: {e}', 'danger')
        traceback.print_exc()
        if 'inventario_id' in locals():
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
        else:
            return redirect(url_for('inventarios.listar_inventarios'))
    finally:
        if conn :
            conn.close()

@inventarios_bp.route('/<int:inventario_id>/reporte/pdf')
@login_required
@permission_required('inventarios.descargar_reporte_pdf')
def descargar_reporte_pdf(inventario_id):
    """
    Genera un reporte en PDF de un inventario, incrustando las imágenes
    de Google Drive como Data URIs.
    """
    
    # --- ✅ Función helper interna para convertir IDs de Drive a Data URI ---
    def _get_image_data_uri(file_id):
        if not file_id or not drive_service or not get_cached_image or not save_to_cache:
            return None
        try:
            # 1. Usar caché primero
            image_bytes = get_cached_image(file_id)
            
            if not image_bytes:
                # 2. Si no, descargar de Drive
                image_bytes = drive_service.get_file_content(file_id)
                save_to_cache(file_id, image_bytes) # Guardar en caché
            
            # 3. Detectar MimeType y codificar en Base64
            # Usamos PIL para detectar el formato (jpeg, png, etc.)
            img = Image.open(io.BytesIO(image_bytes))
            mime_type = Image.MIME.get(img.format, 'image/jpeg') # Default a jpeg
            
            encoded_string = base64.b64encode(image_bytes).decode('utf-8')
            return f"data:{mime_type};base64,{encoded_string}"
        
        except Exception as e:
            current_app.logger.error(f"Error al convertir imagen de Drive {file_id} a Data URI: {e}")
            return None # Retorna None si la imagen falla

    # --- INICIO DE LA LÓGICA DE LA RUTA ---
    conn = None
    try:
        conn = get_db_connection()
        # Usamos DictCursor para que coincida con tus otras rutas
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        fecha_generacion_reporte = datetime.now()

        # --- SECCIÓN 1: RECOPILACIÓN DE DATOS ---

        # 1a. Obtener datos del inventario principal y brigada (Sin cambios)
        cursor.execute("SELECT * FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()
        if not inventario:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))

        sql_brigada_pdf = """
            SELECT u.username, u.nombres AS full_name, u.id
            FROM user u 
            JOIN inventario_brigadas ib ON u.id = ib.user_id 
            WHERE ib.inventario_id = %s 
            ORDER BY u.nombres
        """
        cursor.execute(sql_brigada_pdf, (inventario_id,))
        brigada = cursor.fetchall()
        
        # 1b. Obtener todos los detalles de bienes (Sin cambios)
        sql_detalles = """
            SELECT d.*, b.No_Inventario, b.Descripcion_Del_Bien, b.Valor_En_Libros,
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

        # --- ✅ 1c. (MODIFICADO) Obtener fotos de detalles y convertir a Data URI ---
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
                
                # Convertimos el ID de Drive a Data URI
                data_uri = _get_image_data_uri(foto['ruta_archivo'])
                if data_uri:
                    fotos_por_detalle[detalle_id].append(data_uri)

        # 1d. Procesar y clasificar los datos (Sin cambios)
        faltantes_por_area, discrepancias_por_area, correctos_por_area = {}, {}, {}
        bienes_revisados = []
        area_jefe_map = {}
        # (Tu lógica de clasificación for detalle in todos_los_detalles... va aquí, sin cambios)
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


        # 1e. Obtener los bienes sobrantes (Sin cambios)
        cursor.execute("""
            SELECT s.*, u.username as nombre_capturador FROM inventario_sobrantes s
            LEFT JOIN user u ON s.id_usuario_captura = u.id
            WHERE s.id_inventario = %s
        """, (inventario_id,))
        bienes_sobrantes = cursor.fetchall()

        # --- ✅ 1f. (NUEVO) Obtener fotos de sobrantes y convertir a Data URI ---
        sobrante_ids = [s['id'] for s in bienes_sobrantes]
        fotos_por_sobrante = {}
        if sobrante_ids:
            format_strings_sobrantes = ','.join(['%s'] * len(sobrante_ids))
            cursor.execute(f"SELECT id_inventario_sobrante, ruta_archivo FROM inventario_sobrante_fotos WHERE id_inventario_sobrante IN ({format_strings_sobrantes})", tuple(sobrante_ids))
            fotos_s = cursor.fetchall()
            for foto in fotos_s:
                sobrante_id = foto['id_inventario_sobrante']
                if sobrante_id not in fotos_por_sobrante: 
                    fotos_por_sobrante[sobrante_id] = []
                
                data_uri = _get_image_data_uri(foto['ruta_archivo'])
                if data_uri:
                    fotos_por_sobrante[sobrante_id].append(data_uri)


        # --- SECCIÓN 2: GENERACIÓN DEL PDF ---

        # --- ✅ 2a. (MODIFICADO) Renderizar la plantilla HTML ---
        # (Ahora pasamos las fotos de sobrantes)
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
            fotos_por_detalle=fotos_por_detalle,
            fotos_por_sobrante=fotos_por_sobrante # <-- Variable añadida
        )

        # --- ✅ 2b. (MODIFICADO) Convertir la cadena HTML a PDF ---
        # (Quitamos el 'base_url' ya que las imágenes están incrustadas)
        # 2b. Convertir la cadena HTML a PDF en memoria
        # (Añadimos 'base_url' para que pueda encontrar /static/images/...)
        pdf_file = HTML(string=html_string, base_url=request.base_url).write_pdf()

        # 2c. Crear la respuesta (Sin cambios)
        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=reporte_{inventario.get("nombre", "inventario")}.pdf'
        
        return response

    except Exception as e:
        flash(f'Error al generar el PDF: {e}', 'danger')
        traceback.print_exc()
        return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))
    finally:
        if conn:
            conn.close()

@inventarios_bp.route('/<int:inventario_id>/brigada/agregar', methods=['POST'])
@login_required
@permission_required('inventarios.gestionar_inventario') # O un permiso específico
def agregar_miembros_brigada(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Validar el inventario y los permisos
        cursor.execute("SELECT estatus, id_usuario_creador FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()

        if not inventario:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))

        # Asumimos que solo el creador puede añadir (puedes cambiar esta lógica)
        if inventario['id_usuario_creador'] != current_user.id:
            flash("Solo el creador del inventario puede añadir nuevos miembros.", "danger")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 2. Validar el ESTATUS (la restricción clave)
        if inventario['estatus'] not in ('Planificado', 'En Progreso'):
            flash("No se pueden añadir miembros a la brigada en esta fase del inventario.", "warning")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 3. Obtener los IDs de los nuevos usuarios desde el formulario
        user_ids_a_agregar = request.form.getlist('user_ids')
        if not user_ids_a_agregar:
            flash("No se seleccionó ningún usuario para añadir.", "info")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 4. Obtener brigada existente para evitar duplicados
        cursor.execute("SELECT user_id FROM inventario_brigadas WHERE inventario_id = %s", (inventario_id,))
        miembros_existentes = {row['user_id'] for row in cursor.fetchall()}

        # 5. Preparar solo los IDs que realmente son nuevos
        nuevos_miembros_values = []
        for user_id in user_ids_a_agregar:
            user_id_int = int(user_id)
            if user_id_int not in miembros_existentes:
                nuevos_miembros_values.append((inventario_id, user_id_int))

        # 6. Insertar los nuevos miembros
        if nuevos_miembros_values:
            sql_insert = "INSERT INTO inventario_brigadas (inventario_id, user_id) VALUES (%s, %s)"
            write_cursor = conn.cursor()
            write_cursor.executemany(sql_insert, nuevos_miembros_values)
            conn.commit()
            flash(f"Se añadieron {len(nuevos_miembros_values)} nuevos miembros a la brigada.", "success")
            log_activity(
                action="Añadir Brigada", 
                category="Inventarios", 
                resource_id=inventario_id, 
                details=f"Usuario '{current_user.username}' añadió {len(nuevos_miembros_values)} usuarios a la brigada."
            )
        else:
            flash("Los usuarios seleccionados ya pertenecían a la brigada.", "info")

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al añadir miembros a la brigada: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))


@inventarios_bp.route('/<int:inventario_id>/brigada/remover', methods=['POST'])
@login_required
@permission_required('inventarios.gestionar_inventario') # Re-usamos el permiso
def remover_miembros_brigada(inventario_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor) 

        # 1. Validar el inventario y los permisos del usuario
        cursor.execute("SELECT estatus, id_usuario_creador FROM inventarios WHERE id = %s", (inventario_id,))
        inventario = cursor.fetchone()

        if not inventario:
            flash("Inventario no encontrado.", "danger")
            return redirect(url_for('inventarios.listar_inventarios'))

        # Solo el creador del inventario puede remover miembros
        if inventario['id_usuario_creador'] != current_user.id:
            flash("Solo el creador del inventario puede remover miembros de la brigada.", "danger")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 2. Validar el ESTATUS (misma restricción que para añadir)
        if inventario['estatus'] not in ('Planificado', 'En Progreso'):
            flash("No se pueden remover miembros de la brigada en esta fase del inventario.", "warning")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 3. Obtener los IDs de los usuarios a remover
        user_ids_a_remover = request.form.getlist('user_ids_remover')
        if not user_ids_a_remover:
            flash("No se seleccionó ningún usuario para remover.", "info")
            return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))

        # 4. Regla de negocio: No permitir que el creador sea removido
        user_ids_validados = []
        creador_id = inventario['id_usuario_creador']
        intent_de_remover_creador = False

        for user_id in user_ids_a_remover:
            if int(user_id) == creador_id:
                intent_de_remover_creador = True
            else:
                user_ids_validados.append(int(user_id))

        if intent_de_remover_creador:
            flash("El creador del inventario no puede ser removido de la brigada.", "warning")

        # 5. Ejecutar la eliminación en la BD
        if user_ids_validados:
            # Crear placeholders (%s, %s, ...) para una consulta 'IN' segura
            placeholders = ','.join(['%s'] * len(user_ids_validados))
            sql_delete = f"DELETE FROM inventario_brigadas WHERE inventario_id = %s AND user_id IN ({placeholders})"
            
            # Los parámetros son el ID del inventario + la tupla de IDs de usuario
            params = (inventario_id,) + tuple(user_ids_validados)
            
            write_cursor = conn.cursor()
            write_cursor.execute(sql_delete, params)
            conn.commit()
            flash(f"Se removieron {len(user_ids_validados)} miembros de la brigada.", "success")
            log_activity(
                action="Remover Brigada", 
                category="Inventarios", 
                resource_id=inventario_id, 
                details=f"Usuario '{current_user.username}' removió {len(user_ids_validados)} usuarios de la brigada."
            )

        elif not intent_de_remover_creador:
            flash("No se seleccionó ningún miembro válido para remover.", "info")

    except Exception as e:
        if conn: conn.rollback()
        flash(f'Error al remover miembros de la brigada: {e}', 'danger')
        traceback.print_exc()
    finally:
        if conn :
            conn.close()

    return redirect(url_for('inventarios.gestionar_inventario', inventario_id=inventario_id))