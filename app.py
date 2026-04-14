from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy import inspect create_engine, text
import os

from flask import send_from_directory, abort, current_app
from flask_migrate import Migrate  # <--- 1. Importa la clase
from flask import Response, abort  # <-- Asegúrate de importar esto

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = Flask(__name__)
# Importar la configuración de la base de datos y otras configuraciones
from config import DB_CONFIG,    UPLOAD_FOLDER
from extensions import db
from log_activity import log_activity
import httplib2
import time
# Configuración de la aplicación
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos con la app
db.init_app(app)
migrate = Migrate(app, db)
# --- LÓGICA DE INICIALIZACIÓN DE TABLAS (PARA PRODUCCIÓN) ---
# --- LÓGICA DE INICIALIZACIÓN DE BASE DE DATOS Y TABLAS (PARA PRODUCCIÓN) ---
def init_database_and_tables():
    """
    Verifica si la base de datos existe en el servidor y la crea si es necesario.
    Luego verifica si las tablas existen y las crea.
    """
    # 1. Crear la Base de Datos si no existe
    # Nos conectamos al servidor MySQL directamente, omitiendo el nombre de la BD al final de la URI
    server_uri = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/"
    engine_server = create_engine(server_uri)
    
    try:
        # Usamos AUTOCOMMIT porque CREATE DATABASE es una operación DDL que no requiere transacción
        with engine_server.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`"))
            print(f"✅ Base de datos '{DB_CONFIG['database']}' verificada/creada exitosamente.")
    except Exception as e:
        print(f"--- ERROR: No se pudo conectar al servidor MySQL en {DB_CONFIG['host']}:{DB_CONFIG['port']} ---")
        print("Asegúrate de que el servidor MySQL esté corriendo y las credenciales sean correctas.")
        print(f"Detalle del error: {e}")
        raise e

    # 2. Crear las Tablas
    # Ahora usamos el contexto de la aplicación, el cual ya usa la URI completa (con la BD incluida)
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if not inspector.get_table_names():
                print("--- No se encontraron tablas, creando esquema completo... ---")
                db.create_all()
                print("✅ ¡Tablas creadas exitosamente!")
            else:
                print("ℹ️ Las tablas de la base de datos ya existen.")
        
        except (OperationalError, ProgrammingError) as e:
            print(f"--- ERROR: Problema al interactuar con las tablas en la base de datos '{DB_CONFIG['database']}'. ---")
            print(f"Detalle del error: {e}")
            raise e


# --- IMPORTACIÓN DE MODELOS Y BLUEPRINTS ---
from models import User, Role
from routes.resguardos import resguardos_bp
from routes.areas import areas_bp
from routes.excel_import import excel_import_bp
from routes.handle_errors import handle_errors_bp
from routes.plantillas import plantillas_bp
from routes.admin_users import admin_users_bp
from routes.admin import admin_bp
from routes.bienes import bienes_bp
from routes.traspaso import traspaso_bp
from routes.etiquetas import etiquetas_bp
from routes.bajas import bajas_bp
from routes.inventarios import inventarios_bp  # Asegúrate de importar el blueprint de inventarios
from routes.manual import manual_bp  # Importar el blueprint del manual
# Ejecutar la inicialización de la base de datos y las tablas
init_database_and_tables()

# --- CONFIGURACIÓN DE FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(resguardos_bp)
app.register_blueprint(areas_bp)
app.register_blueprint(excel_import_bp)
app.register_blueprint(handle_errors_bp)
app.register_blueprint(plantillas_bp)
app.register_blueprint(admin_users_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(bienes_bp)
app.register_blueprint(traspaso_bp)
app.register_blueprint(etiquetas_bp)
app.register_blueprint(bajas_bp)
app.register_blueprint(inventarios_bp)  # Registrar el blueprint de inventarios
app.register_blueprint(manual_bp)  # Registrar el blueprint del manual

# --- RUTAS DE AUTENTICACIÓN Y CONFIGURACIÓN INICIAL ---

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.count() > 0:
        flash('El sistema ya ha sido configurado. Por favor, inicie sesión.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Ambos campos son requeridos.', 'danger')
            return render_template('setup.html')
        
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrador del sistema')
            db.session.add(admin_role)
        
        admin_user = User(username=username)
        admin_user.set_password(password)
        admin_user.roles.append(admin_role)
        
        db.session.add(admin_user)
        db.session.commit()
        
        login_user(admin_user)
        flash('¡Configuración completada! Has iniciado sesión como administrador.', 'success')
        return redirect(url_for('index'))

    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if User.query.count() == 0:
        flash('Bienvenido. Por favor, crea la primera cuenta de administrador.', 'info')
        return redirect(url_for('setup'))

    if current_user.is_authenticated:
        return redirect(url_for('resguardos.ver_resguardos'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('¡Inicio de sesión exitoso!', 'success')
            next_page = request.args.get('next')
            log_activity(
                action="Inicio de Sesión", 
                category="Login", 
                details=f"El usuario '{username}' ha iniciado sesión."
            )
            db.session.commit()
            return redirect(next_page or url_for('resguardos.ver_resguardos'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity(
        action="Cierre de Sesión", 
        category="Logout", 
        details=f"El usuario '{current_user.username}' ha cerrado sesión."
    )
    db.session.commit()
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return redirect(url_for('resguardos.ver_resguardos'))

# Cache local para imágenes



@app.route('/uploads/<path:filename>')
@login_required
def serve_uploaded_file(filename):
    upload_dir = app.config.get('UPLOAD_FOLDER')
    
    if not upload_dir:
        app.logger.error("UPLOAD_FOLDER no está configurado.")
        abort(404)
        
    try:
        # CORRECCIÓN VITAL: Reemplazar las barras invertidas de Windows 
        # por barras normales que Flask necesita para navegar subcarpetas.
        safe_filename = filename.replace('\\', '/')
        
        return send_from_directory(upload_dir, safe_filename)
        
    except NotFound:
        # Esto evita que un 404 normal se convierta en un error 500
        abort(404)
    except Exception as e:
        app.logger.error(f"Error interno al servir archivo {filename}: {e}")
        abort(500)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Usar la variable de entorno o por defecto False
    #debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    #app.run(debug=debug_mode)
    app.run(host='0.0.0.0', port=5000, debug=True)


