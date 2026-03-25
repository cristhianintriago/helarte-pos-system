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

    # ==========================================
    # Métodos de verificación de rol
    # Usarlos en los decoradores de rutas y en las plantillas Jinja2
    # ==========================================

    def es_root(self):
        """El 'superusuario'. Tiene acceso total al sistema, incluyendo eliminar registros."""
        return self.rol == 'root'

    def es_admin_o_superior(self):
        """Admin y root pueden gestionar la caja, productos y ver reportes."""
        return self.rol in ['root', 'admin']

    def puede_reabrir_caja(self):
        """Solo admin y root pueden reabrir o reiniciar una caja ya cerrada."""
        return self.rol in ['root', 'admin']

    def puede_gestionar_productos(self):
        """Admin y root pueden crear, editar y eliminar productos del menú."""
        return self.rol in ['root', 'admin']

    def puede_modificar_precios(self):
        """Admin y root pueden modificar los precios de los productos."""
        return self.rol in ['root', 'admin']

    def puede_gestionar_usuarios(self):
        """Root y admin pueden ver y gestionar usuarios del sistema."""
        return self.rol in ['root', 'admin']

    def puede_crear_usuarios(self):
        """Root puede crear cualquier rol. Admin solo puede crear empleados."""
        return self.rol in ['root', 'admin']

    def puede_eliminar_registros(self):
        """Solo root puede eliminar registros históricos de caja y ventas."""
        return self.rol == 'root'

    def roles_creables(self):
        """Retorna la lista de roles que este usuario puede asignar al crear otro."""
        if self.es_root():
            return ['admin', 'empleado']
        if self.rol == 'admin':
            return ['empleado']
        return []
