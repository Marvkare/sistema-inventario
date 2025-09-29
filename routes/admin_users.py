from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
import mysql.connector
import traceback
import uuid
from datetime import datetime, timedelta
from werkzeug.exceptions import abort

# Se importan las funciones y variables de tus otros archivos
from database import get_db_connection
from log_activity import log_activity

admin_users_bp = Blueprint('admin_users', __name__, url_prefix='/admin/users')

# --- Decoradores (Se mantienen igual, no dependen de SQLAlchemy) ---

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(current_user, 'is_admin') or not current_user.is_admin():
            flash('No tienes permisos para acceder a esta página.', 'danger')
            return redirect(url_for('resguardos.ver_resguardos'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(endpoint_name):
    # Esta función ya consulta la BD manualmente, por lo que no necesita cambios.
    # Asegúrate de que tu modelo 'current_user' pueda obtener los roles y permisos.
    # Por simplicidad, se asume que la lógica interna de current_user.roles funciona.
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'danger')
            return redirect(url_for('login'))
        
        # Esta lógica depende de cómo tu objeto 'User' carga sus roles.
        # Asumimos que `current_user.roles` funciona como antes.
        user_permissions = set()
        for role in current_user.roles:
            for permission in role.permissions:
                user_permissions.add(permission.endpoint)
        
        if endpoint_name not in user_permissions:
            flash('No tienes los permisos necesarios para acceder a esta página.', 'danger')
            return redirect(url_for('resguardos.ver_resguardos'))
        
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de Administración de Roles ---

@admin_users_bp.route('/roles')
@login_required
@admin_required
def list_roles():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM role ORDER BY name")
        roles = cursor.fetchall()
        return render_template('admin/list_roles.html', roles=roles)
    except Exception as e:
        flash(f"Error al listar roles: {e}", 'danger')
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn and conn.is_connected(): conn.close()

@admin_users_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_role():
    if request.method == 'POST':
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            name = request.form.get('name')
            description = request.form.get('description')

            if not name:
                flash('El nombre del rol es requerido.', 'danger')
                return redirect(url_for('admin_users.create_role'))

            cursor.execute("INSERT INTO role (name, description) VALUES (%s, %s)", (name, description))
            conn.commit()
            
            # CORRECCIÓN: Se usa 'category' en lugar de 'resource'
            log_activity(action="Creación de Rol", category="Roles", details=f"Se agregó el nuevo rol: {name}")
            flash('Rol creado exitosamente.', 'success')
            return redirect(url_for('admin_users.list_roles'))
        except mysql.connector.Error as err:
            if conn: conn.rollback()
            flash(f"Error de base de datos al crear rol: {err}", 'danger')
        finally:
            if conn and conn.is_connected(): conn.close()
    
    return render_template('admin/create_role.html')

# --- Rutas de Administración de Usuarios ---

@admin_users_bp.route('/')
@login_required
@admin_required
def list_users():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # --- CORRECCIÓN CLAVE ---
        # Se usa COALESCE para manejar el caso en que un usuario no tenga roles.
        # Si GROUP_CONCAT devuelve NULL, se reemplaza por un string vacío.
        cursor.execute("""
            SELECT 
                u.id, 
                u.username, 
                COALESCE(GROUP_CONCAT(r.name SEPARATOR ', '), '') as roles
            FROM user u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN role r ON ur.role_id = r.id
            GROUP BY u.id, u.username
            ORDER BY u.username
        """)
        users = cursor.fetchall()
        return render_template('admin/list_users.html', users=users)
    except Exception as e:
        flash(f"Error al listar usuarios: {e}", 'danger')
        traceback.print_exc() # Imprime el error completo en la consola del servidor
        return redirect(url_for('resguardos.ver_resguardos'))
    finally:
        if conn and conn.is_connected(): conn.close()



@admin_users_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM role ORDER BY name")
        all_roles = cursor.fetchall()
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            selected_role_ids = request.form.getlist('roles')

            if not username or not password:
                flash('Nombre de usuario y contraseña son requeridos.', 'danger')
                return redirect(url_for('admin_users.create_user'))

            hashed_password = generate_password_hash(password)
            
            # Insertar usuario y obtener su ID
            cursor.execute("INSERT INTO user (username, password_hash) VALUES (%s, %s)", (username, hashed_password))
            user_id = cursor.lastrowid

            # Asignar roles
            if selected_role_ids:
                role_data = [(user_id, role_id) for role_id in selected_role_ids]
                cursor.executemany("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", role_data)
            
            conn.commit()
            # CORRECCIÓN: Se usa 'category' en lugar de 'resource'
            log_activity(action="Creación de Usuario", category="Usuarios", details=f"Se creó el usuario: {username}")
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('admin_users.list_users'))

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al crear usuario: {e}", 'danger')
    finally:
        if conn and conn.is_connected(): conn.close()

    return render_template('admin/create_user.html', all_roles=all_roles)


