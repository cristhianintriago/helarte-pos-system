"""
routes/auth.py
--------------
Blueprint de autenticacion: maneja el inicio y cierre de sesion.

Conceptos clave usados en este modulo:
- Flask-Login: extension que gestiona las sesiones de usuario. Cuando se llama a
  login_user(usuario), Flask-Login almacena el ID del usuario en una cookie de sesion
  firmada criptograficamente. En cada solicitud posterior, Flask-Login recupera el
  usuario de la base de datos a traves del 'user_loader' definido en app.py.

- Migracion de hash: el sistema originalmente usaba SHA-256 para hashear contrasenas,
  algoritmo que es rapido pero vulnerable a ataques de fuerza bruta con GPU modernas.
  Ahora usa bcrypt, que es deliberadamente lento y tiene un "factor de trabajo" ajustable.
  Para no forzar a todos los usuarios a cambiar su contrasena, se realiza una migracion
  silenciosa: en el primer login con contrasena SHA-256 valida, se guarda el hash bcrypt.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from models.usuario import Usuario
from models.models import db
import hashlib

auth_bp = Blueprint('auth', __name__)


def _sha256(password: str) -> str:
    """
    Genera un hash SHA-256 de la contrasena.
    Solo se usa para detectar cuentas antiguas y migrarlas a bcrypt.
    SHA-256 es un algoritmo criptografico de una sola via: no se puede obtener
    la contrasena original a partir del hash, solo se puede comparar.
    """
    return hashlib.sha256(password.encode()).hexdigest()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Controlador del formulario de inicio de sesion.

    - GET: renderiza el formulario de login en blanco.
    - POST: recibe el username y password del formulario, los valida y
            si son correctos inicia la sesion del usuario.

    El algoritmo de verificacion soporta dos formatos de hash:
    1. bcrypt (formato moderno, empieza con '$2b$' o '$2a$').
    2. SHA-256 (formato legado, sin prefijo especial). En este caso,
       si la contrasena es correcta, se rehashea automaticamente con bcrypt.
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Busca al usuario por nombre exacto en la base de datos.
        usuario = Usuario.query.filter_by(username=username).first()

        if usuario:
            # Obtenemos la instancia de bcrypt que fue registrada en app.py.
            bcrypt = current_app.extensions.get('bcrypt')
            password_valido = False

            # Detectamos el tipo de hash comparando el prefijo de la contrasena guardada.
            if usuario.password.startswith('$2b$') or usuario.password.startswith('$2a$'):
                # Formato bcrypt moderno: usamos check_password_hash para comparar.
                password_valido = bcrypt.check_password_hash(usuario.password, password)
            else:
                # Formato SHA-256 legado: comparamos los hashes directamente.
                if usuario.password == _sha256(password):
                    password_valido = True
                    # Migracion silenciosa: actualizamos el hash a bcrypt para mayor seguridad.
                    usuario.password = bcrypt.generate_password_hash(password).decode('utf-8')
                    db.session.commit()

            if password_valido:
                # El campo 'remember_me' viene del checkbox del formulario.
                # request.form.get retorna None si el campo no viene en el POST
                # (los checkboxes NO envian ningun valor cuando NO estan marcados).
                # Por eso usamos el valor '1' como indicador de que fue marcado.
                remember = request.form.get('remember_me') == '1'

                # Si remember=True, Flask-Login emite una cookie permanente que
                # persiste aunque el usuario cierre el navegador. La duracion
                # se configura con REMEMBER_COOKIE_DURATION en app.py.
                # Si remember=False (por defecto), la sesion expira al cerrar el navegador.
                login_user(usuario, remember=remember)
                return redirect(url_for('index'))

        # Si el usuario no existe o la contrasena es incorrecta, mostramos un mensaje de error.
        # Usamos 'danger' como categoria para que Bootstrap muestre el mensaje en rojo.
        flash('Usuario o contraseña incorrectos', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    Cierra la sesion activa del usuario actual.
    logout_user() elimina el ID del usuario de la cookie de sesion.
    """
    logout_user()
    return redirect(url_for('auth.login'))
