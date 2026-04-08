"""
models/models.py
----------------
Aqui defino mis clases para que SQLAlchemy las convierta en tablas en mi base de datos SQLite/Postgres.
Asi no tengo que armar sentencias SQL largas a mano.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Se instancia el objeto central de SQLAlchemy. Este objeto 'db' sera pasado
# a la aplicacion Flask en app.py usando db.init_app(app).
# Separar la instancia de la app evita importaciones circulares.
db = SQLAlchemy()


# ==========================================
# TABLA INTERMEDIA: producto_sabores
# ==========================================
# El profe dijo que si un helado tiene muchos sabores y un sabor esta en muchos helados
# debemos hacer una tabla en medio para conectarlos y que no explote la base.
producto_sabores = db.Table(
    'producto_sabores',
    db.Column('producto_id', db.Integer, db.ForeignKey('productos.id'), primary_key=True),
    db.Column('sabor_id', db.Integer, db.ForeignKey('sabores.id'), primary_key=True)
)


# ==========================================
# TABLA: productos
# Almacena el catalogo de helados y productos del menu
# ==========================================
class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)

    # Variables obligatorias para los helados
    nombre      = db.Column(db.String(100), nullable=False)   # Ejemplo: "Copa Oreo"
    precio      = db.Column(db.Float,       nullable=False)   # Ejemplo: 3.50 (en dolares)
    categoria   = db.Column(db.String(50),  nullable=False)   # Ejemplo: "Copa", "Sundae"

    # default=True: si no se especifica al crear el objeto, SQLAlchemy usa True.
    disponible  = db.Column(db.Boolean, default=True)         # False = agotado o archivado

    # Maxima cantidad de sabores que el cliente puede elegir para este producto.
    max_sabores = db.Column(db.Integer, default=1)

    # URL de la imagen almacenada en Cloudinary (servicio externo de imagenes).
    # nullable=True permite que un producto no tenga imagen asignada.
    imagen_url  = db.Column(db.String(500), nullable=True)

    sabores = db.relationship(
        'Sabor',
        secondary=producto_sabores,
        lazy='subquery',
        backref=db.backref('productos', lazy=True)
    )


# ==========================================
# TABLA: sabores
# Catalogo de sabores disponibles en la heladeria
# ==========================================
class Sabor(db.Model):
    __tablename__ = 'sabores'

    id     = db.Column(db.Integer, primary_key=True)
    # unique=True garantiza que no haya dos sabores con el mismo nombre en la tabla.
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    # activo=False permite "desactivar" un sabor sin borrarlo, preservando el historial.
    activo = db.Column(db.Boolean, default=True)


# ==========================================
# TABLA: pedidos
# Representa cada orden realizada por un cliente
# ==========================================
class Pedido(db.Model):
    __tablename__ = 'pedidos'

    id              = db.Column(db.Integer, primary_key=True)

    # Tipo de pedido: "local" (mesa) o "delivery" (domicilio).
    tipo            = db.Column(db.String(20),  nullable=False)
    cliente_nombre  = db.Column(db.String(100), nullable=False)
    cliente_identificacion = db.Column(db.String(20), nullable=True)
    cliente_correo  = db.Column(db.String(120), nullable=True)
    cliente_telefono  = db.Column(db.String(20),  nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    requiere_factura  = db.Column(db.Boolean, default=False)

    # Plataforma de delivery externa, ej: "PedidosYa", "Rappi". Puede ser NULL si es local.
    plataforma      = db.Column(db.String(80),  nullable=True)

    # Estado del ciclo de vida del pedido en cocina.
    # Flujo: pendiente -> en_proceso -> preparado -> entregado
    estado          = db.Column(db.String(20), default='pendiente')

    # Numero visual del ticket mostrado en cocina (del 1 al 50, ciclico).
    numero_pedido   = db.Column(db.Integer, nullable=True)

    total           = db.Column(db.Float, default=0.0)

    # datetime.now (sin parentesis): SQLAlchemy llama a la funcion en el momento
    # de insertar el registro, no al definir el modelo.
    fecha           = db.Column(db.DateTime, default=datetime.now)

    # Forma de pago: "efectivo", "transferencia", "mixto".
    forma_pago      = db.Column(db.String(20), default='efectivo')

    # Campos para pagos con transferencia o mixtos.
    numero_comprobante  = db.Column(db.String(50), nullable=True)
    monto_efectivo      = db.Column(db.Float, nullable=True)
    monto_transferencia = db.Column(db.Float, nullable=True)

    # Relacion 1:N con DetallePedido. Un pedido tiene muchos detalles (items).
    # backref='pedido' crea el atributo inverso detalle.pedido para navegar desde
    # un DetallePedido hacia su Pedido padre.
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)


# ==========================================
# TABLA: detalles_pedido
# Cada fila representa un producto dentro de un pedido
# ==========================================
class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'

    id = db.Column(db.Integer, primary_key=True)

    # Clave foranea (ForeignKey): vincula este detalle al pedido al que pertenece.
    # Si se elimina el pedido padre, SQLAlchemy gestiona la integridad referencial.
    pedido_id   = db.Column(db.Integer, db.ForeignKey('pedidos.id'),   nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)

    cantidad = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float,   nullable=False)

    # Texto libre con el o los sabores elegidos por el cliente, ej: "Vainilla, Fresa".
    sabor    = db.Column(db.String(120), nullable=True)

    # Relacion hacia Producto para acceder al objeto completo desde un detalle.
    # Ejemplo: detalle.producto.nombre
    producto = db.relationship('Producto')


# ==========================================
# TABLA: ventas
# Registro financiero de cada pedido cobrado
# ==========================================
class Venta(db.Model):
    __tablename__ = 'ventas'

    id        = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    total     = db.Column(db.Float, nullable=False)
    fecha     = db.Column(db.DateTime, default=datetime.now)
    forma_pago = db.Column(db.String(20), default='efectivo')
    
    # Datos del cliente al momento de la venta
    cliente_nombre  = db.Column(db.String(100), nullable=True)
    cliente_identificacion = db.Column(db.String(20), nullable=True)
    cliente_correo  = db.Column(db.String(120), nullable=True)
    cliente_telefono  = db.Column(db.String(20),  nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    requiere_factura  = db.Column(db.Boolean, default=False)

    # Campos adicionales para auditar el desglose del pago.
    numero_comprobante  = db.Column(db.String(50), nullable=True)
    monto_efectivo      = db.Column(db.Float, nullable=True)
    monto_transferencia = db.Column(db.Float, nullable=True)

    # Relacion hacia Pedido para acceder a los datos del cliente y tipo desde la venta.
    pedido = db.relationship('Pedido')


# ==========================================
# TABLA: caja
# Registro del turno de cada jornada de trabajo
# ==========================================
class Caja(db.Model):
    __tablename__ = 'caja'

    id    = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    # Fecha operativa del negocio (zona horaria local, America/Guayaquil).
    # Se establece al abrir la caja y nunca cambia aunque el timestamp UTC cruce el dia.
    # Esto garantiza que una caja abierta a las 20:00 Ecuador pertenece al dia correcto,
    # aunque su timestamp UTC sea del dia siguiente.
    fecha_operativa = db.Column(db.Date, nullable=True, index=True)

    # Dinero con el que se abre la caja al inicio del turno.
    monto_inicial = db.Column(db.Float, nullable=False)

    # Acumuladores que se incrementan con cada venta o egreso registrado.
    total_ingresos     = db.Column(db.Float, default=0.0)
    total_egresos      = db.Column(db.Float, default=0.0)
    total_efectivo     = db.Column(db.Float, default=0.0)
    total_transferencia = db.Column(db.Float, default=0.0)

    # Calculado al cerrar: monto_inicial + total_ingresos - total_egresos.
    monto_final = db.Column(db.Float, nullable=True)

    # Estado del turno: "abierta" durante la jornada, "cerrada" al terminar.
    estado = db.Column(db.String(20), default='abierta')

    # Campos del Cierre de Caja Ciego (Blind Close):
    # El cajero cuenta el dinero fisico y declara cuanto hay.
    # El sistema compara con lo esperado y calcula la diferencia.
    monto_declarado = db.Column(db.Float, nullable=True)  # Lo que el cajero dijo que habia
    descuadre       = db.Column(db.Float, nullable=True)  # Diferencia: declarado - esperado


# ==========================================
# TABLA: egresos
# Gastos realizados durante el turno (insumos, pagos, etc.)
# ==========================================
class Egreso(db.Model):
    __tablename__ = 'egresos'

    id          = db.Column(db.Integer, primary_key=True)
    # Vincula el egreso a la caja abierta del dia.
    caja_id     = db.Column(db.Integer, db.ForeignKey('caja.id'), nullable=False)
    descripcion = db.Column(db.String(200), nullable=False)
    monto       = db.Column(db.Float,       nullable=False)
    fecha       = db.Column(db.DateTime,    default=datetime.now)


# ==========================================
# TABLA: configuracion_sistema
# Parametros operativos en formato llave-valor
# ==========================================
class ConfiguracionSistema(db.Model):
    __tablename__ = 'configuracion_sistema'

    # Esta tabla usa un patron llave-valor (key-value store) simple.
    # Permite guardar configuraciones sin necesidad de nuevas columnas o migraciones.
    # Ejemplo de uso: clave='contador_ticket_diario', valor_entero=14
    clave        = db.Column(db.String(80), primary_key=True)
    valor_entero = db.Column(db.Integer,    nullable=True)

# ==========================================
# TABLA: facturas_sri
# Control de comprobantes electronicos
# ==========================================
class FacturaSRI(db.Model):
    __tablename__ = 'facturas_sri'

    id               = db.Column(db.Integer, primary_key=True)
    venta_id         = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False, unique=True)
    
    # Cadena de 49 digitos generada modulo 11
    clave_acceso     = db.Column(db.String(49), unique=True, nullable=False)
    
    # SRI responde con autorizacion al aprobar
    numero_autorizacion = db.Column(db.String(49), nullable=True)
    
    # ciclo: pendiente -> generado -> firmado -> enviado -> autorizado | rechazado | error_certificado | error
    estado           = db.Column(db.String(20), default='pendiente')
    
    # Ej: 001001 (estab + pto_emision)
    serie            = db.Column(db.String(6), default='001001')
    # Ej: 000000001
    secuencial       = db.Column(db.String(9), nullable=False)
    
    # Textos largos para debug y guardado de comprobante
    xml_sin_firma    = db.Column(db.Text, nullable=True)
    xml_firmado      = db.Column(db.Text, nullable=True)
    mensaje_sri      = db.Column(db.Text, nullable=True)
    
    fecha_autorizacion = db.Column(db.DateTime, nullable=True)
    fecha_creacion   = db.Column(db.DateTime, default=datetime.now)
    
    # Relacion con venta. backref asocia 1 a 1 Factura con Venta.
    venta = db.relationship('Venta', backref=db.backref('factura_sri', uselist=False))
