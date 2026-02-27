# Importamos SQLAlchemy, que es la librería que nos permite
# crear tablas de base de datos usando clases de Python
# en lugar de escribir SQL directamente
from flask_sqlalchemy import SQLAlchemy

# Importamos datetime para registrar fechas y horas automáticamente
from datetime import datetime

# Creamos el objeto db que será el puente entre Python y la base de datos
# Este objeto lo usaremos en TODAS las clases para definir columnas
db = SQLAlchemy()


# ==========================================
# TABLA: PRODUCTOS
# Guarda el menú de la heladería
# ==========================================
class Producto(db.Model):
    __tablename__ = 'productos'  # Nombre real de la tabla en la base de datos

    id = db.Column(db.Integer, primary_key=True)          # ID único autoincremental
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
    tipo = db.Column(db.String(20), nullable=False)             # 'local' o 'delivery'
    cliente_nombre = db.Column(db.String(100), nullable=False)  # Nombre del cliente
    cliente_telefono = db.Column(db.String(20), nullable=True)  # Solo se llena si es delivery
    cliente_direccion = db.Column(db.String(200), nullable=True) # Solo se llena si es delivery
    estado = db.Column(db.String(20), default='pendiente')      # pendiente → en_proceso → entregado
    total = db.Column(db.Float, default=0.0)                    # Total en dinero del pedido
    fecha = db.Column(db.DateTime, default=datetime.utcnow)     # Fecha y hora automática

    # Relación: un pedido puede tener MUCHOS detalles (productos)
    # backref='pedido' permite desde un DetallePedido acceder al Pedido padre
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)


# ==========================================
# TABLA: DETALLES DEL PEDIDO
# Guarda QUÉ productos tiene cada pedido y en qué cantidad
# Es la tabla intermedia entre Pedido y Producto
# ==========================================
class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'

    id = db.Column(db.Integer, primary_key=True)

    # ForeignKey = llave foránea, es decir, referencia a otra tabla
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)   # ¿A qué pedido pertenece?
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False) # ¿Qué producto es?

    cantidad = db.Column(db.Integer, nullable=False)   # ¿Cuántas unidades?
    subtotal = db.Column(db.Float, nullable=False)     # cantidad × precio del producto

    # Relación para acceder al objeto Producto directamente desde un DetallePedido
    producto = db.relationship('Producto')


# ==========================================
# TABLA: VENTAS
# Se genera automáticamente cuando un pedido es marcado como entregado
# Es el registro oficial de dinero que entró al negocio
# ==========================================
class Venta(db.Model):
    __tablename__ = 'ventas'

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False) # Qué pedido generó esta venta
    total = db.Column(db.Float, nullable=False)                # Total cobrado
    fecha = db.Column(db.DateTime, default=datetime.utcnow)   # Cuándo se realizó

    pedido = db.relationship('Pedido') # Para acceder al detalle del pedido desde la venta


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
    monto_final = db.Column(db.Float, nullable=True)       # Se calcula al cerrar: inicial + ingresos - egresos
    estado = db.Column(db.String(20), default='abierta')   # 'abierta' o 'cerrada'


# ==========================================
# TABLA: EGRESOS
# Registra los gastos del día (compra de insumos, servicios, etc.)
# Está relacionada con la caja del día
# ==========================================
class Egreso(db.Model):
    __tablename__ = 'egresos'

    id = db.Column(db.Integer, primary_key=True)
    caja_id = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False) # A qué caja pertenece este gasto
    descripcion = db.Column(db.String(200), nullable=False)  # Ej: "Compra de leche"
    monto = db.Column(db.Float, nullable=False)              # Cuánto costó
    fecha = db.Column(db.DateTime, default=datetime.utcnow) # Cuándo fue el gasto
