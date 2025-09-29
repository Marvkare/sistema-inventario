from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import text

# --- TABLAS DE UNIÓN (Many-to-Many Relationships) ---
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True)
)

role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True)
)


# --- MODELOS PRINCIPALES ---

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    activity_logs = db.relationship('ActivityLog', back_populates='user', lazy=True)

    reset_token = db.Column(db.String(255), unique=True, nullable=True)
    reset_token_expiration = db.Column(db.DateTime, nullable=True)
    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return any(role.name == 'admin' for role in self.roles)

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    
    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles')

class Permission(db.Model):
    __tablename__ = 'permission'
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.String(255))

class Area(db.Model):
    __tablename__ = 'areas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False, unique=True)
    numero = db.Column(db.Integer, nullable=True)
    
    resguardos = db.relationship('Resguardo', back_populates='area', lazy=True)

class Bienes(db.Model):
    __tablename__ = 'bienes'
    id = db.Column(db.Integer, primary_key=True)
    No_Inventario = db.Column(db.String(50), unique=True)
    No_Factura = db.Column(db.String(50))
    No_Cuenta = db.Column(db.String(50))
    Proveedor = db.Column(db.String(255))
    Descripcion_Del_Bien = db.Column(db.Text)
    Descripcion_Corta_Del_Bien = db.Column(db.String(512))
    Rubro = db.Column(db.String(100))
    Poliza = db.Column(db.String(50))
    Fecha_Poliza = db.Column(db.Date)
    Sub_Cuenta_Armonizadora = db.Column(db.String(100))
    Fecha_Factura = db.Column(db.Date)
    Costo_Inicial = db.Column(db.Numeric(10, 2))
    Depreciacion_Acumulada = db.Column(db.Numeric(10, 2))
    Costo_Final_Cantidad = db.Column(db.Numeric(10, 2))
    Cantidad = db.Column(db.Integer)
    Estado_Del_Bien = db.Column(db.String(50))
    Marca = db.Column(db.String(100))
    Modelo = db.Column(db.String(100))
    Numero_De_Serie = db.Column(db.String(100))
    Tipo_De_Alta = db.Column(db.String(50))
    
    resguardos = db.relationship('Resguardo', backref='bien', lazy=True, cascade="all, delete-orphan")
    imagenes = db.relationship('ImagenesBien', backref='bien', lazy=True, cascade="all, delete-orphan")

class Resguardo(db.Model):
    __tablename__ = 'resguardos'
    id = db.Column(db.Integer, primary_key=True)
    id_bien = db.Column(db.Integer, db.ForeignKey('bienes.id', ondelete='RESTRICT'), nullable=False)
    id_area = db.Column(db.Integer, db.ForeignKey('areas.id', ondelete='RESTRICT'), nullable=False)
    Ubicacion = db.Column(db.String(100))
    No_Resguardo = db.Column(db.String(50))
    Tipo_De_Resguardo = db.Column(db.Integer)
    Fecha_Resguardo = db.Column(db.Date)
    No_Trabajador = db.Column(db.String(50))
    Puesto_Trabajador = db.Column(db.String(100))
    No_Nomina_Trabajador = db.Column(db.Integer)
    Nombre_Del_Resguardante = db.Column(db.String(255))
    Nombre_Director_Jefe_De_Area = db.Column(db.String(255))
    Activo = db.Column(db.Boolean, default=True, nullable=False)
    Fecha_Registro = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    Fecha_Ultima_Modificacion = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    area = db.relationship('Area', back_populates='resguardos')
    imagenes = db.relationship('ImagenesResguardo', backref='resguardo', lazy=True, cascade="all, delete-orphan")
    traspasos = db.relationship('Traspaso', back_populates='resguardo', lazy=True)
    
    # --- CORRECCIÓN CLAVE: Se añaden las relaciones inversas que faltaban ---
    oficios_traspaso_anteriores = db.relationship('OficiosTraspaso', foreign_keys='OficiosTraspaso.id_resguardo_anterior', back_populates='resguardo_anterior')
    oficios_traspaso_actuales = db.relationship('OficiosTraspaso', foreign_keys='OficiosTraspaso.id_resguardo_actual', back_populates='resguardo_actual')

