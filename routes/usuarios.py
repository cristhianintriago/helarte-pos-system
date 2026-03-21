from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user

from core.decorators import root_required
from core.security import hash_password
from models.models import db
from models.usuario import Usuario


usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@usuarios_bp.route("/", methods=["GET"])
@root_required
def listar():
    return render_template("usuarios.html")


@usuarios_bp.route("/api", methods=["GET"])
@root_required
def api_listar():
    usuarios = Usuario.query.all()
    return jsonify(
        [{"id": usuario.id, "username": usuario.username, "rol": usuario.rol} for usuario in usuarios]
    )


@usuarios_bp.route("/api", methods=["POST"])
@root_required
def crear():
    datos = request.get_json() or {}

    if Usuario.query.filter_by(username=datos["username"]).first():
        return jsonify({"error": "El usuario ya existe"}), 400

    if datos["rol"] == "root":
        return jsonify({"error": "No se puede crear otro usuario root"}), 400

    nuevo = Usuario(
        username=datos["username"],
        password=hash_password(datos["password"]),
        rol=datos["rol"],
    )
    db.session.add(nuevo)
    db.session.commit()

    return jsonify({"mensaje": f"Usuario {nuevo.username} creado"}), 201


@usuarios_bp.route("/api/<int:usuario_id>", methods=["PUT"])
@root_required
def editar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    datos = request.get_json() or {}

    if usuario.rol == "root":
        return jsonify({"error": "No se puede modificar al usuario root"}), 403

    usuario.username = datos.get("username", usuario.username)
    usuario.rol = datos.get("rol", usuario.rol)

    if datos.get("password"):
        usuario.password = hash_password(datos["password"])

    db.session.commit()
    return jsonify({"mensaje": "Usuario actualizado"})


@usuarios_bp.route("/api/<int:usuario_id>", methods=["DELETE"])
@root_required
def eliminar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)

    if usuario.rol == "root":
        return jsonify({"error": "No se puede eliminar al usuario root"}), 403

    if usuario.id == current_user.id:
        return jsonify({"error": "No puedes eliminarte a ti mismo"}), 400

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({"mensaje": "Usuario eliminado"})
