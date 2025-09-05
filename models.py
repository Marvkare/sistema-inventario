from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text

# Nueva tabla de asociación para roles y permisos
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)

# Tabla de asociación para la relación muchos a muchos entre User y Role
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)

class Permission(db.Model):
    __tablename__ = 'permission'
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.String(255))

class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    
    permissions = db.relationship('Permission', secondary=role_permissions,
                                   backref=db.backref('roles', lazy='dynamic'))

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    roles = db.relationship('Role', secondary=user_roles,
                            backref=db.backref('users', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return any(role.name == 'admin' for role in self.roles)
    
class Bienes(db.Model):
    __tablename__ = 'bienes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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

    # Relaciones que usan back_populates
    imagenes = db.relationship('ImagenesBien', back_populates='bien', cascade="all, delete-orphan")
    resguardos = db.relationship('Resguardo', back_populates='bien', lazy=True)

    def __repr__(self):
        return f'<Bien {self.No_Inventario} - {self.Descripcion_Corta_Del_Bien}>'

class Area(db.Model):
    __tablename__ = 'areas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True)
    numero = db.Column(db.Integer)

    resguardos = db.relationship('Resguardo', back_populates='area', lazy=True)

class Resguardo(db.Model):
    __tablename__ = 'resguardos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_bien = db.Column(db.Integer, db.ForeignKey('bienes.id'))
    id_area = db.Column(db.Integer, db.ForeignKey('areas.id'))
    Ubicacion = db.Column(db.String(100))
    No_Resguardo = db.Column(db.String(50), unique=True)
    Tipo_De_Resguardo = db.Column(db.Integer)
    Fecha_Resguardo = db.Column(db.Date)
    No_Trabajador = db.Column(db.String(50))
    Puesto_Trabajador = db.Column(db.String(100))
    Nombre_Del_Resguardante = db.Column(db.String(255))
    Nombre_Director_Jefe_De_Area = db.Column(db.String(255))
    Fecha_Registro = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    Fecha_Ultima_Modificacion = db.Column(db.DateTime, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    Activo = db.Column(db.Boolean, nullable=False, default=True)

    bien = db.relationship('Bienes', back_populates='resguardos')
    area = db.relationship('Area', back_populates='resguardos')

    def __repr__(self):
        return f'<Resguardo {self.No_Resguardo}>'

class ImagenesBien(db.Model):
    __tablename__ = 'imagenes_bien'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_bien = db.Column(db.Integer, db.ForeignKey('bienes.id', ondelete='CASCADE'), nullable=False)
    ruta_imagen = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    bien = db.relationship('Bienes', back_populates='imagenes')
    
    def __repr__(self):
        return f'<Imagen {self.ruta_imagen}>'