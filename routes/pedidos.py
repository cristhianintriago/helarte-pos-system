"""
routes/pedidos.py
-----------------
Aqui voy a hacer todo el tema del carrito de pedidos y los tickets.
Lo pongo en un Blueprint para que el proyecto no quede todo en app.py y ganar nota extra por organizacion.

Tambien uso una libreria para generar los PDF de los tickets porque sale mas facil.
Y uso el socket (visto en un tutorial) para decirle a la cocina que llegó un pedido nuevo.
"""

from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required, current_user
from models.models import db, Pedido, DetallePedido, Producto, Venta, Caja, ConfiguracionSistema
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


# ==========================================
# FUNCIONES PARA CONTAR LOS NUMEROS DE TICKET
# ==========================================
# Necesito guardar esto en la base para que si apagamos la compu, siga donde se quedó.

def _calcular_siguiente_numero_pedido():
    """Retorna el numero de ticket visual que le corresponde al proximo pedido."""
    config = _obtener_o_inicializar_contador_tickets()
    return int(config.valor_entero or 1)


def _obtener_o_inicializar_contador_tickets():
    # Voy a la BD a pedir por mi clave
    config = ConfiguracionSistema.query.filter_by(clave='contador_ticket_diario').first()
    
    if config != None:
        if config.valor_entero != None:
            if int(config.valor_entero) >= 1 and int(config.valor_entero) <= 50:
                return config

    # Si por alguna razon no habia, lo armo en 1
    if config == None:
        config = ConfiguracionSistema(clave='contador_ticket_diario', valor_entero=1)
    else:
        config.valor_entero = 1

    db.session.add(config)
    # Lo dejo ahi en espera para guardarlo luego
    db.session.flush()
    return config


def _avanzar_contador_tickets():
    # Hago que el ticket sume en 1, si llega a 50 lo regreso a 1 sumando normal
    config = _obtener_o_inicializar_contador_tickets()
    
    actual = 1
    if config.valor_entero != None:
        actual = int(config.valor_entero)
        
    actual = actual + 1
    if actual > 50:
        actual = 1
        
    config.valor_entero = actual
    db.session.add(config)


def _numero_visual_pedido(pedido):
    """Retorna el numero de ticket del pedido como entero, o 0 si no tiene asignado."""
    if pedido.numero_pedido and pedido.numero_pedido > 0:
        return int(pedido.numero_pedido)
    return 0


def _obtener_ticket_path(pedido_id):
    """
    Construye la ruta del archivo PDF del ticket en el sistema de archivos local.
    Los tickets se guardan en la carpeta 'instance/tickets/' del proyecto.
    os.makedirs con exist_ok=True crea la carpeta si no existe, sin lanzar error si ya existe.
    """
    tickets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'tickets')
    os.makedirs(tickets_dir, exist_ok=True)
    return os.path.join(tickets_dir, f'ticket_pedido_{pedido_id}.pdf')


# ==========================================
# FUNCIONES AUXILIARES: GENERACION DE PDF
# ==========================================

