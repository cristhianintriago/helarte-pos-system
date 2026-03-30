"""
routes/caja.py
--------------
Blueprint para la gestion del turno de caja (apertura, cierre, egresos e historial).

La caja representa el registro financiero de un turno de trabajo. Su ciclo de vida es:
1. Apertura: el cajero declara cuanto dinero hay en la gaveta al iniciar el dia.
2. Operacion: a lo largo del dia se acumulan ingresos (ventas) y egresos (gastos).
3. Cierre Ciego (Blind Close): al terminar, el cajero cuenta el dinero fisicamente
   y declara el monto sin ver lo que el sistema espera. Esto es una tecnica de auditoria
   que detecta errores o faltantes sin dar "pistas" al cajero de cuanto deberia haber.
4. Historial: los registros cerrados quedan guardados para reportes futuros.

NOTA sobre el filtro de fechas:
----
Se usan rangos de tiempo (>= inicio_dia, <= fin_dia) en lugar de funciones tipo
CAST o func.date(). Esto es porque SQLite y PostgreSQL manejan las conversiones
de fecha de forma diferente. El enfoque de rangos funciona correctamente en ambos
motores de base de datos sin modificaciones adicionales.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.models import db, Caja, Egreso, Venta
from datetime import datetime, date

caja_bp = Blueprint('caja', __name__, url_prefix='/caja')


@caja_bp.route('/abrir', methods=['POST'])
@login_required
def abrir_caja():
    """
    Abre una nueva caja al inicio de la jornada.

    Reglas de negocio:
    - Solo puede existir una caja abierta por dia.
    - Si ya existe una caja cerrada hoy, solo admin/root puede reabrirla.
    - Si no existe ninguna caja hoy, se crea una nueva con el monto inicial recibido.
    """
    from flask_login import current_user

    hoy = date.today()
    from datetime import time

    # Construimos el rango completo del dia de hoy: desde las 00:00:00 hasta las 23:59:59.
    # Esto permite filtrar todos los registros de caja creados en el dia actual,
    # independientemente de la hora exacta en que fueron creados.
    inicio_hoy = datetime.combine(hoy, time.min)
    fin_hoy    = datetime.combine(hoy, time.max)
    caja_hoy   = Caja.query.filter(Caja.fecha >= inicio_hoy, Caja.fecha <= fin_hoy).first()

    if caja_hoy:
        if caja_hoy.estado == 'abierta':
            # Ya hay una caja activa: no se permite abrir otra.
            return jsonify({'error': 'Ya hay una caja abierta hoy'}), 400
        else:
            # La caja de hoy esta cerrada. Solo admin/root pueden reabrirla.
            if not current_user.puede_reabrir_caja():
                return jsonify({'error': 'La caja ya fue cerrada hoy. Solo un administrador puede reabrirla'}), 403
            caja_hoy.estado = 'abierta'
            db.session.commit()
            return jsonify({'mensaje': 'Caja reabierta correctamente'}), 200

    # No existe caja hoy: creamos un nuevo registro con el monto inicial del formulario.
    datos = request.json
    nueva_caja = Caja(monto_inicial=datos['monto_inicial'])
    db.session.add(nueva_caja)
    db.session.commit()
    return jsonify({'mensaje': 'Caja abierta correctamente', 'id': nueva_caja.id}), 201


@caja_bp.route('/egreso', methods=['POST'])
@login_required
def registrar_egreso():
    """
    Registra un gasto realizado durante el turno (egreso).
    El monto se descuenta del total de egresos de la caja abierta.
    Ejemplos de egresos: compra de insumos, pago a proveedores, cambio de caja chica.
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
    # Actualizamos el acumulador de egresos en la caja del dia.
    caja.total_egresos += datos['monto']

    db.session.add(egreso)
    db.session.commit()
    return jsonify({'mensaje': 'Egreso registrado correctamente'})


