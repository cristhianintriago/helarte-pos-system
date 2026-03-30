import sqlite3
import os

db_path = os.path.join('instance', 'helarte.db')
if not os.path.exists(db_path):
    print(f"La base de datos no existe en {db_path}")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE caja ADD COLUMN monto_declarado FLOAT;")
        print("EXITO: Columna monto_declarado agregada.")
    except Exception as e:
        print("ERROR/INFO monto_declarado:", e)
        
    try:
        c.execute("ALTER TABLE caja ADD COLUMN descuadre FLOAT;")
        print("EXITO: Columna descuadre agregada.")
    except Exception as e:
        print("ERROR/INFO descuadre:", e)

    conn.commit()
    conn.close()
    print("Migración completada con éxito.")
