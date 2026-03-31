"""
app.py
------
Punto de entrada principal del sistema Helarte POS.
Este archivo es el primero que se ejecuta cuando corre la aplicacion.
Su responsabilidad es crear y configurar la instancia de Flask,
conectar todas las extensiones, registrar los modulos (Blueprints) y
arrancar el servidor web.

Estructura de la aplicacion:
- Flask: el microframework que procesa cada solicitud HTTP y enruta a la funcion correcta.
- SQLAlchemy: ORM que maneja la conexion y consultas a la base de datos.
- Flask-Login: gestiona la autenticacion y las sesiones de usuario.
- Flask-Bcrypt: provee el algoritmo de hash seguro para contrasenas.
- Flask-Limiter: limita la cantidad de solicitudes por IP (proteccion contra bots).
- Flask-SocketIO: habilita comunicacion WebSocket en tiempo real (para la cocina).
"""

import os

try:
    from dotenv import load_dotenv
    # python-dotenv carga las variables definidas en el archivo '.env' hacia os.environ.
    # Solo se usa en desarrollo local. En Railway las variables de entorno se configuran
    # directamente en el panel de la plataforma, sin necesidad de este archivo.
    load_dotenv()
except ImportError:
    # Si python-dotenv no esta instalado, continuamos sin error.
    # En produccion (Railway) las variables ya estan en el entorno del sistema operativo.
    pass

from flask import Flask, redirect, render_template, jsonify, url_for
from flask_login import LoginManager, login_required, current_user

# Importamos socketio desde extensions.py (no desde app.py directamente)
# para evitar importaciones circulares. Ver extensions.py para la explicacion detallada.
from extensions import socketio
from models.models import db
from models.usuario import Usuario

# Cada uno de estos modulos es un Blueprint: un grupo de rutas relacionadas.
# Al separarlos en archivos distintos, el codigo es mas facil de mantener y entender.
from routes.productos import productos_bp
from routes.pedidos import pedidos_bp
from routes.caja import caja_bp
from routes.ventas import ventas_bp
from routes.reportes import reportes_bp
from routes.auth import auth_bp
from routes.reporte_diario import reporte_diario_bp
from routes.usuarios import usuarios_bp
from routes.admin import admin_bp
from routes.cocina import cocina_bp

import hashlib
from datetime import date, timedelta
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import inspect, text


# ==========================================
# CONFIGURACION CENTRAL DE LA APLICACION
# ==========================================
# ---------------------------

# Flask(__name__) crea la instancia de la aplicacion.
# __name__ es una variable de Python que contiene el nombre del modulo actual ('app').
# Flask lo usa para localizar los archivos de plantillas y archivos estaticos.
app = Flask(__name__)

# Leemos la URL de la base de datos desde las variables de entorno.
# Por defecto usamos SQLite en desarrollo local (archivo helarte.db en la carpeta instance/).
# En produccion (Railway) esta variable apunta al servidor PostgreSQL provisionado.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///helarte.db')

# Railway cambia el prefijo 'postgres://' a 'postgresql://' en versiones antiguas.
# SQLAlchemy 2.0 requiere el prefijo largo, por lo que lo corregimos si es necesario.
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Configuramos los parametros de la aplicacion.
app.config['SQLALCHEMY_DATABASE_URI']        = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Evitamos advertencias innecesarias de SQLAlchemy.

# La clave secreta se usa para firmar las cookies de sesion criptograficamente.
# Si alguien intenta modificar una cookie, Flask la detecta y la invalida.
# IMPORTANTE: en produccion debe ser un valor aleatorio largo e impredecible.
app.secret_key = os.environ.get('SECRET_KEY', 'helarte_secret_key')

# Desactivamos el cache de archivos estaticos (JS, CSS) para que el navegador
# siempre descargue la version mas reciente al recargar la pagina.
# Util en desarrollo; en produccion se puede activar para mejorar el rendimiento.
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD']     = True


# ==========================================
# CONFIGURACION DE FLASK-LOGIN
# ==========================================

# LoginManager conecta Flask-Login con nuestra aplicacion.
login_manager = LoginManager()
login_manager.init_app(app)

# La vista a la que Flask redirige si el usuario intenta acceder a una ruta protegida.
login_manager.login_view             = 'auth.login'
login_manager.login_message          = 'Inicia sesion para continuar'
login_manager.login_message_category = 'warning'

