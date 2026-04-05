from flask import Blueprint, send_file, jsonify
from flask_login import login_required
from models.models import db, Venta, Pedido, DetallePedido, Producto, Caja, Egreso
from datetime import datetime, timedelta, date
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io
import os
import pytz

# Zona horaria de Ecuador (mismo estandar que el resto de modulos)
ZONA_HORARIA_LOCAL = pytz.timezone('America/Guayaquil')

# Blueprint para los reportes diarios
reporte_diario_bp = Blueprint('reporte_diario', __name__, url_prefix='/reporte-diario')



@reporte_diario_bp.route('/pdf', methods=['GET'])
@login_required
def generar_pdf():
    """Genera PDF del reporte diario para hoy (Hora Ecuador)"""
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy = ahora_local.date()
    return generar_pdf_fecha(hoy)



@reporte_diario_bp.route('/pdf/<string:fecha>', methods=['GET'])
@login_required
def generar_pdf_historico(fecha):
    """Genera PDF de un día específico (formato: YYYY-MM-DD)"""
    try:
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        return generar_pdf_fecha(fecha_obj)
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Use YYYY-MM-DD'}), 400


@reporte_diario_bp.route('/historial', methods=['GET'])
@login_required
def listar_historial():
    """Lista los últimos 30 días con reportes disponibles"""
    # Usamos hoy segun Ecuador
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy_local = ahora_local.date()
    hace_30_dias = hoy_local - timedelta(days=30)
    
    # Convertimos a UTC para consultar en la base de datos
    inicio_30_local = ZONA_HORARIA_LOCAL.localize(datetime(hace_30_dias.year, hace_30_dias.month, hace_30_dias.day, 0, 0, 0))
    inicio_30_utc   = inicio_30_local.astimezone(pytz.utc).replace(tzinfo=None)
    
    cajas = Caja.query.filter(
        Caja.fecha >= inicio_30_utc
    ).order_by(Caja.fecha.desc()).all()

    
    return jsonify([{
        'fecha': str(caja.fecha.date()),
        'estado': caja.estado,
        'total_vendido': float(caja.total_ingresos or 0)
    } for caja in cajas])


