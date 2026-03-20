from flask import Blueprint, send_file, jsonify
from flask_login import login_required
from models.models import db, Venta, Pedido, DetallePedido, Producto, Caja, Egreso
from datetime import datetime, timedelta, date
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io

# Blueprint para los reportes diarios
reporte_diario_bp = Blueprint('reporte_diario', __name__, url_prefix='/reporte-diario')


@reporte_diario_bp.route('/pdf', methods=['GET'])
@login_required
def generar_pdf():
    """Genera PDF del reporte diario para hoy"""
    hoy = date.today()
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
    hace_30_dias = date.today() - timedelta(days=30)
    
    cajas = Caja.query.filter(
        db.func.date(Caja.fecha) >= hace_30_dias
    ).order_by(Caja.fecha.desc()).all()
    
    return jsonify([{
        'fecha': str(caja.fecha.date()),
        'estado': caja.estado,
        'total_vendido': float(caja.total_ingresos or 0)
    } for caja in cajas])


def generar_pdf_fecha(fecha):
    """
    Lógica principal para estructurar y dibujar el reporte PDF usando la librería ReportLab.
    Acumula datos de las ventas, cajas, y productos de un día puntual en memoria y luego dibuja las tablas.
    Los emojis usados aquí forman parte del reporte visual (interfaz con el cliente final).
    """
    # 1. Obtener datos del día a procesar configurando el rango de tiempo de horas y minutos.
    inicio_dia = datetime.combine(fecha, datetime.min.time())
    fin_dia = datetime.combine(fecha, datetime.max.time())

    # Caja del día
    caja = Caja.query.filter(
        db.func.date(Caja.fecha) == fecha
    ).first()

    if not caja:
        return jsonify({'error': 'No hay registro de caja para este día'}), 404

    # Ventas del día
    ventas = Venta.query.filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia
    ).all()

    # Pedidos por tipo
    pedidos_local = Pedido.query.join(Venta).filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Pedido.tipo == 'local'
    ).count()

    pedidos_delivery = Pedido.query.join(Venta).filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Pedido.tipo == 'delivery'
    ).count()

    # Producto más vendido
    top_producto = db.session.query(
        Producto.nombre,
        func.sum(DetallePedido.cantidad).label('cantidad')
    ).join(DetallePedido).join(Pedido).join(Venta).filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia
    ).group_by(Producto.nombre).order_by(func.sum(DetallePedido.cantidad).desc()).first()

    # Egresos del día
    egresos = Egreso.query.filter_by(caja_id=caja.id).all()

    # Comparación con día anterior
    dia_anterior = fecha - timedelta(days=1)
    caja_anterior = Caja.query.filter(
        db.func.date(Caja.fecha) == dia_anterior
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

    # Encabezado
    elementos.append(Paragraph("🍦 Helarte - Reporte Diario", titulo_style))
    elementos.append(Paragraph(f"Fecha: {fecha.strftime('%d/%m/%Y')}", subtitulo_style))

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
        ['Total Egresos', f'${caja.total_egresos:.2f}'],
        ['Monto Final', f'${caja.monto_final:.2f}']
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

    # Construir PDF
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'reporte_helarte_{fecha.strftime("%Y%m%d")}.pdf'
    )
