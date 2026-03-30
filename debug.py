from app import app
from models.models import db, Caja, Egreso
import json

app.app_context().push()
cajas = Caja.query.all()
egresos = Egreso.query.all()

res = {
    'cajas': [{
        'id': c.id, 
        'estado': c.estado, 
        'fecha': str(c.fecha),
        'inicio': c.monto_inicial, 
        't_eg': c.total_egresos
    } for c in cajas],
    'egresos': [{
        'id': e.id,
        'caja_id': e.caja_id,
        'desc': e.descripcion,
        'monto': e.monto
    } for e in egresos]
}

print(json.dumps(res, indent=2))
