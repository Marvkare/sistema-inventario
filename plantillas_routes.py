# Importaciones necesarias para la ruta
from flask import Flask, render_template, request, redirect, url_for, flash
import json

# Asume que 'app' ya está definida y configurada en tu aplicación Flask
# app = Flask(__name__)

# Simulación de la base de datos o lista de columnas disponibles
# En una aplicación real, obtendrías esto de tu modelo de datos o del ORM.
# Assumed database columns
AVAILABLE_COLUMNS = [
    'nombre_bien',
    'numero_resguardo',
    'departamento',
    'ubicacion',
    'responsable_nombre',
    'responsable_numero_empleado'
]

