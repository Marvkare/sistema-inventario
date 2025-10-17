from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import text, Enum



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
    Costo_Final = db.Column(db.Numeric(10, 2))
    Cantidad = db.Column(db.Integer)
    Estado_Del_Bien = db.Column(db.String(50))
    Marca = db.Column(db.String(100))
    Modelo = db.Column(db.String(100))
    Numero_De_Serie = db.Column(db.String(100))
    Tipo_De_Alta = db.Column(db.String(50))
    Clasificacion_Legal = db.Column(db.String(50), nullable=False)
    
    # --- Columnas corregidas ---
    Area_Presupuestal = db.Column(db.String(255))
    Documento_Propiedad = db.Column(db.String(255))
    Fecha_Documento_Propiedad = db.Column(db.Date)
    Valor_En_Libros = db.Column(db.Numeric(10, 2))
    Fecha_Adquisicion_Alta = db.Column(db.Date)

    # --- Timestamps y estado ---
    Fecha_Registro = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    Fecha_Ultima_Modificacion = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    Activo = db.Column(db.Boolean, default=True, nullable=False)
    proceso_baja_activo = db.relationship('ProcesoBaja', back_populates='bien', uselist=False, cascade="all, delete-orphan")
    estatus_actual = db.Column(
        Enum('Activo', 'En Mantenimiento', 'En Proceso de Baja', 'Baja', 'Faltante', name='estatus_general_bien_enum'), 
        nullable=False, 
        default='Activo',
        index=True
    )
    # --- Relaciones ---
    resguardos = db.relationship('Resguardo', backref='bien', lazy=True, cascade="all, delete-orphan")
    imagenes = db.relationship('ImagenesBien', backref='bien', lazy=True, cascade="all, delete-orphan")
    usuario_id_registro = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


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
    RFC_Trabajador = db.Column(db.String(15))
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
    usuario_id_registro = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
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

# En tu models.py - MODIFICA esta línea
class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    details = db.Column(db.Text)
    resource_id = db.Column(db.String(50))  # ← CAMBIAR de Integer a String(50)
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
    
    # Campos del Bien (Bienes model)
    No_Inventario = db.Column(db.Text, nullable=True)
    No_Factura = db.Column(db.Text, nullable=True)
    No_Cuenta = db.Column(db.Text, nullable=True)
    Proveedor = db.Column(db.Text, nullable=True)
    Descripcion_Del_Bien = db.Column(db.Text, nullable=True)
    Descripcion_Corta_Del_Bien = db.Column(db.Text, nullable=True)
    Rubro = db.Column(db.Text, nullable=True)
    Poliza = db.Column(db.Text, nullable=True)
    Fecha_Poliza = db.Column(db.Text, nullable=True)
    Sub_Cuenta_Armonizadora = db.Column(db.Text, nullable=True)
    Fecha_Factura = db.Column(db.Text, nullable=True)
    Costo_Inicial = db.Column(db.Text, nullable=True)
    Depreciacion_Acumulada = db.Column(db.Text, nullable=True)
    Costo_Final = db.Column(db.Text, nullable=True)
    Cantidad = db.Column(db.Text, nullable=True)
    Estado_Del_Bien = db.Column(db.Text, nullable=True)
    Marca = db.Column(db.Text, nullable=True)
    Modelo = db.Column(db.Text, nullable=True)
    Numero_De_Serie = db.Column(db.Text, nullable=True)
    Tipo_De_Alta = db.Column(db.Text, nullable=True)
    Clasificacion_Legal = db.Column(db.Text, nullable=True)
    Area_Presupuestal = db.Column(db.Text, nullable=True)
    Documento_Propiedad = db.Column(db.Text, nullable=True)
    Fecha_Documento_Propiedad = db.Column(db.Text, nullable=True)
    Valor_En_Libros = db.Column(db.Text, nullable=True)
    Fecha_Adquisicion_Alta = db.Column(db.Text, nullable=True)
    
    # Campos del Resguardo (Resguardo model)
    No_Resguardo = db.Column(db.Text, nullable=True)
    Area = db.Column(db.Text, nullable=True)  # Nombre del área (para relación con areas.id)
    Ubicacion = db.Column(db.Text, nullable=True)
    Tipo_De_Resguardo = db.Column(db.Text, nullable=True)
    Fecha_Resguardo = db.Column(db.Text, nullable=True)
    No_Trabajador = db.Column(db.Text, nullable=True)
    Puesto_Trabajador = db.Column(db.Text, nullable=True)
    RFC_Trabajador = db.Column(db.Text, nullable=True)
    No_Nomina_Trabajador = db.Column(db.Text, nullable=True)
    Nombre_Del_Resguardante = db.Column(db.Text, nullable=True)
    Nombre_Director_Jefe_De_Area = db.Column(db.Text, nullable=True)
    
    # Campos adicionales del modelo anterior (mantenidos para compatibilidad)
    Descripcion_Fisica = db.Column(db.Text, nullable=True)
    Puesto = db.Column(db.Text, nullable=True)  # Alias de Puesto_Trabajador
    Adscripcion_Direccion_Area = db.Column(db.Text, nullable=True)
    Imagen_Path = db.Column(db.String(255), nullable=True)
    
    # Información del error
    error_message = db.Column(db.Text, nullable=True)
    Fecha_Registro = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    Fecha_Ultima_Modificacion = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))


