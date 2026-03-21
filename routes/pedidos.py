from flask import Blueprint, jsonify, request
from flask_login import login_required

from models.models import Caja, DetallePedido, Pedido, Producto, Venta, db


pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


@pedidos_bp.route("/", methods=["GET"])
@login_required
def obtener_pedidos():
    pedidos = Pedido.query.filter(Pedido.estado != "entregado").all()

    resultado = []
    for pedido in pedidos:
        detalles = [
            {
                "producto": detalle.producto.nombre,
                "cantidad": detalle.cantidad,
                "subtotal": detalle.subtotal,
            }
            for detalle in pedido.detalles
        ]

        resultado.append(
            {
                "id": pedido.id,
                "tipo": pedido.tipo,
                "cliente_nombre": pedido.cliente_nombre,
                "cliente_telefono": pedido.cliente_telefono,
                "cliente_direccion": pedido.cliente_direccion,
                "estado": pedido.estado,
                "total": pedido.total,
                "forma_pago": pedido.forma_pago,
                "fecha": pedido.fecha.strftime("%Y-%m-%d %H:%M"),
                "detalles": detalles,
            }
        )

    return jsonify(resultado)


@pedidos_bp.route("/", methods=["POST"])
@login_required
def crear_pedido():
    datos = request.get_json() or {}

    nuevo_pedido = Pedido(
        tipo=datos["tipo"],
        cliente_nombre=datos.get("cliente_nombre", "Consumidor final"),
        cliente_telefono=datos.get("cliente_telefono"),
        cliente_direccion=datos.get("cliente_direccion"),
        forma_pago=datos.get("forma_pago", "efectivo"),
    )

    db.session.add(nuevo_pedido)
    db.session.flush()

    total = 0
    for item in datos["productos"]:
        producto = Producto.query.get(item["producto_id"])

        if not producto or not producto.disponible:
            return jsonify({"error": "Producto no disponible"}), 400

        subtotal = producto.precio * item["cantidad"]
        total += subtotal

        detalle = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=producto.id,
            cantidad=item["cantidad"],
            subtotal=subtotal,
        )
        db.session.add(detalle)

    nuevo_pedido.total = total
    db.session.commit()

    return (
        jsonify(
            {
                "mensaje": "Pedido creado correctamente",
                "id": nuevo_pedido.id,
                "total": total,
            }
        ),
        201,
    )


@pedidos_bp.route("/<int:pedido_id>/estado", methods=["PUT"])
@login_required
def cambiar_estado(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    datos = request.get_json() or {}
    nuevo_estado = datos["estado"]

    pedido.estado = nuevo_estado

    if nuevo_estado == "entregado":
        venta = Venta(
            pedido_id=pedido.id,
            total=pedido.total,
            forma_pago=pedido.forma_pago,
        )
        db.session.add(venta)

        caja_abierta = Caja.query.filter_by(estado="abierta").first()
        if caja_abierta:
            caja_abierta.total_ingresos += pedido.total
            if pedido.forma_pago == "efectivo":
                caja_abierta.total_efectivo += pedido.total
            elif pedido.forma_pago == "transferencia":
                caja_abierta.total_transferencia += pedido.total
            elif pedido.forma_pago == "mixto":
                mitad = pedido.total / 2
                caja_abierta.total_efectivo += mitad
                caja_abierta.total_transferencia += mitad

    db.session.commit()
    return jsonify({"mensaje": f"Estado actualizado a {nuevo_estado}"})