def _construir_ticket_pdf(pedido):
    """
    Construye el PDF del ticket de un pedido usando la libreria ReportLab.

    ReportLab funciona con un modelo de "flujo de contenido":
    1. Se crea un SimpleDocTemplate con el tamano de pagina y los margenes.
    2. Se define una lista de 'elementos' (Paragraph, Spacer, Table).
    3. doc.build(elementos) renderiza el PDF y lo escribe en el buffer.

    Todo se construye en memoria usando io.BytesIO, sin crear archivos temporales en disco.
    Esto es mas eficiente y funciona bien en servidores en la nube como Railway.
    """
    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.6  * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5   * inch,
        bottomMargin=0.5 * inch,
    )

    # getSampleStyleSheet provee estilos base (Heading1, Normal, etc.) que podemos
    # extender o usar como punto de partida para estilos personalizados.
    styles   = getSampleStyleSheet()
    elementos = []

    # Definicion de estilos personalizados para el ticket.
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

    # Encabezado del ticket: nombre del negocio y titulo.
    elementos.append(Paragraph('Helarte', titulo_style))
    elementos.append(Paragraph('Ticket de Pedido', sub_style))

    # Tabla de metadatos: numero de ticket, fecha, cliente, tipo de pedido y pago.
    encabezado = [
        ['Ticket #', f'{_numero_visual_pedido(pedido)}'],
        ['Fecha',    pedido.fecha.strftime('%d/%m/%Y %H:%M')],
        ['Cliente',  pedido.cliente_nombre or 'Consumidor final'],
        ['Tipo',     pedido.tipo.title()],
        ['Pago',     pedido.forma_pago.title()],
    ]
    # Agregamos filas opcionales segun el tipo de pedido.
    if pedido.tipo == 'delivery' and pedido.plataforma:
        encabezado.append(['Plataforma', pedido.plataforma])
    if pedido.numero_comprobante:
        encabezado.append(['Comprobante', pedido.numero_comprobante])

    tabla_info = Table(encabezado, colWidths=[2.0 * inch, 4.4 * inch])
    tabla_info.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (0, 0), (0, -1), colors.HexColor('#374151')),
        ('TEXTCOLOR',     (1, 0), (1, -1), colors.HexColor('#111827')),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('LINEBELOW',     (0, -1), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabla_info)
    elementos.append(Spacer(1, 0.16 * inch))

    # Tabla de items del pedido: producto, cantidad, precio unitario y subtotal.
    data_items = [['Producto', 'Cant.', 'P. Unit.', 'Subtotal']]
    for d in pedido.detalles:
        nombre_producto = d.producto.nombre
        # Si el item tiene sabor seleccionado, lo incluimos entre parentesis.
        if d.sabor:
            nombre_producto = f"{nombre_producto} ({d.sabor})"

        data_items.append([
            nombre_producto,
            str(d.cantidad),
            # Calculamos el precio unitario dividiendo el subtotal por la cantidad.
            f"${float(d.subtotal) / float(d.cantidad):.2f}",
            f"${float(d.subtotal):.2f}",
        ])

    tabla_items = Table(data_items, colWidths=[3.1 * inch, 0.7 * inch, 1.1 * inch, 1.5 * inch])
    tabla_items.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#111827')),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9fafb'), colors.white]),
        ('GRID',          (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elementos.append(tabla_items)
    elementos.append(Spacer(1, 0.16 * inch))

    # Total a pagar y mensaje de cierre del ticket.
    elementos.append(Paragraph(f"<b>Total a pagar: ${float(pedido.total):.2f}</b>", right_style))
    elementos.append(Spacer(1, 0.08 * inch))
    elementos.append(Paragraph('Gracias por preferir Helarte.', sub_style))

    # doc.build() renderiza todos los elementos y escribe el PDF en el buffer.
    doc.build(elementos)
    # seek(0) mueve el cursor al inicio del buffer para que pueda ser leido desde el principio.
    buffer.seek(0)
    return buffer.getvalue()


def _guardar_ticket_pdf(pedido):
    """
    Genera el PDF del ticket y lo guarda como archivo en el sistema de archivos local.
    Retorna la ruta completa del archivo guardado.
    """
    ticket_path = _obtener_ticket_path(pedido.id)
    pdf_bytes   = _construir_ticket_pdf(pedido)
    with open(ticket_path, 'wb') as ticket_file:
        ticket_file.write(pdf_bytes)
    return ticket_path


# ==========================================
# GET /pedidos/ -> Lista los pedidos activos
# ==========================================

@pedidos_bp.route('/', methods=['GET'])
def obtener_pedidos():
    """
    Retorna todos los pedidos que aun no han sido entregados.
    Este endpoint es consumido por el modulo de cocina para mostrar las comandas activas.
    Se excluyen los pedidos entregados para que la pantalla de cocina no se llene de historial.
    """
    pedidos = Pedido.query.filter(Pedido.estado != 'entregado').order_by(Pedido.id.desc()).all()

    resultado = []
    for p in pedidos:
        # Construimos la lista de detalles (items) de cada pedido.
        detalles = []
        for d in p.detalles:
            detalles.append({
                'producto': d.producto.nombre,
                'sabor':    d.sabor,
                'cantidad': d.cantidad,
                'subtotal': d.subtotal
            })

        resultado.append({
            'id':                 p.id,
            'numero_pedido':      _numero_visual_pedido(p),
            'tipo':               p.tipo,
            'cliente_nombre':     p.cliente_nombre,
            'cliente_telefono':   p.cliente_telefono,
            'cliente_direccion':  p.cliente_direccion,
            'cliente_identificacion': p.cliente_identificacion,
            'cliente_correo':     p.cliente_correo,
            'requiere_factura':   p.requiere_factura,
            'plataforma':         p.plataforma,
            'estado':             p.estado,
            'total':              p.total,
            'forma_pago':         p.forma_pago,
            'numero_comprobante': p.numero_comprobante,
            'monto_efectivo':     p.monto_efectivo,
            'monto_transferencia': p.monto_transferencia,
            # strftime formatea el objeto datetime a un string legible.
            'fecha':    p.fecha.strftime('%Y-%m-%d %H:%M'),
            'detalles': detalles
        })

    return jsonify(resultado)


# ==========================================
# POST /pedidos/ -> Crea un nuevo pedido
# ==========================================

@pedidos_bp.route('/', methods=['POST'])
def crear_pedido():
    """
    Registra un nuevo pedido con todos sus productos en la base de datos.

    Flujo de la funcion:
    1. Valida el metodo de pago y el comprobante si aplica.
    2. Crea el objeto Pedido y hace flush() para obtener su ID.
    3. Itera los productos, valida disponibilidad y sabores, y crea los DetallePedido.
    4. Calcula el total y valida la suma de montos en pagos mixtos.
    5. Crea la Venta y actualiza los acumuladores de la Caja abierta.
    6. Hace commit() para confirmar toda la transaccion a la base de datos.
    7. Emite el evento WebSocket para notificar a la pantalla de cocina.

    Por que flush() antes de commit():
    El flush() envia los cambios al motor SQL en memoria (dentro de la misma transaccion).
    Esto nos permite obtener el ID asignado al nuevo Pedido para usarlo en los DetallePedido,
    sin confirmar la transaccion hasta que todos los datos esten correctos.
    Si algo falla antes del commit(), toda la transaccion se revierte automaticamente.
    """
    datos      = request.json
    forma_pago = datos.get('forma_pago', 'efectivo')

    # Validacion: las transferencias requieren un numero de comprobante.
    if forma_pago == 'transferencia' and not datos.get('numero_comprobante'):
        return jsonify({'error': 'El numero de comprobante es requerido para transferencia'}), 400

    # Paso 1: Creamos el encabezado del pedido sin los detalles aun.
    nuevo_pedido = Pedido(
        tipo=datos['tipo'],
        cliente_nombre=datos.get('cliente_nombre', 'Consumidor final'),
        cliente_telefono=datos.get('cliente_telefono'),
        cliente_direccion=datos.get('cliente_direccion'),
        cliente_identificacion=datos.get('cliente_identificacion'),
        cliente_correo=datos.get('cliente_correo'),
        requiere_factura=datos.get('requiere_factura', False),
        plataforma=datos.get('plataforma'),
        numero_pedido=_calcular_siguiente_numero_pedido(),
        forma_pago=forma_pago,
        numero_comprobante=datos.get('numero_comprobante'),
        monto_efectivo=float(datos.get('monto_efectivo') or 0.0),
        monto_transferencia=float(datos.get('monto_transferencia') or 0.0)
    )

    db.session.add(nuevo_pedido)
    # flush() nos da el ID del pedido para usarlo en los DetallePedido.
    db.session.flush()

    # Paso 2: Procesamos cada producto incluido en el pedido.
    total = 0
    for item in datos['productos']:
        producto = Producto.query.get(item['producto_id'])

        if not producto or not producto.disponible:
            return jsonify({'error': 'Producto no disponible'}), 400

        # Normalizamos la lista de sabores seleccionados.
        sabores_seleccionados = item.get('sabores')
        if sabores_seleccionados is None:
            # Compatibilidad con versiones antiguas del frontend que enviaban un campo unico 'sabor'.
            sabor_unico           = item.get('sabor')
            sabores_seleccionados = [sabor_unico] if sabor_unico else []

        # Limpiamos espacios vacios de la lista de sabores.
        sabores_seleccionados = [str(s).strip() for s in sabores_seleccionados if str(s).strip()]

        # El catalogo de sabores permitidos para este producto.
        sabores_permitidos = []
        for s in producto.sabores:
            if s.activo == True:
                sabores_permitidos.append(s.nombre)

        # Si el producto requiere sabor y no se selecciono ninguno, rechazamos el pedido.
        # (Se permiten observaciones libres, por eso no validamos contra sabores_permitidos estrictamente).
        if sabores_permitidos and not sabores_seleccionados:
            return jsonify({'error': f'Debes detallar {producto.nombre}'}), 400

        # Los pedidos delivery tienen un cargo extra
        precio_final = producto.precio
        if datos.get('tipo') == 'delivery':
            precio_final = precio_final + 0.25
        subtotal     = precio_final * item['cantidad']
        total       += subtotal

        detalle = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=producto.id,
            cantidad=item['cantidad'],
            subtotal=subtotal,
            # Guardamos los sabores como texto separado por comas.
            sabor=', '.join(sabores_seleccionados) if sabores_seleccionados else None
        )
        db.session.add(detalle)

    # Añadimos el recargo del 15% de IVA si se solicito Factura Oficial (SRI)
    if nuevo_pedido.requiere_factura:
        total = round(total * 1.15, 2)

    # Guardamos el total calculado en el encabezado del pedido.
    nuevo_pedido.total = total

    # Paso 3: Validacion especial para pagos mixtos (efectivo + transferencia).
    if forma_pago == 'mixto':
        if not datos.get('numero_comprobante'):
            return jsonify({'error': 'El numero de comprobante es requerido para pagos mixtos'}), 400

        m_efect  = nuevo_pedido.monto_efectivo
        m_transf = nuevo_pedido.monto_transferencia
        # abs() calcula el valor absoluto para comparar sin importar el signo.
        # Usamos 0.01 como margen de tolerancia por decimales de punto flotante.
        if abs((m_efect + m_transf) - total) > 0.01:
            return jsonify({'error': f'Los montos (Efectivo: ${m_efect:.2f}, Transferencia: ${m_transf:.2f}) no suman el total del pedido (${total:.2f})'}), 400

    # Paso 4: Registramos la Venta inmediatamente (el registro contable).
    # Las ventas se crean aqui, no al momento de entrega, para garantizar
    # que el impacto financiero sea atomico (todo o nada).
    venta = Venta(
        pedido_id=nuevo_pedido.id,
        total=total,
        forma_pago=forma_pago,
        cliente_nombre=nuevo_pedido.cliente_nombre,
        cliente_identificacion=nuevo_pedido.cliente_identificacion,
        cliente_correo=nuevo_pedido.cliente_correo,
        cliente_telefono=nuevo_pedido.cliente_telefono,
        cliente_direccion=nuevo_pedido.cliente_direccion,
        requiere_factura=nuevo_pedido.requiere_factura,
        numero_comprobante=nuevo_pedido.numero_comprobante,
        monto_efectivo=nuevo_pedido.monto_efectivo,
        monto_transferencia=nuevo_pedido.monto_transferencia
    )
    db.session.add(venta)

    # Paso 5: Actualizamos los acumuladores de la Caja del dia.
    caja_abierta = Caja.query.filter_by(estado='abierta').first()
    if caja_abierta:
        caja_abierta.total_ingresos += total
        # Distribuimos el ingreso segun el metodo de pago para el desglose de caja.
        if forma_pago == 'efectivo':
            caja_abierta.total_efectivo += total
        elif forma_pago in ['transferencia', 'pago_pedidosya', 'tarjeta']:
            caja_abierta.total_transferencia += total
        elif forma_pago == 'mixto':
            caja_abierta.total_efectivo      += (nuevo_pedido.monto_efectivo      or 0.0)
            caja_abierta.total_transferencia += (nuevo_pedido.monto_transferencia or 0.0)

    # Avanzamos el contador de tickets para el proximo pedido.
    _avanzar_contador_tickets()

    # Paso 6: Confirmamos toda la transaccion en la base de datos.
    db.session.commit()
    
    # IMPORTANTE: Despues de guardar en BD, lo mando al SRI
    if nuevo_pedido.requiere_factura == True:
        import eventlet
        from routes.facturacion import _procesar_factura_sri_background
        from flask import current_app
        # PROFE: Vi en un tutorial hindu que usar eventlet.spawn evita que se 
        # me cuelgue la ventana negra del servidor por internet lento.
        print("Mando esto pero no me trabo esperando")
        eventlet.spawn(_procesar_factura_sri_background, current_app._get_current_object(), venta.id)

    # Paso 7: Notificamos a la pantalla de cocina via WebSocket.
    # El try/except garantiza que si el socket falla, el pedido ya fue guardado
    # correctamente y la funcion retorna exito de todas formas.
    try:
        from extensions import socketio
        socketio.emit('actualizar_cocina', {'mensaje': 'Nuevo pedido', 'id': nuevo_pedido.id})
    except Exception as e:
        print(f"Error emitiendo socket: {e}")

    return jsonify({
        'mensaje':        'Pedido creado correctamente',
        'id':             nuevo_pedido.id,
        'numero_pedido':  _numero_visual_pedido(nuevo_pedido),
        'total':          total,
        'ticket_url':     f'/pedidos/{nuevo_pedido.id}/ticket',
        'ticket_guardado': False,
    }), 201


@pedidos_bp.route('/contador', methods=['GET'])
def obtener_siguiente_numero_pedido():
    """Retorna el numero de ticket que le correspondera al proximo pedido."""
    return jsonify({'siguiente_numero': _calcular_siguiente_numero_pedido()})


@pedidos_bp.route('/contador/reiniciar', methods=['POST'])
@login_required
def reiniciar_contador_pedidos():
    """
    Reinicia el contador visual de tickets a 1 y borra el numero asignado a pedidos anteriores.
    Exclusivo para root. Se recomienda usar junto con /limpiar-datos para evitar confusion visual.
    """
    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'No autorizado para reiniciar contador de pedidos'}), 403

    try:
        config = ConfiguracionSistema.query.filter_by(clave='contador_ticket_diario').first()
        if not config:
            config = ConfiguracionSistema(clave='contador_ticket_diario', valor_entero=1)
        else:
            config.valor_entero = 1

        # Borramos el numero asignado a todos los pedidos existentes.
        Pedido.query.update({Pedido.numero_pedido: None})

        db.session.add(config)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'No se pudo reiniciar el contador de pedidos'}), 500

    return jsonify({'mensaje': 'Contador visual reiniciado. El proximo pedido sera #1.'})


