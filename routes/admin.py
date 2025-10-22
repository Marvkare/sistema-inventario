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


@admin_bp.route('/activity-log')
@login_required
@permission_required('admin.view_activity_log')
def view_activity_log():
    try:
        # --- ESTA ES LA CORRECIÓN DEL ERROR ---
        # 1. Copia todos los argumentos de la URL
        filters = request.args.copy()
        
        # 2. Usa .pop() para OBTENER y QUITAR 'page' del dict de filtros.
        #    'filters' ya no tendrá la clave 'page'.
        try:
            page = int(filters.pop('page', 1))
        except ValueError:
            page = 1
        # --- FIN DE LA CORRECIÓN ---

        # Valores de los filtros
        user_id = filters.get('user_id')
        category = filters.get('category')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        search_term = filters.get('search_term')

        # Consulta base
        query = ActivityLog.query.order_by(ActivityLog.timestamp.desc())

        # Aplicar filtros
        if user_id:
            query = query.filter(ActivityLog.user_id == user_id)
        if category:
            query = query.filter(ActivityLog.category == category)
        if start_date:
            query = query.filter(ActivityLog.timestamp >= start_date)
        if end_date:
            # Añadimos +1 día al end_date para incluir todo el día
            from datetime import datetime, timedelta
            end_date_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(ActivityLog.timestamp < end_date_dt)
        if search_term:
            like_term = f"%{search_term}%"
            query = query.filter(
                or_(
                    ActivityLog.action.like(like_term),
                    ActivityLog.details.like(like_term),
                    ActivityLog.resource_id.like(like_term)
                )
            )

        # Cargar datos para los <select> del formulario
        users = User.query.order_by(User.username).all()
        # Obtener categorías únicas
        categories_db = db.session.query(ActivityLog.category).distinct().order_by(ActivityLog.category).all()
        categories = [c[0] for c in categories_db if c[0]] # Lista de strings

        # Paginar la consulta
        logs_pagination = query.paginate(page=page, per_page=50, error_out=False)

        # Ahora 'filters' se puede pasar de forma segura a url_for
        return render_template(
            'admin/activity_log.html', 
            logs=logs_pagination, 
            users=users, 
            categories=categories, 
            filters=filters # Este dict ya no tiene 'page'
        )

    except Exception as e:
        traceback.print_exc()
        flash(f"Error al cargar la bitácora: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard')) # O a donde prefieras

