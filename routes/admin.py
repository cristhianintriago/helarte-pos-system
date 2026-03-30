"""
routes/admin.py
---------------
Blueprint para el panel de administracion del sistema.

Esta vista es exclusiva para el usuario con rol 'root'. Permite gestionar
y eliminar registros historicos de caja y ventas directamente desde la interfaz.

El acceso se verifica con current_user.puede_eliminar_registros(), que solo
retorna True cuando el rol del usuario es 'root'. Si alguien sin permiso
intenta acceder a esta URL, recibe un error HTTP 403 (Forbidden).
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/', methods=['GET'])
@login_required
def panel():
    """
    Muestra el panel de administracion.
    Si el usuario no tiene el permiso suficiente, se aborta la solicitud
    con un error 403 (Acceso Denegado), que Flask convierte en una pagina de error.
    """
    if not current_user.puede_eliminar_registros():
        from flask import abort
        abort(403)
    return render_template('admin.html')
