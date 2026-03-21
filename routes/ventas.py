from datetime import date

from flask import Blueprint, jsonify
from flask_login import login_required

from models.models import Venta, db


ventas_bp = Blueprint("ventas", __name__, url_prefix="/ventas")


@ventas_bp.route("/", methods=["GET"])
@login_required
def obtener_ventas():
    ventas = Venta.query.filter(db.func.date(Venta.fecha) == date.today()).all()

    lista = []
    total_vendido = 0
    total_delivery = 0
    total_local = 0

    for venta in ventas:
        total_vendido += venta.total
        if venta.pedido.tipo == "delivery":
            total_delivery += 1
        else:
            total_local += 1

        lista.append(
            {
                "id": venta.id,
                "cliente": venta.pedido.cliente_nombre,
                "tipo": venta.pedido.tipo,
                "total": venta.total,
                "fecha": venta.fecha.strftime("%H:%M"),
            }
        )

    return jsonify(
        {
            "ventas": lista,
            "total_pedidos": len(lista),
            "total_vendido": total_vendido,
            "total_delivery": total_delivery,
            "total_local": total_local,
        }
    )
