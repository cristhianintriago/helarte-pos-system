from flask import Blueprint, render_template
from flask_login import login_required, current_user

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/', methods=['GET'])
@login_required
def panel():
    """
    Panel exclusivo para el usuario root.
    Permite gestionar y eliminar registros históricos de caja y ventas.
    """
    if not current_user.puede_eliminar_registros():
        from flask import abort
        abort(403)
    return render_template('admin.html')
