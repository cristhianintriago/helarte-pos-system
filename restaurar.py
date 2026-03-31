import json
from app import app
from models.models import db, Producto

# 1. PEGA AQUÍ LA URL EXTERNA EXACTA QUE TIENES EN RENDER O NEON
URL_NUBE = "postgresql://helarte_db_user:ifXB5yfbM6Hb6hsmhZgmghtPK0Jlbf4O@dpg-d75tctu3jp1c73djrfi0-a.oregon-postgres.render.com/helarte_db"

# 2. Forzamos a Flask a usar esta URL, ignorando cualquier configuración de tu PC
app.config['SQLALCHEMY_DATABASE_URI'] = URL_NUBE

# 3. Leemos tu respaldo
with open('productos_backup.json', 'r', encoding='utf-8') as f:
    productos_json = json.load(f)

with app.app_context():
    print("Conectando a la nube y limpiando productos fantasma...")
    
    # Vaciamos la tabla de productos para tener un inicio limpio
    Producto.query.delete()
    db.session.commit()

    print("Inyectando el menú oficial de Helarte...")
    
    for p in productos_json:
        nuevo = Producto(
            nombre=p['nombre'],
            precio=p['precio'],
            categoria=p['categoria']
        )
        db.session.add(nuevo)
    
    db.session.commit()
    print(f"✅ ¡Éxito Total! {len(productos_json)} productos subidos a la base de datos en vivo.")