@admin_users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            username = request.form['username']
            new_password = request.form.get('password')
            selected_role_ids = request.form.getlist('roles')
            
            # Actualizar datos del usuario
            if new_password:
                hashed_password = generate_password_hash(new_password)
                cursor.execute("UPDATE user SET username = %s, password_hash = %s WHERE id = %s", (username, hashed_password, user_id))
            else:
                cursor.execute("UPDATE user SET username = %s WHERE id = %s", (username, user_id))
            
            # Actualizar roles
            cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            if selected_role_ids:
                role_data = [(user_id, role_id) for role_id in selected_role_ids]
                cursor.executemany("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", role_data)
            
            conn.commit()
            # CORRECCIÓN: Se usa 'category' en lugar de 'resource'
            log_activity(action="Edición de Usuario", category="Usuarios", resource_id=user_id, details=f"Se editó el usuario: {username}")
            flash('Usuario actualizado exitosamente.', 'success')
            return redirect(url_for('admin_users.list_users'))

        # Lógica GET para mostrar el formulario
        cursor.execute("SELECT id, username FROM user WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            abort(404)
        
        cursor.execute("SELECT id, name FROM role ORDER BY name")
        all_roles = cursor.fetchall()
        
        cursor.execute("SELECT role_id FROM user_roles WHERE user_id = %s", (user_id,))
        user_role_ids = {row['role_id'] for row in cursor.fetchall()}

        return render_template('admin/edit_user.html', user=user, all_roles=all_roles, user_role_ids=user_role_ids)

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al editar usuario: {e}", 'danger')
        return redirect(url_for('admin_users.list_users'))
    finally:
        if conn and conn.is_connected(): conn.close()


@admin_users_bp.route('/delete/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('admin_users.list_users'))
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Guardar el nombre de usuario antes de borrarlo para el log
        cursor.execute("SELECT username FROM user WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            flash("Usuario no encontrado", 'danger')
            return redirect(url_for('admin_users.list_users'))
        
        username_deleted = user['username']

        # El ON DELETE CASCADE en la BD se encargará de las tablas relacionadas
        cursor.execute("DELETE FROM user WHERE id = %s", (user_id,))
        conn.commit()
        
        # CORRECCIÓN: Se usa 'category' en lugar de 'resource'
        log_activity(action="Eliminación de Usuario", category="Usuarios", resource_id=user_id, details=f"Se eliminó el usuario: {username_deleted}")
        flash('Usuario eliminado exitosamente.', 'success')
    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al eliminar usuario: {e}", 'danger')
    finally:
        if conn and conn.is_connected(): conn.close()

    return redirect(url_for('admin_users.list_users'))


@admin_users_bp.route('/permissions/manage', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_permissions():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Siempre busca y añade nuevos permisos del servidor.
        endpoints = [str(rule.endpoint) for rule in current_app.url_map.iter_rules()]
        relevant_endpoints = [ep for ep in endpoints if not ep.startswith(('static', 'debugtoolbar'))]
        
        cursor.execute("SELECT endpoint FROM permission")
        existing_permissions = {p['endpoint'] for p in cursor.fetchall()}
        
        new_endpoints = [ep for ep in relevant_endpoints if ep not in existing_permissions]
        if new_endpoints:
            new_perms_data = [(ep, f'Acceso a la ruta {ep}') for ep in new_endpoints]
            cursor.executemany("INSERT INTO permission (endpoint, description) VALUES (%s, %s)", new_perms_data)
            conn.commit()
            flash(f'{len(new_endpoints)} nuevos permisos han sido detectados y agregados.', 'info')

        # 2. Lógica POST para guardar los permisos de un rol.
        if request.method == 'POST':
            role_id = request.form.get('role_id')
            selected_permission_ids = request.form.getlist('permissions')

            cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))
            if selected_permission_ids:
                perm_data = [(role_id, perm_id) for perm_id in selected_permission_ids]
                cursor.executemany("INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)", perm_data)
            
            conn.commit()
            
            cursor.execute("SELECT name FROM role WHERE id = %s", (role_id,))
            role_name = cursor.fetchone()['name']
            
            log_activity(action="Gestión de Permisos", category="Role-permisos", resource_id=int(role_id), details=f"Se actualizaron los permisos para el rol '{role_name}'")
            flash(f'Permisos del rol "{role_name}" actualizados exitosamente.', 'success')
            return redirect(url_for('admin_users.list_roles'))

        # 3. Lógica GET para mostrar la página.
        cursor.execute("SELECT id, name FROM role ORDER BY name")
        all_roles = cursor.fetchall()
        cursor.execute("SELECT id, endpoint, description FROM permission ORDER BY endpoint")
        all_permissions = cursor.fetchall()
        
        # --- CORRECCIÓN CLAVE ---
        # Se crea un mapa de los permisos de cada rol para enviarlo a la plantilla.
        cursor.execute("SELECT role_id, permission_id FROM role_permissions")
        role_perms_map = {}
        for row in cursor.fetchall():
            role_id = row['role_id']
            permission_id = row['permission_id']
            # .setdefault() es una forma eficiente de inicializar la lista si no existe.
            role_perms_map.setdefault(role_id, []).append(permission_id)

        return render_template(
            'admin/manage_permissions.html', 
            all_roles=all_roles, 
            all_permissions=all_permissions, 
            role_perms_map=role_perms_map  # Se pasa el mapa a la plantilla
        )

    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        flash(f"Error al gestionar permisos: {e}", 'danger')
        return redirect(url_for('admin_users.list_roles'))
    finally:
        if conn and conn.is_connected(): conn.close()


@admin_users_bp.route('/reset-password-request/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reset_password_request(user_id):
    """Genera un token y un enlace para que el usuario restablezca su contraseña."""
    conn = None
    try:
        # Generar un token único y seguro
        token = uuid.uuid4().hex
        # Establecer una fecha de expiración (ej. 24 horas desde ahora)
        expiration = datetime.utcnow() + timedelta(hours=24)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Guardar el token y la fecha de expiración en la base de datos
        cursor.execute(
            "UPDATE user SET reset_token = %s, reset_token_expiration = %s WHERE id = %s",
            (token, expiration, user_id)
        )
        conn.commit()
        
        # Crear el enlace de restablecimiento
        reset_link = url_for('admin_users.reset_password', token=token, _external=True)
        
        # Mostrar el enlace al administrador
        flash(f"Copia y envía este enlace al usuario. El enlace expirará en 24 horas: {reset_link}", 'success')
        log_activity(action="Solicitud de reseteo de contraseña", category="Usuarios", resource_id=user_id)

    except Exception as e:
        if conn: conn.rollback()
        flash(f"Error al generar el enlace de reseteo: {e}", 'danger')
        traceback.print_exc()
    finally:
        if conn and conn.is_connected(): conn.close()
        
    return redirect(url_for('admin_users.list_users'))


@admin_users_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Página donde el usuario final establece su nueva contraseña."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verificar si el token es válido y no ha expirado
        cursor.execute(
            "SELECT id, username FROM user WHERE reset_token = %s AND reset_token_expiration > NOW()",
            (token,)
        )
        user = cursor.fetchone()

        if not user:
            flash("El enlace de restablecimiento de contraseña es inválido o ha expirado.", 'danger')
            return redirect(url_for('login'))

        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not password or password != confirm_password:
                flash("Las contraseñas no coinciden o están vacías.", 'danger')
                return render_template('admin/reset_password.html', token=token)

            # Actualizar la contraseña y anular el token
            hashed_password = generate_password_hash(password)
            cursor.execute(
                "UPDATE user SET password_hash = %s, reset_token = NULL, reset_token_expiration = NULL WHERE id = %s",
                (hashed_password, user['id'])
            )
            conn.commit()
            
            log_activity(action="Contraseña restablecida", category="Usuarios", resource_id=user['id'])
            flash("Tu contraseña ha sido actualizada. Ya puedes iniciar sesión.", 'success')
            
            # (Opcional) Iniciar sesión automáticamente al usuario
            # user_obj = User.query.get(user['id'])
            # login_user(user_obj)

            return redirect(url_for('login'))

    except Exception as e:
        flash(f"Ocurrió un error: {e}", 'danger')
        traceback.print_exc()
        return redirect(url_for('login'))
    finally:
        if conn and conn.is_connected(): conn.close()

    return render_template('admin/reset_password.html', token=token)

