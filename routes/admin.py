"""
routes/admin.py
---------------
Blueprint para el panel de administracion del sistema.

Esta vista es exclusiva para el usuario con rol 'root'. Permite gestionar
y eliminar registros historicos de caja y ventas directamente desde la interfaz.

El acceso se verifica con current_user.puede_eliminar_registros(), que solo
retorna True cuando el rol del usuario es 'root'. Si alguien sin permiso
intenta acceder a esta URL, recibe un error HTTP 403 (Forbidden).

Endpoints de catalogo:
- GET  /admin/exportar-catalogo  -> Descarga un JSON con todos los productos y sabores.
- POST /admin/importar-catalogo  -> Importa un JSON y hace upsert inteligente (crea/actualiza).
"""

import json
from datetime import datetime

from flask import Blueprint, render_template, abort, jsonify, request, Response
from flask_login import login_required, current_user

from models.models import db, Producto, Sabor

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _requiere_root():
    """Aborta con 403 si el usuario actual no tiene rol root."""
    if not current_user.puede_eliminar_registros():
        abort(403)


# ==========================================
# PANEL PRINCIPAL
# ==========================================

@admin_bp.route('/', methods=['GET'])
@login_required
def panel():
    """
    Muestra el panel de administracion.
    Si el usuario no tiene el permiso suficiente, se aborta la solicitud
    con un error 403 (Acceso Denegado), que Flask convierte en una pagina de error.
    """
    _requiere_root()
    return render_template('admin.html')


# ==========================================
# EXPORTAR CATALOGO
# ==========================================

@admin_bp.route('/exportar-catalogo', methods=['GET'])
@login_required
def exportar_catalogo():
    """
    Genera y retorna un archivo JSON con el catalogo completo de productos y sabores.

    El JSON incluye:
    - metadata: version, fecha de exportacion y totales.
    - sabores: lista completa de sabores (activos e inactivos).
    - productos: lista completa incluyendo archivados, con sus sabor_ids asociados.

    La respuesta usa Content-Disposition: attachment para que el navegador
    lo descargue directamente en lugar de mostrarlo en pantalla.
    """
    _requiere_root()

    # Cargamos todos los sabores sin filtrar por estado.
    sabores = Sabor.query.order_by(Sabor.nombre.asc()).all()
    sabores_data = [
        {'id': s.id, 'nombre': s.nombre, 'activo': s.activo}
        for s in sabores
    ]

    # Cargamos todos los productos, incluyendo archivados (sin filtros de categoria).
    productos = Producto.query.order_by(Producto.nombre.asc()).all()
    productos_data = []
    for p in productos:
        productos_data.append({
            'id':          p.id,
            'nombre':      p.nombre,
            'precio':      p.precio,
            'categoria':   p.categoria,
            'disponible':  p.disponible,
            'imagen_url':  p.imagen_url or '',
            'max_sabores': int(p.max_sabores or 1),
            # Exportamos los IDs de los sabores asociados (activos e inactivos).
            'sabor_ids': [s.id for s in p.sabores]
        })

    payload = {
        'version':          '1.0',
        'fecha_exportacion': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'total_sabores':    len(sabores_data),
        'total_productos':  len(productos_data),
        'sabores':          sabores_data,
        'productos':        productos_data,
    }

    # json.dumps con indent=2 genera un JSON legible por humanos.
    contenido = json.dumps(payload, ensure_ascii=False, indent=2)

    # Nombre del archivo con la fecha actual para identificarlo facilmente.
    nombre_archivo = f"catalogo_helarte_{datetime.now().strftime('%Y-%m-%d')}.json"

    return Response(
        contenido,
        mimetype='application/json',
        headers={
            # attachment hace que el navegador descargue el archivo en vez de mostrarlo.
            'Content-Disposition': f'attachment; filename="{nombre_archivo}"'
        }
    )


# ==========================================
# IMPORTAR CATALOGO
# ==========================================

