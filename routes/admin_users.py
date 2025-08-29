from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from extensions import db
from models import User, Role,Permission

# Define the blueprint for user administration.
admin_users_bp = Blueprint('admin_users', __name__, url_prefix='/admin/users')

def admin_required(f):
    """
    A decorator to restrict access to a view to only users with the 'admin' role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('No tienes permisos para acceder a esta página.', 'danger')
            return redirect(url_for('resguardos.ver_resguardos'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(endpoint_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debes iniciar sesión para acceder a esta página.', 'danger')
                return redirect(url_for('login'))
            
            # Obtiene todos los permisos del usuario actual
            user_permissions = set()
            for role in current_user.roles:
                for permission in role.permissions:
                    user_permissions.add(permission.endpoint)
            
            # Verifica si el endpoint requerido está en los permisos del usuario
            if endpoint_name not in user_permissions:
                flash('No tienes los permisos necesarios para acceder a esta página.', 'danger')
                return redirect(url_for('resguardos.ver_resguardos'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Role Administration Routes ---

@admin_users_bp.route('/roles')
@login_required
@admin_required
def list_roles():
    """Renders a page with a list of all roles."""
    roles = Role.query.all()
    return render_template('admin/list_roles.html', roles=roles)

@admin_users_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('resguardos.crear_resguardo')
def create_role():
    """Handles the creation of a new role."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name:
            flash('El nombre del rol es requerido.', 'danger')
            return redirect(url_for('admin_users.create_role'))

        new_role = Role(name=name, description=description)
        db.session.add(new_role)
        db.session.commit()
        flash('Rol creado exitosamente.', 'success')
        return redirect(url_for('admin_users.list_roles'))
        
    return render_template('admin/create_role.html')

# --- User Administration Routes ---

@admin_users_bp.route('/')
@login_required
@admin_required
@permission_required('resguardos.crear_resguardo')
def list_users():
    """Renders a page with a list of all users."""
    users = User.query.all()
    return render_template('admin/list_users.html', users=users)

@admin_users_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('resguardos.crear_resguardo')
def create_user():
    """Handles the creation of a new user and assigns roles."""
    all_roles = Role.query.all() # Get all roles from the database

    if request.method == 'POST':
        # Get data from the HTML form
        username = request.form.get('username')
        password = request.form.get('password')
        selected_role_ids = request.form.getlist('roles')

        if not username or not password:
            flash('Nombre de usuario y contraseña son requeridos.', 'danger')
            return redirect(url_for('admin_users.create_user'))

        # Create the new user
        user = User(username=username)
        user.set_password(password)

        # Assign selected roles to the user
        for role_id in selected_role_ids:
            role = Role.query.get(role_id)
            if role:
                user.roles.append(role)
        
        db.session.add(user)
        db.session.commit()
        flash('Usuario creado exitosamente.', 'success')
        return redirect(url_for('admin_users.list_users'))

    return render_template('admin/create_user.html', all_roles=all_roles)

@admin_users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('resguardos.crear_resguardo')
def edit_user(user_id):
    """Handles the editing of an existing user and their roles."""
    user = User.query.get_or_404(user_id)
    all_roles = Role.query.all() # Get all roles for the template

    if request.method == 'POST':
        user.username = request.form['username']
        
        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)
            
        selected_role_ids = request.form.getlist('roles')

        user.roles.clear() # Clear existing roles
        
        for role_id in selected_role_ids:
            role = Role.query.get(role_id)
            if role:
                user.roles.append(role)
        
        db.session.commit()
        flash('Usuario actualizado exitosamente.', 'success')
        return redirect(url_for('admin_users.list_users'))

    return render_template('admin/edit_user.html', user=user, all_roles=all_roles)

@admin_users_bp.route('/delete/<int:user_id>')
@login_required
@permission_required('resguardos.crear_resguardo')
@admin_required
def delete_user(user_id):
    """Deletes a user from the database."""
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('admin_users.list_users'))

    db.session.delete(user)
    db.session.commit()
    flash('Usuario eliminado exitosamente.', 'success')
    return redirect(url_for('admin_users.list_users'))

@admin_users_bp.route('/roles/edit_permissions/<int:role_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@permission_required('resguardos.crear_resguardo')
def edit_role_permissions(role_id):
    """Handles the assignment of permissions to a specific role."""
    role = Role.query.get_or_404(role_id)
    all_permissions = Permission.query.all()

    if request.method == 'POST':
        selected_permission_ids = request.form.getlist('permissions')

        # Clear existing permissions
        role.permissions.clear()
        
        # Add new permissions
        for perm_id in selected_permission_ids:
            permission = Permission.query.get(perm_id)
            if permission:
                role.permissions.append(permission)
        
        db.session.commit()
        flash(f'Permisos del rol {role.name} actualizados exitosamente.', 'success')
        return redirect(url_for('admin_users.list_roles'))
        
    return render_template('admin/edit_role_permissions.html', role=role, all_permissions=all_permissions)


@admin_users_bp.route('/permissions/manage', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_permissions():
    all_roles = Role.query.all()
    
    # 1. Obtener todas las rutas del servidor y crear los permisos que falten
    endpoints = [str(rule.endpoint) for rule in current_app.url_map.iter_rules()]
    relevant_endpoints = [ep for ep in endpoints if not ep.startswith(('static', 'debugtoolbar', 'admin.'))]
    
    existing_permissions = set([p.endpoint for p in Permission.query.all()])
    
    new_permissions = []
    for endpoint in relevant_endpoints:
        if endpoint not in existing_permissions:
            new_perm = Permission(endpoint=endpoint, description=f'Acceso a la ruta {endpoint}')
            new_permissions.append(new_perm)
            db.session.add(new_perm)

    if new_permissions:
        db.session.commit()
        flash(f'{len(new_permissions)} nuevos permisos han sido detectados y agregados.', 'success')
    
    all_permissions = Permission.query.all()

    if request.method == 'POST':
        selected_role_id = request.form.get('role_id')
        selected_permission_ids = request.form.getlist('permissions')

        role = Role.query.get(selected_role_id)
        if not role:
            flash('Rol no encontrado.', 'danger')
            return redirect(url_for('admin_users.manage_permissions'))

        # Limpiar y reasignar los permisos
        role.permissions.clear()
        for perm_id in selected_permission_ids:
            permission = Permission.query.get(perm_id)
            if permission:
                role.permissions.append(permission)
        
        db.session.commit()
        flash(f'Permisos del rol "{role.name}" actualizados exitosamente.', 'success')
        return redirect(url_for('admin_users.list_roles'))
    
    return render_template('admin/manage_permissions.html', all_roles=all_roles, all_permissions=all_permissions)