# ==========================================
# PUT /pedidos/<id>/estado -> Cambia el estado
# ==========================================

@pedidos_bp.route('/<int:pedido_id>/estado', methods=['PUT'])
def cambiar_estado(pedido_id):
    """
    Actualiza el estado de un pedido en su ciclo de vida de cocina.
    Estados posibles: pendiente -> en_proceso -> preparado -> entregado.

    Nota: el impacto financiero (venta y caja) ya fue registrado al crear el pedido.
    Este endpoint solo actualiza el estado operativo para la pantalla de cocina.
    Al cambiar el estado, se notifica a la cocina via WebSocket.
    """
    pedido       = Pedido.query.get_or_404(pedido_id)
    datos        = request.json
    nuevo_estado = datos['estado']

    pedido.estado = nuevo_estado
    db.session.commit()

    # Notificamos a la pantalla de cocina que debe actualizar su vista.
    try:
        from extensions import socketio
        socketio.emit('actualizar_cocina', {'mensaje': 'Estado actualizado'})
    except Exception:
        pass

    return jsonify({'mensaje': f'Estado actualizado a {nuevo_estado}'})


# ==========================================
# DELETE /pedidos/<id> -> Cancela un pedido
# ==========================================

@pedidos_bp.route('/<int:pedido_id>', methods=['DELETE'])
def eliminar_pedido(pedido_id):
    """
    Cancela y elimina un pedido activo.
    Si el pedido ya fue entregado, no se puede cancelar.

    Cuando se cancela un pedido, se revierte el impacto financiero:
    - Se elimina la Venta asociada.
    - Se descuentan los montos de los acumuladores de la Caja abierta.
    - Se eliminan los DetallePedido (items) del pedido.
    Todo esto ocurre dentro de una transaccion: si algo falla, se hace rollback completo.
    """
    pedido = Pedido.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'El pedido ya no existe o fue eliminado'}), 404

    if pedido.estado == 'entregado':
        return jsonify({'error': 'No se puede eliminar un pedido ya entregado'}), 400

    try:
        # Paso 1: revertir el impacto en la caja si existe una venta asociada.
        venta_asociada = Venta.query.filter_by(pedido_id=pedido.id).first()
        if venta_asociada:
            caja_abierta = Caja.query.filter_by(estado='abierta').first()
            if caja_abierta:
                # Revertimos el total de ingresos de la caja.
                caja_abierta.total_ingresos -= venta_asociada.total
                # Revertimos el desglose segun el metodo de pago original.
                if venta_asociada.forma_pago == 'efectivo':
                    caja_abierta.total_efectivo -= venta_asociada.total
                elif venta_asociada.forma_pago in ['transferencia', 'pago_pedidosya', 'tarjeta']:
                    caja_abierta.total_transferencia -= venta_asociada.total
                elif venta_asociada.forma_pago == 'mixto':
                    caja_abierta.total_efectivo      -= (venta_asociada.monto_efectivo      or 0.0)
                    caja_abierta.total_transferencia -= (venta_asociada.monto_transferencia or 0.0)
            db.session.delete(venta_asociada)

        # Paso 2: eliminar los items del pedido.
        DetallePedido.query.filter_by(pedido_id=pedido.id).delete()

        # Paso 3: eliminar el pedido.
        db.session.delete(pedido)
        db.session.commit()

        # Notificamos a la cocina que el pedido fue cancelado.
        try:
            from extensions import socketio
            socketio.emit('actualizar_cocina', {'mensaje': 'Pedido eliminado'})
        except Exception:
            pass

    except Exception:
        # Si algo falla, revertimos toda la transaccion para no dejar datos inconsistentes.
        db.session.rollback()
        return jsonify({'error': 'Ocurrio un problema al eliminar el pedido'}), 500

    return jsonify({'mensaje': 'Pedido eliminado correctamente'})


