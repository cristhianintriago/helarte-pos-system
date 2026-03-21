import os
from datetime import date

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from flask import Flask, jsonify, redirect, render_template, url_for
from flask_login import LoginManager, current_user, login_required

from core.config import Config, normalize_database_url
from core.decorators import admin_required
from core.security import hash_password
from models.models import db
from models.usuario import Usuario
from routes.auth import auth_bp
from routes.caja import caja_bp
from routes.pedidos import pedidos_bp
from routes.productos import productos_bp
from routes.reporte_diario import reporte_diario_bp
from routes.reportes import reportes_bp
from routes.usuarios import usuarios_bp
from routes.ventas import ventas_bp


app = Flask(__name__)
app.config.from_object(Config)
app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(
    app.config["SQLALCHEMY_DATABASE_URI"]
)
app.secret_key = app.config["SECRET_KEY"]

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Inicia sesión para continuar"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


db.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(productos_bp)
app.register_blueprint(pedidos_bp)
app.register_blueprint(caja_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(reporte_diario_bp)
app.register_blueprint(usuarios_bp)


with app.app_context():
    db.create_all()

    default_root_username = app.config["DEFAULT_ROOT_USERNAME"]
    default_root_password = app.config["DEFAULT_ROOT_PASSWORD"]

    if default_root_password and not Usuario.query.filter_by(
        username=default_root_username
    ).first():
        root = Usuario(
            username=default_root_username,
            password=hash_password(default_root_password),
            rol="root",
        )
        db.session.add(root)
        db.session.commit()
        print(f"Usuario root creado -> usuario: {default_root_username}")

    print("Base de datos lista")


@app.route("/")
@login_required
def index():
    return render_template("index.html", fecha_hoy=date.today().strftime("%d/%m/%Y"))


@app.route("/resumen")
@login_required
def resumen():
    from models.models import Caja, Pedido, Venta

    pedidos_activos = Pedido.query.filter(
        Pedido.estado.in_(["pendiente", "en_proceso"])
    ).count()

    ventas_hoy = Venta.query.filter(db.func.date(Venta.fecha) == date.today()).all()
    total_vendido = sum(v.total for v in ventas_hoy)

    caja = Caja.query.filter(
        db.func.date(Caja.fecha) == date.today(),
        Caja.estado == "abierta",
    ).first()

    return jsonify(
        {
            "pedidos_activos": pedidos_activos,
            "total_ventas": len(ventas_hoy),
            "total_vendido": float(total_vendido),
            "caja_abierta": caja is not None,
            "monto_caja": float(caja.monto_inicial) if caja else 0,
        }
    )


@app.route("/pedidos")
@login_required
def pedidos():
    return render_template("pedidos.html")


@app.route("/ventas")
@login_required
def ventas():
    return render_template("ventas.html")


@app.route("/caja")
@login_required
def caja():
    return render_template("caja.html")


@app.route("/productos")
@login_required
def productos():
    return render_template("productos.html")


@app.route("/reportes")
@login_required
def reportes():
    return render_template("reportes.html")


@app.route("/usuarios")
@login_required
def usuarios():
    if not current_user.puede_gestionar_usuarios():
        return redirect(url_for("index"))
    return render_template("usuarios.html")


@app.route("/limpiar-datos", methods=["POST"])
@admin_required
def limpiar_datos():
    from models.models import Caja, DetallePedido, Egreso, Pedido, Venta

    Egreso.query.delete()
    Caja.query.delete()
    Venta.query.delete()
    DetallePedido.query.delete()
    Pedido.query.delete()
    db.session.commit()
    return jsonify({"mensaje": "Datos limpiados, productos intactos"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
