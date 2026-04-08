"""
routes/reportes.py
------------------
Blueprint para el dashboard analitico y la exportacion de datos de ventas.

Este modulo implementa consultas de agregacion SQL a traves de SQLAlchemy.
La agregacion consiste en agrupar multiples filas de datos y calcular resumenes,
similar a como funcionan las tablas dinamicas en Excel.

Conceptos clave:
- func.sum(), func.count(): funciones SQL que suman y cuentan valores agrupados.
- GROUP BY: agrupa resultado por un campo. Ej: total de ventas agrupado por dia.
- Compatibilidad entre bases de datos: SQLite y PostgreSQL manejan la conversion
  de DateTime a Date de diferente manera, por lo que se detecta el motor activo
  y se usa la expresion apropiada para cada uno.
"""

from flask import Blueprint, jsonify, request, Response, send_file
from flask_login import login_required, current_user
from models.models import db, Venta, DetallePedido, Producto
from datetime import datetime, date, time
from sqlalchemy import func, text
from io import StringIO, BytesIO
import csv
from utils.tz_utils import (
    ahora_local,
    fecha_operativa_hoy,
    rango_utc_de_fecha,
    formatear_local,
    APP_TIMEZONE_NAME,
    APP_TZ,
)

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')


# ==========================================
# FUNCIONES AUXILIARES (HELPERS)
# ==========================================

def _rango_fechas(desde_str, hasta_str):
    """
    Convierte strings de fecha en objetos datetime UTC para filtrar en la BD.
    Si no se reciben parametros, usa el dia de hoy segun Ecuador por defecto.
    """
    hoy_local = fecha_operativa_hoy()

    desde_str = desde_str or hoy_local.strftime('%Y-%m-%d')
    hasta_str = hasta_str or hoy_local.strftime('%Y-%m-%d')

    desde_date = datetime.strptime(desde_str, '%Y-%m-%d').date()
    hasta_date  = datetime.strptime(hasta_str, '%Y-%m-%d').date()

    desde_utc, _       = rango_utc_de_fecha(desde_date)
    _,         hasta_utc = rango_utc_de_fecha(hasta_date)

    return desde_utc, hasta_utc



def _obtener_ventas_rango(desde_str, hasta_str):
    """
    Consulta las ventas de un rango de fechas, ordenadas de la mas reciente a la mas antigua.
    Esta funcion es reutilizada por los exportadores (CSV y Excel) para mantener
    el mismo criterio de filtrado en todos los formatos de descarga.
    """
    desde, hasta = _rango_fechas(desde_str, hasta_str)
    ventas = Venta.query.filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).order_by(Venta.fecha.desc()).all()
    return ventas, desde, hasta


# ==========================================
# ENDPOINTS DE DATOS PARA EL DASHBOARD
# ==========================================

