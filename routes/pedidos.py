from flask import Blueprint, jsonify, request, send_file
from models.models import db, Pedido, DetallePedido, Producto, Venta, Caja
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io
import os


pedidos_bp = Blueprint('pedidos', __name__, url_prefix='/pedidos')


def _obtener_ticket_path(pedido_id):
    tickets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'tickets')
    os.makedirs(tickets_dir, exist_ok=True)
    return os.path.join(tickets_dir, f'ticket_pedido_{pedido_id}.pdf')


def _construir_ticket_pdf(pedido):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )
    styles = getSampleStyleSheet()
    elementos = []

    titulo_style = ParagraphStyle(
        'TicketTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#202124'),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        'TicketSub',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#5f6368'),
        spaceAfter=10,
    )
    right_style = ParagraphStyle(
        'TicketRight',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#202124'),
    )

    elementos.append(Paragraph('Helarte', titulo_style))
    elementos.append(Paragraph('Ticket de Pedido', sub_style))

    encabezado = [
        ['Ticket #', f'{pedido.id}'],
        ['Fecha', pedido.fecha.strftime('%d/%m/%Y %H:%M')],
        ['Cliente', pedido.cliente_nombre or 'Consumidor final'],
        ['Tipo', pedido.tipo.title()],
        ['Pago', pedido.forma_pago.title()],
    ]
    if pedido.numero_comprobante:
        encabezado.append(['Comprobante', pedido.numero_comprobante])

    tabla_info = Table(encabezado, colWidths=[2.0 * inch, 4.4 * inch])
    tabla_info.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#111827')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla_info)
    elementos.append(Spacer(1, 0.16 * inch))

    data_items = [['Producto', 'Cant.', 'P. Unit.', 'Subtotal']]
    for d in pedido.detalles:
        data_items.append([
            d.producto.nombre,
            str(d.cantidad),
            f"${float(d.subtotal) / float(d.cantidad):.2f}",
            f"${float(d.subtotal):.2f}",
        ])

    tabla_items = Table(data_items, colWidths=[3.1 * inch, 0.7 * inch, 1.1 * inch, 1.5 * inch])
    tabla_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_items)
    elementos.append(Spacer(1, 0.16 * inch))

    elementos.append(Paragraph(f"<b>Total a pagar: ${float(pedido.total):.2f}</b>", right_style))
    elementos.append(Spacer(1, 0.08 * inch))
    elementos.append(Paragraph('Gracias por preferir Helarte.', sub_style))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()


def _guardar_ticket_pdf(pedido):
    ticket_path = _obtener_ticket_path(pedido.id)
    pdf_bytes = _construir_ticket_pdf(pedido)
    with open(ticket_path, 'wb') as ticket_file:
        ticket_file.write(pdf_bytes)
    return ticket_path



# ==========================================
# GET /pedidos/ → Retorna todos los pedidos activos
# ==========================================
@pedidos_bp.route('/', methods=['GET'])
def obtener_pedidos():
    # Solo mostramos pedidos que NO están entregados aún
    pedidos = Pedido.query.filter(Pedido.estado != 'entregado').all()

    resultado = []
    for p in pedidos:
        # Para cada pedido, también enviamos sus productos
        detalles = []
        for d in p.detalles:
            detalles.append({
                'producto': d.producto.nombre,
                'cantidad': d.cantidad,
                'subtotal': d.subtotal
            })

        resultado.append({
            'id': p.id,
            'tipo': p.tipo,
            'cliente_nombre': p.cliente_nombre,
            'cliente_telefono': p.cliente_telefono,
            'cliente_direccion': p.cliente_direccion,
            'estado': p.estado,
            'total': p.total,
            'forma_pago': p.forma_pago,
            'numero_comprobante': p.numero_comprobante,
            'monto_efectivo': p.monto_efectivo,
            'monto_transferencia': p.monto_transferencia,
            'fecha': p.fecha.strftime('%Y-%m-%d %H:%M'),  # Formato legible
            'detalles': detalles
        })

    return jsonify(resultado)



