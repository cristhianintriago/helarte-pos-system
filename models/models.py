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


# ==========================================
# TABLA: PEDIDOS
# Guarda cada pedido que llega al negocio
# ==========================================
class Pedido(db.Model):
    __tablename__ = 'pedidos'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)              # 'local' o 'delivery'
    cliente_nombre = db.Column(db.String(100), nullable=False)   # Nombre del cliente
    cliente_telefono = db.Column(db.String(20), nullable=True)   # Solo se llena si es delivery
    cliente_direccion = db.Column(db.String(200), nullable=True) # Solo se llena si es delivery
    estado = db.Column(db.String(20), default='pendiente')       # pendiente → en_proceso → entregado
    total = db.Column(db.Float, default=0.0)                     # Total en dinero del pedido
    fecha = db.Column(db.DateTime, default=datetime.utcnow)      # Fecha y hora automática
    # ── NUEVO: forma de pago del cliente
    forma_pago = db.Column(db.String(20), default='efectivo')    # efectivo, transferencia, mixto

    # Relación: un pedido puede tener MUCHOS detalles (productos)
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)


# ==========================================
# TABLA: DETALLES DEL PEDIDO
# Guarda QUÉ productos tiene cada pedido y en qué cantidad
# ==========================================
class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'

    id = db.Column(db.Integer, primary_key=True)

    # ForeignKey = llave foránea, referencia a otra tabla
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)

    cantidad = db.Column(db.Integer, nullable=False)  # ¿Cuántas unidades?
    subtotal = db.Column(db.Float, nullable=False)    # cantidad × precio del producto

    # Relación para acceder al objeto Producto directamente
    producto = db.relationship('Producto')


# ==========================================
# TABLA: VENTAS
# Se genera automáticamente cuando un pedido es marcado como entregado
# ==========================================
class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)               # Total cobrado
    fecha = db.Column(db.DateTime, default=datetime.utcnow)  # Cuándo se realizó
    # ── NUEVO: forma de pago copiada del pedido
    forma_pago = db.Column(db.String(20), default='efectivo') # efectivo, transferencia, mixto

    pedido = db.relationship('Pedido')


# ==========================================
# TABLA: CAJA
# Representa la apertura y cierre de caja de cada día
# ==========================================
class Caja(db.Model):
    __tablename__ = 'caja'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    monto_inicial = db.Column(db.Float, nullable=False)    # Dinero con el que abre la caja
    total_ingresos = db.Column(db.Float, default=0.0)      # Suma de todas las ventas del día
    total_egresos = db.Column(db.Float, default=0.0)       # Suma de todos los gastos del día
    monto_final = db.Column(db.Float, nullable=True)       # inicial + ingresos - egresos
    estado = db.Column(db.String(20), default='abierta')   # 'abierta' o 'cerrada'
    # ── NUEVO: desglose por forma de pago
    total_efectivo = db.Column(db.Float, default=0.0)          # Solo pagos en efectivo
    total_transferencia = db.Column(db.Float, default=0.0)     # Solo pagos en transferencia


# ==========================================
# TABLA: EGRESOS
# Registra los gastos del día
# ==========================================
class Egreso(db.Model):
    __tablename__ = 'egresos'

    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)  # Ej: "Compra de leche"
    monto = db.Column(db.Float, nullable=False)              # Cuánto costó
    fecha = db.Column(db.DateTime, default=datetime.utcnow) # Cuándo fue el gasto
