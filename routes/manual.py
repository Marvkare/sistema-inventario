from flask import Blueprint, render_template, abort
from flask_login import login_required
from jinja2.exceptions import TemplateNotFound

# 1. Definimos el nuevo Blueprint para el manual
manual_bp = Blueprint('manual', __name__)

@manual_bp.route('/manual')
@login_required
def index():
    """
    Muestra la página principal del manual (el índice de todos los módulos).
    """
    try:
        # Esta será la portada de tu manual.
        # Desde aquí enlazarás a /manual/bienes, /manual/usuarios, etc.
        return render_template('manual/index.html')
    except TemplateNotFound:
        abort(404)

@manual_bp.route('/manual/bienes/')
@manual_bp.route('/manual/bienes/<path:pagina>')
@login_required
def manual_bienes_pagina(pagina='index'):
    """
    Muestra una página de ayuda específica del módulo de bienes.
    
    - Si se accede a /manual/bienes/, 'pagina' será 'index'.
    - Si se accede a /manual/bienes/agregar, 'pagina' será 'agregar'.
    - Si se accede a /manual/bienes/resguardos/crear, 'pagina' será 'resguardos/crear'.
    
    El <path:pagina> es clave porque nos permite tener subdirectorios.
    """
    try:
        # Construimos la ruta de la plantilla de forma dinámica y segura.
        # Ej: 'manual/bienes/agregar.html'
        # Ej: 'manual/bienes/resguardos/crear.html'
        template_name = f"manual/bienes/{pagina}.html"
        
        # render_template() ya está "enjaulado" en tu carpeta 'templates'.
        # Si alguien intenta un ataque (ej. <path:pagina> = '../../app.py'),
        # jinja2 buscará 'templates/manual/bienes/../../app.py' y 
        # fallará con TemplateNotFound, que es lo que capturamos abajo.
        return render_template(template_name)
    
    except TemplateNotFound:
        # Si la plantilla no existe (ej. /manual/bienes/pagina_inventada),
        # mostramos un error 404 "Not Found".
        abort(404)

# --- NOTA ---
# No necesitas NINGUNA conexión a la base de datos, lógica de formularios
# ni decoradores de permisos aquí. Este blueprint solo MUESTRA información.
# El @login_required es suficiente para asegurar que solo usuarios
# autenticados puedan ver el manual.