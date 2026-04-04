"""
routes/ventas.py
----------------
Blueprint para consultar las ventas registradas en el dia actual.

Este modulo es de solo lectura (GET): no crea ni modifica ventas.
Las ventas se crean automaticamente en routes/pedidos.py cuando se registra un pedido.
La razon de esta separacion es el principio de responsabilidad unica (SRP):
cada modulo tiene una sola funcion clara y bien definida.
"""

from flask import Blueprint, jsonify, render_template
from flask_login import login_required
from models.models import db, Venta, Pedido
from datetime import datetime, date
import pytz
# Zona horaria de Ecuador (UTC-5, sin cambio de horario de verano)
ZONA_HORARIA_LOCAL = pytz.timezone('America/Guayaquil')

def a_hora_local(fecha_utc):
    """Convierte una fecha guardada en UTC a la hora local de Ecuador."""
    if fecha_utc is None:
        return None
    # Le decimos a Python que la fecha es UTC primero
    fecha_con_zona = pytz.utc.localize(fecha_utc)
    # Luego la convertimos a Ecuador
    return fecha_con_zona.astimezone(ZONA_HORARIA_LOCAL)


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
    # Obtenemos la fecha de HOY segun la hora local de Ecuador (no la hora UTC del servidor)
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy = ahora_local.date()

    # Construimos el rango del dia EN HORA UTC para comparar contra la BD
    # porque la BD guarda todo en UTC
    inicio_hoy_local = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0))
    fin_hoy_local    = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59))
    inicio_hoy_utc   = inicio_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)
    fin_hoy_utc      = fin_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)

    # Filtramos las ventas que cayeron dentro del dia de hoy en hora Ecuador
    ventas = Venta.query.filter(
        Venta.fecha >= inicio_hoy_utc,
        Venta.fecha <= fin_hoy_utc
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
            # Convertimos de UTC a hora local de Ecuador antes de mostrar
            'fecha': a_hora_local(v.fecha).strftime('%H:%M')
        })

    return jsonify({
        'ventas': lista,
        'total_pedidos': len(lista),
        'total_vendido': total_vendido,
        'total_delivery': total_delivery,
        'total_local': total_local
    })
