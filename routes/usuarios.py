"""
routes/usuarios.py
------------------
Blueprint para la gestion de cuentas de usuario del sistema.

Conceptos importantes de este modulo:

1. Decoradores personalizados: Python permite crear "wrappers" de funciones para
   reutilizar logica de autorizacion. En lugar de repetir el chequeo de rol en
   cada ruta, se define una sola vez en un decorador (ej: @solo_root, @admin_o_superior).

2. Hash de contrasenas: las contrasenas NUNCA se guardan en texto plano.
   Se usa SHA-256 (hashlib) para generar un string irreversible. Si la base de
   datos fuera comprometida, el atacante no podria leer las contrasenas directamente.

3. Jerarquia de roles:
   - root: puede crear/editar/eliminar admins y empleados.
   - admin: solo puede gestionar empleados.
   - empleado: no puede gestionar usuarios.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.usuario import Usuario
from models.models import db
import hashlib

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')


def hashear(password):
    """
    Genera un hash SHA-256 de la contrasena recibida.
    encode() convierte el string a bytes (requerido por hashlib).
    hexdigest() devuelve el hash en formato hexadecimal legible.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def solo_root(f):
    """
    Decorador de autorizacion: solo permite acceso al usuario con rol 'root'.
    Si el usuario actual no es root, responde con error 403 (Acceso Denegado).

    El patron 'from functools import wraps' preserva el nombre y docstring de
    la funcion original, lo cual es importante para Flask al registrar las rutas.
    """
    from functools import wraps

    @wraps(f)
    def decorador(*args, **kwargs):
        if not current_user.es_root():
            return jsonify({'error': 'No tienes permisos para esta accion'}), 403
        return f(*args, **kwargs)
    return decorador


def admin_o_superior(f):
    """
    Decorador de autorizacion: permite acceso a admin y root.
    Los empleados son rechazados con error 403.
    """
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
    """Renderiza la vista HTML de gestion de usuarios (solo para admin y root)."""
    from flask import render_template
    return render_template('usuarios.html')


@usuarios_bp.route('/api', methods=['GET'])
@login_required
@admin_o_superior
def api_listar():
    """Retorna la lista de todos los usuarios en formato JSON para el frontend."""
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
    Crea un nuevo usuario en el sistema.
    Las reglas de la jerarquia determinan que roles puede crear cada tipo de usuario:
    - root puede crear admins y empleados.
    - admin solo puede crear empleados.
    - No se puede crear otro usuario root (solo puede existir uno).
    """
    if not current_user.puede_crear_usuarios():
        return jsonify({'error': 'No tienes permisos para crear usuarios'}), 403

    datos = request.json
    rol_solicitado = datos.get('rol', 'empleado')

    # Proteccion de integridad: no se puede crear un segundo superusuario root.
    if rol_solicitado == 'root':
        return jsonify({'error': 'No se puede crear otro usuario root'}), 400

    # Verificamos que el rol solicitado este dentro de los que puede asignar el usuario actual.
    if rol_solicitado not in current_user.roles_creables():
        return jsonify({'error': f'No puedes crear usuarios con rol "{rol_solicitado}"'}), 403

    # Verificamos que el nombre de usuario no este ya en uso.
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
    """
    Actualiza los datos de un usuario existente.
    Restricciones:
    - No se puede modificar al usuario root.
    - Un admin solo puede modificar empleados, no a otros admins.
    """
    usuario = Usuario.query.get_or_404(usuario_id)
    datos = request.json

    if usuario.rol == 'root':
        return jsonify({'error': 'No se puede modificar al usuario root'}), 403

    if current_user.rol == 'admin' and usuario.rol != 'empleado':
        return jsonify({'error': 'Solo puedes modificar usuarios con rol empleado'}), 403

    # Actualizamos solo los campos que vienen en el cuerpo de la solicitud.
    # El patron datos.get('campo', valor_actual) mantiene el valor vigente si no se envia.
    usuario.username = datos.get('username', usuario.username)
    usuario.rol      = datos.get('rol', usuario.rol)

    # Solo actualizamos la contrasena si se envio una nueva en la solicitud.
    if datos.get('password'):
        usuario.password = hashear(datos['password'])

    db.session.commit()
    return jsonify({'mensaje': 'Usuario actualizado'})


@usuarios_bp.route('/api/<int:usuario_id>', methods=['DELETE'])
@login_required
@admin_o_superior
def eliminar(usuario_id):
    """
    Elimina un usuario del sistema.
    Restricciones:
    - No se puede eliminar al usuario root.
    - Un admin solo puede eliminar empleados.
    - Un usuario no puede eliminarse a si mismo.
    """
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
    """Retorna los roles que el usuario actual puede asignar al crear una nueva cuenta."""
    return jsonify(current_user.roles_creables())
