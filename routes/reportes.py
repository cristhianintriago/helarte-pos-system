from flask import Blueprint, jsonify, request
from models.models import db, Venta, DetallePedido, Producto
from datetime import datetime
from sqlalchemy import func

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

@reportes_bp.route('/', methods=['GET'])
def obtener_reporte():
    # Recibimos las fechas como parámetros de la URL
    desde_str = request.args.get('desde')
    hasta_str = request.args.get('hasta')

    # Convertimos strings a fechas
    desde = datetime.strptime(desde_str, '%Y-%m-%d')
    hasta = datetime.strptime(hasta_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    # Ventas en el rango de fechas
    ventas = Venta.query.filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).all()

    total_vendido = sum(v.total for v in ventas)

    # Ventas agrupadas por día
    ventas_por_dia = db.session.query(
        func.date(Venta.fecha).label('fecha'),
        func.count(Venta.id).label('cantidad'),
        func.sum(Venta.total).label('total')
    ).filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).group_by(func.date(Venta.fecha)).order_by(func.date(Venta.fecha).desc()).all()

    # Productos más vendidos
    top_productos = db.session.query(
        Producto.nombre,
        func.sum(DetallePedido.cantidad).label('cantidad')
    ).join(DetallePedido).join(Venta, DetallePedido.pedido_id == Venta.pedido_id).filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc()).limit(5).all()

    return jsonify({
        'total_pedidos': len(ventas),
        'total_vendido': total_vendido,
        'producto_top': top_productos[0].nombre if top_productos else None,
        'ventas_por_dia': [
            {'fecha': str(v.fecha), 'cantidad': v.cantidad, 'total': float(v.total)}
            for v in ventas_por_dia
        ],
        'top_productos': [
            {'nombre': p.nombre, 'cantidad': int(p.cantidad)}
            for p in top_productos
        ]
    })
