from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.usuario import Usuario
from models.models import db
import hashlib

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')


def hashear(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Decorador personalizado para rutas exclusivas de root
def solo_root(f):
    from functools import wraps
    @wraps(f)
    def decorador(*args, **kwargs):
        if not current_user.es_root():
            return jsonify({'error': 'No tienes permisos para esta acción'}), 403
        return f(*args, **kwargs)
    return decorador


# Decorador para rutas accesibles por admin y root
def admin_o_superior(f):
    from functools import wraps
    @wraps(f)
    def decorador(*args, **kwargs):
        if not current_user.es_admin_o_superior():
            return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403
        return f(*args, **kwargs)
    return decorador


@usuarios_bp.route('/', methods=['GET'])
@login_required
@admin_o_superior
def listar():
    from flask import render_template
    return render_template('usuarios.html')


@usuarios_bp.route('/api', methods=['GET'])
@login_required
@admin_o_superior
def api_listar():
    usuarios = Usuario.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'rol': u.rol
    } for u in usuarios])


@usuarios_bp.route('/api', methods=['POST'])
@login_required
def crear():
    """
    Root puede crear cualquier rol (menos otro root).
    Admin solo puede crear empleados.
    """
    if not current_user.puede_crear_usuarios():
        return jsonify({'error': 'No tienes permisos para crear usuarios'}), 403

    datos = request.json
    rol_solicitado = datos.get('rol', 'empleado')

    # Validación de rol según jerarquía
    if rol_solicitado == 'root':
        return jsonify({'error': 'No se puede crear otro usuario root'}), 400

    if rol_solicitado not in current_user.roles_creables():
        return jsonify({'error': f'No puedes crear usuarios con rol "{rol_solicitado}"'}), 403

    if Usuario.query.filter_by(username=datos['username']).first():
        return jsonify({'error': 'El usuario ya existe'}), 400

    nuevo = Usuario(
        username=datos['username'],
        password=hashear(datos['password']),
        rol=rol_solicitado
    )
    db.session.add(nuevo)
    db.session.commit()

    return jsonify({'mensaje': f'Usuario {nuevo.username} creado'}), 201


@usuarios_bp.route('/api/<int:usuario_id>', methods=['PUT'])
@login_required
@admin_o_superior
def editar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    datos = request.json

    if usuario.rol == 'root':
        return jsonify({'error': 'No se puede modificar al usuario root'}), 403

    if current_user.rol == 'admin' and usuario.rol != 'empleado':
        return jsonify({'error': 'Solo puedes modificar usuarios con rol empleado'}), 403

    usuario.username = datos.get('username', usuario.username)
    usuario.rol = datos.get('rol', usuario.rol)

    if datos.get('password'):
        usuario.password = hashear(datos['password'])

    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado'})


@usuarios_bp.route('/api/<int:usuario_id>', methods=['DELETE'])
@login_required
@admin_o_superior
def eliminar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)

    if usuario.rol == 'root':
        return jsonify({'error': 'No se puede eliminar al usuario root'}), 403

    if current_user.rol == 'admin' and usuario.rol != 'empleado':
        return jsonify({'error': 'Solo puedes eliminar usuarios con rol empleado'}), 403

    if usuario.id == current_user.id:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario eliminado'})


@usuarios_bp.route('/roles-disponibles', methods=['GET'])
@login_required
def roles_disponibles():
    """Devuelve los roles que el usuario actual puede asignar al crear un nuevo usuario."""
    return jsonify(current_user.roles_creables())
