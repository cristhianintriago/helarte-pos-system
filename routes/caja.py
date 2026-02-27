from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.models import db, Caja, Egreso, Venta
from datetime import datetime, date

caja_bp = Blueprint('caja', __name__, url_prefix='/caja')


@caja_bp.route('/abrir', methods=['POST'])
@login_required
def abrir_caja():
    from flask_login import current_user

    hoy = date.today()
    caja_hoy = Caja.query.filter(
        db.func.date(Caja.fecha) == hoy
    ).first()

    if caja_hoy:
        if caja_hoy.estado == 'abierta':
            return jsonify({'error': 'Ya hay una caja abierta hoy'}), 400
        else:
            if not current_user.puede_reabrir_caja():
                return jsonify({'error': 'La caja ya fue cerrada hoy. Solo un administrador puede reabrirla'}), 403
            caja_hoy.estado = 'abierta'
            db.session.commit()
            return jsonify({'mensaje': 'Caja reabierta correctamente ✅'}), 200

    datos = request.json
    nueva_caja = Caja(monto_inicial=datos['monto_inicial'])
    db.session.add(nueva_caja)
    db.session.commit()
    return jsonify({'mensaje': 'Caja abierta correctamente ✅', 'id': nueva_caja.id}), 201


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
    return jsonify({'mensaje': 'Egreso registrado correctamente ✅'})


@caja_bp.route('/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'error': 'No hay caja abierta'}), 400

    caja.monto_final = caja.monto_inicial + caja.total_ingresos - caja.total_egresos
    caja.estado = 'cerrada'
    db.session.commit()

    return jsonify({
        'mensaje': 'Caja cerrada correctamente ✅',
        'monto_inicial': caja.monto_inicial,
        'total_ingresos': caja.total_ingresos,
        'total_efectivo': caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos': caja.total_egresos,
        'monto_final': caja.monto_final
    })


@caja_bp.route('/estado', methods=['GET'])
@login_required
def estado_caja():
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'estado': 'cerrada', 'mensaje': 'No hay caja abierta hoy'})

    return jsonify({
        'estado': 'abierta',
        'monto_inicial': caja.monto_inicial,
        'total_ingresos': caja.total_ingresos,
        'total_efectivo': caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos': caja.total_egresos,
        'balance_actual': caja.monto_inicial + caja.total_ingresos - caja.total_egresos
    })

@caja_bp.route('/egresos', methods=['GET'])
@login_required
def obtener_egresos():
    # ✅ Busca por la caja de HOY sin importar si está abierta o cerrada
    hoy = date.today()
    caja = Caja.query.filter(
        db.func.date(Caja.fecha) == hoy
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
        db.func.date(Caja.fecha) >= hace_30_dias
    ).order_by(Caja.fecha.desc()).all()

    return jsonify([{
        'id': c.id,
        'fecha': c.fecha.strftime('%d/%m/%Y'),
        'monto_inicial': float(c.monto_inicial),
        'total_ingresos': float(c.total_ingresos),
        'total_egresos': float(c.total_egresos),
        'monto_final': float(c.monto_final)
    } for c in cajas])
