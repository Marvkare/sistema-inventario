# bajas.py

from flask import Blueprint, request, jsonify, current_app, render_template, flash, redirect, url_for
from flask_login import current_user
# Asegúrate de que la ruta de importación a tus modelos sea la correcta para tu estructura de proyecto
# Por ejemplo, si tus modelos están en 'mi_app/modelos.py', sería: from mi_app.modelos import db, Bienes, ProcesoBaja
from models import db, Bienes, ProcesoBaja , DocumentoBaja, DisposicionFinal, Resguardo, ArchivoAdjunto
from sqlalchemy.orm import joinedload, subqueryload
from sqlalchemy.exc import IntegrityError
import datetime
import traceback
import os
from decorators import login_required, permission_required
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_
from log_activity import log_activity
from flask import send_from_directory, abort
import json
from .workflows import WORKFLOWS, DEFAULT_WORKFLOW



# Se crea un Blueprint para organizar las rutas del módulo de bajas de forma ordenada.
# El 'template_folder' le dice a Flask que busque las plantillas en una carpeta llamada 'templates'.
bajas_bp = Blueprint('bajas', __name__)


@bajas_bp.route('/bajas', methods=['GET'])
@login_required
@permission_required('bajas.gestionar_bajas') 
def gestionar_bajas():
    """
    Renderiza la página principal de gestión de bajas, obteniendo todos los
    procesos de la base de datos de manera eficiente.
    """
    try:
        # La consulta es eficiente y correcta.
        # Carga los bienes relacionados en la misma query para optimizar.
        procesos = db.session.query(ProcesoBaja).options(
            joinedload(ProcesoBaja.bien)
        ).order_by(ProcesoBaja.fecha_inicio.desc()).all()
        
        # Renderiza la plantilla correcta con los datos obtenidos.
        return render_template('bajas/bajas.html', procesos=procesos)

    except Exception as err:
        # En caso de error, muestra un mensaje y renderiza la misma página
        # pero sin datos en la tabla, para no confundir al usuario.
        flash(f"Error al cargar la página de gestión de bajas: {err}", 'danger')
        
        # Imprime el error en la consola para depuración.
        traceback.print_exc() 
        
        # Renderiza la plantilla de bajas con una lista vacía.
        return render_template('bajas/bajas.html', procesos=[])


@bajas_bp.route('/proceso/<int:proceso_id>', methods=['GET'])
@login_required
@permission_required('bajas.ver_proceso')
def ver_proceso(proceso_id):
    """
    Ruta para mostrar los detalles de un proceso de baja específico.
    Ahora también carga la configuración del workflow correspondiente al motivo.
    """
    try:
        # La consulta para obtener el proceso no cambia
        proceso = db.session.query(ProcesoBaja).options(
            joinedload(ProcesoBaja.bien),
            joinedload(ProcesoBaja.usuario_captura),
            subqueryload(ProcesoBaja.documentos).options(
                subqueryload(DocumentoBaja.archivos_adjuntos)
            ).joinedload(DocumentoBaja.usuario_carga),
            joinedload(ProcesoBaja.disposicion_final)
        ).filter_by(id=proceso_id).first_or_404()

        # -*-*- LÓGICA AÑADIDA -*-*-
        # Obtiene la configuración específica para el motivo de este proceso.
        # Usa un workflow por defecto si el motivo no se encuentra.
        workflow_config = WORKFLOWS.get(proceso.motivo, DEFAULT_WORKFLOW)

        # -*-*- RENDERIZADO ACTUALIZADO -*-*-
        # Renderizamos la plantilla pasándole ambas variables: proceso y workflow.
        return render_template('bajas/ver_proceso.html', proceso=proceso, workflow=workflow_config)

    except Exception as e:
        current_app.logger.error(f"Error al ver el proceso {proceso_id}: {e}")
        flash("Ocurrió un error al cargar los detalles del proceso.", "danger")
        return redirect(url_for('bajas.gestionar_bajas'))

# --- API Endpoints (Usados por JavaScript para la interactividad del modal) ---

