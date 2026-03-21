import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('instance/helarte.db')
        cursor = conn.cursor()
        
        # Add columns to pedidos
        try:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN numero_comprobante VARCHAR(50);")
            cursor.execute("ALTER TABLE pedidos ADD COLUMN monto_efectivo FLOAT;")
            cursor.execute("ALTER TABLE pedidos ADD COLUMN monto_transferencia FLOAT;")
            print("Tablas 'pedidos' actualizadas.")
        except Exception as e:
            print(f"Nota (pedidos): {e}")

        # Add columns to ventas
        try:
            cursor.execute("ALTER TABLE ventas ADD COLUMN numero_comprobante VARCHAR(50);")
            cursor.execute("ALTER TABLE ventas ADD COLUMN monto_efectivo FLOAT;")
            cursor.execute("ALTER TABLE ventas ADD COLUMN monto_transferencia FLOAT;")
            print("Tablas 'ventas' actualizadas.")
        except Exception as e:
            print(f"Nota (ventas): {e}")
            
        conn.commit()
        print("Migración completada exitosamente.")
    except Exception as e:
        print(f"Error general: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    migrate()
