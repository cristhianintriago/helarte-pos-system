from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from models.usuario import Usuario
from models.models import db
import hashlib

auth_bp = Blueprint('auth', __name__)


def _sha256(password: str) -> str:
    """Hash SHA-256 legado. Solo se usa para detectar y migrar cuentas antiguas."""
    return hashlib.sha256(password.encode()).hexdigest()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Controlador de inicio de sesión con:
    - Rate limiting de 10 intentos/min por IP (gestionado desde app.py con Flask-Limiter)
    - Migración transparente de SHA-256 → bcrypt en el primer login exitoso
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        usuario = Usuario.query.filter_by(username=username).first()

        if usuario:
            bcrypt = current_app.extensions.get('bcrypt')
            password_valido = False

            if usuario.password.startswith('$2b$') or usuario.password.startswith('$2a$'):
                # Contraseña en formato bcrypt moderno
                password_valido = bcrypt.check_password_hash(usuario.password, password)
            else:
                # Contraseña en formato SHA-256 legado → migramos automáticamente
                if usuario.password == _sha256(password):
                    password_valido = True
                    usuario.password = bcrypt.generate_password_hash(password).decode('utf-8')
                    db.session.commit()

            if password_valido:
                login_user(usuario)
                return redirect(url_for('index'))

        flash('Usuario o contraseña incorrectos', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Cierra la sesión activa del usuario."""
    logout_user()
    return redirect(url_for('auth.login'))
