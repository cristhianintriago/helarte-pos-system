from flask_socketio import SocketIO

# Motor de comunicación bidireccional en tiempo real para el sistema KDS de cocina.
# Configurado para permitir CORS desde cualquier origen (útil en Railway / local).
socketio = SocketIO(cors_allowed_origins="*")
