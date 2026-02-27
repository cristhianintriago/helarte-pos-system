from flask_login import UserMixin
from models.models import db

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), default='empleado')  # 'root', 'admin', 'empleado'

    # Métodos de verificación de rol reutilizables en toda la app
    def es_root(self):
        return self.rol == 'root'

    def es_admin_o_superior(self):
        return self.rol in ['root', 'admin']

    def puede_reabrir_caja(self):
        return self.rol in ['root', 'admin']

    def puede_gestionar_productos(self):
        return self.rol in ['root', 'admin']

    def puede_gestionar_usuarios(self):
        return self.rol == 'root'