@bajas_bp.route('/api/bienes/buscar', methods=['GET'])
@login_required
@permission_required('bajas.buscar_bienes_para_baja')
def buscar_bienes_para_baja():
    """
    API endpoint para buscar bienes candidatos a baja.
    Ahora excluye bienes que ya están en un proceso de baja activo.
    """
    query_string = request.args.get('q', '').strip()

    if not query_string:
        return jsonify({"error": "Parámetro de búsqueda 'q' es requerido"}), 400
    
    try:
        # Campos en los que se realizará la búsqueda
        searchable_fields = [
            Bienes.No_Inventario, Bienes.Descripcion_Del_Bien,
            Bienes.Descripcion_Corta_Del_Bien, Bienes.Marca,
            Bienes.Modelo, Bienes.Numero_De_Serie
        ]
        
        search_terms = query_string.split()
        conditions = [
            or_(*[field.ilike(f'%{term}%') for field in searchable_fields])
            for term in search_terms
        ]

        # --- MODIFICADO: Se añade la nueva condición al filtro base ---
        # Construye la consulta para bienes activos que NO estén en un proceso de baja.
        query = db.session.query(Bienes).filter(
            Bienes.Activo == 1,
            Bienes.estatus_actual == 'Activo',
            Bienes.proceso_baja_activo == None  # <-- LÍNEA AÑADIDA
        )

        # Aplica todas las condiciones de búsqueda de texto
        if conditions:
            query = query.filter(and_(*conditions))
        
        bienes_encontrados = query.limit(50).all()

        # Prepara la respuesta JSON
        resultado_json = []
        for bien in bienes_encontrados:
            resguardo_activo = db.session.query(Resguardo).filter_by(id_bien=bien.id, Activo=True).first()
            
            resultado_json.append({
                "id": bien.id,
                "No_Inventario": bien.No_Inventario,
                "Descripcion_Del_Bien": bien.Descripcion_Del_Bien,
                "Marca": bien.Marca,
                "Modelo": bien.Modelo,
                "Costo_Inicial": str(bien.Costo_Inicial),
                "nombre_solicitante": resguardo_activo.Nombre_Del_Resguardante if resguardo_activo else "N/A",
                "nombre_jefe_area": resguardo_activo.Nombre_Director_Jefe_De_Area if resguardo_activo else "N/A"
            })
        
        return jsonify(resultado_json)

    except Exception as e:
        current_app.logger.error(f"Error en la búsqueda de bienes: {e}")
        return jsonify({"error": "Ocurrió un error en el servidor al buscar."}), 500

@bajas_bp.route('/api/procesos-baja', methods=['POST'])
@login_required
@permission_required('bajas.crear_proceso_baja')
def crear_proceso_baja():
    """
    API endpoint para crear un ProcesoBaja y su documento de solicitud inicial.
    Recibe datos como multipart/form-data.
    """
    # --- Se obtienen datos de request.form y request.files ---
    id_bien = request.form.get('id_bien')
    motivo = request.form.get('motivo')
    justificacion = request.form.get('justificacion_solicitud')
    solicitud_file = request.files.get('solicitud_file')

    # --- Validación de datos y archivo ---
    if not all([id_bien, motivo, justificacion]):
        return jsonify({"error": "Faltan datos requeridos (bien, motivo, justificación)."}), 400
    
    if not solicitud_file or solicitud_file.filename == '':
        return jsonify({"error": "El documento de solicitud es obligatorio."}), 400

    try:
        # --- Lógica de transacción atómica para crear todo junto ---
        bien = db.session.query(Bienes).filter_by(id=id_bien).first()
        if not bien:
             return jsonify({"error": "El bien no existe."}), 404
        
        resguardo_activo = db.session.query(Resguardo).filter_by(id_bien=bien.id, Activo=True).first()
        if not resguardo_activo:
            return jsonify({"error": "El bien no tiene un resguardo activo."}), 409
        
        # 1. Crear el Proceso de Baja
        nuevo_proceso = ProcesoBaja(
            id_bien=id_bien, motivo=motivo, justificacion_solicitud=justificacion,
            nombre_solicitante=resguardo_activo.Nombre_Del_Resguardante,
            nombre_jefe_area=resguardo_activo.Nombre_Director_Jefe_De_Area,
            id_usuario_captura=current_user.id, estatus='Solicitado',
            fecha_inicio=datetime.datetime.utcnow()
        )
        db.session.add(nuevo_proceso)
        db.session.flush()  # Obtenemos el ID del nuevo proceso para usarlo a continuación

        # 2. Crear el DocumentoBaja (expediente de la solicitud)
        doc_solicitud = DocumentoBaja(
            id_proceso_baja=nuevo_proceso.id,
            tipo_documento='Solicitud de Baja', # Asignamos el tipo de documento
            metadatos=json.dumps({"descripcion": "Documento inicial de la solicitud."}),
            id_usuario_carga=current_user.id
        )
        db.session.add(doc_solicitud)
        db.session.flush() # Obtenemos el ID del nuevo documento

        # 3. Guardar el archivo físico y crear el ArchivoAdjunto
        filename = secure_filename(solicitud_file.filename)
        unique_filename = f"doc_{doc_solicitud.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        solicitud_file.save(upload_path)

        adjunto_solicitud = ArchivoAdjunto(
            id_documento_baja=doc_solicitud.id,
            nombre_archivo=filename,
            ruta_archivo=unique_filename,
            tipo_mime=solicitud_file.mimetype
        )
        db.session.add(adjunto_solicitud)
        
        # 4. Actualizar el estado del bien
        bien.Estado_Del_Bien = 'En Proceso de Baja'
        
        # 5. Confirmar toda la transacción
        db.session.commit()

        log_activity(
            action="Inicio de Proceso de Baja con Documento", category="Bajas",
            resource_id=nuevo_proceso.id,
            details=f"Usuario '{current_user.username}' inició proceso para el bien '{bien.No_Inventario}' adjuntando solicitud '{filename}'."
        ) 

        return jsonify({"message": "Proceso de baja iniciado exitosamente.", "proceso_id": nuevo_proceso.id}), 201
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error inesperado al crear proceso de baja: {e}")
        error_msg = f"Error inesperado: {str(e)}" if current_app.config.get('DEBUG') else "Ocurrió un error inesperado."
        return jsonify({"error": error_msg}), 500