# ==========================================
# FUNCIONES AUXILIARES: GENERACION DE CPCL
# ==========================================
# CPCL (Comtec Printer Control Language) es el lenguaje nativo de la iMZ320.
# Cada linea de un documento CPCL es un comando que la impresora ejecuta en orden.
#
# Parametros del encabezado CPCL:
#   ! <offset> <hdpi> <vdpi> <altura_dots> <copias>
#   - offset: desplazamiento horizontal (0 = sin offset).
#   - hdpi/vdpi: resolucion horizontal y vertical (200 para la iMZ320).
#   - altura_dots: altura total del documento en dots (calculada dinamicamente).
#   - copias: numero de copias a imprimir.
#
# La iMZ320 usa papel de 3 pulgadas (72mm). A 203 DPI el ancho imprimible
# es de ~576 dots. El comando PW establece el ancho del papel.
#
# Comandos clave:
#   TEXT <fuente> <tamanio> <x> <y> <texto>  -> Imprime texto en la posicion dada.
#   LINE <x1> <y1> <x2> <y2> <grosor>        -> Dibuja una linea horizontal.
#   PRINT                                     -> Finaliza e imprime el documento.

def _construir_ticket_cpcl(pedido):
    """
    Genera el string CPCL del ticket de un pedido para la impresora Zebra iMZ320.

    El CPCL es texto plano: cada linea es un comando. La funcion construye
    las lineas dinamicamente segun los items del pedido y retorna el string completo.

    Consideraciones de formato para 72mm (576 dots):
    - Fuente 0 = fuente vectorial escalable de Zebra.
    - Tamanios usados: 28 (normal), 32 (subtitulo), 36 (titulo), 48 (total).
    - El avance vertical (Y) se acumula manualmente segun la altura de cada bloque.
    """
    # --- Constantes de layout ---
    ANCHO_DOTS  = 560   # Ancho imprimible en dots (72mm @ 203 DPI, con margenes).
    COL_CANT_X  = 370   # Columna de cantidad (alineada a la derecha).
    COL_PREC_X  = 460   # Columna de precio unitario.
    INTERLINEA  = 38    # Separacion vertical entre lineas de texto normales (dots).

    # Acumulador de posicion Y. Cada bloque incrementa este valor.
    y = 20
    # Lista de comandos CPCL. Al final se unen con saltos de linea.
    lineas = []

    def agregar_texto(fuente, tam, x, texto, negrita=False):
        """Agrega un comando TEXT al acumulador y avanza el cursor Y."""
        nonlocal y
        cmd_fuente = f"{fuente}" if not negrita else f"{fuente}"
        lineas.append(f"TEXT {cmd_fuente} {tam} {x} {y} {texto}")
        y += tam + 10

    def agregar_linea_horizontal():
        """Agrega una linea horizontal separadora y avanza el cursor Y."""
        nonlocal y
        y += 6
        lineas.append(f"LINE 0 {y} {ANCHO_DOTS} {y} 2")
        y += 12

    # --- Encabezado del negocio ---
    lineas.append(f"CENTER")                                     # Alineacion centrada.
    lineas.append(f"TEXT 4 1 0 {y} HELARTE")                    # Nombre en fuente grande.
    y += 50
    lineas.append(f"TEXT 0 28 0 {y} Ticket de Pedido")
    y += INTERLINEA

    agregar_linea_horizontal()

    # --- Metadatos del pedido ---
    lineas.append("LEFT")                                        # Cambio a alineacion izquierda.
    numero_display = _numero_visual_pedido(pedido)
    fecha_display  = pedido.fecha.strftime('%d/%m/%Y %H:%M')
    cliente        = (pedido.cliente_nombre or 'Consumidor final')[:28]  # Truncamos para que quepa.
    tipo_display   = pedido.tipo.upper()
    pago_display   = pedido.forma_pago.replace('_', ' ').title()

    lineas.append(f"TEXT 0 28 0 {y} Ticket: #{numero_display}")
    y += INTERLINEA
    lineas.append(f"TEXT 0 28 0 {y} Fecha:  {fecha_display}")
    y += INTERLINEA
    lineas.append(f"TEXT 0 28 0 {y} Cliente: {cliente}")
    y += INTERLINEA
    lineas.append(f"TEXT 0 28 0 {y} Tipo:   {tipo_display}")
    y += INTERLINEA
    lineas.append(f"TEXT 0 28 0 {y} Pago:   {pago_display}")
    y += INTERLINEA

    if pedido.numero_comprobante:
        comp = str(pedido.numero_comprobante)[:20]
        lineas.append(f"TEXT 0 28 0 {y} Comp:   #{comp}")
        y += INTERLINEA

    agregar_linea_horizontal()

    # --- Encabezado de la tabla de items ---
    lineas.append(f"TEXT 0 28 0 {y} Producto")
    lineas.append(f"TEXT 0 28 {COL_CANT_X} {y} Cant")
    lineas.append(f"TEXT 0 28 {COL_PREC_X} {y} Total")
    y += INTERLINEA

    agregar_linea_horizontal()

    # --- Items del pedido ---
    # Cada item ocupa una o dos lineas segun si tiene sabor.
    for d in pedido.detalles:
        nombre = d.producto.nombre[:22]   # Truncamos el nombre si es muy largo.
        subtotal_str = f"${float(d.subtotal):.2f}"

        lineas.append(f"TEXT 0 28 0 {y} {nombre}")
        lineas.append(f"TEXT 0 28 {COL_CANT_X} {y} {d.cantidad}x")
        lineas.append(f"TEXT 0 28 {COL_PREC_X} {y} {subtotal_str}")
        y += INTERLINEA

        # Si el item tiene sabor, lo imprimimos en una segunda linea con indentacion.
        if d.sabor:
            sabor_display = f"  > {d.sabor}"[:30]
            lineas.append(f"TEXT 0 24 0 {y} {sabor_display}")
            y += INTERLINEA - 6

    agregar_linea_horizontal()

    # --- Total ---
    total_str = f"TOTAL: ${float(pedido.total):.2f}"
    lineas.append(f"CENTER")
    lineas.append(f"TEXT 4 0 0 {y} {total_str}")    # Fuente grande para el total.
    y += 48

    agregar_linea_horizontal()

    # --- Mensaje de cierre ---
    lineas.append(f"TEXT 0 28 0 {y} Gracias por preferir Helarte!")
    y += INTERLINEA + 20    # Espacio extra antes del corte de papel.

    # --- Ensamblar el documento CPCL ---
    # El encabezado "! 0 200 200 <altura> 1" abre el documento.
    # La altura (y) debe calcularse DESPUES de generar todos los comandos.
    encabezado = f"! 0 200 200 {y} 1\nPW {ANCHO_DOTS}"
    cuerpo     = "\n".join(lineas)
    pie        = "PRINT"

    return f"{encabezado}\n{cuerpo}\n{pie}\n"


