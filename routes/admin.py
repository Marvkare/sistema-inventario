# routes/admin.py
from flask import Blueprint, redirect, url_for, flash, request, render_template
from flask_login import login_required,  current_user
from flask_admin.contrib.sqla import ModelView
from extensions import db
from models import User, Role
from wtforms import StringField, validators, PasswordField
from flask_admin.contrib.sqla.fields import QuerySelectField
from decorators import admin_required

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