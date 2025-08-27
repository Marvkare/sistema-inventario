# routes/admin_users.py
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import User, Role
from forms import UserForm

admin_users_bp = Blueprint('admin_users', __name__, url_prefix='/admin/users')

# Decorador para restringir el acceso solo a administradores
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('No tienes permisos para acceder a esta página.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verifica si el usuario actual tiene el rol requerido
            if not current_user.is_authenticated or not any(role.name == role_name for role in current_user.roles):
                flash('No tienes los permisos necesarios para acceder a esta página.', 'danger')
                return redirect(url_for('login')) # Redirige al login o a otra página
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@admin_users_bp.route('/')
@login_required
@admin_required
def list_users():
    users = User.query.all()
    return render_template('admin/list_users.html', users=users)

@admin_users_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = UserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        
        # Asignar un rol por defecto, si es necesario
        default_role = Role.query.filter_by(name='user').first()
        if default_role:
            user.roles.append(default_role)

        db.session.add(user)
        db.session.commit()
        flash('Usuario creado exitosamente.', 'success')
        return redirect(url_for('admin_users.list_users'))

    return render_template('admin/create_user.html', form=form)