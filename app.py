# Importaciones de librerías estandar y de terceros
import os
try:
    from dotenv import load_dotenv
    # Se cargan las variables de entorno en desarrollo local (útil para contraseñas, configuraciones)
    load_dotenv() 
except ImportError:
    pass  # Si la librería no está (ej., en el servidor de Railway), se ignorará y se usarán las del sistema

# Importaciones de módulos principales del framework web
from flask import Flask, redirect, render_template, jsonify, url_for
from flask_login import LoginManager, login_required, current_user

# Importaciones de nuestros modelos de la base de datos (BD)
from models.models import db
from models.usuario import Usuario

# Importaciones de los controladores o rutas (Blueprints que modularizan la arquitectura)
from routes.productos import productos_bp
from routes.pedidos import pedidos_bp
from routes.caja import caja_bp
from routes.ventas import ventas_bp
from routes.reportes import reportes_bp
from routes.auth import auth_bp
from routes.reporte_diario import reporte_diario_bp
from routes.usuarios import usuarios_bp
from routes.admin import admin_bp

import hashlib
from datetime import date
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import inspect, text


# ==========================================
# CONFIGURACION CENTRAL DE APLICACION
# ==========================================


# Se instancia la aplicación de Flask, esto será el núcleo de nuestro proyecto
app = Flask(__name__)

# Configuramos la URL de la base de datos (por defecto usaremos SQLite en local si no hay variable de entorno)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///helarte.db')

# Pequeña validación si se usa PostgreSQL en producción (ej. Railway cambia postgres:// a postgresql://)
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Asignaciones de configuraciones a la instancia de la aplicación
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# La clave secreta es necesaria para mantener sesiones seguras
app.secret_key = os.environ.get('SECRET_KEY', 'helarte_secret_key')
# Desactivamos el caché de archivos estáticos para que el browser siempre cargue el JS/CSS más reciente
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True


# Se instancia Flask-Login para el manejo y protección de rutas con autenticación
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesión para continuar'
login_manager.login_message_category = 'warning'

# Función decoradora de Flask-login que devuelve un objeto usuario desde la base de datos según su ID
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Se inicializa SQLAlchemy en nuestra app
db.init_app(app)

# ── Flask-Bcrypt: biblioteca para hasheo seguro de contraseñas con bcrypt ──
# A diferencia de SHA-256, bcrypt incluye salt automático y es resistente a ataques de fuerza bruta.
bcrypt = Bcrypt(app)
app.extensions['bcrypt'] = bcrypt

# ── Flask-Limiter: protege rutas contra abuso por exceso de peticiones ──
# Por defecto limita por dirección IP del cliente.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day"],
    storage_uri="memory://"  # En producción usar Redis
)

