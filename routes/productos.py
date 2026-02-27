# Blueprint es el sistema de Flask para modularizar rutas
# igual que los Cogs en discord.py
from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.models import db, Producto

# Creamos el blueprint de productos con su prefijo de URL
productos_bp = Blueprint('productos', __name__, url_prefix='/productos')


# ==========================================
# GET /productos/ → Retorna todos los productos
# ==========================================
@productos_bp.route('/', methods=['GET'])
def obtener_productos():
    # Consultamos todos los productos de la base de datos
    productos = Producto.query.all()

    # Convertimos cada objeto Python a un diccionario para enviarlo como JSON
    resultado = []
    for p in productos:
        resultado.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio': p.precio,
            'categoria': p.categoria,
            'disponible': p.disponible
        })

    return jsonify(resultado)


# ==========================================
# POST /productos/ → Crea un nuevo producto
# ==========================================
@productos_bp.route('/', methods=['POST'])
def crear_producto():
    # request.json contiene los datos enviados desde el frontend
    datos = request.json

    nuevo_producto = Producto(
        nombre=datos['nombre'],
        precio=datos['precio'],
        categoria=datos['categoria'],
        disponible=datos.get('disponible', True)  # Si no se envía, por defecto True
    )

    db.session.add(nuevo_producto)   # Preparamos la inserción
    db.session.commit()              # Guardamos en la base de datos

    return jsonify({'mensaje': 'Producto creado correctamente ✅', 'id': nuevo_producto.id}), 201


# ==========================================
# PUT /productos/<id> → Actualiza un producto existente
# ==========================================
@productos_bp.route('/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    # Buscamos el producto, si no existe retorna error 404 automáticamente
    producto = Producto.query.get_or_404(producto_id)
    datos = request.json

    # Actualizamos solo los campos que vengan en la petición
    producto.nombre = datos.get('nombre', producto.nombre)
    producto.precio = datos.get('precio', producto.precio)
    producto.categoria = datos.get('categoria', producto.categoria)
    producto.disponible = datos.get('disponible', producto.disponible)

    db.session.commit()  # Guardamos los cambios

    return jsonify({'mensaje': 'Producto actualizado correctamente ✅'})


# ==========================================
# DELETE /productos/<id> → Elimina un producto
# ==========================================
@productos_bp.route('/<int:producto_id>', methods=['DELETE'])
@login_required
def eliminar_producto(producto_id):
    from models.models import DetallePedido, Pedido

    producto = Producto.query.get_or_404(producto_id)

    # Verifica si tiene pedidos activos (pendiente o en proceso)
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
    return jsonify({'mensaje': f'Producto "{producto.nombre}" eliminado ✅'})