@caja_bp.route('/cerrar', methods=['POST'])
@login_required
def cerrar_caja():
    """
    Cierra el turno de caja aplicando el protocolo de Cierre Ciego (Blind Close).

    El Cierre Ciego es una tecnica de auditoria interna:
    1. El sistema NO muestra al cajero cuanto dinero deberia haber en la gaveta.
    2. El cajero cuenta el dinero fisicamente y declara el monto que encontro.
    3. El sistema calcula el descuadre: diferencia entre lo declarado y lo esperado.
       - Descuadre positivo (sobrante): habia mas dinero del esperado.
       - Descuadre negativo (faltante): habia menos dinero del esperado.
    4. El descuadre queda registrado en la base de datos para auditoria.
    """
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'error': 'No hay caja abierta'}), 400

    datos = request.json or {}
    monto_declarado = datos.get('monto_declarado')

    # El monto declarado es obligatorio para el Cierre Ciego.
    if monto_declarado is None:
        return jsonify({'error': 'Debes declarar el monto fisico en caja para certificar el cierre'}), 400

    # Convertimos a float y manejamos el caso de input no numerico.
    try:
        monto_declarado = float(monto_declarado)
    except ValueError:
        return jsonify({'error': 'El monto declarado no es valido'}), 400

    # Calculo del monto final teorico de la caja.
    # Formula: lo que habia al abrir + todo lo que entro - todo lo que salio.
    caja.monto_final = caja.monto_inicial + caja.total_ingresos - caja.total_egresos

    # Calculo del efectivo esperado en la gaveta fisica.
    # Solo se cuenta el efectivo real (no transferencias) menos los egresos.
    efectivo_esperado = caja.monto_inicial + (caja.total_efectivo or 0.0) - caja.total_egresos

    # Guardamos los datos del Cierre Ciego y marcamos la caja como cerrada.
    caja.monto_declarado = monto_declarado
    caja.descuadre       = monto_declarado - efectivo_esperado
    caja.estado          = 'cerrada'

    db.session.commit()

    return jsonify({
        'mensaje': 'Caja cerrada auditada correctamente',
        'monto_inicial':      caja.monto_inicial,
        'total_ingresos':     caja.total_ingresos,
        'total_efectivo':     caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos':      caja.total_egresos,
        'monto_final':        caja.monto_final,
        'efectivo_esperado':  efectivo_esperado,
        'monto_declarado':    caja.monto_declarado,
        'descuadre':          caja.descuadre
    })


@caja_bp.route('/reiniciar', methods=['POST'])
@login_required
def reiniciar_caja():
    """
    Ruta exclusiva para administradores y root.
    Reinicia todos los contadores de la caja del dia a cero, dejandola en estado 'abierta'.
    Tambien elimina los egresos y las ventas registradas durante el dia.
    Util para corregir errores graves al inicio del turno o para pruebas del sistema.
    """
    from flask_login import current_user

    if not current_user.puede_reabrir_caja():
        return jsonify({'error': 'No tienes permisos para reiniciar la caja'}), 403

    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        # Si no hay caja abierta, buscamos la de hoy para reabrirla antes de reiniciar.
        hoy = date.today()
        from datetime import time
        inicio, fin = datetime.combine(hoy, time.min), datetime.combine(hoy, time.max)
        caja = Caja.query.filter(Caja.fecha >= inicio, Caja.fecha <= fin).first()
        if not caja:
            return jsonify({'error': 'No hay caja registrada hoy'}), 404
        caja.estado = 'abierta'

    # Ponemos todos los acumuladores en cero, manteniendo el monto_inicial intacto.
    caja.total_ingresos     = 0.0
    caja.total_egresos      = 0.0
    caja.total_efectivo     = 0.0
    caja.total_transferencia = 0.0
    caja.monto_final        = None

    # Eliminamos los egresos vinculados a esta caja.
    Egreso.query.filter_by(caja_id=caja.id).delete()

    # Eliminamos las ventas del dia para que el historial quede limpio tras el reinicio.
    from datetime import time
    hoy = date.today()
    inicio, fin = datetime.combine(hoy, time.min), datetime.combine(hoy, time.max)
    ventas_hoy = Venta.query.filter(Venta.fecha >= inicio, Venta.fecha <= fin).all()
    for v in ventas_hoy:
        db.session.delete(v)

    db.session.commit()
    return jsonify({'mensaje': 'Caja reiniciada correctamente. Contadores y ventas del dia en cero.'})