# ==========================================
# GET /pedidos/<id>/ticket/cpcl -> CPCL para impresora termica
# ==========================================

@pedidos_bp.route('/<int:pedido_id>/ticket/cpcl', methods=['GET'])
def generar_ticket_cpcl(pedido_id):
    """
    Genera y retorna el string CPCL del ticket de un pedido.

    Este endpoint es consumido por el modulo zebra.js del frontend,
    que lo envia a la impresora Zebra iMZ320 a traves del daemon
    Zebra Browser Print corriendo localmente en el PC de caja.

    Retorna text/plain (no JSON) porque el CPCL es un protocolo de texto
    que se envia directamente a la impresora sin procesamiento adicional.

    El header Access-Control-Allow-Origin es necesario porque Zebra Browser Print
    realiza la solicitud desde localhost, que es un origen diferente al servidor.
    """
    pedido = Pedido.query.get_or_404(pedido_id)
    cpcl   = _construir_ticket_cpcl(pedido)

    from flask import Response
    response = Response(cpcl, mimetype='text/plain')
    # Permitimos que el script del navegador lea esta respuesta desde cualquier origen.
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


# ==========================================
# GET /pedidos/<id>/ticket -> Descarga el PDF
# ==========================================

@pedidos_bp.route('/<int:pedido_id>/ticket', methods=['GET'])
def generar_ticket_pedido(pedido_id):
    """
    Genera y descarga el ticket PDF de un pedido especifico.
    Si el archivo ya fue generado previamente, lo sirve desde el disco.
    Si no existe, lo genera en ese momento y lo guarda para futuros usos.
    """
    pedido      = Pedido.query.get_or_404(pedido_id)
    ticket_path = _obtener_ticket_path(pedido.id)

    # Generamos el PDF solo si no existe ya en el sistema de archivos.
    if not os.path.exists(ticket_path):
        _guardar_ticket_pdf(pedido)

    return send_file(
        ticket_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'ticket_pedido_{pedido.id}.pdf'
    )


