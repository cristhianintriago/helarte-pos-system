"""
models/usuario.py
-----------------
Aqui va la base de datos de los usuarios. Heredo de UserMixin copiado de la 
documentacion oficial para no hacer la sesion de login a mano y no aplazarme.
"""

from flask_login import UserMixin
from models.models import db


class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id       = db.Column(db.Integer, primary_key=True)
    # unique=True garantiza que no haya dos usuarios con el mismo nombre en la tabla.
    username = db.Column(db.String(50),  unique=True, nullable=False)
    # Las contrasenas se almacenan hasheadas (cifradas), nunca en texto plano.
    # El hash es una operacion de un solo sentido: no se puede "revertir" para obtener
    # la contrasena original, solo se puede comparar hash con hash.
    password = db.Column(db.String(200), nullable=False)
    # Sistema de roles jerarquico:
    #   'root'    -> superusuario, acceso total, puede eliminar registros historicos.
    #   'admin'   -> gestor, puede manejar caja, productos y ver reportes.
    #   'empleado'-> operativo, solo puede tomar pedidos y registrar ventas.
    rol      = db.Column(db.String(20),  default='empleado')

    # ==========================================
    # Metodos de verificacion de permisos por rol
    #
    # El patron recomendado es encapsular la logica de roles en el modelo.
    # De esta forma, si la logica cambia, solo se modifica aqui y no en cada ruta.
    # ==========================================

    def es_root(self):
        # Valido si es root
        if self.rol == 'root':
            return True
        else:
            return False

    def es_admin_o_superior(self):
        """Retorna True si el usuario es admin o root (puede gestionar caja y productos)."""
        return self.rol in ['root', 'admin']

    def puede_reabrir_caja(self):
        """Retorna True si el usuario puede reabrir o reiniciar una caja ya cerrada."""
        return self.rol in ['root', 'admin']

    def puede_gestionar_productos(self):
        """Retorna True si el usuario puede crear, editar y eliminar productos del menu."""
        return self.rol in ['root', 'admin']

    def puede_modificar_precios(self):
        """Retorna True si el usuario puede modificar los precios de los productos."""
        return self.rol in ['root', 'admin']

    def puede_gestionar_usuarios(self):
        """Retorna True si el usuario puede ver y gestionar otros usuarios del sistema."""
        return self.rol in ['root', 'admin']

    def puede_crear_usuarios(self):
        """Retorna True si el usuario puede crear nuevas cuentas."""
        return self.rol in ['root', 'admin']

    def puede_eliminar_registros(self):
        """Retorna True si el usuario puede borrar registros historicos de caja y ventas."""
        return self.rol == 'root'

    def roles_creables(self):
        # Si soy root creo lo que sea, si soy admin solo mozos.
        if self.es_root() == True:
            return ['admin', 'empleado']
        if self.rol == 'admin':
            return ['empleado']
        return []
