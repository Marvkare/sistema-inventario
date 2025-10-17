# routes/admin.py
from flask import Blueprint, redirect, url_for, flash, request, render_template
from flask_login import login_required,  current_user
from flask_admin.contrib.sqla import ModelView
from extensions import db
from models import User, Role
from wtforms import StringField, validators, PasswordField
from flask_admin.contrib.sqla.fields import QuerySelectField
from decorators import admin_required, permission_required
from datetime import datetime, timedelta
from flask import render_template, request
from flask_login import login_required
from models import ActivityLog, User # Asegúrate de importar tus modelos

from sqlalchemy import or_


# Define the blueprint for your custom admin routes.
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Define the Flask-Admin model views for managing User and Role
class AdminUserView(ModelView):
    # This excludes the password_hash from being displayed
    column_exclude_list = ['password_hash']
    # Define the columns that appear in the form for creating/editing users
    form_columns = ('username', 'roles', 'password')
    
    # Define extra form fields not directly from the model
    form_extra_fields = {
        'password': PasswordField('Contraseña', validators=[validators.Optional()]),
        'roles': QuerySelectField(
            'Roles',
            query_factory=lambda: Role.query.all(),
            get_pk=lambda a: a.id,
            get_label=lambda a: a.name,
        )
    }

    # This function is called before a user object is saved to the database
    def on_model_change(self, form, model, is_created):
        # Hash the password if a new one is provided
        if form.password.data:
            model.set_password(form.password.data)

    # Restrict access to this view to authenticated admin users
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin()

    def inaccessible_callback(self, name, **kwargs):
        flash('No tienes permiso para acceder a esta página.', 'danger')
        return redirect(url_for('login', next=request.url))

class AdminRoleView(ModelView):
    # This view is for managing roles
    column_list = ('name', 'description')
    form_columns = ('name', 'description')

    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin()

    def inaccessible_callback(self, name, **kwargs):
        flash('No tienes permiso para acceder a esta página.', 'danger')
        return redirect(url_for('login', next=request.url))

@admin_bp.route('/')
@login_required
def admin_dashboard():
    # You can pass data to the template here, e.g., statistics
    return render_template('admin/dashboard.html')

@admin_bp.route('/settings')
@login_required
def admin_settings():
    return render_template('admin/settings.html')



# ... (dentro de tu Blueprint de administración) ...

@admin_bp.route('/activity-log')
@login_required
@permission_required('admin.view_activity_log') # Un permiso recomendado
def view_activity_log():
    """
    Muestra los logs de actividad con filtros y paginación.
    """
    # Obtener el número de página de los argumentos de la URL, por defecto es 1
    page = request.args.get('page', 1, type=int)
    
    # Construir la consulta base, uniendo con User para poder filtrar por nombre
    query = ActivityLog.query.join(User, User.id == ActivityLog.user_id, isouter=True)

    # --- Aplicar filtros desde los argumentos de la URL ---
    user_id = request.args.get('user_id')
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search_term = request.args.get('search_term')

    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if category:
        query = query.filter(ActivityLog.category == category)
    if start_date:
        query = query.filter(ActivityLog.timestamp >= start_date)
    if end_date:
        # Añadimos un día a la fecha final para incluir todos los logs de ese día
        end_date_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(ActivityLog.timestamp < end_date_dt)
    if search_term:
        # Búsqueda flexible en acción, detalles o ID del recurso
        search_like = f"%{search_term}%"
        query = query.filter(or_(
            ActivityLog.action.ilike(search_like),
            ActivityLog.details.ilike(search_like),
            ActivityLog.resource_id.ilike(search_like)
        ))

    # --- Obtener datos para los menús desplegables de los filtros ---
    # Obtener todos los usuarios para el <select>
    users = User.query.order_by(User.username).all()
    # Obtener todas las categorías distintas para el <select>
    categories = db.session.query(ActivityLog.category).distinct().order_by(ActivityLog.category).all()

    # Ordenar por fecha descendente y paginar los resultados
    logs = query.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        'admin/activity_log.html', 
        logs=logs,
        users=users,
        categories=[c[0] for c in categories if c[0]], # Limpiar la lista de categorías
        filters=request.args # Pasar los filtros actuales para mantenerlos en el formulario
    )