def generar_pdf_fecha(fecha):
    """
    Lógica principal para estructurar y dibujar el reporte PDF usando la librería ReportLab.
    'fecha' es un objeto date en horario local.
    """
    # 1. Obtener rango en UTC para consultar la base de datos
    inicio_dia_local = ZONA_HORARIA_LOCAL.localize(datetime(fecha.year, fecha.month, fecha.day, 0, 0, 0))
    fin_dia_local    = ZONA_HORARIA_LOCAL.localize(datetime(fecha.year, fecha.month, fecha.day, 23, 59, 59))
    
    inicio_dia_utc = inicio_dia_local.astimezone(pytz.utc).replace(tzinfo=None)
    fin_dia_utc    = fin_dia_local.astimezone(pytz.utc).replace(tzinfo=None)

    # Caja del día
    caja = Caja.query.filter(
        Caja.fecha >= inicio_dia_utc,
        Caja.fecha <= fin_dia_utc
    ).first()


    if not caja:
        # Si no hay caja abierta ni cerrada hoy, no hay nada que reportar
        return jsonify({'error': 'No hay caja registrada para este dia. Abre la caja primero.'}), 404

    # Ventas del día
    ventas = Venta.query.filter(
        Venta.fecha >= inicio_dia_utc,
        Venta.fecha <= fin_dia_utc
    ).all()


    # Pedidos por tipo
    pedidos_local = Pedido.query.join(Venta).filter(
        Venta.fecha >= inicio_dia_utc,
        Venta.fecha <= fin_dia_utc,
        Pedido.tipo == 'local'
    ).count()

    pedidos_delivery = Pedido.query.join(Venta).filter(
        Venta.fecha >= inicio_dia_utc,
        Venta.fecha <= fin_dia_utc,
        Pedido.tipo == 'delivery'
    ).count()


    # Producto más vendido
    top_producto = db.session.query(
        Producto.nombre,
        func.sum(DetallePedido.cantidad).label('cantidad')
    ).join(DetallePedido).join(Pedido).join(Venta).filter(
        Venta.fecha >= inicio_dia_utc,
        Venta.fecha <= fin_dia_utc
    ).group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc()).first()

    top_productos = db.session.query(
        Producto.nombre,
        func.sum(DetallePedido.cantidad).label('cantidad')
    ).join(DetallePedido).join(Pedido).join(Venta).filter(
        Venta.fecha >= inicio_dia_utc,
        Venta.fecha <= fin_dia_utc
    ).group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc()).limit(5).all()


    # Egresos del día
    egresos = Egreso.query.filter_by(caja_id=caja.id).all()

    # Comparación con día anterior (local)
    dia_anterior = fecha - timedelta(days=1)
    
    inicio_ant_local = ZONA_HORARIA_LOCAL.localize(datetime(dia_anterior.year, dia_anterior.month, dia_anterior.day, 0, 0, 0))
    fin_ant_local    = ZONA_HORARIA_LOCAL.localize(datetime(dia_anterior.year, dia_anterior.month, dia_anterior.day, 23, 59, 59))
    
    inicio_ant_utc = inicio_ant_local.astimezone(pytz.utc).replace(tzinfo=None)
    fin_ant_utc    = fin_ant_local.astimezone(pytz.utc).replace(tzinfo=None)

    caja_anterior = Caja.query.filter(
        Caja.fecha >= inicio_ant_utc,
        Caja.fecha <= fin_ant_utc
    ).first()


    # 2. Crear PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elementos = []
    styles = getSampleStyleSheet()

    # Estilos personalizados
    titulo_style = ParagraphStyle(
        'TituloCustom',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1f2121'),
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    subtitulo_style = ParagraphStyle(
        'SubtituloCustom',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#626c71'),
        alignment=TA_CENTER,
        spaceAfter=20
    )

    encabezado_style = ParagraphStyle(
        'EncabezadoSeccion',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1f2121'),
        spaceAfter=10,
        spaceBefore=15
    )

    foot_style = ParagraphStyle(
        'FootCustom',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER,
        spaceBefore=14
    )

    indicador_style = ParagraphStyle(
        'IndicadorStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#111827'),
        leading=14,
    )

    # Encabezado
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=0.9 * inch, height=0.9 * inch)
        logo.hAlign = 'CENTER'
        elementos.append(logo)
        elementos.append(Spacer(1, 0.08 * inch))

    import pytz
    tz_local = pytz.timezone('America/Guayaquil')
    ahora_local = datetime.now(tz_local)
    
    elementos.append(Paragraph("Helarte · Reporte de Corte", titulo_style))
    elementos.append(Paragraph(
        f"Fecha operativa: {fecha.strftime('%d/%m/%Y')} &nbsp;&nbsp; Corte generado: {ahora_local.strftime('%d/%m/%Y %H:%M')} (hora Ecuador)",
        subtitulo_style
    ))

    indicadores_data = [[
        Paragraph(f"<b>Total ventas</b><br/>${sum(v.total for v in ventas):.2f}", indicador_style),
        Paragraph(f"<b>Tickets emitidos</b><br/>{len(ventas)}", indicador_style),
        Paragraph(f"<b>Ticket promedio</b><br/>${(sum(v.total for v in ventas) / len(ventas)) if ventas else 0:.2f}", indicador_style),
    ]]
    tabla_indicadores = Table(indicadores_data, colWidths=[2.1 * inch, 2.1 * inch, 2.1 * inch])
    tabla_indicadores.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f4f6')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    elementos.append(tabla_indicadores)
    elementos.append(Spacer(1, 0.22 * inch))

    # RESUMEN GENERAL
    elementos.append(Paragraph("📊 Resumen General", encabezado_style))
    
    total_vendido = sum(v.total for v in ventas)
    ticket_promedio = total_vendido / len(ventas) if ventas else 0
    
    datos_resumen = [
        ['Concepto', 'Valor'],
        ['Total Vendido', f'${total_vendido:.2f}'],
        ['Número de Ventas', str(len(ventas))],
        ['Pedidos Local', str(pedidos_local)],
        ['Pedidos Delivery', str(pedidos_delivery)],
        ['Ticket Promedio', f'${ticket_promedio:.2f}'],
        ['Producto Top', top_producto.nombre if top_producto else 'N/A']
    ]
    
    tabla_resumen = Table(datos_resumen, colWidths=[3.5*inch, 2.5*inch])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2121')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fcfcf9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#5e5240')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcf9'), colors.HexColor('#ffffff')])
    ]))
    elementos.append(tabla_resumen)
    elementos.append(Spacer(1, 0.3*inch))

    # DETALLE DE CAJA
    elementos.append(Paragraph("💰 Detalle de Caja", encabezado_style))
    
    datos_caja = [
        ['Concepto', 'Monto'],
        ['Monto Inicial', f'${caja.monto_inicial:.2f}'],
        ['Total Ingresos', f'${caja.total_ingresos:.2f}'],
        ['  Efectivo', f'${float(caja.total_efectivo or 0):.2f}'],
        ['  Transferencia', f'${float(caja.total_transferencia or 0):.2f}'],
        ['Total Egresos', f'${caja.total_egresos:.2f}'],
        ['Balance Actual', f'${(caja.monto_inicial + caja.total_ingresos - caja.total_egresos):.2f}'],
        ['Estado Caja', caja.estado.upper()],
    ]
    
    tabla_caja = Table(datos_caja, colWidths=[3.5*inch, 2.5*inch])
    tabla_caja.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2121')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fcfcf9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#5e5240')),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcf9'), colors.HexColor('#ffffff')])
    ]))
    elementos.append(tabla_caja)
    elementos.append(Spacer(1, 0.3*inch))

    # DESGLOSE POR MEDIO DE PAGO
    elementos.append(Paragraph("💳 Desglose por Forma de Pago", encabezado_style))
    datos_pago = [
        ['Forma de pago', 'Monto'],
        ['Efectivo', f'${float(caja.total_efectivo or 0):.2f}'],
        ['Transferencia', f'${float(caja.total_transferencia or 0):.2f}'],
    ]
    tabla_pago = Table(datos_pago, colWidths=[3.5 * inch, 2.5 * inch])
    tabla_pago.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2121')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcf9'), colors.HexColor('#ffffff')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#5e5240')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elementos.append(tabla_pago)
    elementos.append(Spacer(1, 0.22 * inch))

    if top_productos:
        elementos.append(Paragraph("🏆 Top 5 Productos del Día", encabezado_style))
        datos_top = [['Producto', 'Unidades vendidas']]
        for item in top_productos:
            datos_top.append([item.nombre, str(int(item.cantidad))])
        tabla_top = Table(datos_top, colWidths=[4.3 * inch, 1.7 * inch])
        tabla_top.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2121')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#5e5240')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcf9'), colors.HexColor('#ffffff')]),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elementos.append(tabla_top)
        elementos.append(Spacer(1, 0.22 * inch))

    # DETALLE DE EGRESOS
    if egresos:
        elementos.append(Paragraph("📝 Detalle de Egresos", encabezado_style))
        
        datos_egresos = [['Descripción', 'Monto']]
        for egreso in egresos:
            datos_egresos.append([egreso.descripcion, f'${egreso.monto:.2f}'])
        
        tabla_egresos = Table(datos_egresos, colWidths=[4*inch, 2*inch])
        tabla_egresos.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2121')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fcfcf9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#5e5240')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcf9'), colors.HexColor('#ffffff')])
        ]))
        elementos.append(tabla_egresos)
        elementos.append(Spacer(1, 0.3*inch))

    # COMPARACIÓN CON DÍA ANTERIOR
    if caja_anterior:
        elementos.append(Paragraph("📈 Comparación con Día Anterior", encabezado_style))
        
        diferencia = total_vendido - caja_anterior.total_ingresos
        porcentaje = (diferencia / caja_anterior.total_ingresos * 100) if caja_anterior.total_ingresos > 0 else 0
        tendencia = "↗️ Mejor" if diferencia > 0 else "↘️ Menor" if diferencia < 0 else "→ Igual"
        
        datos_comparacion = [
            ['Concepto', 'Valor'],
            ['Ventas Día Anterior', f'${caja_anterior.total_ingresos:.2f}'],
            ['Ventas Hoy', f'${total_vendido:.2f}'],
            ['Diferencia', f'${abs(diferencia):.2f}'],
            ['Porcentaje', f'{abs(porcentaje):.1f}%'],
            ['Tendencia', tendencia]
        ]
        
        tabla_comparacion = Table(datos_comparacion, colWidths=[3.5*inch, 2.5*inch])
        tabla_comparacion.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2121')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fcfcf9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#5e5240')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fcfcf9'), colors.HexColor('#ffffff')])
        ]))
        elementos.append(tabla_comparacion)

    elementos.append(Paragraph('Helarte · Reporte automático de cierre diario', foot_style))

    # Construir PDF
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'reporte_helarte_{fecha.strftime("%Y%m%d")}.pdf'
    )
