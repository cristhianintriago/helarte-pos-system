from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from core.security import hash_password, is_legacy_sha256_hash, verify_password
from models.models import db
from models.usuario import Usuario


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and verify_password(usuario.password, password):
            if is_legacy_sha256_hash(usuario.password):
                usuario.password = hash_password(password)
                db.session.commit()
            login_user(usuario)
            return redirect(url_for("index"))

        flash("Usuario o contraseña incorrectos", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