class ImagenesBien(db.Model):
    __tablename__ = 'imagenes_bien'
    id = db.Column(db.Integer, primary_key=True)
    id_bien = db.Column(db.Integer, db.ForeignKey('bienes.id', ondelete='CASCADE'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)

class ImagenesResguardo(db.Model):
    __tablename__ = 'imagenes_resguardo'
    id = db.Column(db.Integer, primary_key=True)
    id_resguardo = db.Column(db.Integer, db.ForeignKey('resguardos.id', ondelete='CASCADE'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)

class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    details = db.Column(db.Text)
    resource_id = db.Column(db.Integer)
    user = db.relationship('User', back_populates='activity_logs')

class Traspaso(db.Model):
    __tablename__ = 'traspaso'
    id = db.Column(db.Integer, primary_key=True)
    id_resguardo = db.Column(db.Integer, db.ForeignKey('resguardos.id'), nullable=False)
    fecha_traspaso = db.Column(db.DateTime, default=datetime.utcnow)
    area_origen_id = db.Column(db.Integer, db.ForeignKey('areas.id'))
    area_destino_id = db.Column(db.Integer, db.ForeignKey('areas.id'))
    usuario_origen_nombre = db.Column(db.String(255))
    usuario_destino_nombre = db.Column(db.String(255))
    motivo = db.Column(db.Text)
    
    area_origen = db.relationship('Area', foreign_keys=[area_origen_id])
    area_destino = db.relationship('Area', foreign_keys=[area_destino_id])
    resguardo = db.relationship('Resguardo', back_populates='traspasos')

class OficiosTraspaso(db.Model):
    __tablename__ = 'oficios_traspaso'
    id = db.Column(db.Integer, primary_key=True)
    id_resguardo_anterior = db.Column(db.Integer, db.ForeignKey('resguardos.id', ondelete='RESTRICT'), nullable=False)
    id_resguardo_actual = db.Column(db.Integer, db.ForeignKey('resguardos.id', ondelete='RESTRICT'), nullable=False)
    Dependencia = db.Column(db.String(255))
    Oficio_clave = db.Column(db.String(255))
    Asunto = db.Column(db.Text)
    Lugar_Fecha = db.Column(db.Date)
    Secretaria_General_Municipal = db.Column(db.String(255))
    Fecha_Registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    imagenes = db.relationship('ImagenesOficiosTraspaso', backref='oficio', lazy=True, cascade="all, delete-orphan")
    
    # --- CORRECCIÓN CLAVE: Se definen las relaciones de vuelta hacia Resguardo ---
    resguardo_anterior = db.relationship('Resguardo', foreign_keys=[id_resguardo_anterior], back_populates='oficios_traspaso_anteriores')
    resguardo_actual = db.relationship('Resguardo', foreign_keys=[id_resguardo_actual], back_populates='oficios_traspaso_actuales')


    __tablename__ = 'oficios_traspaso'
    id = db.Column(db.Integer, primary_key=True)
    id_resguardo_anterior = db.Column(db.Integer, db.ForeignKey('resguardos.id', ondelete='RESTRICT'), nullable=False)
    id_resguardo_actual = db.Column(db.Integer, db.ForeignKey('resguardos.id', ondelete='RESTRICT'), nullable=False)
    Dependencia = db.Column(db.String(255))
    Oficio_clave = db.Column(db.String(255))
    Asunto = db.Column(db.Text)
    Lugar_Fecha = db.Column(db.Date)
    Secretaria_General_Municipal = db.Column(db.String(255))
    Fecha_Registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    imagenes = db.relationship('ImagenesOficiosTraspaso', backref='oficio', lazy=True, cascade="all, delete-orphan")
    
    # CORRECCIÓN: La relación 'resguardo' redundante ha sido eliminada.
    # Las relaciones correctas ya están aquí:
    resguardo_anterior = db.relationship('Resguardo', foreign_keys=[id_resguardo_anterior], back_populates='oficios_traspaso_anteriores')
    resguardo_actual = db.relationship('Resguardo', foreign_keys=[id_resguardo_actual], back_populates='oficios_traspaso_actuales')

class ImagenesOficiosTraspaso(db.Model):
    __tablename__ = 'imagenes_oficios_traspaso'
    id = db.Column(db.Integer, primary_key=True)
    id_oficio = db.Column(db.Integer, db.ForeignKey('oficios_traspaso.id', ondelete='CASCADE'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)

class QueryTemplates(db.Model):
    __tablename__ = 'query_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    columns = db.Column(db.JSON)
    filters = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    

class ResguardoErrores(db.Model):
    __tablename__ = 'resguardo_errores'
    
    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.String(255), nullable=False, index=True)
    No_Inventario = db.Column(db.Text, nullable=True)
    No_Factura = db.Column(db.Text, nullable=True)
    No_Cuenta = db.Column(db.Text, nullable=True)
    No_Resguardo = db.Column(db.Text, nullable=True)
    No_Trabajador = db.Column(db.Text, nullable=True)
    Proveedor = db.Column(db.Text, nullable=True)
    Fecha_Resguardo = db.Column(db.Text, nullable=True)
    Descripcion_Del_Bien = db.Column(db.Text, nullable=True)
    Descripcion_Fisica = db.Column(db.Text, nullable=True)
    Area = db.Column(db.Text, nullable=True)
    Rubro = db.Column(db.Text, nullable=True)
    Poliza = db.Column(db.Text, nullable=True)
    Fecha_Poliza = db.Column(db.Text, nullable=True)
    Sub_Cuenta_Armonizadora = db.Column(db.Text, nullable=True)
    Fecha_Factura = db.Column(db.Text, nullable=True)
    Costo_Inicial = db.Column(db.Text, nullable=True)
    Depreciacion_Acumulada = db.Column(db.Text, nullable=True)
    Costo_Final_Cantidad = db.Column(db.Text, nullable=True)
    Cantidad = db.Column(db.Text, nullable=True)
    Puesto = db.Column(db.Text, nullable=True)
    Nombre_Director_Jefe_De_Area = db.Column(db.Text, nullable=True)
    Tipo_De_Resguardo = db.Column(db.Text, nullable=True)
    Adscripcion_Direccion_Area = db.Column(db.Text, nullable=True)
    Nombre_Del_Resguardante = db.Column(db.Text, nullable=True)
    Estado_Del_Bien = db.Column(db.Text, nullable=True)
    Marca = db.Column(db.Text, nullable=True)
    Modelo = db.Column(db.Text, nullable=True)
    Numero_De_Serie = db.Column(db.Text, nullable=True)
    Imagen_Path = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    Fecha_Registro = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    Fecha_Ultima_Modificacion = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
