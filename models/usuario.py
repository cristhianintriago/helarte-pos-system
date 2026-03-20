from flask_login import UserMixin
from models.models import db

# La clase hereda de db.Model (necesario para ser una tabla en la BD)
# y de UserMixin (provee implementaciones por defecto de los métodos is_authenticated, is_active, get_id, etc. para Flask-Login).
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # unique=True, no pueden existir dos usuarios con el mismo nombre
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
