# decorators.py

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user, login_required

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
            
            user_permissions = set()
            for role in current_user.roles:
                for permission in role.permissions:
                    user_permissions.add(permission.endpoint)
            
            if endpoint_name not in user_permissions:
                flash('No tienes los permisos necesarios para acceder a esta página.', 'danger')
                return redirect(url_for('resguardos.ver_resguardos'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator