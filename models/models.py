from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Creamos la instancia 'db' de SQLAlchemy, un ORM (Object-Relational Mapping).
# Esto nos permite interactuar con la base de datos usando objetos Python en lugar de puro código SQL.
db = SQLAlchemy()


producto_sabores = db.Table(
    'producto_sabores',
    db.Column('producto_id', db.Integer, db.ForeignKey('productos.id'), primary_key=True),
    db.Column('sabor_id', db.Integer, db.ForeignKey('sabores.id'), primary_key=True)
)
# Relacion N:N: un producto puede tener multiples sabores y cada sabor pertenecer a multiples productos.


# ==========================================
# TABLA: PRODUCTOS
# Guarda el menú de la heladería
# ==========================================
class Producto(db.Model):
    # Definimos explícitamente el nombre de la tabla en SQL
    __tablename__ = 'productos'

    # db.Column crea las columnas, asignándole el tipo de dato (Integer, String, etc)
    # primary_key=True define que este campo es el identificador único (Clave Primaria)
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)    # Ej: "Copa Oreo" - nullable=False hace que sea un campo obligatorio
    precio = db.Column(db.Float, nullable=False)          # Ej: 3.50
    categoria = db.Column(db.String(50), nullable=False)  # Ej: "Copa", "Sundae", "Malteada"
    disponible = db.Column(db.Boolean, default=True)      # True = está en carta, False = agotado
    max_sabores = db.Column(db.Integer, default=1)
    
    # URL para las imágenes de los productos desde un servicio externo como Cloudinary
    imagen_url = db.Column(db.String(500), nullable=True) 

    sabores = db.relationship(
        'Sabor',
        secondary=producto_sabores,
        lazy='subquery',
        backref=db.backref('productos', lazy=True)
    )


class Sabor(db.Model):
    __tablename__ = 'sabores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True)


# ==========================================
# TABLA: PEDIDOS
# ==========================================
class Pedido(db.Model):
    __tablename__ = 'pedidos'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False) # ej. "domicilio", "mesa"
    cliente_nombre = db.Column(db.String(100), nullable=False)
    cliente_telefono = db.Column(db.String(20), nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    plataforma = db.Column(db.String(80), nullable=True)
    estado = db.Column(db.String(20), default='pendiente')
    numero_pedido = db.Column(db.Integer, nullable=True)
    total = db.Column(db.Float, default=0.0)
    fecha = db.Column(db.DateTime, default=datetime.now) # Guarda la fecha y hora de creación según el reloj local del servidor
    forma_pago = db.Column(db.String(20), default='efectivo')
    
    # Nuevos campos para registro de pagos mixtos y transferencias
    numero_comprobante = db.Column(db.String(50), nullable=True)
    monto_efectivo = db.Column(db.Float, nullable=True)
    monto_transferencia = db.Column(db.Float, nullable=True)

    # Relación uno-a-muchos: Un pedido puede tener muchos Detalles de Pedido.
    # 'backref' crea virtualmente un atributo 'pedido' dentro del modelo DetallePedido para acceder de regreso.
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)

# ==========================================
# TABLA: DETALLES DEL PEDIDO
# ==========================================
class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'

    id = db.Column(db.Integer, primary_key=True)
    # Llave foránea (ForeignKey): liga este detalle con la tabla pedidos a través de su 'id'
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    # Llave foránea: liga este detalle con la tabla productos
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    
    cantidad = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    sabor = db.Column(db.String(120), nullable=True)

    # Relación que permite acceder al objeto 'Producto' completo asociado a este detalle.
    producto = db.relationship('Producto')


# ==========================================
# TABLA: VENTAS
# ==========================================
class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)
    forma_pago = db.Column(db.String(20), default='efectivo')

    # Guardar comprobante e importes del detalle del pago de la venta
    numero_comprobante = db.Column(db.String(50), nullable=True)
    monto_efectivo = db.Column(db.Float, nullable=True)
    monto_transferencia = db.Column(db.Float, nullable=True)

    pedido = db.relationship('Pedido')


# ==========================================
# TABLA: CAJA
# ==========================================
class Caja(db.Model):
    __tablename__ = 'caja'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    monto_inicial = db.Column(db.Float, nullable=False)
    total_ingresos = db.Column(db.Float, default=0.0)
    total_egresos = db.Column(db.Float, default=0.0)
    monto_final = db.Column(db.Float, nullable=True)
    estado = db.Column(db.String(20), default='abierta')
    total_efectivo = db.Column(db.Float, default=0.0)
    total_transferencia = db.Column(db.Float, default=0.0)
    monto_declarado = db.Column(db.Float, nullable=True)  # Efectivo real contado por el cajero
    descuadre = db.Column(db.Float, nullable=True)        # Faltante (-) o Soobrante (+)


# ==========================================
# TABLA: EGRESOS
# ==========================================
class Egreso(db.Model):
    __tablename__ = 'egresos'

    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)


class ConfiguracionSistema(db.Model):
    __tablename__ = 'configuracion_sistema'

    # Tabla llave-valor para parametros operativos sin migrar esquema completo.
    clave = db.Column(db.String(80), primary_key=True)
    valor_entero = db.Column(db.Integer, nullable=True)
