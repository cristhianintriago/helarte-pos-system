from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models.usuario import Usuario
from models.models import db
import hashlib

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

def hashear(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Decorador personalizado: verifica dinámicamente si el usuario actual ('current_user') 
# tiene o no el rol 'root' requerido, antes de dejarle accesar a la función decorada.
def solo_root(f):
    from functools import wraps
    @wraps(f)
    def decorador(*args, **kwargs):
        if not current_user.es_root():
            return jsonify({'error': 'No tienes permisos para esta acción'}), 403
        return f(*args, **kwargs)
    return decorador


@usuarios_bp.route('/', methods=['GET'])
@login_required
@solo_root
def listar():
    return render_template('usuarios.html')


@usuarios_bp.route('/api', methods=['GET'])
@login_required
@solo_root
def api_listar():
    usuarios = Usuario.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'rol': u.rol
    } for u in usuarios])


@usuarios_bp.route('/api', methods=['POST'])
@login_required
@solo_root
def crear():
    datos = request.json

    if Usuario.query.filter_by(username=datos['username']).first():
        return jsonify({'error': 'El usuario ya existe'}), 400

    # Root no puede ser creado desde el panel, solo existe uno
    if datos['rol'] == 'root':
        return jsonify({'error': 'No se puede crear otro usuario root'}), 400

    nuevo = Usuario(
        username=datos['username'],
        password=hashear(datos['password']),
        rol=datos['rol']
    )
    db.session.add(nuevo)
    db.session.commit()

    return jsonify({'mensaje': f'Usuario {nuevo.username} creado'}), 201


@usuarios_bp.route('/api/<int:usuario_id>', methods=['PUT'])
@login_required
@solo_root
def editar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)
    datos = request.json

    # No se puede modificar al root
    if usuario.rol == 'root':
        return jsonify({'error': 'No se puede modificar al usuario root'}), 403

    usuario.username = datos.get('username', usuario.username)
    usuario.rol = datos.get('rol', usuario.rol)

    if datos.get('password'):
        usuario.password = hashear(datos['password'])

    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado'})


@usuarios_bp.route('/api/<int:usuario_id>', methods=['DELETE'])
@login_required
@solo_root
def eliminar(usuario_id):
    usuario = Usuario.query.get_or_404(usuario_id)

    if usuario.rol == 'root':
        return jsonify({'error': 'No se puede eliminar al usuario root'}), 403

    if usuario.id == current_user.id:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 400

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({'mensaje': 'Usuario eliminado'})
