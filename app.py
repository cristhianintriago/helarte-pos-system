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

# Registramos los distintos módulos del proyecto, también conocidos en Flask como 'blueprints'.
# Esto nos ayuda a mantener un diseño modular y escalable.
app.register_blueprint(auth_bp)
app.register_blueprint(productos_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(caja_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(reporte_diario_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(admin_bp)

# Bloque que interacciona con el contexto de la aplicación, ejecutado al inicio para asegurar la BD
with app.app_context():
    # Creamos las tablas en la BD en caso de que no existan aún
    db.create_all()

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
