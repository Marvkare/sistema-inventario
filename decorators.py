# decorators.py

from functools import wraps
from flask import flash, redirect, url_for, request, jsonify
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
                # --- Manejo para usuarios no autenticados ---
                if 'application/json' in request.accept_mimetypes:
                    return jsonify({'error': 'Autenticación requerida.'}), 401
                flash('Debes iniciar sesión para acceder a esta página.', 'danger')
                return redirect(url_for('auth.login')) # Asegúrate que 'auth.login' sea tu ruta de login
            
            # Construye los permisos del usuario
            user_permissions = {permission.endpoint for role in current_user.roles for permission in role.permissions}
            
            if endpoint_name not in user_permissions:
                # --- LÓGICA AÑADIDA: Detectar si es una petición AJAX ---
                # Si el cliente (fetch) prefiere una respuesta JSON...
                if 'application/json' in request.accept_mimetypes:
                    # Devolvemos un error JSON en lugar de redirigir
                    return jsonify({'error': 'No tienes los permisos necesarios para esta acción.'}), 403 # 403 Forbidden
                else:
                    # Para navegación normal, mantenemos el comportamiento anterior
                    flash('No tienes los permisos necesarios para acceder a esta página.', 'danger')
                    return redirect(url_for('bienes.listar_bienes')) # Redirige a una página segura como el listado
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator