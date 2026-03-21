import os

import cloudinary
import cloudinary.uploader
from flask import Blueprint, jsonify, request
from flask_login import login_required

from core.decorators import admin_required
from models.models import Producto, db


productos_bp = Blueprint("productos", __name__, url_prefix="/productos")

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)


@productos_bp.route("/", methods=["GET"])
@login_required
def obtener_productos():
    productos = Producto.query.all()

    return jsonify(
        [
            {
                "id": producto.id,
                "nombre": producto.nombre,
                "precio": producto.precio,
                "categoria": producto.categoria,
                "disponible": producto.disponible,
                "imagen_url": producto.imagen_url or "",
            }
            for producto in productos
        ]
    )


@productos_bp.route("/", methods=["POST"])
@admin_required
def crear_producto():
    datos = request.get_json() or {}

    nuevo_producto = Producto(
        nombre=datos["nombre"],
        precio=datos["precio"],
        categoria=datos["categoria"],
        disponible=datos.get("disponible", True),
        imagen_url=datos.get("imagen_url", ""),
    )

    db.session.add(nuevo_producto)
    db.session.commit()

    return (
        jsonify({"mensaje": "Producto creado correctamente", "id": nuevo_producto.id}),
        201,
    )


@productos_bp.route("/upload-imagen", methods=["POST"])
@login_required
def upload_imagen():
    if "imagen" not in request.files:
        return jsonify({"error": "No se envió ninguna imagen"}), 400

    archivo = request.files["imagen"]
    if archivo.filename == "":
        return jsonify({"error": "Archivo vacío"}), 400

    try:
        resultado = cloudinary.uploader.upload(
            archivo,
            folder="helarte",
            transformation=[{"width": 400, "height": 400, "crop": "fill"}],
        )
        return jsonify({"imagen_url": resultado["secure_url"]})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@productos_bp.route("/<int:producto_id>", methods=["PUT"])
@admin_required
def actualizar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    datos = request.get_json() or {}

    producto.nombre = datos.get("nombre", producto.nombre)
    producto.precio = datos.get("precio", producto.precio)
    producto.categoria = datos.get("categoria", producto.categoria)
    producto.disponible = datos.get("disponible", producto.disponible)
    producto.imagen_url = datos.get("imagen_url", producto.imagen_url)

    db.session.commit()
    return jsonify({"mensaje": "Producto actualizado correctamente"})


@productos_bp.route("/<int:producto_id>", methods=["DELETE"])
@admin_required
def eliminar_producto(producto_id):
    from models.models import DetallePedido, Pedido

    producto = Producto.query.get_or_404(producto_id)

    pedidos_activos = db.session.query(DetallePedido).join(Pedido).filter(
        DetallePedido.producto_id == producto_id,
        Pedido.estado.in_(["pendiente", "en_proceso"]),
    ).count()

    if pedidos_activos > 0:
        return (
            jsonify(
                {
                    "error": (
                        f'No se puede eliminar "{producto.nombre}" porque tiene '
                        f"{pedidos_activos} pedido(s) activo(s)"
                    )
                }
            ),
            400,
        )

    db.session.delete(producto)
    db.session.commit()
    return jsonify({"mensaje": f'Producto "{producto.nombre}" eliminado'})