@bajas_bp.route('/proceso/<int:proceso_id>/cargar-documento', methods=['POST'])
@login_required
@permission_required('bajas.cargar_documento')
def cargar_documento(proceso_id):
    """
    Ruta para manejar la subida de archivos de un proceso de baja.
    """
    proceso = db.session.get(ProcesoBaja, proceso_id)
    if not proceso:
        flash("El proceso de baja no fue encontrado.", "danger")
        return redirect(url_for('bajas.gestionar_bajas'))

    tipo_documento = request.form.get('tipo_documento')
    file = request.files.get('documento_file')

    if not file or file.filename == '':
        flash("No se seleccionó ningún archivo para subir.", "warning")
        return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))
    
    if not tipo_documento:
        flash("Debe seleccionar un tipo de documento.", "warning")
        return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{proceso.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(upload_path)

        nuevo_documento = DocumentoBaja(
            id_proceso_baja=proceso.id,
            tipo_documento=tipo_documento,
            nombre_archivo=filename,
            ruta_archivo=unique_filename,
            id_usuario_carga=current_user.id
        )
        db.session.add(nuevo_documento)
        db.session.commit()

        log_activity(
            action="Carga de Documento",
            category="Bajas",
            resource_id=proceso.id,
            details=f"Usuario '{current_user.username}' cargó el documento '{tipo_documento}' para el proceso de baja ID {proceso.id}"
        )
        flash(f"Documento '{tipo_documento}' cargado exitosamente.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al cargar documento para proceso {proceso.id}: {e}")
        flash("Ocurrió un error al guardar el documento.", "danger")

    return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

# En routes/bajas.py, dentro de la sección de "RUTAS DE ACCIONES"

@bajas_bp.route('/documento/<int:adjunto_id>/descargar') # <-- CAMBIO AQUÍ
@login_required
@permission_required('bajas.ver_proceso')
def descargar_documento(adjunto_id): # <-- Y CAMBIO AQUÍ
    """
    Envía un archivo adjunto para que el usuario pueda verlo o descargarlo.
    """
    try:
        # Busca el registro del ARCHIVO ADJUNTO por su ID
        adjunto = db.session.get(ArchivoAdjunto, adjunto_id) # Usa la variable correcta
        if not adjunto:
            flash("El archivo solicitado no fue encontrado.", "danger")
            return redirect(request.referrer or url_for('bajas.gestionar_bajas'))

        # Envía el archivo de forma segura
        return send_from_directory(
            directory=current_app.config['UPLOAD_FOLDER'],
            path=adjunto.ruta_archivo,
            as_attachment=False
        )
    
    except FileNotFoundError:
        current_app.logger.error(f"Archivo no encontrado para ArchivoAdjunto ID: {adjunto_id}")
        flash("Error: El archivo físico no fue encontrado en el servidor.", "danger")
        return redirect(request.referrer or url_for('bajas.gestionar_bajas'))
    
    except Exception as e:
        current_app.logger.error(f"Error al descargar adjunto {adjunto_id}: {e}")
        flash("Ocurrió un error inesperado al obtener el documento.", "danger")
        return redirect(request.referrer or url_for('bajas.gestionar_bajas'))

@bajas_bp.route('/proceso/<int:proceso_id>/nuevo-documento', methods=['GET', 'POST'])
@login_required
@permission_required('bajas.crear_documento_expediente')
def crear_documento_expediente(proceso_id):
    proceso = db.session.get(ProcesoBaja, proceso_id)
    if not proceso:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Proceso no encontrado'}), 404
        abort(404)

    if request.method == 'POST':
        tipo_documento = request.form.get('tipo_documento')
        metadatos_str = request.form.get('metadatos', '{}')
        archivos = request.files.getlist('archivos_adjuntos')
        
        # Validación básica
        if not tipo_documento:
            return jsonify({'error': 'El tipo de documento es requerido'}), 400
        
        if not archivos or archivos[0].filename == '':
            return jsonify({'error': 'Se requiere al menos un archivo adjunto'}), 400

        # Verificación de duplicados
        documento_existente = DocumentoBaja.query.filter_by(
            id_proceso_baja=proceso_id, 
            tipo_documento=tipo_documento
        ).first()
        
        if documento_existente:
            return jsonify({
                'error': f"Ya existe un documento de tipo '{tipo_documento}' en este expediente"
            }), 400

        try:
            # 1. Crear el registro principal del DocumentoBaja
            nuevo_documento = DocumentoBaja(
                id_proceso_baja=proceso_id,
                tipo_documento=tipo_documento,
                metadatos=metadatos_str,
                id_usuario_carga=current_user.id
            )
            db.session.add(nuevo_documento)
            db.session.flush()

            # 2. Iterar y guardar cada archivo adjunto
            for file in archivos:
                if file.filename:  # Solo procesar archivos con nombre
                    filename = secure_filename(file.filename)
                    unique_filename = f"doc_{nuevo_documento.id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(upload_path)

                    nuevo_adjunto = ArchivoAdjunto(
                        id_documento_baja=nuevo_documento.id,
                        nombre_archivo=filename,
                        ruta_archivo=unique_filename,
                        tipo_mime=file.mimetype
                    )
                    db.session.add(nuevo_adjunto)
            
            db.session.commit()
            
            log_activity(
                action="Creación de Expediente de Baja", 
                category="Bajas", 
                resource_id=proceso.id,
                details=f"Usuario '{current_user.username}' creó el expediente '{tipo_documento}' para el proceso #{proceso.id}."
            )
            
            return jsonify({
                'message': f"Documento '{tipo_documento}' creado y archivos adjuntados exitosamente."
            }), 201

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear documento para proceso {proceso.id}: {e}")
            return jsonify({'error': 'Error interno del servidor al guardar el documento'}), 500

    return render_template('bajas/crear_documento.html', proceso=proceso)
# ... (otros imports) ...

@bajas_bp.route('/proceso/<int:proceso_id>/actualizar-estatus', methods=['POST'])
@login_required
@permission_required('bajas.actualizar_estatus')
def actualizar_estatus(proceso_id):
    proceso = db.session.get(ProcesoBaja, proceso_id)
    if not proceso:
        flash("El proceso de baja no fue encontrado.", "danger")
        return redirect(url_for('bajas.gestionar_bajas'))

    nuevo_estatus = request.form.get('nuevo_estatus')
    if not nuevo_estatus:
        flash("No se especificó un nuevo estatus.", "warning")
        return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

    estatus_anterior = proceso.estatus
    
    # --- LÓGICA DE WORKFLOW DINÁMICO ---
    
    # 1. Obtiene la configuración del workflow para el motivo de este proceso
    workflow_config = WORKFLOWS.get(proceso.motivo, DEFAULT_WORKFLOW)
    
    # 2. Manejo especial para el estatus 'Rechazado' (se puede llegar desde varias etapas)
    if nuevo_estatus == 'Rechazado':
        pass  # Permitimos rechazar sin más validaciones de documentos
    else:
        # 3. Para cualquier otra transición, se consultan las reglas del workflow
        regla_transicion = workflow_config.get('transiciones', {}).get(estatus_anterior)

        # Valida si la transición solicitada es la que dicta la regla
        if not regla_transicion or nuevo_estatus != regla_transicion.get('siguiente_estatus'):
            flash(f"La transición de '{estatus_anterior}' a '{nuevo_estatus}' no es válida.", "danger")
            return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

        # Valida si se ha subido el documento necesario para esta transición
        doc_requerido = regla_transicion.get('documento_necesario')
        if doc_requerido:
            doc_existente = DocumentoBaja.query.filter_by(id_proceso_baja=proceso.id, tipo_documento=doc_requerido).first()
            if not doc_existente:
                flash(f"Error: Para avanzar, se requiere el documento: '{doc_requerido}'.", "danger")
                return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

    # 4. Manejo especial para la finalización del proceso

    
        # Obtenemos el bien para actualizarlo DENTRO de la transacción
        bien_a_dar_de_baja = proceso.bien
        if bien_a_dar_de_baja:
            bien_a_dar_de_baja.Activo = False
            bien_a_dar_de_baja.estatus_actual = 'Baja' # Asegúrate de que este sea el nombre correcto de la columna
        else:
            flash("Error crítico: No se encontró el bien asociado para darlo de baja.", "danger")
            return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

    try:
        # Actualiza el estatus del proceso y guarda todos los cambios
        proceso.estatus = nuevo_estatus
        db.session.commit()

        # Registra la actividad principal
        log_activity(
            action="Cambio de Estatus de Proceso", category="Bajas", resource_id=proceso.id,
            details=f"Usuario '{current_user.username}' cambió el estatus del proceso #{proceso.id} de '{estatus_anterior}' a '{nuevo_estatus}'."
        )

        # Si se finalizó, registra también la baja del bien
        if nuevo_estatus == 'Finalizado' and bien_a_dar_de_baja:
            log_activity(
                action="Baja de Bien", category="Bienes", resource_id=bien_a_dar_de_baja.id,
                details=f"El bien '{bien_a_dar_de_baja.No_Inventario}' fue dado de baja permanentemente por '{current_user.username}' (Proceso #{proceso.id})."
            )

        flash(f"El estatus del proceso ha sido actualizado a '{nuevo_estatus}'.", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al actualizar estatus del proceso {proceso.id}: {e}")
        flash("Ocurrió un error al actualizar el estatus.", "danger")
    
    return redirect(url_for('bajas.ver_proceso', proceso_id=proceso.id))

@bajas_bp.route('/proceso/<int:proceso_id>/registrar-disposicion', methods=['POST'])
@login_required
@permission_required('bajas.registrar_disposicion_final') # Necesitarás crear este permiso
def registrar_disposicion_final(proceso_id):
    """
    Crea el registro de la disposición final para un proceso de baja.
    """
    proceso = db.session.get(ProcesoBaja, proceso_id)
    if not proceso:
        flash("El proceso de baja no fue encontrado.", "danger")
        return redirect(url_for('bajas.gestionar_bajas'))

    

    if proceso.disposicion_final:
        flash("Error: Ya existe un registro de disposición final para este proceso.", "warning")
        return redirect(url_for('bajas.ver_proceso', proceso_id=proceso_id))

    # --- Obtener datos del formulario ---
    tipo_disposicion = request.form.get('tipo_disposicion')
    fecha_disposicion = request.form.get('fecha_disposicion')
    valor_enajenacion = request.form.get('valor_enajenacion')
    nombre_donatario = request.form.get('nombre_donatario')
    detalles_destruccion = request.form.get('detalles_destruccion')

    if not tipo_disposicion or not fecha_disposicion:
        flash("El tipo y la fecha de disposición son obligatorios.", "danger")
        return redirect(url_for('bajas.ver_proceso', proceso_id=proceso_id))

    try:
        nueva_disposicion = DisposicionFinal(
            id_proceso_baja=proceso_id,
            tipo_disposicion=tipo_disposicion,
            fecha_disposicion=datetime.datetime.strptime(fecha_disposicion, '%Y-%m-%d').date(),
            valor_enajenacion=valor_enajenacion if valor_enajenacion else None,
            nombre_donatario=nombre_donatario,
            detalles_destruccion=detalles_destruccion
        )

        db.session.add(nueva_disposicion)
        db.session.commit()

        log_activity(
            action="Registro de Disposición Final", category="Bajas", resource_id=proceso.id,
            details=f"Se registró la disposición final ({tipo_disposicion}) para el proceso #{proceso.id}."
        )
        flash("La disposición final ha sido registrada exitosamente.", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al registrar disposición final para proceso {proceso.id}: {e}")
        flash("Ocurrió un error al registrar la disposición final.", "danger")
    
    return redirect(url_for('bajas.ver_proceso', proceso_id=proceso_id))