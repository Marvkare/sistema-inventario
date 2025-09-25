from extensions import db
from models import ActivityLog
from flask_login import current_user
from datetime import datetime

def log_activity(action, category=None, details=None, resource_id=None):
    """
    Crea un registro de actividad y lo añade a la sesión de la base de datos.
    NO hace commit. El commit se debe hacer en la ruta que llama a esta función.
    """
    try:
        # Asegurarse de que hay un usuario autenticado
        user_id = current_user.id if current_user and current_user.is_authenticated else None

        log_entry = ActivityLog(
            user_id=user_id,
            action=action,
            category=category,
            details=details,
            resource_id=resource_id,
            timestamp=datetime.utcnow()
        )
        db.session.add(log_entry)
        # Nota: No hacemos db.session.commit() aquí.
        # La ruta que llama a esta función es responsable de hacer el commit.
        
    except Exception as e:
        # En caso de error, para no detener la aplicación principal,
        # simplemente lo imprimimos. En un entorno de producción,
        # podrías usar un logger más avanzado.
        print(f"Error al registrar actividad: {e}")

