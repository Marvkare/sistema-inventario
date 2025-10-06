from extensions import db
from models import ActivityLog
from flask_login import current_user
from datetime import datetime

def log_activity(action, category=None, details=None, resource_id=None):
    """
    Versión mejorada con manejo de errores y límites de longitud
    """
    try:
        # Asegurar que la sesión esté limpia
        db.session.rollback()
        
        # Limitar longitudes para evitar truncamiento
        if resource_id and len(str(resource_id)) > 50:
            resource_id = str(resource_id)[:50]
        
        if details and len(str(details)) > 500:
            details = str(details)[:500]
        
        if category and len(str(category)) > 100:
            category = str(category)[:100]
        
        if action and len(str(action)) > 100:
            action = str(action)[:100]

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
        db.session.commit()
        
    except Exception as e:
        print(f"Error al registrar actividad: {e}")
        db.session.rollback()  # Siempre hacer rollback en caso de error