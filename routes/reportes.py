from flask import Blueprint, jsonify, request, Response, send_file
from flask_login import login_required, current_user
from models.models import db, Venta, DetallePedido, Producto
from datetime import datetime, date, time
from sqlalchemy import func
from io import StringIO, BytesIO
import csv

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')


# ==========================================
# HELPERS DE RANGO Y CONSULTA
# ==========================================
def _rango_fechas(desde_str, hasta_str):
    """Normaliza rango de fechas; si no se envía, usa el día actual."""
    hoy = date.today()
    desde_str = desde_str or hoy.strftime('%Y-%m-%d')
    hasta_str = hasta_str or hoy.strftime('%Y-%m-%d')
    desde = datetime.strptime(desde_str, '%Y-%m-%d')
    hasta = datetime.strptime(hasta_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    return desde, hasta


@reportes_bp.route('/', methods=['GET'])
@login_required
def obtener_reporte():
    """
    Construye las estadísticas que alimentan el Dashboard.
    Usa el motor de agregación de SQLAlchemy (func.date, func.count, func.sum)
    simulando comportamientos nativos de SQL avanzado como 'GROUP BY'.
    Accesible por todos los roles (empleado, admin, root).
    """
    desde_str = request.args.get('desde')
    hasta_str = request.args.get('hasta')

    desde, hasta = _rango_fechas(desde_str, hasta_str)

    # Ventas detalladas para metricas de resumen.
    ventas = Venta.query.filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).all()

    total_vendido = sum(v.total for v in ventas)

    # Cross-platform date grouping: SQLite uses func.date, Postgres uses db.cast
    is_sqlite = 'sqlite' in str(db.engine.url)
    date_expr = func.date(Venta.fecha) if is_sqlite else db.cast(Venta.fecha, db.Date)

    # Serie temporal agregada para graficos del dashboard.
    ventas_por_dia = db.session.query(
        date_expr.label('fecha'),
        func.count(Venta.id).label('cantidad'),
        func.sum(Venta.total).label('total')
    ).filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).group_by(date_expr).order_by(date_expr.desc()).all()

    # Ranking de productos mas vendidos en el rango.
    top_productos = db.session.query(
        Producto.nombre,
        func.sum(DetallePedido.cantidad).label('cantidad')
    ).join(DetallePedido).join(Venta, DetallePedido.pedido_id == Venta.pedido_id).filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc()).limit(5).all()

    # Desglose de Pagos
    efectivo = sum(v.total for v in ventas if v.forma_pago == 'Efectivo')
    transferencia = sum(v.total for v in ventas if v.forma_pago == 'Transferencia')

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
        ],
        'desglose_pagos': {
            'efectivo': float(efectivo),
            'transferencia': float(transferencia)
        }
    })


@reportes_bp.route('/dashboard-hoy', methods=['GET'])
@login_required
def dashboard_hoy():
    """Devuelve resumen del día y serie de ventas por hora para gráficos."""
    inicio = datetime.combine(date.today(), time.min)
    fin = datetime.combine(date.today(), time.max)
    ventas_hoy = Venta.query.filter(Venta.fecha >= inicio, Venta.fecha <= fin).all()

    labels = [f"{h:02d}:00" for h in range(24)]
    ventas_por_hora = [0.0] * 24
    tickets_por_hora = [0] * 24

    for venta in ventas_hoy:
        hora = venta.fecha.hour
        ventas_por_hora[hora] += float(venta.total)
        tickets_por_hora[hora] += 1

    return jsonify({
        'fecha': date.today().strftime('%Y-%m-%d'),
        'total_vendido_hoy': round(sum(ventas_por_hora), 2),
        'total_tickets_hoy': len(ventas_hoy),
        'labels': labels,
        'ventas_por_hora': [round(v, 2) for v in ventas_por_hora],
        'tickets_por_hora': tickets_por_hora,
    })


def _obtener_ventas_rango(desde_str, hasta_str):
    # Reutilizado por exportadores para mantener filtros consistentes.
    desde, hasta = _rango_fechas(desde_str, hasta_str)
    ventas = Venta.query.filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).order_by(Venta.fecha.desc()).all()
    return ventas, desde, hasta


@reportes_bp.route('/export/csv', methods=['GET'])
@login_required
def exportar_csv():
    # Export plano para integraciones y auditoria externa.
    ventas, desde, hasta = _obtener_ventas_rango(request.args.get('desde'), request.args.get('hasta'))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['id_venta', 'fecha', 'cliente', 'tipo_pedido', 'forma_pago', 'total'])
    for venta in ventas:
        pedido = venta.pedido
        writer.writerow([
            venta.id,
            venta.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            pedido.cliente_nombre if pedido else '',
            pedido.tipo if pedido else '',
            venta.forma_pago,
            f"{float(venta.total):.2f}",
        ])

    filename = f"reporte_{desde.strftime('%Y%m%d')}_{hasta.strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@reportes_bp.route('/export/excel', methods=['GET'])
@login_required
def exportar_excel():
    # Export enriquecido para analisis operativo en hojas de calculo.
    ventas, desde, hasta = _obtener_ventas_rango(request.args.get('desde'), request.args.get('hasta'))

    try:
        from openpyxl import Workbook
    except ModuleNotFoundError:
        return jsonify({
            'error': 'Exportacion a Excel no disponible: falta dependencia openpyxl en el servidor.'
        }), 503

    wb = Workbook()
    ws = wb.active
    ws.title = 'Reporte Ventas'
    ws.append(['ID Venta', 'Fecha', 'Cliente', 'Tipo Pedido', 'Forma Pago', 'Total'])

    for venta in ventas:
        pedido = venta.pedido
        ws.append([
            venta.id,
            venta.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            pedido.cliente_nombre if pedido else '',
            pedido.tipo if pedido else '',
            venta.forma_pago,
            float(venta.total),
        ])

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"reporte_{desde.strftime('%Y%m%d')}_{hasta.strftime('%Y%m%d')}.xlsx"
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@reportes_bp.route('/ventas/lista', methods=['GET'])
@login_required
def listar_ventas():
    """
    Endpoint exclusivo para el panel de administración.
    Devuelve todas las ventas con su ID para poder seleccionarlas y eliminarlas.
    Solo accesible para el usuario root.
    """
    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'Solo root puede acceder a esta función'}), 403

    ventas = Venta.query.order_by(Venta.fecha.desc()).all()
    return jsonify([{
        'id': v.id,
        'cliente': v.pedido.cliente_nombre if v.pedido else '—',
        'tipo': v.pedido.tipo if v.pedido else '—',
        'forma_pago': v.forma_pago,
        'total': v.total,
        'fecha': v.fecha.strftime('%d/%m/%Y %H:%M')
    } for v in ventas])


@reportes_bp.route('/ventas/eliminar', methods=['DELETE'])
@login_required
def eliminar_ventas():
    """
    Elimina un grupo de ventas por sus IDs (selección root desde el panel de admin).
    Solo accesible para root.
    """
    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'Solo root puede eliminar registros de ventas'}), 403

    datos = request.json
    ids = datos.get('ids', [])

    if not ids:
        return jsonify({'error': 'No se proporcionaron IDs para eliminar'}), 400

    eliminadas = 0
    for venta_id in ids:
        v = Venta.query.get(venta_id)
        if v:
            db.session.delete(v)
            eliminadas += 1

    db.session.commit()
    return jsonify({'mensaje': f'{eliminadas} venta(s) eliminada(s) correctamente'})