@admin_bp.route('/importar-catalogo', methods=['POST'])
@login_required
def importar_catalogo():
    """
    Importa un JSON exportado previamente y aplica un upsert inteligente al catalogo.

    Estrategia (nunca elimina datos existentes):
    1. Importa/actualiza sabores: busca el sabor por nombre (insensible a mayusculas).
       - Si existe: lo actualiza (reactiva si estaba inactivo).
       - Si no existe: lo crea nuevo. Guarda mapa old_id -> new_id para los productos.
    2. Importa/actualiza productos: busca por nombre + categoria como clave unica.
       - Si existe: actualiza precio, disponible, max_sabores e imagen_url.
       - Si no existe: crea uno nuevo.
       - En ambos casos reasigna los sabores usando el mapa de IDs.

    Retorna un resumen JSON con contadores de: creados, actualizados, errores.
    """
    _requiere_root()

    # El archivo llega como multipart/form-data con la clave 'archivo'.
    archivo = request.files.get('archivo')
    if not archivo:
        return jsonify({'error': 'No se envio ningun archivo'}), 400

    try:
        contenido = archivo.read().decode('utf-8')
        datos = json.loads(contenido)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return jsonify({'error': f'El archivo no es un JSON valido: {str(e)}'}), 400

    # Validacion minima: el JSON debe tener las claves esperadas.
    if 'sabores' not in datos or 'productos' not in datos:
        return jsonify({'error': 'El archivo no tiene el formato correcto (faltan "sabores" o "productos")'}), 400

    sabores_creados    = 0
    sabores_actualizados = 0
    productos_creados  = 0
    productos_actualizados = 0
    errores            = []

    # ----------------------------------------
    # PASO 1: Importar Sabores
    # Mapa: id_original_en_json -> id_real_en_bd
    # Necesario para reasignar las relaciones de productos correctamente.
    # ----------------------------------------
    mapa_sabor_ids = {}

    for s_data in datos.get('sabores', []):
        try:
            nombre = (s_data.get('nombre') or '').strip()
            if not nombre:
                continue

            # Busqueda insensible a mayusculas para evitar duplicados por capitalización.
            existente = Sabor.query.filter(
                db.func.lower(Sabor.nombre) == nombre.lower()
            ).first()

            if existente:
                # Si estava inactivo lo reactivamos para que este disponible.
                if not existente.activo and s_data.get('activo', True):
                    existente.activo = True
                    sabores_actualizados += 1
                mapa_sabor_ids[s_data['id']] = existente.id
            else:
                nuevo_sabor = Sabor(nombre=nombre, activo=s_data.get('activo', True))
                db.session.add(nuevo_sabor)
                db.session.flush()  # flush() nos da el id generado antes del commit.
                mapa_sabor_ids[s_data['id']] = nuevo_sabor.id
                sabores_creados += 1

        except Exception as e:
            errores.append(f"Sabor '{s_data.get('nombre', '?')}': {str(e)}")

    # ----------------------------------------
    # PASO 2: Importar Productos
    # Clave de busqueda: nombre + categoria (insensible a mayusculas).
    # ----------------------------------------
    _CATEGORIA_ARCHIVADA = '__archivado__'

    for p_data in datos.get('productos', []):
        try:
            nombre    = (p_data.get('nombre') or '').strip()
            categoria = (p_data.get('categoria') or '').strip()

            if not nombre or not categoria:
                errores.append(f"Producto sin nombre o categoria, omitido.")
                continue

            # Buscamos por nombre+categoria como clave compuesta unica del negocio.
            existente = Producto.query.filter(
                db.func.lower(Producto.nombre)    == nombre.lower(),
                db.func.lower(Producto.categoria) == categoria.lower()
            ).first()

            max_sabores = int(p_data.get('max_sabores') or 1)
            max_sabores = max(1, min(5, max_sabores))  # Clamp entre 1 y 5.

            if existente:
                # Actualizamos los campos modificables sin tocar el historial.
                existente.precio     = p_data.get('precio', existente.precio)
                existente.disponible = p_data.get('disponible', existente.disponible)
                existente.imagen_url = p_data.get('imagen_url', existente.imagen_url) or ''
                existente.max_sabores = max_sabores

                # Reasignamos sabores usando el mapa de IDs traducidos.
                sabor_ids_originales = p_data.get('sabor_ids', [])
                sabor_ids_reales = [
                    mapa_sabor_ids[sid]
                    for sid in sabor_ids_originales
                    if sid in mapa_sabor_ids
                ]
                if sabor_ids_reales:
                    existente.sabores = Sabor.query.filter(
                        Sabor.id.in_(sabor_ids_reales)
                    ).all()
                else:
                    existente.sabores = []

                productos_actualizados += 1
            else:
                nuevo = Producto(
                    nombre      = nombre,
                    precio      = p_data.get('precio', 0.0),
                    categoria   = categoria,
                    disponible  = p_data.get('disponible', True),
                    imagen_url  = p_data.get('imagen_url', '') or '',
                    max_sabores = max_sabores
                )

                sabor_ids_originales = p_data.get('sabor_ids', [])
                sabor_ids_reales = [
                    mapa_sabor_ids[sid]
                    for sid in sabor_ids_originales
                    if sid in mapa_sabor_ids
                ]
                if sabor_ids_reales:
                    nuevo.sabores = Sabor.query.filter(
                        Sabor.id.in_(sabor_ids_reales)
                    ).all()

                db.session.add(nuevo)
                productos_creados += 1

        except Exception as e:
            errores.append(f"Producto '{p_data.get('nombre', '?')}': {str(e)}")

    # Confirmamos todos los cambios en una sola transaccion.
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al guardar en base de datos: {str(e)}'}), 500

    return jsonify({
        'mensaje':               'Importacion completada',
        'sabores_creados':       sabores_creados,
        'sabores_actualizados':  sabores_actualizados,
        'productos_creados':     productos_creados,
        'productos_actualizados': productos_actualizados,
        'errores':               errores
    })
