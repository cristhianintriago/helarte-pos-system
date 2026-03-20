from flask import Blueprint, jsonify
from models.models import db, Venta, Pedido  # ← agrega db aquí
from datetime import datetime, date


ventas_bp = Blueprint('ventas', __name__, url_prefix='/ventas')


@ventas_bp.route('/', methods=['GET'])
def obtener_ventas():
    """ Lista e itera en un ciclo común las ventas del día actual """
    hoy = date.today()
    ventas = Venta.query.filter(
        db.func.date(Venta.fecha) == hoy
    ).all()

    lista = []
    total_vendido = 0
    total_delivery = 0
    total_local = 0

    for v in ventas:
        total_vendido += v.total
        if v.pedido.tipo == 'delivery':
            total_delivery += 1
        else:
            total_local += 1

        lista.append({
            'id': v.id,
            'cliente': v.pedido.cliente_nombre,
            'tipo': v.pedido.tipo,
            'total': v.total,
            'fecha': v.fecha.strftime('%H:%M')
        })

    return jsonify({
        'ventas': lista,
        'total_pedidos': len(lista),
        'total_vendido': total_vendido,
        'total_delivery': total_delivery,
        'total_local': total_local
    })
