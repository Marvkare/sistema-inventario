# your_flask_app/routes/main.py
from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from database import get_db # Import get_table_columns

main_bp = Blueprint('main', __name__)

# You can move your `index` route here if you prefer
# @main_bp.route('/')
# def index():
#     empty_resguardo = {col: '' for col in get_table_columns()}
#     empty_resguardo['id'] = ''
#     empty_resguardo['Tipo_De_Resguardo'] = ''
#     return render_template('index.html', form_data=empty_resguardo)

@main_bp.route('/resguardos_list')
@login_required
def resguardos_list():
    conn, cursor = get_db()
    if not conn:
        return render_template('resguardos_list.html', resguardos=[])

    resguardos = []
    try:
        cursor.execute("SELECT * FROM resguardo ORDER BY id DESC")
        resguardos = cursor.fetchall()
        
    except Exception as err:
        flash(f"Error al cargar datos: {err}", 'error')
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            
    return render_template('resguardos_list.html', resguardos=resguardos)


@main_bp.route('/resguardos_clasificados')
@login_required
def resguardos_clasificados():
    conn, cursor = get_db()
    if not conn:
        flash("Error de conexión a la base de datos", 'error')
        return redirect(url_for('index')) # Note the blueprint prefix

    try:
        cursor.execute("""
            SELECT r.*,
                CASE
                    WHEN r.Tipo_De_Resguardo LIKE '%Control%' THEN 'Sujeto de Control'
                    ELSE 'Resguardo Normal'
                END AS Tipo_De_Resguardo_Display
            FROM resguardo r
            ORDER BY
                CASE
                    WHEN r.Tipo_De_Resguardo LIKE '%Control%' THEN 0
                    ELSE 1
                END,
                r.id
        """)
        resguardos = cursor.fetchall()
        
        column_names = [desc[0] for desc in cursor.description]
        
        return render_template('resguardos_clasificados.html', 
                               resguardos=resguardos,
                               column_names=column_names)
    except Exception as e:
        flash(f"Error al obtener resguardos: {str(e)}", 'error')
        return redirect(url_for('index')) # Note the blueprint prefix
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()