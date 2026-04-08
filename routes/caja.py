"""
routes/caja.py
--------------
Aqui controlo si la caja esta abierta o cerrada.
Tambien los gastos que se hacen en el dia, le decimos egresos.
Tuve que buscar en foros como filtrar por fechas en sqlite porque no salia.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from models.models import db, Caja, Egreso, Venta
from datetime import datetime, date, timedelta
import pytz

# Zona horaria de Ecuador (mismo estandar que ventas.py y reportes.py)
ZONA_HORARIA_LOCAL = pytz.timezone('America/Guayaquil')

def a_hora_local(fecha_utc):
    """Convierte una fecha guardada en UTC a la hora local de Ecuador."""
    if fecha_utc is None:
        return None
    # Le decimos a Python que la fecha es UTC primero
    fecha_con_zona = pytz.utc.localize(fecha_utc)
    # Luego la convertimos a Ecuador
    return fecha_con_zona.astimezone(ZONA_HORARIA_LOCAL)

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

    # Determinamos que dia es hoy segun la zona horaria del negocio, no del servidor.
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy = ahora_local.date()
    from datetime import time

    # Construimos el rango del dia completo en hora local para luego convertir a UTC.
    # Esto es necesario porque la base de datos guarda todo en UTC estandar.
    inicio_hoy_local = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0))
    fin_hoy_local    = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59))
    
    # Convertimos los limites a UTC para la consulta SQL.
    inicio_hoy_utc = inicio_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)
    fin_hoy_utc    = fin_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)

    # Buscamos si ya existe una caja registrada para el dia de hoy (version local).
    caja_hoy = Caja.query.filter(Caja.fecha >= inicio_hoy_utc, Caja.fecha <= fin_hoy_utc).first()

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
    # Cierro la caja del dia, pidiendo al cajero que ponga lo que contó fisicamente
    # y hago una resta simple para ver si le falta plata
    caja = Caja.query.filter_by(estado='abierta').first()
    if not caja:
        return jsonify({'error': 'No hay caja abierta'}), 400

    datos = request.json or {}
    monto_declarado = datos.get('monto_declarado')  # Puede ser None: cierre rapido sin contar

    # Calculo del monto final teorico de la caja.
    caja.monto_final  = caja.monto_inicial + caja.total_ingresos - caja.total_egresos

    # Calculo del efectivo esperado en gaveta (solo efectivo, sin transferencias, menos egresos).
    efectivo_esperado = caja.monto_inicial + (caja.total_efectivo or 0.0) - caja.total_egresos

    # Si el cajero no declara un monto manual, usamos el efectivo esperado directamente.
    # Esto simplifica el cierre: el sistema asume que cuadra y registra descuadre = 0.
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
        'mensaje':          'Caja cerrada correctamente',
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
        # Si la caja ya fue cerrada, buscamos la del dia actual para mostrar sus egresos.
        # Debemos asegurar que 'hoy' sea segun la hora de Ecuador.
        ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
        hoy = ahora_local.date()
        from datetime import time

        # Rango del dia local convertido a UTC para la base de datos
        inicio_hoy_local = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0))
        fin_hoy_local    = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59))
        inicio_hoy_utc   = inicio_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)
        fin_hoy_utc      = fin_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)

        caja = Caja.query.filter(Caja.fecha >= inicio_hoy_utc, Caja.fecha <= fin_hoy_utc).first()
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
                try: os.remove(_obtener_ticket_path(pe.id))
                except: pass
                db.session.delete(pe)

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
        # Determinamos que dia es hoy segun la zona horaria de Ecuador (America/Guayaquil)
        ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
        hoy = ahora_local.date()
        from datetime import time

        # Definimos el rango del dia local convertido a UTC para buscar en la base de datos
        inicio_hoy_local = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0))
        fin_hoy_local    = ZONA_HORARIA_LOCAL.localize(datetime(hoy.year, hoy.month, hoy.day, 23, 59, 59))
        inicio_hoy_utc   = inicio_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)
        fin_hoy_utc      = fin_hoy_local.astimezone(pytz.utc).replace(tzinfo=None)

        # Buscamos la caja (sea abierta o cerrada) que corresponda al dia de hoy en el local
        caja = Caja.query.filter(Caja.fecha >= inicio_hoy_utc, Caja.fecha <= fin_hoy_utc).first()
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
    """
    Retorna los registros de caja cerrados de los ultimos 30 dias.
    Este historial se muestra en la seccion de reportes del modulo de caja.
    """
    # Calculamos el limite inferior de la consulta: 30 dias atras desde hoy (Ecuador).
    ahora_local = datetime.now(ZONA_HORARIA_LOCAL)
    hoy = ahora_local.date()
    hace_30_dias = hoy - timedelta(days=30)
    
    # Convertimos el inicio de hace 30 dias (local) a UTC para la base de datos.
    inicio_30_local = ZONA_HORARIA_LOCAL.localize(datetime(hace_30_dias.year, hace_30_dias.month, hace_30_dias.day, 0, 0, 0))
    inicio_30_utc   = inicio_30_local.astimezone(pytz.utc).replace(tzinfo=None)

    cajas = Caja.query.filter(
        Caja.estado == 'cerrada',
        Caja.fecha >= inicio_30_utc
    ).order_by(Caja.fecha.desc()).all()


    return jsonify([{
        'id':             c.id,
        'fecha':          a_hora_local(c.fecha).strftime('%d/%m/%Y'),
        'monto_inicial':  float(c.monto_inicial),
        'total_ingresos': float(c.total_ingresos),
        'total_egresos':  float(c.total_egresos),
        'efectivo_esperado': float(c.monto_inicial + (c.total_efectivo or 0.0) - c.total_egresos),
        'monto_declarado': float(c.monto_declarado) if c.monto_declarado is not None else 0.0,
        'descuadre':      float(c.descuadre) if c.descuadre is not None else 0.0
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
        # Debemos convertir la fecha de la caja (UTC) a local para determinar el rango correcto del dia.
        fecha_local = caja.fecha.replace(tzinfo=pytz.utc).astimezone(ZONA_HORARIA_LOCAL)
        dia_local   = fecha_local.date()

        # Rango del dia local vuelto a convertir a UTC para la consulta.
        inicio_l = ZONA_HORARIA_LOCAL.localize(datetime(dia_local.year, dia_local.month, dia_local.day, 0, 0, 0))
        fin_l    = ZONA_HORARIA_LOCAL.localize(datetime(dia_local.year, dia_local.month, dia_local.day, 23, 59, 59))
        inicio_u = inicio_l.astimezone(pytz.utc).replace(tzinfo=None)
        fin_u    = fin_l.astimezone(pytz.utc).replace(tzinfo=None)

        ventas_del_dia = Venta.query.filter(Venta.fecha >= inicio_u, Venta.fecha <= fin_u).all()

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
                    try: os.remove(_obtener_ticket_path(pe.id))
                    except: pass
                    db.session.delete(pe)

        # Paso 3: eliminamos el registro de caja.
        db.session.delete(caja)
        eliminadas += 1

    db.session.commit()
    return jsonify({'mensaje': f'{eliminadas} registro(s) de caja eliminado(s) correctamente'})