# --- MODELOS PARA EL PROCESO DE BAJA DE BIENES ---

class ProcesoBaja(db.Model):
    """
    Tabla central que representa un flujo de trabajo completo para dar de baja un bien.
    Cada solicitud de baja creará un registro en esta tabla.
    """
    __tablename__ = 'procesos_baja'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relación con el bien que se está dando de baja (un bien solo puede tener un proceso activo).
    id_bien = db.Column(db.Integer, db.ForeignKey('bienes.id'), nullable=False, unique=True)
    
    # Motivo de la solicitud de baja.
    motivo = db.Column(Enum('Obsolescencia', 'Inutilidad', 'Robo', 'Extravío', 'Siniestro', 'Enajenación', name='motivo_baja_enum'), nullable=False)
    
    # Estatus actual del proceso, clave para el flujo de trabajo.
    estatus = db.Column(Enum('Solicitado', 'En Dictamen Técnico', 'Pendiente de Comité', 'Autorizado para Disposición', 'Rechazado', 'Finalizado', name='estatus_baja_enum'), nullable=False, default='Solicitado')
    
    # Detalles y justificación inicial.
    justificacion_solicitud = db.Column(db.Text, nullable=False)
    id_usuario_captura = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    nombre_solicitante = db.Column(db.String(255), nullable=False)
    nombre_jefe_area = db.Column(db.String(255), nullable=True)
   
    # Fechas clave del proceso.
    fecha_inicio = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    fecha_finalizacion = db.Column(db.DateTime, nullable=True) # Se llena al finalizar o rechazar.
    
    # Relaciones (back-references)
    bien = db.relationship('Bienes', back_populates='proceso_baja_activo')
    usuario_captura = db.relationship('User')
    documentos = db.relationship('DocumentoBaja', back_populates='proceso_baja', cascade="all, delete-orphan")
    disposicion_final = db.relationship('DisposicionFinal', back_populates='proceso_baja', uselist=False, cascade="all, delete-orphan")

class DocumentoBaja(db.Model):
    """
    Almacena todos los documentos probatorios asociados a un proceso de baja,
    creando un expediente digital auditable.
    """
    __tablename__ = 'documentos_baja'
    
    id = db.Column(db.Integer, primary_key=True)
    id_proceso_baja = db.Column(db.Integer, db.ForeignKey('procesos_baja.id'), nullable=False)
    
   

    # Tipo de documento para saber qué representa.
    tipo_documento = db.Column(Enum(
    'Solicitud de Baja',
    'Dictamen Técnico',
    'Denuncia de Robo',
    'Acta de Siniestro',
    'Avalúo Comercial',
    'Acta de Comité',
    'Acta de Baja',
    'Acta de Investigación', 
    'Fotografías del bien',
    'Acta de echos',
    'Otro',
      # Nuevo tipo de documento para el acta interna de hechos
    name='tipo_doc_baja_enum'
), nullable=False)
    
   
    # Metadatos opcionales para datos específicos (ej. valor del avalúo).
    metadatos = db.Column(db.Text) # Se puede usar JSON/JSONB si la BD lo soporta.
    
    # Usuario que subió el documento.
    id_usuario_carga = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fecha_carga = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    # Relaciones (back-references)
    proceso_baja = db.relationship('ProcesoBaja', back_populates='documentos')
    usuario_carga = db.relationship('User')
    # Un 'DocumentoBaja' (expediente) puede tener múltiples archivos adjuntos (fotos, pdfs).
    archivos_adjuntos = db.relationship('ArchivoAdjunto', back_populates='documento_baja', cascade="all, delete-orphan")

