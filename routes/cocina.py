from flask import Blueprint, render_template
from flask_login import login_required

cocina_bp = Blueprint('cocina', __name__, url_prefix='/cocina')

@cocina_bp.route('/', methods=['GET'])
@login_required
def index():
    return render_template('cocina.html')
