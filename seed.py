# seed.py - Poblar la base de datos con productos de ejemplo
# Ejecutar UNA SOLA VEZ con: python seed.py

from app import app
from models.models import db, Producto

productos_ejemplo = [
    # Copas
    {'nombre': 'Copa Oreo',         'precio': 3.50, 'categoria': 'Copa'},
    {'nombre': 'Copa Brownie',       'precio': 3.75, 'categoria': 'Copa'},
    {'nombre': 'Copa Tropical',      'precio': 3.25, 'categoria': 'Copa'},
    {'nombre': 'Copa Clásica',       'precio': 2.75, 'categoria': 'Copa'},
    # Sundaes
    {'nombre': 'Sundae Chocolate',   'precio': 2.50, 'categoria': 'Sundae'},
    {'nombre': 'Sundae Fresa',       'precio': 2.50, 'categoria': 'Sundae'},
    {'nombre': 'Sundae Caramelo',    'precio': 2.75, 'categoria': 'Sundae'},
    # Malteadas
    {'nombre': 'Malteada Vainilla',  'precio': 4.00, 'categoria': 'Malteada'},
    {'nombre': 'Malteada Chocolate', 'precio': 4.00, 'categoria': 'Malteada'},
    {'nombre': 'Malteada Fresa',     'precio': 4.00, 'categoria': 'Malteada'},
    # Helados simples
    {'nombre': 'Bola Simple',        'precio': 1.00, 'categoria': 'Helado'},
    {'nombre': 'Bola Doble',         'precio': 1.75, 'categoria': 'Helado'},
    {'nombre': 'Cono Simple',        'precio': 1.25, 'categoria': 'Helado'},
]

with app.app_context():
    # Solo agrega si no hay productos ya cargados
    if Producto.query.count() == 0:
        for p in productos_ejemplo:
            db.session.add(Producto(**p))
        db.session.commit()
        print(f"✅ {len(productos_ejemplo)} productos cargados correctamente")
    else:
        print("⚠️ Ya existen productos en la base de datos, seed omitido")