class ArchivoAdjunto(db.Model):
    """
    Almacena la URL y detalles de cada archivo físico (imagen o PDF)
    que conforma un DocumentoBaja.
    """
    __tablename__ = 'archivos_adjuntos_baja'
    
    id = db.Column(db.Integer, primary_key=True)
    id_documento_baja = db.Column(db.Integer, db.ForeignKey('documentos_baja.id'), nullable=False)
    
    nombre_archivo = db.Column(db.String(255), nullable=False)
    ruta_archivo = db.Column(db.String(512), nullable=False)
    tipo_mime = db.Column(db.String(100))
    orden = db.Column(db.Integer, default=1)
    
    fecha_subida = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    # --- Relación ---
    documento_baja = db.relationship('DocumentoBaja', back_populates='archivos_adjuntos')


class DisposicionFinal(db.Model):
    """
    Registra los detalles de CÓMO se concluyó la baja del bien.
    Se crea solo cuando el proceso es autorizado y ejecutado.
    """
    __tablename__ = 'disposiciones_finales'
    
    id = db.Column(db.Integer, primary_key=True)
    id_proceso_baja = db.Column(db.Integer, db.ForeignKey('procesos_baja.id'), nullable=False, unique=True)
    
    # Método de disposición final.
    tipo_disposicion = db.Column(Enum('Enajenación', 'Donación', 'Destrucción', name='tipo_disposicion_enum'), nullable=False)
    
    fecha_disposicion = db.Column(db.Date, nullable=False)
    
    # Campos específicos según el tipo de disposición.
    valor_enajenacion = db.Column(db.Numeric(10, 2), nullable=True) # Para 'Enajenación'.
    nombre_donatario = db.Column(db.String(255), nullable=True) # Para 'Donación'.
    detalles_destruccion = db.Column(db.Text, nullable=True) # Para 'Destrucción'.
    
    # Relación (back-reference)
    proceso_baja = db.relationship('ProcesoBaja', back_populates='disposicion_final')

# Tablas de asociación para relaciones Muchos-a-Muchos
inventario_areas = db.Table('inventario_areas',
    db.Column('inventario_id', db.Integer, db.ForeignKey('inventarios.id'), primary_key=True),
    db.Column('area_id', db.Integer, db.ForeignKey('areas.id'), primary_key=True)
)