# ==========================================
# POST /pedidos/ -> Crea un nuevo pedido con sus productos
# ==========================================
@pedidos_bp.route('/', methods=['POST'])
def crear_pedido():
    """
    Ruta para la creación de un Pedido en la que recibimos un objeto estructurado en JSON 
    desde el Frontend, insertamos en BD y iteramos los detalles (productos).
    """
    datos = request.json

    forma_pago = datos.get('forma_pago', 'efectivo')
    
    if forma_pago == 'transferencia' and not datos.get('numero_comprobante'):
        return jsonify({'error': 'El número de comprobante es requerido para transferencia'}), 400

    # Creamos el pedido principal
    nuevo_pedido = Pedido(
        tipo=datos['tipo'],
        cliente_nombre=datos.get('cliente_nombre', 'Consumidor final'),
        cliente_telefono=datos.get('cliente_telefono'),
        cliente_direccion=datos.get('cliente_direccion'),
        forma_pago=forma_pago,
        numero_comprobante=datos.get('numero_comprobante'),
        monto_efectivo=float(datos.get('monto_efectivo') or 0.0),
        monto_transferencia=float(datos.get('monto_transferencia') or 0.0)
    )

    db.session.add(nuevo_pedido)
    db.session.flush()  # flush() asigna el ID sin hacer commit aún

    # Procesamos cada producto del pedido
    total = 0
    for item in datos['productos']:
        producto = Producto.query.get(item['producto_id'])

        if not producto or not producto.disponible:
            return jsonify({'error': f'Producto no disponible'}), 400

        subtotal = producto.precio * item['cantidad']
        total += subtotal

        detalle = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=producto.id,
            cantidad=item['cantidad'],
            subtotal=subtotal
        )
        db.session.add(detalle)

    # Actualizamos el total general del pedido a nivel de la cabecera
    nuevo_pedido.total = total
    
    # Validar montos para pagos mixtos asegurando que la suma de efectivo y transferencia coincida con el total
    if forma_pago == 'mixto':
        if not datos.get('numero_comprobante'):
            return jsonify({'error': 'El número de comprobante es requerido para pagos mixtos'}), 400
        
        m_efect = nuevo_pedido.monto_efectivo
        m_transf = nuevo_pedido.monto_transferencia
        if abs((m_efect + m_transf) - total) > 0.01:
            return jsonify({'error': f'Los montos (Efectivo: ${m_efect:.2f}, Transferencia: ${m_transf:.2f}) no suman el total del pedido (${total:.2f})'}), 400

    db.session.commit()

    return jsonify({
        'mensaje': 'Pedido creado correctamente',
        'id': nuevo_pedido.id,
        'total': total,
        'ticket_url': f'/pedidos/{nuevo_pedido.id}/ticket',
        'ticket_guardado': False,
    }), 201

# ==========================================
# PUT /pedidos/<id>/estado → Cambia el estado del pedido
# Cuando se marca como 'entregado', genera una Venta automáticamente
# ==========================================
@pedidos_bp.route('/<int:pedido_id>/estado', methods=['PUT'])
def cambiar_estado(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    datos = request.json
    nuevo_estado = datos['estado']

    pedido.estado = nuevo_estado

    # Si el pedido fue entregado, registramos la venta y actualizamos la caja
    if nuevo_estado == 'entregado':
        venta = Venta(
            pedido_id=pedido.id,
            total=pedido.total,
            forma_pago=pedido.forma_pago,
            numero_comprobante=pedido.numero_comprobante,
            monto_efectivo=pedido.monto_efectivo,
            monto_transferencia=pedido.monto_transferencia
        )
        db.session.add(venta)

        # Buscamos la caja abierta del día y sumamos el ingreso
        caja_abierta = Caja.query.filter_by(estado='abierta').first()
        if caja_abierta:
            caja_abierta.total_ingresos += pedido.total
            # ── NUEVO: suma al desglose por forma de pago
            if pedido.forma_pago == 'efectivo':
                caja_abierta.total_efectivo += pedido.total
            elif pedido.forma_pago == 'transferencia':
                caja_abierta.total_transferencia += pedido.total
            elif pedido.forma_pago == 'mixto':
                caja_abierta.total_efectivo += (pedido.monto_efectivo or 0.0)
                caja_abierta.total_transferencia += (pedido.monto_transferencia or 0.0)

    db.session.commit()
    return jsonify({'mensaje': f'Estado actualizado a {nuevo_estado}'})


@pedidos_bp.route('/<int:pedido_id>', methods=['DELETE'])
def eliminar_pedido(pedido_id):
    """Elimina un pedido activo cuando el cliente cancela la orden."""
    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'El pedido ya no existe o fue eliminado'}), 404

    if pedido.estado == 'entregado':
        return jsonify({'error': 'No se puede eliminar un pedido ya entregado'}), 400

    venta_asociada = Venta.query.filter_by(pedido_id=pedido.id).first()
    if venta_asociada:
        return jsonify({'error': 'No se puede eliminar un pedido con venta registrada'}), 400

    try:
        DetallePedido.query.filter_by(pedido_id=pedido.id).delete()
        db.session.delete(pedido)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Ocurrió un problema al eliminar el pedido'}), 500

    return jsonify({'mensaje': 'Pedido eliminado correctamente'})


@pedidos_bp.route('/<int:pedido_id>/ticket', methods=['GET'])
def generar_ticket_pedido(pedido_id):
    """Genera un ticket imprimible (PDF) para un pedido específico."""
    pedido = Pedido.query.get_or_404(pedido_id)
    ticket_path = _obtener_ticket_path(pedido.id)
    if not os.path.exists(ticket_path):
        _guardar_ticket_pdf(pedido)

    return send_file(
        ticket_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'ticket_pedido_{pedido.id}.pdf'
    )
