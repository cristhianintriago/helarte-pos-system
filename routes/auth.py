from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models.usuario import Usuario
from models.models import db
import hashlib

# Registramos este archivo como un "Blueprint" en Flask.
# Los Blueprints permiten definir rutas de manera modular en lugar de escribir todas en app.py.
auth_bp = Blueprint('auth', __name__)


# Función simple para hashear contraseñas
def hashear(password):
    return hashlib.sha256(password.encode()).hexdigest()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """ 
    Controlador para iniciar sesión. 
    Atiende peticiones GET (para mostrar el formulario) y POST (para validar datos).
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Buscamos en la base de datos si existe el usuario con las credenciales dadas
        usuario = Usuario.query.filter_by(
            username=username,
            password=hashear(password)
        ).first()

        if usuario:
            # login_user es una función de Flask-Login que inicializa la sesión del usuario
            login_user(usuario)
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required # Este decorador protege la ruta: solo usuarios logueados pueden acceder a ella
def logout():
    """ Cierra la sesión activa del usuario y borra la cookie de sesión """
    logout_user()
    return redirect(url_for('auth.login'))
