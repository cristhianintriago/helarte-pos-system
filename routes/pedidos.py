from flask import Blueprint, jsonify, request
from models.models import db, Pedido, DetallePedido, Producto, Venta, Caja
from datetime import datetime


pedidos_bp = Blueprint('pedidos', __name__, url_prefix='/pedidos')



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

    return jsonify({'mensaje': 'Pedido creado correctamente', 'id': nuevo_pedido.id, 'total': total}), 201

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
