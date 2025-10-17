from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy import inspect
import os
from flask_migrate import Migrate  # <--- 1. Importa la clase


# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
app = Flask(__name__)
# Importar la configuración de la base de datos y otras configuraciones
from config import DB_CONFIG, UPLOAD_FOLDER
from extensions import db
from log_activity import log_activity

# Configuración de la aplicación
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos con la app
db.init_app(app)
migrate = Migrate(app, db)
# --- LÓGICA DE INICIALIZACIÓN DE TABLAS (PARA PRODUCCIÓN) ---
def init_tables():
    """
    Verifica si las tablas existen y las crea si es necesario.
    Asume que la base de datos ya ha sido creada manualmente.
    """
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
            print(f"--- ERROR: No se pudo conectar a la base de datos '{DB_CONFIG['database']}'. Asegúrate de que exista y que las credenciales sean correctas. ---")
            print(f"Detalle del error: {e}")
            # En un entorno de producción, es mejor que la app no inicie si no puede conectar a la BD.
            # Podrías optar por salir o simplemente registrar el error.
            raise e

# --- IMPORTACIÓN DE MODELOS Y BLUEPRINTS ---
from models import User, Role
from routes.main import main_bp
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

# Ejecutar la inicialización de las tablas
init_tables()

# --- CONFIGURACIÓN DE FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(main_bp)
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
            log_activity(action=f"Inicio de sesión del usuario: {username}", category="Login")
            db.session.commit()
            return redirect(next_page or url_for('resguardos.ver_resguardos'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity(action=f"Cierre de sesión del usuario: {current_user.username}", category="Logout")
    db.session.commit()
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return redirect(url_for('resguardos.ver_resguardos'))

@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)



# --- Bloque para ejecutar la aplicación en modo de desarrollo ---
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