# ==========================================
# GET /pedidos/cliente/<identificacion> -> Buscar Cliente
# ==========================================

@pedidos_bp.route('/cliente/<identificacion>', methods=['GET'])
def buscar_cliente(identificacion):
    """
    Busca los datos de un cliente basado en su identificacion (Cedula/RUC)
    en el historial de ventas previas.
    Útil para autocompletar formularios SRI.
    """
    from models.models import Venta, Pedido
    from flask import jsonify
    ident = identificacion.strip()
    
    # Buscamos la última venta donde esta identificación fue usada
    venta = Venta.query.filter(Venta.cliente_identificacion == ident).order_by(Venta.id.desc()).first()
    
    if venta:
        return jsonify({
            'encontrado': True,
            'nombre': venta.cliente_nombre,
            'correo': venta.cliente_correo,
            'direccion': venta.cliente_direccion,
            'telefono': venta.cliente_telefono
        })
    else:
        # Fallback a pedido si no cerró venta todavía o falló pago
        pedido = Pedido.query.filter(Pedido.cliente_identificacion == ident).order_by(Pedido.id.desc()).first()
        if pedido:
            return jsonify({
                'encontrado': True,
                'nombre': pedido.cliente_nombre,
                'correo': pedido.cliente_correo,
                'direccion': pedido.cliente_direccion,
                'telefono': pedido.cliente_telefono
            })

    return jsonify({'encontrado': False})
