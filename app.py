# your_flask_app/app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
import os

# Importar la configuración de la base de datos
from config import DB_CONFIG, PDF_TEMPLATE_PATH, UPLOAD_FOLDER, ALLOWED_EXTENSIONS

# Importar las funciones de la base de datos
from database import get_db, get_db_connection

# Importar los Blueprints
from routes.main import main_bp
from routes.resguardos import resguardos_bp
from routes.areas import areas_bp
from routes.excel_import import excel_import_bp
from routes.handle_errors import handle_errors_bp
from routes.plantillas import plantillas_bp
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui' # ¡Cambia esto por una clave fuerte en producción!

# Cargar configuración de la app
app.config['DB_CONFIG'] = DB_CONFIG
app.config['PDF_TEMPLATE_PATH'] = PDF_TEMPLATE_PATH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

# Helper function to check allowed file extensions (keep it here or in a utils.py)
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

app.jinja_env.globals.update(allowed_file=allowed_file) # Make it available in templates

# Registrar Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(resguardos_bp)
app.register_blueprint(areas_bp)
app.register_blueprint(excel_import_bp)
app.register_blueprint(handle_errors_bp)
app.register_blueprint(plantillas_bp)


# Puedes mantener algunas rutas generales aquí si lo deseas, o moverlas al blueprint 'main'
@app.route('/')
def index():
    # Esta ruta puede quedarse aquí o ir a main.py si es la única ruta principal
    conn, cursor = get_db()
    if not conn:
        return render_template('index.html', form_data={}, areas=[], is_editing=False) # handle error gracefully
    
    try:
        cursor.execute("SELECT id, nombre, numero FROM areas ORDER BY nombre")
        areas_data = [{'id': row['id'], 'name': row['nombre'], 'numero': row['numero']} for row in cursor.fetchall()]
    except Exception as e:
        flash(f"Error al cargar las áreas: {e}", 'error')
        areas_data = []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            
    return render_template('index.html', form_data={}, areas=areas_data, is_editing=False )


if __name__ == '__main__':
    # Asegúrate de que el directorio de uploads exista al inicio
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True) # Siempre usa debug=False en producción


#-------------------------------------------------------------

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS




@app.route('/add', methods=['POST'])
def add_resguardo():
    """Agrega un nuevo resguardo a la base de datos."""
    if request.method == 'POST':
        form_values = request.form.to_dict()
        # 'id' ya no es autoincrementado por la base de datos
        form_values.pop('id', None)

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
                    elif key in ["Fecha_Resguardo", "Fecha_Poliza", "Fecha_Factura"]:
                        try:
                            insert_data[key] = date.fromisoformat(value)
                        except ValueError:
                            flash(f"El campo '{key.replace('_', ' ')}' debe tener el formato YYYY-MM-DD.", 'error')
                            return redirect(url_for('index'))
                    else:
                        insert_data[key] = value
            
            final_insert_data = {k: v for k, v in insert_data.items() if k in VALID_DB_COLUMNS}

            cols = ', '.join(f"`{col}`" for col in final_insert_data.keys())
            placeholders = ', '.join(['%s'] * len(final_insert_data))
            query = f"INSERT INTO resguardo ({cols}) VALUES ({placeholders})"
            
            cursor.execute(query, tuple(final_insert_data.values()))
            conn.commit()
            flash("Resguardo agregado correctamente.", 'success')
        except mysql.connector.Error as err:
            flash(f"Error al agregar resguardo: {err}", 'error')
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('index'))