@reportes_bp.route('/', methods=['GET'])
@login_required
def obtener_reporte():
    """
    Construye y retorna las estadisticas agregadas para el dashboard principal.

    Recibe los parametros 'desde' y 'hasta' como query params en la URL.
    Ejemplo: GET /reportes/?desde=2024-01-01&hasta=2024-01-31

    Retorna:
    - total_pedidos: numero de ventas en el rango.
    - total_vendido: suma total de ingresos.
    - producto_top: nombre del producto mas vendido.
    - ventas_por_dia: lista con ventas agrupadas por dia (para el grafico de lineas).
    - top_productos: los 5 productos mas vendidos (para el grafico de dona).
    - desglose_pagos: monto en efectivo vs transferencia (para el grafico circular).
    """
    desde_str = request.args.get('desde')
    hasta_str = request.args.get('hasta')

    desde, hasta = _rango_fechas(desde_str, hasta_str)

    # Consulta base: todas las ventas en el rango especificado.
    ventas = Venta.query.filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).all()

    total_vendido = sum(v.total for v in ventas)

    # Deteccion del motor para construir la expresion de fecha en zona local.
    # - PostgreSQL: convierte el timestamp UTC a Ecuador antes de extraer la fecha.
    #   Esto garantiza que ventas a las 20:00 Ecuador (01:00 UTC siguiente) se
    #   agrupen bajo el dia correcto del negocio.
    # - SQLite (desarrollo local): func.date() usa UTC, pero es aceptable en dev.
    is_sqlite  = 'sqlite' in str(db.engine.url)
    if is_sqlite:
        date_expr = func.date(Venta.fecha)
    else:
        # AT TIME ZONE convierte el timestamp UTC al instante en zona local,
        # luego ::date extrae solo la parte de fecha ya en hora Ecuador.
        date_expr = func.date(
            func.timezone(APP_TIMEZONE_NAME, Venta.fecha)
        )

    # Consulta de agregacion: agrupa las ventas por dia y calcula totales.
    # El resultado es una lista de filas con (fecha, cantidad_ventas, suma_ventas).
    ventas_por_dia = db.session.query(
        date_expr.label('fecha'),
        func.count(Venta.id).label('cantidad'),
        func.sum(Venta.total).label('total')
    ).filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).group_by(date_expr).order_by(date_expr.desc()).all()

    # Consulta de ranking: productos mas vendidos usando JOIN entre tablas.
    # JOIN enlaza tres tablas: Producto -> DetallePedido -> Venta.
    top_productos = db.session.query(
        Producto.nombre,
        func.sum(DetallePedido.cantidad).label('cantidad')
    ).join(DetallePedido).join(Venta, DetallePedido.pedido_id == Venta.pedido_id).filter(
        Venta.fecha >= desde,
        Venta.fecha <= hasta
    ).group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc()).limit(5).all()

    # Desglose por forma de pago (comparamos en minuscula porque asi se guarda en la BD)
    efectivo      = 0.0
    transferencia = 0.0
    for v in ventas:
        forma = (v.forma_pago or '').lower()
        if forma == 'efectivo':
            efectivo += float(v.total)
        elif forma in ('transferencia', 'tarjeta'):
            transferencia += float(v.total)
        elif forma == 'mixto':
            # En pago mixto sumamos cada parte a su categoria
            efectivo      += float(v.monto_efectivo      or 0)
            transferencia += float(v.monto_transferencia or 0)

    return jsonify({
        'total_pedidos':  len(ventas),
        'total_vendido':  total_vendido,
        'producto_top':   top_productos[0].nombre if top_productos else None,
        'ventas_por_dia': [
            {'fecha': str(v.fecha), 'cantidad': v.cantidad, 'total': float(v.total)}
            for v in ventas_por_dia
        ],
        'top_productos': [
            {'nombre': p.nombre, 'cantidad': int(p.cantidad)}
            for p in top_productos
        ],
        'desglose_pagos': {
            'efectivo':      float(efectivo),
            'transferencia': float(transferencia)
        }
    })


@reportes_bp.route('/dashboard-hoy', methods=['GET'])
@login_required
def dashboard_hoy():
    hoy_local  = fecha_operativa_hoy()
    import pytz
    inicio_utc, fin_utc = rango_utc_de_fecha(hoy_local)

    ventas_hoy = Venta.query.filter(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc).all()

    labels           = [f"{h:02d}:00" for h in range(24)]
    ventas_por_hora  = [0.0] * 24
    tickets_por_hora = [0]   * 24

    for venta in ventas_hoy:
        # Convertimos la hora UTC de la BD a la hora local del negocio.
        fecha_local = pytz.utc.localize(venta.fecha).astimezone(APP_TZ)
        hora = fecha_local.hour
        ventas_por_hora[hora]  += float(venta.total)
        tickets_por_hora[hora] += 1

    return jsonify({
        'fecha':             hoy_local.strftime('%Y-%m-%d'),
        'total_vendido_hoy': round(sum(ventas_por_hora), 2),
        'total_tickets_hoy': len(ventas_hoy),
        'labels':            labels,
        'ventas_por_hora':   [round(v, 2) for v in ventas_por_hora],
        'tickets_por_hora':  tickets_por_hora,
    })


# ==========================================
# EXPORTACION DE DATOS
# ==========================================

