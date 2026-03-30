"""
routes/cocina.py
----------------
Blueprint para la pantalla de la cocina (Kitchen Display System, KDS).

Este modulo es intencionalmente simple: solo renderiza la plantilla HTML.
Toda la logica de visualizacion de pedidos en tiempo real ocurre en el
archivo JavaScript 'cocina.js', que se comunica con el servidor usando WebSockets.

Un Blueprint en Flask es una forma de organizar rutas en modulos separados.
En lugar de definir todas las rutas en app.py, cada modulo funcional tiene
su propio Blueprint que luego se "registra" en la app principal.
"""

from flask import Blueprint, render_template
from flask_login import login_required

# Se instancia el Blueprint con un prefijo de URL.
# Todas las rutas definidas aqui estaran bajo '/cocina/...'.
cocina_bp = Blueprint('cocina', __name__, url_prefix='/cocina')


@cocina_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Renderiza la pantalla de cocina.
    El decorador @login_required redirige al login si el usuario no esta autenticado.
    """
    return render_template('cocina.html')
