from functools import wraps

from flask import jsonify
from flask_login import current_user, login_required


def role_required(checker):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            if not checker(current_user):
                return jsonify({"error": "No tienes permisos para esta acción"}), 403
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required(lambda user: user.es_admin_o_superior())
root_required = role_required(lambda user: user.es_root())