@reportes_bp.route('/export/csv', methods=['GET'])
@login_required
def exportar_csv():
    """
    Exporta las ventas del rango seleccionado en formato CSV (valores separados por coma).
    El CSV es el formato mas universal para intercambiar datos entre sistemas.
    Se construye en memoria usando StringIO para no crear archivos temporales en disco.
    """
    ventas, desde, hasta = _obtener_ventas_rango(request.args.get('desde'), request.args.get('hasta'))

    # StringIO es un "archivo en memoria" que se comporta como un archivo real de texto.
    output = StringIO()
    writer = csv.writer(output)

    # Primera fila: encabezados de las columnas.
    writer.writerow(['id_venta', 'fecha', 'cliente', 'tipo_pedido', 'forma_pago', 'total'])

    for venta in ventas:
        pedido = venta.pedido
        writer.writerow([
            venta.id,
            formatear_local(venta.fecha, '%Y-%m-%d %H:%M:%S'),
            pedido.cliente_nombre if pedido else '',
            pedido.tipo           if pedido else '',
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
    """
    Exporta las ventas en formato Excel (.xlsx) usando la libreria openpyxl.
    Si openpyxl no esta instalado en el servidor, retorna un error 503 descriptivo.

    BytesIO es como StringIO pero para datos binarios, ya que Excel es un formato binario.
    """
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
    # Encabezados de la hoja de calculo.
    ws.append(['ID Venta', 'Fecha', 'Cliente', 'Tipo Pedido', 'Forma Pago', 'Total'])

    for venta in ventas:
        pedido = venta.pedido
        ws.append([
            venta.id,
            formatear_local(venta.fecha, '%Y-%m-%d %H:%M:%S'),
            pedido.cliente_nombre if pedido else '',
            pedido.tipo           if pedido else '',
            venta.forma_pago,
            float(venta.total),
        ])

    # Guardamos el libro en un buffer de bytes en memoria y lo enviamos como descarga.
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)  # Volvemos al inicio del buffer para que send_file pueda leerlo.
    filename = f"reporte_{desde.strftime('%Y%m%d')}_{hasta.strftime('%Y%m%d')}.xlsx"
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ==========================================
# GESTION DE VENTAS (PANEL ADMIN)
# ==========================================

@reportes_bp.route('/ventas/lista', methods=['GET'])
@login_required
def listar_ventas():
    """
    Retorna todas las ventas con sus datos para el panel de administracion.
    Solo root puede acceder a este endpoint, ya que es el punto de entrada para
    la eliminacion de registros historicos.
    """
    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'Solo root puede acceder a esta funcion'}), 403

    ventas = Venta.query.order_by(Venta.fecha.desc()).all()
    return jsonify([{
        'id':        v.id,
        'cliente':   v.pedido.cliente_nombre if v.pedido else '—',
        'tipo':      v.pedido.tipo           if v.pedido else '—',
        'forma_pago': v.forma_pago,
        'total':     v.total,
        'fecha':     formatear_local(v.fecha, '%d/%m/%Y %H:%M')
    } for v in ventas])


@reportes_bp.route('/ventas/eliminar', methods=['DELETE'])
@login_required
def eliminar_ventas():
    """
    Elimina una seleccion de ventas por sus IDs.
    Esta operacion es irreversible y exclusiva para root.
    Se usa para corregir datos erroneos en el historial de ventas.
    """
    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'Solo root puede eliminar registros de ventas'}), 403

    datos = request.json
    ids   = datos.get('ids', [])

    if not ids:
        return jsonify({'error': 'No se proporcionaron IDs para eliminar'}), 400

    eliminadas = 0
    for venta_id in ids:
        v = Venta.query.get(venta_id)
        if v:
            from models.models import FacturaSRI, Pedido, DetallePedido
            FacturaSRI.query.filter_by(venta_id=v.id).delete()
            
            # El usuario pide borrar todo tipo de ticket generado (Pedido) para los ambientes de prueba.
            pe_id = v.pedido_id
            db.session.delete(v)
            if pe_id:
                pe = Pedido.query.get(pe_id)
                if pe:
                    DetallePedido.query.filter_by(pedido_id=pe.id).delete()
                    import os
                    from routes.pedidos import _obtener_ticket_path
                    try:
                        os.remove(_obtener_ticket_path(pe.id))
                    except:
                        pass
                    db.session.delete(pe)

            eliminadas += 1

    db.session.commit()
    return jsonify({'mensaje': f'{eliminadas} venta(s) eliminada(s) correctamente'})
