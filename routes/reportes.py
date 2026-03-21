from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import func

from models.models import DetallePedido, Producto, Venta, db


reportes_bp = Blueprint("reportes", __name__, url_prefix="/reportes")


@reportes_bp.route("/", methods=["GET"])
@login_required
def obtener_reporte():
    desde_str = request.args.get("desde")
    hasta_str = request.args.get("hasta")

    desde = datetime.strptime(desde_str, "%Y-%m-%d")
    hasta = datetime.strptime(hasta_str, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59
    )

    ventas = Venta.query.filter(Venta.fecha >= desde, Venta.fecha <= hasta).all()
    total_vendido = sum(venta.total for venta in ventas)

    ventas_por_dia = (
        db.session.query(
            func.date(Venta.fecha).label("fecha"),
            func.count(Venta.id).label("cantidad"),
            func.sum(Venta.total).label("total"),
        )
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .group_by(func.date(Venta.fecha))
        .order_by(func.date(Venta.fecha).desc())
        .all()
    )

    top_productos = (
        db.session.query(
            Producto.nombre,
            func.sum(DetallePedido.cantidad).label("cantidad"),
        )
        .join(DetallePedido)
        .join(Venta, DetallePedido.pedido_id == Venta.pedido_id)
        .filter(Venta.fecha >= desde, Venta.fecha <= hasta)
        .group_by(Producto.nombre)
        .order_by(func.sum(DetallePedido.cantidad).desc())
        .limit(5)
        .all()
    )

    return jsonify(
        {
            "total_pedidos": len(ventas),
            "total_vendido": total_vendido,
            "producto_top": top_productos[0].nombre if top_productos else None,
            "ventas_por_dia": [
                {
                    "fecha": str(venta.fecha),
                    "cantidad": venta.cantidad,
                    "total": float(venta.total),
                }
                for venta in ventas_por_dia
            ],
            "top_productos": [
                {"nombre": producto.nombre, "cantidad": int(producto.cantidad)}
                for producto in top_productos
            ],
        }
    )
