from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from log_activity import log_activity
from decimal import Decimal
from decorators import permission_required
from extensions import db
from models import Bienes, ImagenesBien, Resguardo
from werkzeug.utils import secure_filename
import uuid
import os
import traceback
from database import get_db_connection
import mysql.connector
bienes_bp = Blueprint('bienes', __name__)

def allowed_file(filename):
    """
    Función para verificar si la extensión del archivo es permitida.
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@bienes_bp.route('/bienes')
@login_required
@permission_required('bienes.listar_bienes') # Asume un permiso para ver bienes
def listar_bienes():
    conn = None
    cursor = None
    bienes_data = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Consulta SQL corregida para unir las tres tablas
        sql_query = """
                SELECT 
                    b.id,
                    b.No_Inventario, 
                    b.Descripcion_Del_Bien,
                    r.id AS resguardo_id, -- AQUI AGREGAMOS EL ID DEL RESGUARDO
                    a.Nombre AS Area_Nombre,
                    b.Estado_Del_Bien,
                    CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END AS tiene_resguardo
                FROM bienes b
                LEFT JOIN resguardos r ON b.id = r.id_bien
                LEFT JOIN areas a ON r.id_area = a.id
                ORDER BY b.id DESC
            """
        cursor.execute(sql_query)
        bienes_data = cursor.fetchall()
        
        return render_template('bienes/listar_bienes.html', bienes=bienes_data)
        
    except mysql.connector.Error as err:
        flash(f"Error al obtener los bienes: {err}", 'error')
        return render_template('bienes/listar_bienes.html', bienes=[])
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bienes_bp.route('/bienes/agregar', methods=['GET', 'POST'])
@login_required
@permission_required('bienes.agregar_bien') # Asume un permiso para agregar bienes
def agregar_bien():
    """Maneja la adición de un nuevo bien."""
    if request.method == 'POST':
        try:
            # Helper para convertir valores vacíos a None
            def to_none(val):
                return None if val == '' else val
            
            # Crea una nueva instancia del modelo Bienes
            nuevo_bien = Bienes(
                No_Inventario=request.form.get('No_Inventario'),
                No_Factura=to_none(request.form.get('No_Factura')),
                No_Cuenta=to_none(request.form.get('No_Cuenta')),
                Proveedor=to_none(request.form.get('Proveedor')),
                Descripcion_Del_Bien=to_none(request.form.get('Descripcion_Del_Bien')),
                Descripcion_Corta_Del_Bien=to_none(request.form.get('Descripcion_Corta_Del_Bien')),
                Rubro=to_none(request.form.get('Rubro')),
                Poliza=to_none(request.form.get('Poliza')),
                Fecha_Poliza=to_none(request.form.get('Fecha_Poliza')),
                Sub_Cuenta_Armonizadora=to_none(request.form.get('Sub_Cuenta_Armonizadora')),
                Fecha_Factura=to_none(request.form.get('Fecha_Factura')),
                Costo_Inicial=Decimal(request.form.get('Costo_Inicial')) if request.form.get('Costo_Inicial') else None,
                Depreciacion_Acumulada=Decimal(request.form.get('Depreciacion_Acumulada')) if request.form.get('Depreciacion_Acumulada') else None,
                Costo_Final_Cantidad=Decimal(request.form.get('Costo_Final_Cantidad')) if request.form.get('Costo_Final_Cantidad') else None,
                Cantidad=int(request.form.get('Cantidad')) if request.form.get('Cantidad') else None,
                Estado_Del_Bien=to_none(request.form.get('Estado_Del_Bien')),
                Marca=to_none(request.form.get('Marca')),
                Modelo=to_none(request.form.get('Modelo')),
                Numero_De_Serie=to_none(request.form.get('Numero_De_Serie')),
                Tipo_De_Alta=to_none(request.form.get('Tipo_De_Alta'))
            )

            db.session.add(nuevo_bien)
            db.session.commit()

            # --- Image Handling ---
            imagenes = request.files.getlist('imagenes_bien')
            for imagen in imagenes:
                if imagen and imagen.filename != '':
                    filename = secure_filename(imagen.filename)
                    # Create a unique filename to prevent collisions
                    unique_filename = f"{uuid.uuid4()}-{filename}"
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                    imagen.save(save_path)

                    # Save the path to the database
                    nueva_imagen_db = ImagenesBien(id_bien=nuevo_bien.id, ruta_imagen=unique_filename)
                    db.session.add(nueva_imagen_db)
            
            db.session.commit() # Save the image records to the database
            log_activity(
                f"Agregó un nuevo bien: {nuevo_bien.No_Inventario}", 
                "Bienes", 
                f"El usuario {current_user.username} agregó el bien con No. de Inventario {nuevo_bien.No_Inventario}"
            )
            flash('Bien agregado exitosamente.', 'success')
            return redirect(url_for('bienes.listar_bienes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al agregar el bien: {e}', 'danger')
            current_app.logger.error(f"Error al agregar un bien: {e}")
            log_activity(
                f"Error al agregar un bien", 
                "Bienes", 
                f"El usuario {current_user.username} falló al agregar un bien. Error: {e}"
            )
            
    return render_template('bienes/agregar_bien.html')

@bienes_bp.route('/bienes/editar/<int:bien_id>', methods=['GET', 'POST'])
@login_required
@permission_required('bienes.editar_bien') # Asume un permiso para editar bienes
def editar_bien(bien_id):
    """Maneja la edición de un bien existente."""
    bien = Bienes.query.get_or_404(bien_id)
    
    if request.method == 'POST':
        try:
            # Helper para convertir valores vacíos a None
            def to_none(val):
                return None if val == '' else val

            # Actualiza los campos del bien
            bien.No_Inventario = request.form.get('No_Inventario')
            bien.No_Factura = to_none(request.form.get('No_Factura'))
            bien.No_Cuenta = to_none(request.form.get('No_Cuenta'))
            bien.Proveedor = to_none(request.form.get('Proveedor'))
            bien.Descripcion_Del_Bien = to_none(request.form.get('Descripcion_Del_Bien'))
            bien.Descripcion_Corta_Del_Bien = to_none(request.form.get('Descripcion_Corta_Del_Bien'))
            bien.Rubro = to_none(request.form.get('Rubro'))
            bien.Poliza = to_none(request.form.get('Poliza'))
            bien.Fecha_Poliza = to_none(request.form.get('Fecha_Poliza'))
            bien.Sub_Cuenta_Armonizadora = to_none(request.form.get('Sub_Cuenta_Armonizadora'))
            bien.Fecha_Factura = to_none(request.form.get('Fecha_Factura'))
            bien.Costo_Inicial = Decimal(request.form.get('Costo_Inicial')) if request.form.get('Costo_Inicial') else None
            bien.Depreciacion_Acumulada = Decimal(request.form.get('Depreciacion_Acumulada')) if request.form.get('Depreciacion_Acumulada') else None
            bien.Costo_Final_Cantidad = Decimal(request.form.get('Costo_Final_Cantidad')) if request.form.get('Costo_Final_Cantidad') else None
            bien.Cantidad = int(request.form.get('Cantidad')) if request.form.get('Cantidad') else None
            bien.Estado_Del_Bien = to_none(request.form.get('Estado_Del_Bien'))
            bien.Marca = to_none(request.form.get('Marca'))
            bien.Modelo = to_none(request.form.get('Modelo'))
            bien.Numero_De_Serie = to_none(request.form.get('Numero_De_Serie'))
            bien.Tipo_De_Alta = to_none(request.form.get('Tipo_De_Alta'))

            db.session.commit()
            log_activity(
                f"Editó el bien: {bien.No_Inventario}", 
                "Bienes", 
                f"El usuario {current_user.username} editó el bien con No. de Inventario {bien.No_Inventario}"
            )
            flash('Bien actualizado exitosamente.', 'success')
            return redirect(url_for('bienes.listar_bienes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el bien: {e}', 'danger')
            current_app.logger.error(f"Error al editar un bien: {e}")
            log_activity(
                f"Error al editar un bien", 
                "Bienes", 
                f"El usuario {current_user.username} falló al editar el bien {bien.No_Inventario}. Error: {e}"
            )

    return render_template('bienes/editar_bien.html', bien=bien)

@bienes_bp.route('/bienes/eliminar/<int:bien_id>', methods=['POST'])
@login_required
@permission_required('bienes.eliminar_bien')
def eliminar_bien(bien_id):
    """Elimina un bien de la base de datos."""
    bien = Bienes.query.get_or_404(bien_id)
    try:
        db.session.delete(bien)
        db.session.commit()
        log_activity(
            f"Eliminó el bien: {bien.No_Inventario}", 
            "Bienes", 
            f"El usuario {current_user.username} eliminó el bien con No. de Inventario {bien.No_Inventario}"
        )
        flash('Bien eliminado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el bien: {e}', 'danger')
        current_app.logger.error(f"Error al eliminar un bien: {e}")
        log_activity(
            f"Error al eliminar un bien", 
            "Bienes", 
            f"El usuario {current_user.username} falló al eliminar el bien {bien.No_Inventario}. Error: {e}"
        )
    return redirect(url_for('bienes.listar_bienes'))


@bienes_bp.route('/bienes/<int:bien_id>/detalles')
@login_required
@permission_required('bienes.ver_detalles_bien')
def ver_detalles_bien(bien_id):
    """Muestra los detalles completos de un bien y sus resguardos asociados."""
    bien = Bienes.query.get_or_404(bien_id)
    # Suponiendo que la tabla `resguardos` tiene una columna `id_bien`
    # y que tienes el modelo Resguardo definido
    resguardos = Resguardo.query.filter_by(id_bien=bien.id).all()
    # Para el propósito de este ejemplo, devolveré una lista vacía para evitar errores
    # Si tienes el modelo Resguardo, puedes descomentar la línea de arriba.
    

    return render_template('bienes/detalles_bien.html', bien=bien, resguardos=resguardos)
