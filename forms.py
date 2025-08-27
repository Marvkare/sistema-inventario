# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo
from flask_wtf.db import QuerySelectMultipleField

# Función para obtener todos los roles, usada por el formulario
def get_all_roles():
    from models import Role
    return Role.query.all()

class UserForm(FlaskForm):
    # Campo para el nombre de usuario
    username = StringField('Nombre de Usuario', validators=[DataRequired()])
    # Campo para la contraseña, opcional en la edición
    password = PasswordField('Contraseña', validators=[])
    # Campo para confirmar la contraseña
    confirm_password = PasswordField('Confirmar Contraseña', validators=[EqualTo('password', message='Las contraseñas no coinciden.')])
    
    # Campo para seleccionar roles (múltiple)
    roles = QuerySelectMultipleField(
        'Roles',
        query_factory=get_all_roles,
        get_label='name',
        allow_blank=True,
        blank_text='Ninguno'
    )
    submit = SubmitField('Crear Usuario')

class EditUserForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña')
    confirm_password = PasswordField('Confirmar Contraseña', validators=[EqualTo('password', message='Las contraseñas no coinciden.')])
    
    roles = QuerySelectMultipleField(
        'Roles',
        query_factory=get_all_roles,
        get_label='name',
    )
    submit = SubmitField('Guardar Cambios')