# Registramos los distintos módulos del proyecto, también conocidos en Flask como 'blueprints'.
# Esto nos ayuda a mantener un diseño modular y escalable.
app.register_blueprint(auth_bp)
# Aplicamos rate limiting al login: máx 10 intentos por minuto por IP
# Esto evita ataques de fuerza bruta sin modificar el blueprint directamente.
limiter.limit("10 per minute")(app.view_functions['auth.login'])
app.register_blueprint(productos_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(caja_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(reporte_diario_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(admin_bp)


def _agregar_columna_si_falta(table_name, column_name, ddl):
    """Aplica una migracion aditiva minima para despliegues legacy sin romper datos existentes."""
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return

    columnas = {c['name'] for c in inspector.get_columns(table_name)}
    if column_name in columnas:
        return

    # Solo agrega columnas faltantes; no altera ni elimina estructura existente.
    db.session.execute(text(ddl))
    db.session.commit()
    print(f"Migracion aplicada: {table_name}.{column_name}")


def _sincronizar_esquema_legacy():
    # Mantiene compatibilidad con BDs antiguas en despliegues sin migraciones formales.
    # Migraciones aditivas necesarias cuando el despliegue usa una BD previa a estos campos.
    _agregar_columna_si_falta('productos', 'imagen_url', 'ALTER TABLE productos ADD COLUMN imagen_url VARCHAR(500)')
    _agregar_columna_si_falta('productos', 'max_sabores', 'ALTER TABLE productos ADD COLUMN max_sabores INTEGER')
    _agregar_columna_si_falta('detalles_pedido', 'sabor', 'ALTER TABLE detalles_pedido ADD COLUMN sabor VARCHAR(120)')

    _agregar_columna_si_falta('pedidos', 'numero_comprobante', 'ALTER TABLE pedidos ADD COLUMN numero_comprobante VARCHAR(50)')
    _agregar_columna_si_falta('pedidos', 'numero_pedido', 'ALTER TABLE pedidos ADD COLUMN numero_pedido INTEGER')
    _agregar_columna_si_falta('pedidos', 'plataforma', 'ALTER TABLE pedidos ADD COLUMN plataforma VARCHAR(80)')
    _agregar_columna_si_falta('pedidos', 'monto_efectivo', 'ALTER TABLE pedidos ADD COLUMN monto_efectivo FLOAT')
    _agregar_columna_si_falta('pedidos', 'monto_transferencia', 'ALTER TABLE pedidos ADD COLUMN monto_transferencia FLOAT')

    _agregar_columna_si_falta('ventas', 'numero_comprobante', 'ALTER TABLE ventas ADD COLUMN numero_comprobante VARCHAR(50)')
    _agregar_columna_si_falta('ventas', 'monto_efectivo', 'ALTER TABLE ventas ADD COLUMN monto_efectivo FLOAT')
    _agregar_columna_si_falta('ventas', 'monto_transferencia', 'ALTER TABLE ventas ADD COLUMN monto_transferencia FLOAT')

    _agregar_columna_si_falta('caja', 'total_efectivo', 'ALTER TABLE caja ADD COLUMN total_efectivo FLOAT')
    _agregar_columna_si_falta('caja', 'total_transferencia', 'ALTER TABLE caja ADD COLUMN total_transferencia FLOAT')

    # Normaliza registros antiguos para evitar nulos en reglas de sabores.
    db.session.execute(text('UPDATE productos SET max_sabores = 1 WHERE max_sabores IS NULL OR max_sabores < 1'))
    db.session.commit()


def _crear_sabores_default():
    from models.models import Sabor

    if Sabor.query.count() > 0:
        return

    # Seeder idempotente: solo ejecuta cuando la tabla de sabores esta vacia.
    defaults = ['Vainilla', 'Chocolate', 'Fresa', 'Oreo', 'Mora', 'Ron Pasas']
    for nombre in defaults:
        db.session.add(Sabor(nombre=nombre, activo=True))
    db.session.commit()
    print('Sabores base creados')
# Bloque que interacciona con el contexto de la aplicación, ejecutado al inicio para asegurar la BD
with app.app_context():
    # Creamos las tablas en la BD en caso de que no existan aún
    db.create_all()
    _sincronizar_esquema_legacy()
    _crear_sabores_default()

    # Inserción de cuenta administradora de defecto ('root')
    if not Usuario.query.filter_by(username='root').first():
        root = Usuario(
            username='root',
            password=hashlib.sha256('root123'.encode()).hexdigest(),
            rol='root'
        )
        db.session.add(root)
        db.session.commit()
        print("Usuario root creado -> usuario: root | contraseña: root123")

    print("Base de datos lista")


# ==========================================
# RUTAS PRINCIPALES DEL APLICATIVO
# ==========================================

@app.route('/')
@login_required
def index():
    # El método render_template es usado para dibujar un archivo HTML pasando atributos variables
    return render_template('index.html', fecha_hoy=date.today().strftime('%d/%m/%Y'))


@app.route('/resumen')
@login_required
def resumen():
    """ 
    Ruta API, retorna en formato JSON el resumen operativo del día:
    la cantidad de pedidos en marcha, ventas de la fecha, montos de caja, etc.
    """
    from models.models import Pedido, Venta, Caja

    # Consultamos total de pedidos haciendo filtros mediante .in_()
    pedidos_activos = Pedido.query.filter(
        Pedido.estado.in_(['pendiente', 'en_proceso'])
    ).count()

    # Buscamos ventas cuya fecha sea igual al dia de hoy
    ventas_hoy = Venta.query.filter(
        db.func.date(Venta.fecha) == date.today()
    ).all()

    # List comprehension (suma de los totales de cada objeto de tipo "Venta" iterado)
    total_vendido = sum(v.total for v in ventas_hoy)

    # Identificamos el estado de la caja de hoy (si está abierta)
    caja = Caja.query.filter(
        db.func.date(Caja.fecha) == date.today(),
        Caja.estado == 'abierta'
    ).first()

    return jsonify({
        'pedidos_activos': pedidos_activos,
        'total_ventas': len(ventas_hoy),
        'total_vendido': float(total_vendido),
        'caja_abierta': caja is not None,
        'monto_caja': float(caja.monto_inicial) if caja else 0
    })


@app.route('/pedidos')
@login_required
def pedidos():
    # Redirigimos al usuario a la vista HTML de pedidos
    return render_template('pedidos.html')


@app.route('/ventas')
@login_required
def ventas():
    return render_template('ventas.html')


@app.route('/caja')
@login_required
def caja():
    return render_template('caja.html')


@app.route('/productos')
@login_required
def productos():
    return render_template('productos.html')


@app.route('/reportes')
@login_required
def reportes():
    return render_template('reportes.html')


@app.route('/usuarios')
@login_required
def usuarios():
    # Validamos permisos para acceder a esta ruta sensible
    if not current_user.puede_gestionar_usuarios():
        return redirect(url_for('index'))
    return render_template('usuarios.html')


@app.route('/limpiar-datos', methods=['GET'])
def limpiar_datos():
    """ 
    Punto de enlace usado para limpiar tablas dinámicas para pruebas, 
    dejando intactos por ejemplo los productos que son estáticos/persistentes. 
    """
    from models.models import Venta, Pedido, DetallePedido, Caja, Egreso

    Egreso.query.delete()
    Caja.query.delete()
    Venta.query.delete()
    DetallePedido.query.delete()
    Pedido.query.delete()
    db.session.commit()
    return jsonify({'mensaje': 'Datos limpiados, productos intactos. Sistema reiniciado.'})

# Main point: Inicia el levantamiento del proceso o servidor web local (en este caso en el puerto port)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
