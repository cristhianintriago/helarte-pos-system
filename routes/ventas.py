"""
routes/ventas.py
----------------
Blueprint para consultar las ventas registradas en el dia actual.

Este modulo es de solo lectura (GET): no crea ni modifica ventas.
Las ventas se crean automaticamente en routes/pedidos.py cuando se registra un pedido.
La razon de esta separacion es el principio de responsabilidad unica (SRP):
cada modulo tiene una sola funcion clara y bien definida.
"""

from flask import Blueprint, jsonify
from models.models import db, Venta, Pedido
from datetime import datetime, date


ventas_bp = Blueprint('ventas', __name__, url_prefix='/ventas')


@ventas_bp.route('/', methods=['GET'])
def obtener_ventas():
    """
    Retorna todas las ventas del dia actual con un resumen agregado.

    La consulta filtra por fecha usando db.func.date(), que extrae solo
    la parte de fecha (YYYY-MM-DD) del campo DateTime, ignorando la hora.
    Esto permite comparar fechas sin importar a que hora se hizo la venta.

    Respuesta JSON:
    - ventas: lista de ventas individuales.
    - total_pedidos: numero total de ventas del dia.
    - total_vendido: suma del monto de todas las ventas.
    - total_delivery: cantidad de pedidos de tipo delivery.
    - total_local: cantidad de pedidos de tipo local/mesa.
    """
    hoy = date.today()

    # Filtramos las ventas cuya fecha (sin hora) sea igual a hoy.
    ventas = Venta.query.filter(
        db.func.date(Venta.fecha) == hoy
    ).all()

    lista = []
    total_vendido = 0
    total_delivery = 0
    total_local = 0

    # Iteramos cada venta para construir el resumen y la lista de respuesta.
    for v in ventas:
        total_vendido += v.total

        # Contamos por tipo de pedido para la estadistica del dia.
        if v.pedido.tipo == 'delivery':
            total_delivery += 1
        else:
            total_local += 1

        lista.append({
            'id': v.id,
            'cliente': v.pedido.cliente_nombre,
            'tipo': v.pedido.tipo,
            'total': v.total,
            # strftime('%H:%M') formatea la hora como "14:30" (hora:minuto).
            'fecha': v.fecha.strftime('%H:%M')
        })

    return jsonify({
        'ventas': lista,
        'total_pedidos': len(lista),
        'total_vendido': total_vendido,
        'total_delivery': total_delivery,
        'total_local': total_local
    })
