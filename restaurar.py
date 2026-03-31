import os
import json

# 1. ¡PRIMERO DEFINIMOS LA VARIABLE DE ENTORNO!
# Pega tu External Database URL de Render (asegúrate de que empiece con postgresql://)
os.environ['DATABASE_URL'] = "postgresql://helarte_db_user:ifXB5yfbM6Hb6hsmhZgmghtPK0Jlbf4O@dpg-d75tctu3jp1c73djrfi0-a.oregon-postgres.render.com/helarte_db"

from app import app
from models.models import db, Producto
from sqlalchemy import text # <--- Importamos 'text' para comandos SQL puros

# 2. Leemos tu archivo de respaldo
with open('productos_backup.json', 'r', encoding='utf-8') as f:
    productos_json = json.load(f)

with app.app_context():
    print("Conectando a la Base de Datos en Render...")
    
    # 3. EL SUPER BORRADOR: Limpiamos los productos y todas sus dependencias (sabores, etc.)
    db.session.execute(text("TRUNCATE TABLE productos CASCADE;"))
    db.session.commit()

    print("Subiendo el menú oficial...")
    
    # 4. Inyectamos los reales
    for p in productos_json:
        nuevo = Producto(
            nombre=p['nombre'],
            precio=p['precio'],
            categoria=p['categoria']
        )
        db.session.add(nuevo)
    
    db.session.commit()
    print(f"✅ ¡Éxito! {len(productos_json)} productos inyectados directamente en la nube.")