# Duracion de la cookie "Mantener sesion iniciada".
# timedelta(days=30): cuando el usuario marca el checkbox, su sesion dura 30 dias
# aunque cierre el navegador. Sin el checkbox, la sesion expira al cerrar.
# Flask-Login usa este valor cuando login_user() recibe remember=True.
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

# HttpOnly: impide que JavaScript lea la cookie (proteccion contra ataques XSS).
app.config['REMEMBER_COOKIE_HTTPONLY'] = True

# IMPORTANTE: REMEMBER_COOKIE_SECURE se mantiene en False siempre.
# Si se activa (True), el navegador SOLO envia la cookie por HTTPS.
# En local (HTTP), el navegador la rechaza silenciosamente y la sesion
# nunca se restaura aunque la cookie se haya creado correctamente.
# En produccion Railway, el servidor ya fuerza HTTPS a nivel de infraestructura,
# por lo que la seguridad no se ve comprometida con este valor en False.
app.config['REMEMBER_COOKIE_SECURE']   = False


@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login llama a esta funcion en cada solicitud para cargar el usuario actual.
    Recibe el ID del usuario guardado en la cookie de sesion y
    retorna el objeto Usuario correspondiente desde la base de datos.
    Si el ID no corresponde a ningun usuario, retorna None (sesion invalida).
    """
    return Usuario.query.get(int(user_id))


# ==========================================
# INICIALIZACION DE EXTENSIONES
# ==========================================

# Conectamos SQLAlchemy con la app. El parametro 'app' le dice a la extension
# que use la configuracion que definimos arriba (SQLALCHEMY_DATABASE_URI, etc.).
db.init_app(app)

# Conectamos SocketIO con la app. Esto habilita el servidor de WebSockets.
socketio.init_app(app)

# Flask-Bcrypt: algoritmo de hash para contrasenas. A diferencia de SHA-256,
# bcrypt incluye un "salt" aleatorio y es deliberadamente lento,
# lo que lo hace mucho mas resistente a ataques de fuerza bruta.
bcrypt = Bcrypt(app)
app.extensions['bcrypt'] = bcrypt  # Lo registramos en extensions para acceder desde auth.py.

# Flask-Limiter: protege rutas criticas contra abusos por exceso de peticiones.
# get_remote_address es la funcion que identifica al cliente por su IP.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day"],
    storage_uri="memory://"  # Almacena los contadores en memoria RAM. En produccion escalar a Redis.
)


# ==========================================
# REGISTRO DE BLUEPRINTS
# ==========================================

# Registramos cada Blueprint en la app. Flask ahora conoce todas las rutas del sistema.
app.register_blueprint(auth_bp)

# Aplicamos rate limiting especifico al endpoint de login para prevenir ataques de fuerza bruta.
# 10 intentos por minuto por IP es un limite razonable para usuarios reales.
limiter.limit("10 per minute")(app.view_functions['auth.login'])

app.register_blueprint(productos_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(caja_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(cocina_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(reporte_diario_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(admin_bp)


# ==========================================
# MIGRACIONES DE ESQUEMA AUTOMATICAS
# ==========================================
# Este sistema no usa Flask-Migrate (Alembic) para gestionar migraciones.
# En su lugar, usamos funciones que agregan columnas faltantes al inicio de cada despliegue.
# Esto permite actualizar la base de datos de produccion sin borrar datos existentes.

def _agregar_columna_si_falta(table_name, column_name, ddl):
    """
    Verifica si una columna existe en la tabla. Si no existe, ejecuta el DDL para crearla.
    DDL (Data Definition Language) son sentencias SQL que modifican la estructura de tablas
    (ALTER TABLE, CREATE TABLE, DROP TABLE, etc.), en contraste con DML (INSERT, UPDATE, etc.).

    Parametros:
    - table_name: nombre de la tabla en la base de datos.
    - column_name: nombre de la columna que se quiere verificar/agregar.
    - ddl: sentencia SQL para agregar la columna si no existe.
    """
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return  # La tabla aun no existe, db.create_all() la creara con las columnas correctas.

    # Obtenemos la lista de columnas actuales de la tabla.
    columnas = {c['name'] for c in inspector.get_columns(table_name)}
    if column_name in columnas:
        return  # La columna ya existe, no hacemos nada.

    # La columna no existe: la agregamos ejecutando el DDL.
    db.session.execute(text(ddl))
    db.session.commit()
    print(f"Migracion aplicada: {table_name}.{column_name}")


def _sincronizar_esquema_legacy():
    """
    Aplica todas las migraciones aditivas necesarias para actualizar una base de datos
    que existia antes de que se agregaran las columnas nuevas.
    Se ejecuta cada vez que arranca la aplicacion, pero solo hace cambios si es necesario.
    """
    # Columnas agregadas en versiones previas del sistema.
    _agregar_columna_si_falta('productos', 'imagen_url',   'ALTER TABLE productos ADD COLUMN imagen_url VARCHAR(500)')
    _agregar_columna_si_falta('productos', 'max_sabores',  'ALTER TABLE productos ADD COLUMN max_sabores INTEGER')
    _agregar_columna_si_falta('detalles_pedido', 'sabor',  'ALTER TABLE detalles_pedido ADD COLUMN sabor VARCHAR(120)')

    _agregar_columna_si_falta('pedidos', 'numero_comprobante',  'ALTER TABLE pedidos ADD COLUMN numero_comprobante VARCHAR(50)')
    _agregar_columna_si_falta('pedidos', 'numero_pedido',       'ALTER TABLE pedidos ADD COLUMN numero_pedido INTEGER')
    _agregar_columna_si_falta('pedidos', 'plataforma',          'ALTER TABLE pedidos ADD COLUMN plataforma VARCHAR(80)')
    _agregar_columna_si_falta('pedidos', 'monto_efectivo',      'ALTER TABLE pedidos ADD COLUMN monto_efectivo FLOAT')
    _agregar_columna_si_falta('pedidos', 'monto_transferencia', 'ALTER TABLE pedidos ADD COLUMN monto_transferencia FLOAT')

    _agregar_columna_si_falta('ventas', 'numero_comprobante',  'ALTER TABLE ventas ADD COLUMN numero_comprobante VARCHAR(50)')
    _agregar_columna_si_falta('ventas', 'monto_efectivo',      'ALTER TABLE ventas ADD COLUMN monto_efectivo FLOAT')
    _agregar_columna_si_falta('ventas', 'monto_transferencia', 'ALTER TABLE ventas ADD COLUMN monto_transferencia FLOAT')

    _agregar_columna_si_falta('caja', 'total_efectivo',      'ALTER TABLE caja ADD COLUMN total_efectivo FLOAT')
    _agregar_columna_si_falta('caja', 'total_transferencia', 'ALTER TABLE caja ADD COLUMN total_transferencia FLOAT')

    # Columnas del Cierre de Caja Ciego (Blind Close), agregadas en Fase 4.
    _agregar_columna_si_falta('caja', 'monto_declarado', 'ALTER TABLE caja ADD COLUMN monto_declarado FLOAT')
    _agregar_columna_si_falta('caja', 'descuadre',       'ALTER TABLE caja ADD COLUMN descuadre FLOAT')

    # Corregimos registros de productos que tengan max_sabores en NULL o valor invalido.
    # text() convierte el string a una expresion SQL ejecutable por SQLAlchemy.
    db.session.execute(text('UPDATE productos SET max_sabores = 1 WHERE max_sabores IS NULL OR max_sabores < 1'))
    db.session.commit()


def _crear_sabores_default():
    """
    Inserta un conjunto de sabores iniciales si la tabla de sabores esta completamente vacia.
    Este patron se llama 'seeder idempotente': puede ejecutarse muchas veces pero
    solo tiene efecto la primera vez (cuando la tabla esta vacia).
    """
    from models.models import Sabor

    if Sabor.query.count() > 0:
        return  # Ya hay sabores; no insertamos duplicados.

    defaults = ['Vainilla', 'Chocolate', 'Fresa', 'Oreo', 'Mora', 'Ron Pasas']
    for nombre in defaults:
        db.session.add(Sabor(nombre=nombre, activo=True))
    db.session.commit()
    print('Sabores base creados')


# ==========================================
# INICIALIZACION DE LA BASE DE DATOS
# ==========================================
# El bloque 'with app.app_context()' establece el contexto de la aplicacion.
# Las operaciones de base de datos en Flask requieren un contexto activo para saber
# a que app y a que base de datos conectarse. Fuera de una solicitud HTTP,
# debemos crearlo manualmente con este bloque.
with app.app_context():
    # Crea todas las tablas definidas en models.py si aun no existen.
    # Si ya existen, no hace nada (no borra ni modifica datos).
    db.create_all()

    # Aplica las migraciones aditivas para compatibilidad con bases de datos antiguas.
    _sincronizar_esquema_legacy()

    # Inserta los sabores iniciales si la tabla esta vacia.
    _crear_sabores_default()

    # Crea el usuario administrador 'root' si no existe.
    # La contrasena inicial se hashea con SHA-256 y sera migrada a bcrypt en el primer login.
    if not Usuario.query.filter_by(username='root').first():
        root = Usuario(
            username='root',
            password=hashlib.sha256('root123'.encode()).hexdigest(),
            rol='root'
        )
        db.session.add(root)
        db.session.commit()
        print("Usuario root creado -> usuario: root | contrasena: root123")

    print("Base de datos lista")


# ==========================================
# RUTAS PRINCIPALES DE LA INTERFAZ WEB
# ==========================================

@app.route('/')
@login_required
def index():
    """Renderiza el dashboard principal. Pasa la fecha de hoy para el encabezado."""
    return render_template('index.html', fecha_hoy=date.today().strftime('%d/%m/%Y'))


@app.route('/resumen')
@login_required
def resumen():
    """
    Retorna en formato JSON el resumen operativo del dia actual.
    Es consumido por el dashboard (index.html) para mostrar los indicadores en tiempo real.
    """
    from models.models import Pedido, Venta, Caja

    # Contamos pedidos que estan activos (en cocina o pendientes de preparar).
    pedidos_activos = Pedido.query.filter(
        Pedido.estado.in_(['pendiente', 'en_proceso'])
    ).count()

    # Obtenemos las ventas de hoy usando db.func.date() para ignorar la hora.
    ventas_hoy = Venta.query.filter(
        db.func.date(Venta.fecha) == date.today()
    ).all()

    # List comprehension: suma los totales de todos los objetos Venta en la lista.
    total_vendido = sum(v.total for v in ventas_hoy)

    # Buscamos si hay una caja abierta hoy para mostrar el estado en el dashboard.
    caja = Caja.query.filter(
        db.func.date(Caja.fecha) == date.today(),
        Caja.estado == 'abierta'
    ).first()

    return jsonify({
        'pedidos_activos': pedidos_activos,
        'total_ventas':    len(ventas_hoy),
        'total_vendido':   float(total_vendido),
        'caja_abierta':    caja is not None,
        'monto_caja':      float(caja.monto_inicial) if caja else 0
    })


@app.route('/pedidos')
@login_required
def pedidos():
    """Renderiza la vista HTML del modulo de toma de pedidos."""
    return render_template('pedidos.html')


@app.route('/ventas')
@login_required
def ventas():
    """Renderiza la vista HTML del historial de ventas del dia."""
    return render_template('ventas.html')


@app.route('/caja')
@login_required
def caja():
    """Renderiza la vista HTML del modulo de gestion de caja."""
    return render_template('caja.html')


@app.route('/productos')
@login_required
def productos():
    """Renderiza la vista HTML del catalogo de productos."""
    return render_template('productos.html')


@app.route('/reportes')
@login_required
def reportes():
    """Renderiza la vista HTML del dashboard analitico y exportacion de reportes."""
    return render_template('reportes.html')


@app.route('/usuarios')
@login_required
def usuarios():
    """
    Renderiza la vista de gestion de usuarios.
    Si el usuario no tiene permiso de gestionar usuarios, lo redirigimos al inicio.
    """
    if not current_user.puede_gestionar_usuarios():
        return redirect(url_for('index'))
    return render_template('usuarios.html')


@app.route('/limpiar-datos', methods=['GET'])
def limpiar_datos():
    """
    Endpoint de utilidad para reiniciar los datos de prueba.
    Elimina todas las cajas, ventas, pedidos y egresos del sistema,
    pero preserva los productos y sabores (datos de configuracion estatica).
    ADVERTENCIA: esta operacion es irreversible. Solo usar en entorno de pruebas.
    """
    from models.models import Venta, Pedido, DetallePedido, Caja, Egreso

    Egreso.query.delete()
    Caja.query.delete()
    Venta.query.delete()
    DetallePedido.query.delete()
    Pedido.query.delete()
    db.session.commit()
    return jsonify({'mensaje': 'Datos limpiados, productos intactos. Sistema reiniciado.'})


# ==========================================
# PUNTO DE ARRANQUE DEL SERVIDOR
# ==========================================
# Este bloque solo se ejecuta si el script se corre directamente (python app.py).
# Si la app es importada por otro modulo (como Gunicorn en produccion), este bloque NO se ejecuta.

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # socketio.run() reemplaza a app.run() para que el servidor soporte WebSockets.
    # allow_unsafe_werkzeug=True es necesario cuando se usa el servidor de desarrollo de Werkzeug
    # (en produccion, Gunicorn con eventlet se encarga de esto automaticamente).
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