@caja_bp.route('/estado', methods=['GET'])
@login_required
def estado_caja():
    """
    Retorna el estado actual de la caja para que el frontend muestre la informacion
    de turno actualizada (saldos, totales, estado de la sesion).
    """
    from flask_login import current_user

    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({
            'estado': 'cerrada',
            'mensaje': 'No hay caja abierta hoy',
            # El frontend usa is_admin para mostrar u ocultar el boton de reinicio.
            'is_admin': current_user.puede_reabrir_caja()
        })

    return jsonify({
        'estado': 'abierta',
        'monto_inicial':     caja.monto_inicial,
        'total_ingresos':    caja.total_ingresos,
        'total_efectivo':    caja.total_efectivo,
        'total_transferencia': caja.total_transferencia,
        'total_egresos':     caja.total_egresos,
        # balance_actual = total teorico del dinero manejado durante el dia.
        'balance_actual':    caja.monto_inicial + caja.total_ingresos - caja.total_egresos,
        # efectivo_en_caja = estimado del efectivo fisico en la gaveta ahora mismo.
        'efectivo_en_caja':  caja.monto_inicial + (caja.total_efectivo or 0) - caja.total_egresos,
        'is_admin':          current_user.puede_reabrir_caja()
    })


@caja_bp.route('/egresos', methods=['GET'])
@login_required
def obtener_egresos():
    """
    Retorna la lista de egresos asociados a la caja activa del dia.
    Primero busca una caja abierta. Si no hay, busca la caja de hoy (ya cerrada)
    para que el cajero pueda ver el historial de gastos incluso despues del cierre.
    """
    # Se prioriza la caja con estado 'abierta' (la activa del turno actual).
    caja = Caja.query.filter_by(estado='abierta').first()

    if not caja:
        # Si la caja ya fue cerrada, buscamos la del dia actual para mostrar sus egresos.
        hoy = date.today()
        from datetime import time
        caja = Caja.query.filter(
            Caja.fecha >= datetime.combine(hoy, time.min),
            Caja.fecha <= datetime.combine(hoy, time.max)
        ).first()

    if not caja:
        # Si no existe ninguna caja hoy, retornamos una lista vacia.
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
    """
    Retorna los registros de caja cerrados de los ultimos 30 dias.
    Este historial se muestra en la seccion de reportes del modulo de caja.
    """
    from datetime import timedelta, time

    # Calculamos el limite inferior de la consulta: 30 dias atras desde hoy.
    hace_30_dias = date.today() - timedelta(days=30)
    # Construimos el datetime de inicio para el filtro de rango.
    inicio_30 = datetime.combine(hace_30_dias, time.min)

    cajas = Caja.query.filter(
        Caja.estado == 'cerrada',
        Caja.fecha >= inicio_30
    ).order_by(Caja.fecha.desc()).all()

    return jsonify([{
        'id':             c.id,
        'fecha':          c.fecha.strftime('%d/%m/%Y'),
        'monto_inicial':  float(c.monto_inicial),
        'total_ingresos': float(c.total_ingresos),
        'total_egresos':  float(c.total_egresos),
        # Si monto_final es NULL (caja reiniciada sin cerrar), devolvemos 0.0.
        'monto_final':    float(c.monto_final) if c.monto_final else 0.0
    } for c in cajas])


@caja_bp.route('/registros', methods=['DELETE'])
@login_required
def eliminar_registros_caja():
    """
    Endpoint exclusivo para root.
    Elimina una seleccion de registros de caja por sus IDs.
    Ademas elimina en cascada los egresos y las ventas del periodo de cada caja.
    Esta operacion es irreversible y solo debe usarse para correccion de datos.
    """
    from flask_login import current_user
    from models.models import Venta
    from datetime import time

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
            continue  # Si el ID no existe, lo ignoramos y seguimos con el siguiente.

        # Paso 1: eliminamos los egresos vinculados a esta caja.
        Egreso.query.filter_by(caja_id=caja.id).delete()

        # Paso 2: eliminamos las ventas del dia que corresponde a esta caja.
        # Usamos un rango de tiempo para ser compatibles con SQLite y PostgreSQL.
        fecha_caja = caja.fecha.date()
        inicio = datetime.combine(fecha_caja, time.min)
        fin    = datetime.combine(fecha_caja, time.max)
        ventas_del_dia = Venta.query.filter(Venta.fecha >= inicio, Venta.fecha <= fin).all()
        for v in ventas_del_dia:
            db.session.delete(v)

        # Paso 3: eliminamos el registro de caja.
        db.session.delete(caja)
        eliminadas += 1

    db.session.commit()
    return jsonify({'mensaje': f'{eliminadas} registro(s) de caja eliminado(s) correctamente'})
