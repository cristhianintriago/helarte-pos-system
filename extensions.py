"""
extensions.py
-------------
Este archivo existe para resolver un problema clasico en proyectos Flask medianos
y grandes llamado "importacion circular" (circular import).

El problema ocurre cuando dos modulos se importan mutuamente:
    - app.py importa 'socketio' de extensions.py
    - routes/pedidos.py importa 'socketio' de extensions.py
    - Si socketio estuviera definido en app.py, pedidos.py tendria que importar app.py
      y app.py a su vez importaria pedidos.py -> bucle infinito de importaciones.

La solucion: crear una instancia de SocketIO aqui, sin ligarlo a una app todavia.
Luego, en app.py, se hace socketio.init_app(app) para conectar ambos.
"""

from flask_socketio import SocketIO

# Se crea la instancia de SocketIO sin pasar la app de Flask todavia.
# cors_allowed_origins="*" significa que cualquier dominio puede conectarse
# via WebSocket. En produccion mas estricta se limitaria a un dominio especifico.
socketio = SocketIO(cors_allowed_origins="*")

import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_database_uri():
    uri = os.getenv("DATABASE_URL")
    if uri and uri.startswith("postgres://"):
        # Esto cambia postgres:// por postgresql:// automáticamente
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri
    
#SE AÑADE ESTO EN EXTENSIONS.PY
