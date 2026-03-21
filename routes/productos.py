from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.models import db, Producto, Sabor
import cloudinary
import cloudinary.uploader
import os

productos_bp = Blueprint('productos', __name__, url_prefix='/productos')

# ── Configuración de Cloudinary desde variables de entorno
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)


# ==========================================
# GET /productos/ -> Retorna todos los productos
# ==========================================
@productos_bp.route('/', methods=['GET'])
def obtener_productos():
    """ 
    Obtiene todos los productos de la base de datos utilizando SQLAlchemy (orm).
    Retorna un arreglo JSON listo para ser consumido por el frontend.
    """
    productos = Producto.query.all()

    resultado = []
    for p in productos:
        resultado.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio': p.precio,
            'categoria': p.categoria,
            'disponible': p.disponible,
            'imagen_url': p.imagen_url or '',
            'max_sabores': int(p.max_sabores or 1),
            'sabores': [{'id': s.id, 'nombre': s.nombre} for s in p.sabores if s.activo]
        })

    return jsonify(resultado)


# ==========================================
# POST /productos/ → Crea un nuevo producto
# ==========================================
@productos_bp.route('/', methods=['POST'])
@login_required
def crear_producto():
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403
    datos = request.json

    sabor_ids = datos.get('sabor_ids') or []
    max_sabores = int(datos.get('max_sabores') or 1)

    if max_sabores < 1 or max_sabores > 5:
        return jsonify({'error': 'El limite de sabores por producto debe estar entre 1 y 5'}), 400

    if not sabor_ids and max_sabores != 1:
        return jsonify({'error': 'Si no hay sabores asignados, el limite debe ser 1'}), 400

    if sabor_ids and max_sabores > len(sabor_ids):
        return jsonify({'error': 'El limite no puede ser mayor al numero de sabores asignados'}), 400

    nuevo_producto = Producto(
        nombre=datos['nombre'],
        precio=datos['precio'],
        categoria=datos['categoria'],
        disponible=datos.get('disponible', True),
        imagen_url=datos.get('imagen_url', ''),
        max_sabores=max_sabores
    )

    if sabor_ids:
        sabores = Sabor.query.filter(Sabor.id.in_(sabor_ids), Sabor.activo.is_(True)).all()
        nuevo_producto.sabores = sabores

    db.session.add(nuevo_producto)
    db.session.commit()

    return jsonify({'mensaje': 'Producto creado correctamente', 'id': nuevo_producto.id}), 201


# ==========================================
# POST /productos/upload-imagen → Sube imagen a Cloudinary
# ==========================================
@productos_bp.route('/upload-imagen', methods=['POST'])
@login_required
def upload_imagen():
    if not all([
        os.environ.get('CLOUDINARY_CLOUD_NAME'),
        os.environ.get('CLOUDINARY_API_KEY'),
        os.environ.get('CLOUDINARY_API_SECRET')
    ]):
        return jsonify({
            'error': 'Cloudinary no esta configurado en el servidor (faltan variables de entorno).'
        }), 503

    if 'imagen' not in request.files:
        return jsonify({'error': 'No se envió ninguna imagen'}), 400

    archivo = request.files['imagen']
    if archivo.filename == '':
        return jsonify({'error': 'Archivo vacío'}), 400

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            folder='helarte',        # Carpeta en Cloudinary
            transformation=[
                {'width': 400, 'height': 400, 'crop': 'fill'}  # Recorte cuadrado
            ]
        )
        return jsonify({'imagen_url': resultado['secure_url']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================
# PUT /productos/<id> → Actualiza un producto existente
# ==========================================
@productos_bp.route('/<int:producto_id>', methods=['PUT'])
@login_required
def actualizar_producto(producto_id):
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403
    producto = Producto.query.get_or_404(producto_id)
    datos = request.json

    producto.nombre = datos.get('nombre', producto.nombre)
    producto.precio = datos.get('precio', producto.precio)
    producto.categoria = datos.get('categoria', producto.categoria)
    producto.disponible = datos.get('disponible', producto.disponible)
    producto.imagen_url = datos.get('imagen_url', producto.imagen_url)
    producto.max_sabores = int(datos.get('max_sabores') or producto.max_sabores or 1)

    if producto.max_sabores < 1 or producto.max_sabores > 5:
        return jsonify({'error': 'El limite de sabores por producto debe estar entre 1 y 5'}), 400

    if 'sabor_ids' in datos:
        sabor_ids = datos.get('sabor_ids') or []
        sabores = Sabor.query.filter(Sabor.id.in_(sabor_ids), Sabor.activo.is_(True)).all() if sabor_ids else []

        if not sabores and producto.max_sabores != 1:
            return jsonify({'error': 'Si no hay sabores asignados, el limite debe ser 1'}), 400

        if sabores and producto.max_sabores > len(sabores):
            return jsonify({'error': 'El limite no puede ser mayor al numero de sabores asignados'}), 400

        producto.sabores = sabores

    db.session.commit()
    return jsonify({'mensaje': 'Producto actualizado correctamente'})


# ==========================================
# DELETE /productos/<id> → Elimina un producto
# ==========================================
@productos_bp.route('/<int:producto_id>', methods=['DELETE'])
@login_required
def eliminar_producto(producto_id):
    from models.models import DetallePedido, Pedido

    producto = Producto.query.get_or_404(producto_id)

    pedidos_activos = db.session.query(DetallePedido).join(Pedido).filter(
        DetallePedido.producto_id == producto_id,
        Pedido.estado.in_(['pendiente', 'en_proceso'])
    ).count()

    if pedidos_activos > 0:
        return jsonify({
            'error': f'No se puede eliminar "{producto.nombre}" porque tiene {pedidos_activos} pedido(s) activo(s)'
        }), 400

    db.session.delete(producto)
    db.session.commit()
    return jsonify({'mensaje': f'Producto "{producto.nombre}" eliminado'})


@productos_bp.route('/sabores', methods=['GET'])
@login_required
def listar_sabores():
    sabores = Sabor.query.order_by(Sabor.nombre.asc()).all()
    return jsonify([
        {'id': s.id, 'nombre': s.nombre, 'activo': s.activo}
        for s in sabores
    ])


@productos_bp.route('/sabores', methods=['POST'])
@login_required
def crear_sabor():
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403

    datos = request.json or {}
    nombre = (datos.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre del sabor es obligatorio'}), 400

    existente = Sabor.query.filter(db.func.lower(Sabor.nombre) == nombre.lower()).first()
    if existente:
        if not existente.activo:
            existente.activo = True
            db.session.commit()
        return jsonify({'id': existente.id, 'nombre': existente.nombre, 'activo': existente.activo}), 200

    sabor = Sabor(nombre=nombre, activo=True)
    db.session.add(sabor)
    db.session.commit()
    return jsonify({'id': sabor.id, 'nombre': sabor.nombre, 'activo': sabor.activo}), 201


@productos_bp.route('/sabores/<int:sabor_id>', methods=['PUT'])
@login_required
def actualizar_sabor(sabor_id):
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403

    sabor = Sabor.query.get_or_404(sabor_id)
    datos = request.json or {}

    if 'nombre' in datos:
        nombre = (datos.get('nombre') or '').strip()
        if not nombre:
            return jsonify({'error': 'El nombre del sabor es obligatorio'}), 400
        sabor.nombre = nombre

    if 'activo' in datos:
        sabor.activo = bool(datos.get('activo'))

    db.session.commit()
    return jsonify({'id': sabor.id, 'nombre': sabor.nombre, 'activo': sabor.activo})
