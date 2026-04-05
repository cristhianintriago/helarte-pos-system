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
from sqlalchemy import func
from io import StringIO, BytesIO
import csv
import pytz

# Zona horaria de Ecuador (UTC-5, sin cambio de horario de verano)
ZONA_HORARIA_LOCAL = pytz.timezone('America/Guayaquil')

def a_hora_local(fecha_utc):
    """Convierte una fecha guardada en UTC a la hora local de Ecuador."""
    if fecha_utc is None:
        return fecha_utc
    fecha_con_zona = pytz.utc.localize(fecha_utc)
    return fecha_con_zona.astimezone(ZONA_HORARIA_LOCAL)

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')


# ==========================================
# FUNCIONES AUXILIARES (HELPERS)
# ==========================================

def _rango_fechas(desde_str, hasta_str):
    """
    Convierte strings de fecha en objetos datetime con hora de inicio y fin.
    Si no se reciben parametros, usa el dia de hoy segun Ecuador por defecto.
    """
    # Determinamos 'hoy' segun Ecuador
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy_local   = ahora_local.date()

    desde_str = desde_str or hoy_local.strftime('%Y-%m-%d')
    hasta_str = hasta_str or hoy_local.strftime('%Y-%m-%d')
    
    # Convertimos strings a datetime (naive)
    desde_dt = datetime.strptime(desde_str, '%Y-%m-%d')
    hasta_dt = datetime.strptime(hasta_str, '%Y-%m-%d')
    
    # Localizamos a Ecuador (00:00:00 y 23:59:59)
    desde_loc = ZONA_HORARIA_LOCAL.localize(datetime(desde_dt.year, desde_dt.month, desde_dt.day, 0, 0, 0))
    hasta_loc = ZONA_HORARIA_LOCAL.localize(datetime(hasta_dt.year, hasta_dt.month, hasta_dt.day, 23, 59, 59))
    
    # Convertimos a UTC para la base de datos
    desde_utc = desde_loc.astimezone(pytz.utc).replace(tzinfo=None)
    hasta_utc = hasta_loc.astimezone(pytz.utc).replace(tzinfo=None)
    
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

    # Deteccion del motor de base de datos activo.
    # SQLite no soporta db.cast(..., db.Date) correctamente en todos los casos,
    # mientras que PostgreSQL lo requiere para agrupar por fecha sin la hora.
    is_sqlite = 'sqlite' in str(db.engine.url)
    date_expr = func.date(Venta.fecha) if is_sqlite else db.cast(Venta.fecha, db.Date)

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
    # Usamos la hora local de Ecuador para el rango y para clasificar las ventas por hora
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy_local   = ahora_local.date()

    inicio_local = ZONA_HORARIA_LOCAL.localize(datetime(hoy_local.year, hoy_local.month, hoy_local.day, 0, 0, 0))
    fin_local    = ZONA_HORARIA_LOCAL.localize(datetime(hoy_local.year, hoy_local.month, hoy_local.day, 23, 59, 59))
    inicio_utc   = inicio_local.astimezone(pytz.utc).replace(tzinfo=None)
    fin_utc      = fin_local.astimezone(pytz.utc).replace(tzinfo=None)

    ventas_hoy = Venta.query.filter(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc).all()

    # Etiquetas del eje X del grafico en hora local: "00:00", "01:00", ..., "23:00".
    labels           = [f"{h:02d}:00" for h in range(24)]
    ventas_por_hora  = [0.0] * 24
    tickets_por_hora = [0]   * 24

    for venta in ventas_hoy:
        # Convertimos la hora UTC de la BD a la hora local de Ecuador
        fecha_local = pytz.utc.localize(venta.fecha).astimezone(ZONA_HORARIA_LOCAL)
        hora = fecha_local.hour
        ventas_por_hora[hora]  += float(venta.total)
        tickets_por_hora[hora] += 1

    return jsonify({
        'fecha':            hoy_local.strftime('%Y-%m-%d'),
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
            a_hora_local(venta.fecha).strftime('%Y-%m-%d %H:%M:%S'),
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
            a_hora_local(venta.fecha).strftime('%Y-%m-%d %H:%M:%S'),
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
        'fecha':     a_hora_local(v.fecha).strftime('%d/%m/%Y %H:%M')
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
