# extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Aquí es donde se define la variable 'db' que tu app está buscando
db = SQLAlchemy()

# También definimos 'migrate' aquí
migrate = Migrate()