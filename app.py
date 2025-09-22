# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory
import os
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash

from log_activity import log_activity

# Importar la configuración de la base de datos y otras configuraciones
from config import DB_CONFIG, PDF_TEMPLATE_PATH, UPLOAD_FOLDER, ALLOWED_EXTENSIONS

# Importar las funciones de la base de datos (tus funciones existentes)
from database import get_db, get_db_connection

# Crear la aplicación y el objeto SQLAlchemy
app = Flask(__name__)
from extensions import db # <-- La instancia de SQLAlchemy se crea aquí

# Configuración de la aplicación
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui' # ¡CAMBIA ESTO!
app.config['DB_CONFIG'] = DB_CONFIG
app.config['PDF_TEMPLATE_PATH'] = PDF_TEMPLATE_PATH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos
db.init_app(app) # <-- Se vincula la instancia de db con la app

# AHORA, después de que 'db' ha sido inicializado, se pueden importar los modelos
from models import User, Role

# Importar los Blueprints
from routes.main import main_bp
from routes.resguardos import resguardos_bp
from routes.areas import areas_bp
from routes.excel_import import excel_import_bp
from routes.handle_errors import handle_errors_bp
from routes.plantillas import plantillas_bp
from routes.admin_users import admin_users_bp # No necesitas admin_routes_bp, admin_users_bp lo reemplaza
from routes.admin import admin_bp# Configuración de Flask-Login
from routes.bienes import bienes_bp
from routes.traspaso import traspaso_bp  # Importar el Blueprint de traspaso
from routes.etiquetas import etiquetas_bp
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Registro de Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(resguardos_bp)
app.register_blueprint(areas_bp)
app.register_blueprint(excel_import_bp)
app.register_blueprint(handle_errors_bp)
app.register_blueprint(plantillas_bp)
app.register_blueprint(admin_users_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(bienes_bp)
app.register_blueprint(traspaso_bp)  # Registrar el Blueprint de traspaso
app.register_blueprint(etiquetas_bp)
# Rutas de Autenticación
@app.route('/login', methods=['GET', 'POST'])
def login():
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
            print(user)
            log_activity("Inicio sesion el usuario: "+username, "Login", "Inicio de sesion por el usuario"+username)
            return redirect(next_page or url_for('resguardos.ver_resguardos'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    print(current_user)
    log_activity("Cerro sesion el usuario: ", "Logout")
    logout_user()
    
   
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return  render_template('index.html')
    
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

app.jinja_env.globals.update(allowed_file=allowed_file)

@app.route('/static/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def create_default_admin():
    # La lógica para crear el usuario 'admin' se mantiene aquí
    with app.app_context():
        db.create_all()
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', description='Administrador del sistema')
            db.session.add(admin_role)
            db.session.commit()

        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin')
            admin_user.set_password('tu_contraseña_segura')
            admin_user.roles.append(admin_role)
            db.session.add(admin_user)
            db.session.commit()
            print("✅ Usuario 'admin' creado exitosamente.")
        else:
            print("El usuario 'admin' ya existe.")

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # La llamada se hace dentro de un contexto de aplicación
    with app.app_context():
        create_default_admin()
    

    # 1. Definir la función que actuará como filtro
    def default_if_none(value, default=''):
        """Devuelve un valor por defecto (string vacío) si el valor es None."""
        return default if value is None else value

    # 2. Registrar la función como un filtro en el entorno de Jinja2
    app.jinja_env.filters['default_if_none'] = default_if_none

        
    app.run(debug=True)

