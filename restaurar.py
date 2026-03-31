import json
import os

# 1. PEGA AQUÍ TU URL DE NEON (Asegúrate de que empiece con postgresql://)
os.environ['DATABASE_URL'] = "postgresql://helarte_db_user:ifXB5yfbM6Hb6hsmhZgmghtPK0Jlbf4O@dpg-d75tctu3jp1c73djrfi0-a/helarte_db"

from app import app
from models.models import db, Producto

# 2. Leemos tu archivo de respaldo
with open('productos_backup.json', 'r', encoding='utf-8') as f:
    productos_json = json.load(f)

with app.app_context():
    # 3. Solo restauramos si la base de datos está vacía
    if Producto.query.count() == 0:
        print("Restaurando productos en la nube...")
        for p in productos_json:
            # Filtramos solo los campos que sabemos que acepta tu modelo
            nuevo = Producto(
                nombre=p['nombre'],
                precio=p['precio'],
                categoria=p['categoria']
            )
            db.session.add(nuevo)
        
        db.session.commit()
        print(f"✅ ¡Éxito! {len(productos_json)} productos restaurados perfectamente.")
    else:
        print("⚠️ La base de datos ya tiene productos. No se hizo nada para evitar duplicados.")