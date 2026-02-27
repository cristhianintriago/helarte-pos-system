from flask import Flask, redirect, render_template
from flask_login import LoginManager, login_required
from models.models import db
from models.usuario import Usuario
from routes.productos import productos_bp
from routes.pedidos import pedidos_bp
from routes.caja import caja_bp
from routes.ventas import ventas_bp
from routes.reportes import reportes_bp
from routes.auth import auth_bp
import hashlib
from flask_login import LoginManager, login_required, current_user
from routes.reporte_diario import reporte_diario_bp



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///helarte.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'helarte_secret_key'

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'          # Redirige aquí si no está logueado
login_manager.login_message = 'Inicia sesión para continuar'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

db.init_app(app)

# Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(productos_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(caja_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(reporte_diario_bp)
with app.app_context():
    db.create_all()

    # Crea root si no existe
    if not Usuario.query.filter_by(username='root').first():
        root = Usuario(
            username='root',
            password=hashlib.sha256('root123'.encode()).hexdigest(),
            rol='root'
        )
        db.session.add(root)
        db.session.commit()
        print("Usuario root creado → usuario: root | contraseña: root123")

    print("Base de datos lista ✅")     

# Todas las rutas protegidas con @login_required
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/pedidos')
@login_required
def pedidos():
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

from routes.usuarios import usuarios_bp
app.register_blueprint(usuarios_bp)

@app.route('/usuarios')
@login_required
def usuarios():
    if not current_user.puede_gestionar_usuarios():
        return redirect(url_for('index'))
    return render_template('usuarios.html')



if __name__ == '__main__':
    app.run(debug=True)
