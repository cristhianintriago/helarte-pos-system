"""
routes/productos.py
-------------------
Blueprint para la gestion del catalogo de productos y sabores del menu.

Operaciones disponibles (CRUD):
- GET    /productos/        -> Lista todos los productos activos.
- POST   /productos/        -> Crea un nuevo producto.
- POST   /productos/upload-imagen -> Sube una imagen a Cloudinary.
- PUT    /productos/<id>    -> Actualiza un producto existente.
- DELETE /productos/<id>    -> Elimina o archiva un producto.
- GET    /productos/sabores -> Lista todos los sabores.
- POST   /productos/sabores -> Crea un nuevo sabor.
- PUT    /productos/sabores/<id> -> Actualiza un sabor.

Conceptos importantes:
- Cloudinary: servicio de almacenamiento de imagenes en la nube. Se usa para
  guardar las fotos de los productos sin ocupar espacio en el servidor propio.
- Borrado logico (soft delete): cuando un producto tiene historial de ventas,
  no se borra de la base de datos (para no romper los reportes), sino que se
  marca como archivado. El catalogo operativo lo filtra automaticamente.
- Integridad referencial: antes de borrar un producto, se verifica que no tenga
  pedidos activos asociados para no dejar datos "huerfanos" en la base de datos.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models.models import db, Producto, Sabor
import cloudinary
import cloudinary.uploader
import os
import re
from sqlalchemy.exc import IntegrityError

productos_bp = Blueprint('productos', __name__, url_prefix='/productos')

# Valor especial que se usa como categoria de un producto archivado.
# Los productos con esta categoria se excluyen de todas las listas del sistema.
_CATEGORIA_ARCHIVADA = '__archivado__'

# Configuramos el cliente de Cloudinary usando variables de entorno.
# Las variables de entorno evitan poner credenciales sensibles directamente en el codigo.
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)


def _extraer_public_id_cloudinary(imagen_url):
    """
    Extrae el 'public_id' de una URL de Cloudinary para poder eliminar la imagen
    del servidor de Cloudinary cuando se borra un producto.

    Ejemplo:
    URL: https://res.cloudinary.com/demo/image/upload/v1234/helarte/copa-oreo.jpg
    public_id extraido: helarte/copa-oreo

    Se usa una expresion regular (regex) para encontrar la parte relevante de la URL.
    El patron busca todo lo que viene despues de '/upload/' ignorando el version tag.
    """
    if not imagen_url or 'res.cloudinary.com' not in imagen_url:
        return None

    # re.search busca el patron en cualquier parte del string.
    # El grupo de captura (.+) toma todo lo que hay despues del prefijo.
    match = re.search(r'/upload/(?:v\d+/)?(.+)$', imagen_url)
    if not match:
        return None

    ruta = match.group(1)
    # Removemos la extension del archivo (ej: .jpg) para obtener solo el public_id.
    return re.sub(r'\.[a-zA-Z0-9]+$', '', ruta)


@productos_bp.route('/', methods=['GET'])
def obtener_productos():
    """
    Retorna todos los productos activos del catalogo en formato JSON.
    Excluye los productos archivados (categoria == _CATEGORIA_ARCHIVADA).
    No requiere autenticacion para que el modulo de toma de pedidos pueda usarlo.
    """
    productos = Producto.query.filter(Producto.categoria != _CATEGORIA_ARCHIVADA).all()

    resultado = []
    for p in productos:
        resultado.append({
            'id':          p.id,
            'nombre':      p.nombre,
            'precio':      p.precio,
            'categoria':   p.categoria,
            'disponible':  p.disponible,
            'imagen_url':  p.imagen_url or '',
            'max_sabores': int(p.max_sabores or 1),
            # Solo incluimos los sabores que estan activos (no desactivados).
            'sabores': [{'id': s.id, 'nombre': s.nombre} for s in p.sabores if s.activo]
        })

    return jsonify(resultado)


@productos_bp.route('/', methods=['POST'])
@login_required
def crear_producto():
    """
    Crea un nuevo producto en el catalogo.
    Solo admin y root tienen permiso para modificar el catalogo.

    Validaciones de negocio:
    - max_sabores debe estar entre 1 y 5.
    - Si no hay sabores asignados, max_sabores debe ser 1.
    - max_sabores no puede superar la cantidad de sabores asignados.
    """
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403
    datos = request.json

    sabor_ids   = datos.get('sabor_ids') or []
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
        # Consultamos solo los sabores activos que esten en la lista de IDs enviada.
        sabores = Sabor.query.filter(Sabor.id.in_(sabor_ids), Sabor.activo.is_(True)).all()
        nuevo_producto.sabores = sabores

    db.session.add(nuevo_producto)
    db.session.commit()

    return jsonify({'mensaje': 'Producto creado correctamente', 'id': nuevo_producto.id}), 201


@productos_bp.route('/upload-imagen', methods=['POST'])
@login_required
def upload_imagen():
    """
    Sube una imagen al servicio de Cloudinary y retorna la URL publica.
    La URL se usa luego al crear o actualizar el producto.

    El archivo se sube como 'multipart/form-data' (no JSON), por eso usamos
    request.files en lugar de request.json.
    Cloudinary aplica una transformacion de recorte cuadrado (400x400 px).
    """
    # Verificamos que las credenciales de Cloudinary esten configuradas.
    if not all([
        os.environ.get('CLOUDINARY_CLOUD_NAME'),
        os.environ.get('CLOUDINARY_API_KEY'),
        os.environ.get('CLOUDINARY_API_SECRET')
    ]):
        return jsonify({
            'error': 'Cloudinary no esta configurado en el servidor (faltan variables de entorno).'
        }), 503

    if 'imagen' not in request.files:
        return jsonify({'error': 'No se envio ninguna imagen'}), 400

    archivo = request.files['imagen']
    if archivo.filename == '':
        return jsonify({'error': 'Archivo vacio'}), 400

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            folder='helarte',
            transformation=[
                # crop='fill' recorta la imagen para que quede exactamente de 400x400 px.
                {'width': 400, 'height': 400, 'crop': 'fill'}
            ]
        )
        return jsonify({'imagen_url': resultado['secure_url']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@productos_bp.route('/<int:producto_id>', methods=['PUT'])
@login_required
def actualizar_producto(producto_id):
    """
    Actualiza los datos de un producto existente.
    Solo se modifican los campos que vienen en el cuerpo JSON de la solicitud.
    Los campos no enviados conservan su valor actual.
    """
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403

    # get_or_404: si el producto no existe, Flask responde automaticamente con 404 Not Found.
    producto = Producto.query.get_or_404(producto_id)
    datos    = request.json

    producto.nombre      = datos.get('nombre',      producto.nombre)
    producto.precio      = datos.get('precio',      producto.precio)
    producto.categoria   = datos.get('categoria',   producto.categoria)
    producto.disponible  = datos.get('disponible',  producto.disponible)
    producto.imagen_url  = datos.get('imagen_url',  producto.imagen_url)
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


@productos_bp.route('/<int:producto_id>', methods=['DELETE'])
@login_required
def eliminar_producto(producto_id):
    """
    Elimina un producto del sistema, respetando la integridad historica de los datos.

    Flujo de decision:
    1. Si el producto tiene pedidos ACTIVOS: se rechaza la eliminacion (error 400).
    2. Si el producto tiene historial de ventas pasadas: se aplica borrado logico
       (queda como 'archivado', invisible en el catalogo pero visible en reportes).
    3. Si el producto no tiene historial alguno: se borra fisicamente de la BD
       y su imagen se elimina de Cloudinary.
    """
    from models.models import DetallePedido, Pedido

    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403

    producto             = Producto.query.get_or_404(producto_id)
    nombre_producto      = producto.nombre
    imagen_url_producto  = producto.imagen_url

    # Verificamos si hay pedidos en estado 'pendiente' o 'en_proceso' con este producto.
    pedidos_activos = db.session.query(DetallePedido).join(Pedido).filter(
        DetallePedido.producto_id == producto_id,
        Pedido.estado.in_(['pendiente', 'en_proceso'])
    ).count()

    if pedidos_activos > 0:
        return jsonify({
            'error': f'No se puede eliminar "{nombre_producto}" porque tiene {pedidos_activos} pedido(s) activo(s)'
        }), 400

    # Verificamos si tiene detalle en pedidos pasados (historial de ventas).
    historial_registros = db.session.query(DetallePedido).filter(
        DetallePedido.producto_id == producto_id
    ).count()

    if historial_registros > 0:
        # Borrado logico: el producto queda en la BD pero invisible para el sistema operativo.
        # Esto preserva la integridad de los reportes historicos.
        producto.disponible = False
        producto.imagen_url = ''
        producto.categoria  = _CATEGORIA_ARCHIVADA
        db.session.commit()
        return jsonify({
            'mensaje': f'"{nombre_producto}" tiene historial ({historial_registros} registros). Se elimino del catalogo operativo.'
        }), 200

    try:
        # Sin historial: borrado fisico.
        # Paso 1: limpiamos la relacion N:N con sabores antes de borrar.
        # Si no hacemos esto, la base de datos lanzara un error de integridad referencial.
        producto.sabores = []
        db.session.flush()  # flush() aplica el cambio en memoria sin hacer commit aun.

        # Paso 2: borramos el registro del producto.
        db.session.delete(producto)
        db.session.commit()

        # Paso 3: intentamos borrar la imagen de Cloudinary.
        # Si falla, no revertimos el borrado de BD (la imagen huerfana no es critica).
        public_id = _extraer_public_id_cloudinary(imagen_url_producto)
        if public_id:
            try:
                cloudinary.uploader.destroy(public_id, invalidate=True)
            except Exception:
                pass

        return jsonify({'mensaje': f'Producto "{nombre_producto}" eliminado'})

    except IntegrityError:
        # IntegrityError ocurre si la base de datos detecta una violacion de restricciones
        # (ej: una FK que no esperabamos). Hacemos rollback para cancelar la transaccion.
        db.session.rollback()
        return jsonify({
            'error': f'No se puede eliminar "{nombre_producto}" por integridad de datos (relaciones asociadas).'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error interno al eliminar producto: {str(e)}'}), 500


@productos_bp.route('/sabores', methods=['GET'])
@login_required
def listar_sabores():
    """Retorna todos los sabores del sistema, ordenados alfabeticamente."""
    sabores = Sabor.query.order_by(Sabor.nombre.asc()).all()
    return jsonify([
        {'id': s.id, 'nombre': s.nombre, 'activo': s.activo}
        for s in sabores
    ])


@productos_bp.route('/sabores', methods=['POST'])
@login_required
def crear_sabor():
    """
    Crea un nuevo sabor en el catalogo.
    Si el sabor ya existe pero esta inactivo, lo reactiva en lugar de crear uno duplicado.
    La busqueda es insensible a mayusculas/minusculas (usa db.func.lower para comparar).
    """
    if not current_user.puede_gestionar_productos():
        return jsonify({'error': 'Se requiere rol de administrador o superior'}), 403

    datos  = request.json or {}
    nombre = (datos.get('nombre') or '').strip()
    if not nombre:
        return jsonify({'error': 'El nombre del sabor es obligatorio'}), 400

    # Buscamos si ya existe un sabor con ese nombre (sin distinguir mayusculas).
    existente = Sabor.query.filter(db.func.lower(Sabor.nombre) == nombre.lower()).first()
    if existente:
        if not existente.activo:
            # Si existia pero estaba desactivado, lo reactivamos.
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
    """
    Actualiza el nombre o el estado activo/inactivo de un sabor.
    Si se desactiva un sabor, deja de aparecer en las opciones del modulo de pedidos.
    """
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
