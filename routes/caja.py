from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.models import db, Caja, Egreso, Venta
from datetime import datetime, date

caja_bp = Blueprint('caja', __name__, url_prefix='/caja')

@caja_bp.route('/abrir', methods=['POST'])
@login_required
def abrir_caja():
    """ 
    Permite abrir una nueva caja al inicio de la jornada.
    Solo puede haber una caja abierta por día.
    """
    from flask_login import current_user

    hoy = date.today()
    caja_hoy = Caja.query.filter(
        db.cast(Caja.fecha, db.Date) == hoy
    ).first()

    if caja_hoy:
        if caja_hoy.estado == 'abierta':
            return jsonify({'error': 'Ya hay una caja abierta hoy'}), 400
        else:
            if not current_user.puede_reabrir_caja():
                return jsonify({'error': 'La caja ya fue cerrada hoy. Solo un administrador puede reabrirla'}), 403
            caja_hoy.estado = 'abierta'
            db.session.commit()
            return jsonify({'mensaje': 'Caja reabierta correctamente'}), 200

    # Extraemos el monto con el cual el usuario abrirá la caja hoy
    datos = request.json
    nueva_caja = Caja(monto_inicial=datos['monto_inicial'])
    
    # Preparamos en sesión el objeto y hacemos persistencia (commit) hacia la BD
    db.session.add(nueva_caja)
    db.session.commit()
    return jsonify({'mensaje': 'Caja abierta correctamente', 'id': nueva_caja.id}), 201

@caja_bp.route('/egreso', methods=['POST'])
@login_required
def registrar_egreso():
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

@caja_bp.route('/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'error': 'No hay caja abierta'}), 400

    # Calculamos el monto final base 
    caja.monto_final = caja.monto_inicial + caja.total_ingresos - caja.total_egresos
    caja.estado = 'cerrada'

    db.session.commit()

    return jsonify({
        'mensaje': 'Caja cerrada correctamente',
        'monto_inicial': caja.monto_inicial,
        'total_ingresos': caja.total_ingresos,
        'total_efectivo': caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos': caja.total_egresos,
        'monto_final': caja.monto_final,
        'efectivo_en_caja': caja.monto_inicial + (caja.total_efectivo or 0) - caja.total_egresos
    })


@caja_bp.route('/reiniciar', methods=['POST'])
@login_required
def reiniciar_caja():
    """
    Ruta exclusiva para administradores y root.
    Permite reiniciar los contadores de la caja del día a cero,
    manteniendo el monto inicial y dejándola abierta.
    Útil para corrección de errores o apertura de una nueva jornada en el mismo día.
    """
    from flask_login import current_user

    if not current_user.puede_reabrir_caja():
        return jsonify({'error': 'No tienes permisos para reiniciar la caja'}), 403

    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        # Si está cerrada, la reabrimos y reiniciamos sus contadores
        hoy = date.today()
        caja = Caja.query.filter(db.cast(Caja.fecha, db.Date) == hoy).first()
        if not caja:
            return jsonify({'error': 'No hay caja registrada hoy'}), 404
        caja.estado = 'abierta'

    # Reiniciamos todos los contadores a cero preservando el monto_inicial
    caja.total_ingresos = 0.0
    caja.total_egresos = 0.0
    caja.total_efectivo = 0.0
    caja.total_transferencia = 0.0
    caja.monto_final = None

    # Eliminamos los egresos del día para que la pantalla quede limpia
    Egreso.query.filter_by(caja_id=caja.id).delete()

    # Eliminamos también las ventas del día para que el módulo de Ventas quede limpio
    hoy = date.today()
    ventas_hoy = Venta.query.filter(db.cast(Venta.fecha, db.Date) == hoy).all()
    for v in ventas_hoy:
        db.session.delete(v)

    db.session.commit()
    return jsonify({'mensaje': 'Caja reiniciada correctamente. Contadores y ventas del día en cero.'})


@caja_bp.route('/estado', methods=['GET'])
@login_required
def estado_caja():
    from flask_login import current_user

    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({
            'estado': 'cerrada',
            'mensaje': 'No hay caja abierta hoy',
            'is_admin': current_user.puede_reabrir_caja()
        })

    return jsonify({
        'estado': 'abierta',
        'monto_inicial': caja.monto_inicial,
        'total_ingresos': caja.total_ingresos,
        'total_efectivo': caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos': caja.total_egresos,
        'balance_actual': caja.monto_inicial + caja.total_ingresos - caja.total_egresos,
        'efectivo_en_caja': caja.monto_inicial + (caja.total_efectivo or 0) - caja.total_egresos,
        'is_admin': current_user.puede_reabrir_caja()  # Flag para mostrar botón de reinicio en el frontend
    })


@caja_bp.route('/egresos', methods=['GET'])
@login_required
def obtener_egresos():
    # ✅ Busca por la caja de HOY sin importar si está abierta o cerrada
    hoy = date.today()
    caja = Caja.query.filter(
        db.cast(Caja.fecha, db.Date) == hoy
    ).first()

    if not caja:
        return jsonify([])

    egresos = Egreso.query.filter_by(caja_id=caja.id).all()
    return jsonify([{
        'id': e.id,
        'descripcion': e.descripcion,
        'monto': float(e.monto)
    } for e in egresos])

@caja_bp.route('/historial', methods=['GET'])
@login_required
def historial_cajas():
    from datetime import date, timedelta
    hace_30_dias = date.today() - timedelta(days=30)

    cajas = Caja.query.filter(
        Caja.estado == 'cerrada',
        db.cast(Caja.fecha, db.Date) >= hace_30_dias
    ).order_by(Caja.fecha.desc()).all()

    return jsonify([{
        'id': c.id,
        'fecha': c.fecha.strftime('%d/%m/%Y'),
        'monto_inicial': float(c.monto_inicial),
        'total_ingresos': float(c.total_ingresos),
        'total_egresos': float(c.total_egresos),
        'monto_final': float(c.monto_final) if c.monto_final else 0.0
    } for c in cajas])


@caja_bp.route('/registros', methods=['DELETE'])
@login_required
def eliminar_registros_caja():
    """
    Endpoint exclusivo para root.
    Elimina registros de caja por sus IDs, incluyendo en cascada:
    - Egresos vinculados a esa caja
    - Ventas del período de esa caja (por fecha)
    """
    from flask_login import current_user
    from models.models import Venta

    if not current_user.puede_eliminar_registros():
        return jsonify({'error': 'Solo root puede eliminar registros de caja'}), 403

    datos = request.json
    ids = datos.get('ids', [])

    if not ids:
        return jsonify({'error': 'No se proporcionaron IDs'}), 400

    eliminadas = 0
    for caja_id in ids:
        caja = Caja.query.get(caja_id)
        if not caja:
            continue

        # Eliminamos los egresos de esta caja
        Egreso.query.filter_by(caja_id=caja.id).delete()

        # Eliminamos las ventas del día de esta caja
        fecha_caja = caja.fecha.date()
        ventas_del_dia = Venta.query.filter(
            db.cast(Venta.fecha, db.Date) == fecha_caja
        ).all()
        for v in ventas_del_dia:
            db.session.delete(v)

        db.session.delete(caja)
        eliminadas += 1

    db.session.commit()
    return jsonify({'mensaje': f'{eliminadas} registro(s) de caja eliminado(s) correctamente'})