inventario_brigadas = db.Table('inventario_brigadas',
    db.Column('inventario_id', db.Integer, db.ForeignKey('inventarios.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class Inventario(db.Model):
    """
    Tabla principal que representa una sesión o evento de inventario.
    Agrupa todo el proceso, desde la planificación hasta el cierre.
    """
    __tablename__ = 'inventarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False, comment="Nombre descriptivo del inventario, ej: 'Inventario Anual 2025'")
    
    # Tipo de inventario para diferenciar la formalidad y el alcance.
    tipo = db.Column(
        Enum('Físico-Contable', 'Preventivo', name='tipo_inventario_enum'),
        nullable=False,
        default='Físico-Contable',
        comment="Distingue entre un inventario formal completo y una revisión rápida o preventiva."
    )
    
    # Estatus general del proceso de inventariado.
    estatus = db.Column(
        Enum('Planificado', 'En Progreso', 'En Conciliación', 'Finalizado', 'Cancelado', name='estatus_inventario_enum'),
        nullable=False,
        default='Planificado'
    )
    
    fecha_inicio = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    fecha_cierre = db.Column(db.DateTime, nullable=True, comment="Se establece cuando el estatus cambia a 'Finalizado'.")
    
    id_usuario_creador = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relaciones (Muchos-a-Muchos)
    areas_a_inventariar = db.relationship('Area', secondary=inventario_areas, backref='inventarios')
    brigada_asignada = db.relationship('User', secondary=inventario_brigadas, backref='inventarios_asignados')
    
    # Relaciones (Uno-a-Muchos)
    detalles = db.relationship('InventarioDetalle', back_populates='inventario', cascade="all, delete-orphan")
    sobrantes = db.relationship('InventarioSobrante', back_populates='inventario', cascade="all, delete-orphan")

class InventarioDetalle(db.Model):
    """
    Corresponde a cada renglón de la "Cédula de Levantamiento".
    Registra el resultado de la verificación de un bien específico durante un inventario.
    """
    __tablename__ = 'inventario_detalle'
    id = db.Column(db.Integer, primary_key=True)
    id_inventario = db.Column(db.Integer, db.ForeignKey('inventarios.id'), nullable=False)
    id_bien = db.Column(db.Integer, db.ForeignKey('bienes.id'), nullable=False)
    
    # --- Datos "congelados" al momento de generar la cédula ---
    id_resguardo_esperado = db.Column(db.Integer, nullable=True, comment="FK a Resguardo al iniciar el inventario.")
    id_area_esperada = db.Column(db.Integer, nullable=True, comment="FK a Area donde se esperaba encontrar el bien.")
    nombre_resguardante_esperado = db.Column(db.String(255), comment="Nombre del resguardante esperado.")
    
    # --- Resultados de la verificación en campo ---
    estatus_hallazgo = db.Column(
        Enum('Pendiente', 'Localizado', 'No Localizado', 'Localizado con Discrepancia', name='estatus_hallazgo_enum'),
        nullable=False,
        default='Pendiente'
    )
    condicion_fisica_reportada = db.Column(db.String(50), comment="Estado del bien observado en campo (Bueno, Regular, Malo).")
    observaciones = db.Column(db.Text)
    
    id_usuario_verificador = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, comment="Miembro de la brigada que verificó el bien.")
    fecha_verificacion = db.Column(db.DateTime, nullable=True)
    
    # Relaciones
    inventario = db.relationship('Inventario', back_populates='detalles')
    bien = db.relationship('Bienes')
    usuario_verificador = db.relationship('User')
    
    # --- Relación con Fotos ---
    fotos = db.relationship('InventarioFoto', back_populates='detalle', cascade="all, delete-orphan")

class InventarioFoto(db.Model):
    """
    Almacena las rutas de las fotografías tomadas para un bien específico
    durante una sesión de inventario (InventarioDetalle).
    """
    __tablename__ = 'inventario_fotos'
    
    id = db.Column(db.Integer, primary_key=True)
    id_inventario_detalle = db.Column(db.Integer, db.ForeignKey('inventario_detalle.id'), nullable=False)
    
    # --- Datos de la imagen ---
    ruta_archivo = db.Column(db.String(512), nullable=False, comment="Ruta donde se guarda el archivo de la imagen.")
    descripcion = db.Column(db.Text, nullable=True, comment="Nota o descripción sobre lo que muestra la foto.")
    fecha_carga = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    # --- Relación de vuelta ---
    detalle = db.relationship('InventarioDetalle', back_populates='fotos')

class InventarioSobrante(db.Model):
    """
    Registra los bienes físicos encontrados en un área que no estaban en la
    Cédula de Levantamiento original para esa área.
    """
    __tablename__ = 'inventario_sobrantes'
    id = db.Column(db.Integer, primary_key=True)
    id_inventario = db.Column(db.Integer, db.ForeignKey('inventarios.id'), nullable=False)
    id_area_encontrado = db.Column(db.Integer, db.ForeignKey('areas.id'), nullable=False, comment="Área donde fue físicamente localizado.")
    
    # --- Datos capturados en campo ---
    descripcion_bien = db.Column(db.Text, nullable=False, comment="Descripción detallada de lo que se encontró.")
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    numero_serie = db.Column(db.String(100))
    condicion_fisica = db.Column(db.String(50))
    observaciones = db.Column(db.Text)
    
    # --- Estatus para la fase de regularización ---
    estatus_resolucion = db.Column(
        Enum('Pendiente de Identificación', 'Identificado y Reubicado', 'Requiere Alta', 'Alta Completada', name='estatus_resolucion_sobrante_enum'),
        nullable=False,
        default='Pendiente de Identificación'
    )
    
    # Si se identifica o se da de alta, se vincula al registro oficial del bien.
    id_bien_asociado = db.Column(db.Integer, db.ForeignKey('bienes.id'), nullable=True)
    id_usuario_captura = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    fecha_captura = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Relaciones
    inventario = db.relationship('Inventario', back_populates='sobrantes')
    area_encontrado = db.relationship('Area')
    bien_asociado = db.relationship('Bienes')
    usuario_captura = db.relationship('User')
    # --- Relación con Fotos ---
    fotos = db.relationship('InventarioSobranteFoto', back_populates='sobrante', cascade="all, delete-orphan")
 

class InventarioSobranteFoto(db.Model):
    """
    Almacena las evidencias fotográficas para un bien sobrante no registrado
    encontrado durante una sesión de inventario.
    """
    __tablename__ = 'inventario_sobrante_fotos'
    
    id = db.Column(db.Integer, primary_key=True)
    id_inventario_sobrante = db.Column(db.Integer, db.ForeignKey('inventario_sobrantes.id'), nullable=False)
    
    # --- Datos de la imagen ---
    ruta_archivo = db.Column(db.String(512), nullable=False, comment="Ruta donde se guarda el archivo de la imagen.")
    descripcion = db.Column(db.Text, nullable=True, comment="Nota sobre lo que muestra la foto.")
    fecha_carga = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))
    
    # --- Relación de vuelta ---
    sobrante = db.relationship('InventarioSobrante', back_populates='fotos')