"""
routes/caja.py
--------------
Modulo de gestion de caja: apertura, cierre, egresos e historial.

TIMEZONE DESIGN (post-refactor):
- Todos los timestamps se almacenan en UTC (campo 'fecha').
- El dia de negocio se representa con 'fecha_operativa' (tipo Date, zona Ecuador).
- Las busquedas de "la caja de hoy" usan 'fecha_operativa == hoy_local',
  NO rangos UTC calculados en tiempo real. Esto es inmune al crossover UTC a las 19:00.
- Todas las conversiones de zona horaria pasan por utils.tz_utils.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.models import db, Caja, Egreso, Venta
from datetime import datetime, date, timedelta
from utils.tz_utils import (
    ahora_utc,
    ahora_local,
    fecha_operativa_hoy,
    fecha_operativa_de,
    rango_utc_de_fecha,
    formatear_local,
)

caja_bp = Blueprint('caja', __name__, url_prefix='/caja')


def _caja_de_hoy():
    """
    Retorna la Caja correspondiente al dia de negocio de HOY (Ecuador).
    Usa fecha_operativa para el filtro, lo que hace la consulta inmune al
    cambio de dia UTC (que ocurre a las 19:00 Ecuador).

    Returns:
        Objeto Caja si existe registro para hoy, None en caso contrario.
    """
    hoy = fecha_operativa_hoy()
    return Caja.query.filter_by(fecha_operativa=hoy).first()


def _caja_de_fecha(fecha_negocio: date):
    """
    Retorna la Caja de una fecha de negocio especifica.

    Args:
        fecha_negocio: date en zona horaria del negocio.

    Returns:
        Objeto Caja si existe, None en caso contrario.
    """
    return Caja.query.filter_by(fecha_operativa=fecha_negocio).first()


# ==============================================================================
# APERTURA
# ==============================================================================

@caja_bp.route('/abrir', methods=['POST'])
@login_required
def abrir_caja():
    """
    Abre una nueva caja al inicio de la jornada.

    Reglas de negocio:
    - Solo puede existir una caja por fecha_operativa.
    - Si ya existe una caja cerrada hoy, solo admin/root puede reabrirla.
    - Si no existe ninguna caja hoy, se crea una nueva con el monto inicial recibido.
    """
    from flask_login import current_user

    hoy = fecha_operativa_hoy()
    caja_hoy = _caja_de_hoy()

    if caja_hoy:
        if caja_hoy.estado == 'abierta':
            return jsonify({'error': 'Ya hay una caja abierta hoy'}), 400
        else:
            # Caja cerrada: solo admin/root pueden reabrirla.
            if not current_user.puede_reabrir_caja():
                return jsonify({'error': 'La caja ya fue cerrada hoy. Solo un administrador puede reabrirla'}), 403
            caja_hoy.estado = 'abierta'
            db.session.commit()
            return jsonify({'mensaje': 'Caja reabierta correctamente'}), 200

    # No existe caja hoy: se crea un nuevo registro.
    datos = request.json
    nueva_caja = Caja(
        monto_inicial=datos['monto_inicial'],
        fecha=ahora_utc(),           # Timestamp de apertura en UTC (auditoria)
        fecha_operativa=hoy,         # Fecha del negocio en Ecuador (logica de dia)
    )
    db.session.add(nueva_caja)
    db.session.commit()
    return jsonify({'mensaje': 'Caja abierta correctamente', 'id': nueva_caja.id}), 201


# ==============================================================================
# EGRESOS
# ==============================================================================

@caja_bp.route('/egreso', methods=['POST'])
@login_required
def registrar_egreso():
    """
    Registra un gasto realizado durante el turno (egreso).
    El monto se descuenta del total de egresos de la caja abierta.
    """
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'error': 'No hay caja abierta'}), 400

    datos = request.json
    egreso = Egreso(
        caja_id=caja.id,
        descripcion=datos['descripcion'],
        monto=datos['monto']
    )
    caja.total_egresos += datos['monto']

    db.session.add(egreso)
    db.session.commit()
    return jsonify({'mensaje': 'Egreso registrado correctamente'})


# ==============================================================================
# CIERRE
# ==============================================================================

@caja_bp.route('/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    """
    Cierra la caja activa, calcula el descuadre y registra el monto declarado.
    El cierre SOLO ocurre por accion explicita del cajero desde el frontend.
    No hay ningun mecanismo automatico de cierre por cambio de dia.
    """
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'error': 'No hay caja abierta'}), 400

    datos = request.json or {}
    monto_declarado = datos.get('monto_declarado')

    caja.monto_final = caja.monto_inicial + caja.total_ingresos - caja.total_egresos
    efectivo_esperado = caja.monto_inicial + (caja.total_efectivo or 0.0) - caja.total_egresos

    if monto_declarado is None:
        monto_declarado = efectivo_esperado
    else:
        try:
            monto_declarado = float(monto_declarado)
        except ValueError:
            return jsonify({'error': 'El monto declarado no es valido'}), 400

    caja.monto_declarado = monto_declarado
    caja.descuadre       = round(monto_declarado - efectivo_esperado, 2)
    caja.estado          = 'cerrada'

    db.session.commit()

    return jsonify({
        'mensaje':             'Caja cerrada correctamente',
        'monto_inicial':       caja.monto_inicial,
        'total_ingresos':      caja.total_ingresos,
        'total_efectivo':      caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos':       caja.total_egresos,
        'monto_final':         caja.monto_final,
        'efectivo_esperado':   efectivo_esperado,
        'monto_declarado':     caja.monto_declarado,
        'descuadre':           caja.descuadre
    })


# ==============================================================================
# REINICIO (solo admin/root)
# ==============================================================================

@caja_bp.route('/reiniciar', methods=['POST'])
@login_required
def reiniciar_caja():
    """
    Reinicia los contadores de la caja del dia a cero.
    Tambien elimina las ventas registradas durante el dia.
    Solo disponible para administradores.
    """
    from flask_login import current_user

    if not current_user.puede_reabrir_caja():
        return jsonify({'error': 'No tienes permisos para reiniciar la caja'}), 403

    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        # Buscamos la caja de hoy (ya cerrada) para reiniciarla.
        caja = _caja_de_hoy()
        if not caja:
            return jsonify({'error': 'No hay caja registrada hoy'}), 404
        caja.estado = 'abierta'

    # Ponemos todos los acumuladores en cero.
    caja.total_ingresos      = 0.0
    caja.total_egresos       = 0.0
    caja.total_efectivo      = 0.0
    caja.total_transferencia = 0.0
    caja.monto_final         = None

    Egreso.query.filter_by(caja_id=caja.id).delete()

    # Eliminamos las ventas del dia de negocio de esta caja.
    # Usamos fecha_operativa para calcular el rango UTC correcto.
    fecha_op = caja.fecha_operativa or fecha_operativa_de(caja.fecha)
    if fecha_op:
        inicio_utc, fin_utc = rango_utc_de_fecha(fecha_op)
        ventas_hoy = Venta.query.filter(
            Venta.fecha >= inicio_utc,
            Venta.fecha <= fin_utc
        ).all()

        for v in ventas_hoy:
            from models.models import FacturaSRI, Pedido, DetallePedido
            import os
            from routes.pedidos import _obtener_ticket_path

            FacturaSRI.query.filter_by(venta_id=v.id).delete()
            pe_id = v.pedido_id
            db.session.delete(v)

            if pe_id:
                pe = Pedido.query.get(pe_id)
                if pe:
                    DetallePedido.query.filter_by(pedido_id=pe.id).delete()
                    try:
                        os.remove(_obtener_ticket_path(pe.id))
                    except Exception:
                        pass
                    db.session.delete(pe)

    db.session.commit()
    return jsonify({'mensaje': 'Caja reiniciada correctamente. Contadores y ventas del dia en cero.'})


# ==============================================================================
# ESTADO ACTUAL
# ==============================================================================

@caja_bp.route('/estado', methods=['GET'])
@login_required
def estado_caja():
    """
    Retorna el estado actual de la caja activa.
    """
    from flask_login import current_user

    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({
            'estado':   'cerrada',
            'mensaje':  'No hay caja abierta hoy',
            'is_admin': current_user.puede_reabrir_caja()
        })

    return jsonify({
        'estado':              'abierta',
        'monto_inicial':       caja.monto_inicial,
        'total_ingresos':      caja.total_ingresos,
        'total_efectivo':      caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos':       caja.total_egresos,
        'balance_actual':      caja.monto_inicial + caja.total_ingresos - caja.total_egresos,
        'efectivo_en_caja':    caja.monto_inicial + (caja.total_efectivo or 0) - caja.total_egresos,
        'is_admin':            current_user.puede_reabrir_caja()
    })


# ==============================================================================
# EGRESOS DEL DIA
# ==============================================================================

@caja_bp.route('/egresos', methods=['GET'])
@login_required
def obtener_egresos():
    """
    Retorna la lista de egresos de la caja activa o de la caja de hoy (ya cerrada).
    """
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        caja = _caja_de_hoy()
        if not caja:
            return jsonify([])

    egresos = Egreso.query.filter_by(caja_id=caja.id).all()
    return jsonify([{
        'id':          e.id,
        'descripcion': e.descripcion,
        'monto':       float(e.monto)
    } for e in egresos])


# ==============================================================================
# HISTORIAL
# ==============================================================================

@caja_bp.route('/historial', methods=['GET'])
@login_required
def historial_cajas():
    """
    Retorna los registros de caja cerrados de los ultimos 30 dias.
    Usa fecha_operativa para filtrar por dia de negocio, no por timestamp UTC.
    """
    hoy          = fecha_operativa_hoy()
    hace_30_dias = hoy - timedelta(days=30)

    cajas = Caja.query.filter(
        Caja.estado == 'cerrada',
        Caja.fecha_operativa >= hace_30_dias
    ).order_by(Caja.fecha_operativa.desc()).all()

    # Fallback para cajas antiguas sin fecha_operativa: usamos el timestamp UTC convertido.
    resultado = []
    for c in cajas:
        fecha_display = (
            c.fecha_operativa.strftime('%d/%m/%Y')
            if c.fecha_operativa
            else formatear_local(c.fecha, '%d/%m/%Y')
        )
        resultado.append({
            'id':                c.id,
            'fecha':             fecha_display,
            'monto_inicial':     float(c.monto_inicial),
            'total_ingresos':    float(c.total_ingresos),
            'total_egresos':     float(c.total_egresos),
            'efectivo_esperado': float(c.monto_inicial + (c.total_efectivo or 0.0) - c.total_egresos),
            'monto_declarado':   float(c.monto_declarado) if c.monto_declarado is not None else 0.0,
            'descuadre':         float(c.descuadre) if c.descuadre is not None else 0.0
        })

    return jsonify(resultado)


# ==============================================================================
# ELIMINACION (solo root)
# ==============================================================================

@caja_bp.route('/registros', methods=['DELETE'])
@login_required
def eliminar_registros_caja():
    """
    Elimina registros de caja por ID (solo root).
    Elimina en cascada los egresos y ventas del dia de negocio de cada caja.
    """
    from flask_login import current_user

    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'Solo root puede eliminar registros de caja'}), 403

    datos = request.json
    ids   = datos.get('ids', [])
    if not ids:
        return jsonify({'error': 'No se proporcionaron IDs'}), 400

    eliminadas = 0
    for caja_id in ids:
        caja = Caja.query.get(caja_id)
        if not caja:
            continue

        Egreso.query.filter_by(caja_id=caja.id).delete()

        # Determinamos el dia de negocio de esta caja para eliminar sus ventas.
        fecha_op = caja.fecha_operativa or fecha_operativa_de(caja.fecha)
        if fecha_op:
            inicio_utc, fin_utc = rango_utc_de_fecha(fecha_op)
            ventas_del_dia = Venta.query.filter(
                Venta.fecha >= inicio_utc,
                Venta.fecha <= fin_utc
            ).all()

            for v in ventas_del_dia:
                from models.models import FacturaSRI, Pedido, DetallePedido
                import os
                from routes.pedidos import _obtener_ticket_path

                FacturaSRI.query.filter_by(venta_id=v.id).delete()
                pe_id = v.pedido_id
                db.session.delete(v)

                if pe_id:
                    pe = Pedido.query.get(pe_id)
                    if pe:
                        DetallePedido.query.filter_by(pedido_id=pe.id).delete()
                        try:
                            os.remove(_obtener_ticket_path(pe.id))
                        except Exception:
                            pass
                        db.session.delete(pe)

        db.session.delete(caja)
        eliminadas += 1

    db.session.commit()
    return jsonify({'mensaje': f'{eliminadas} registro(s) de caja eliminado(s) correctamente'})
