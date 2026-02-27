from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Creamos el objeto db que será el puente entre Python y la base de datos
db = SQLAlchemy()


# ==========================================
# TABLA: PRODUCTOS
# Guarda el menú de la heladería
# ==========================================
class Producto(db.Model):
    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)    # Ej: "Copa Oreo" - obligatorio
    precio = db.Column(db.Float, nullable=False)          # Ej: 3.50 - obligatorio
    categoria = db.Column(db.String(50), nullable=False)  # Ej: "Copa", "Sundae", "Malteada"
    disponible = db.Column(db.Boolean, default=True)      # True = está en carta, False = agotado
    # ── NUEVO: imagen del producto desde Cloudinary
    imagen_url = db.Column(db.String(500), nullable=True) # URL de la imagen


# ==========================================
# TABLA: PEDIDOS
# ==========================================
class Pedido(db.Model):
    __tablename__ = 'pedidos'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    cliente_nombre = db.Column(db.String(100), nullable=False)
    cliente_telefono = db.Column(db.String(20), nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    estado = db.Column(db.String(20), default='pendiente')
    total = db.Column(db.Float, default=0.0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    forma_pago = db.Column(db.String(20), default='efectivo')

    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)


# ==========================================
# TABLA: DETALLES DEL PEDIDO
# ==========================================
class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    producto = db.relationship('Producto')


# ==========================================
# TABLA: VENTAS
# ==========================================
class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    forma_pago = db.Column(db.String(20), default='efectivo')

    pedido = db.relationship('Pedido')


# ==========================================
# TABLA: CAJA
# ==========================================
class Caja(db.Model):
    __tablename__ = 'caja'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    monto_inicial = db.Column(db.Float, nullable=False)
    total_ingresos = db.Column(db.Float, default=0.0)
    total_egresos = db.Column(db.Float, default=0.0)
    monto_final = db.Column(db.Float, nullable=True)
    estado = db.Column(db.String(20), default='abierta')
    total_efectivo = db.Column(db.Float, default=0.0)
    total_transferencia = db.Column(db.Float, default=0.0)


# ==========================================
# TABLA: EGRESOS
# ==========================================
class Egreso(db.Model):
    __tablename__ = 'egresos'

    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
