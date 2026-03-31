# Helarte POS System

Sistema web de punto de venta (POS) para heladería, desarrollado con Python + Flask. Proyecto universitario de Ingeniería en Software — 2026.

---

## Funcionalidades

| Módulo | Descripción |
|--------|-------------|
| **Toma de pedidos** | Gestión de pedidos locales y delivery con selector de sabores, modo rápido (doble tap) y cola offline |
| **Cocina** | Pantalla en tiempo real vía WebSockets; síntesis de voz para notificaciones de nuevas órdenes |
| **Ventas** | Historial de ventas del día con filtros y refresco automático |
| **Caja** | Apertura, registro de egresos, cierre ciego (Blind Close) con auditoría de descuadre e historial de 30 días |
| **Productos** | Catálogo con imágenes, categorías, sabores configurables y disponibilidad |
| **Reportes** | Gráficos interactivos con Chart.js, exportación a PDF y Excel por rango de fechas |
| **Usuarios** | Gestión de roles (root, admin, cajero) con permisos diferenciados |
| **Sesión persistente** | Checkbox "Mantener sesión iniciada" (cookie de 30 días via Flask-Login remember_token) |

---

## Stack tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.11 + Flask |
| Base de datos | PostgreSQL (Railway) / SQLite (local) + SQLAlchemy ORM |
| Tiempo real | Flask-SocketIO + Eventlet (WebSockets) |
| Autenticación | Flask-Login + Flask-Bcrypt (bcrypt) |
| Frontend | HTML5 + Bootstrap 5 + JavaScript vanilla |
| Gráficos | Chart.js |
| Concurrencia | Gunicorn + Eventlet worker + NullPool |
| Deploy | Railway |

---

## Arquitectura

```
helarte-pos-system/
├── app.py                  # Punto de entrada: configuración, Flask, blueprints
├── extensions.py           # SocketIO desacoplado (evita importaciones circulares)
├── Procfile                # Gunicorn + Eventlet para producción en Railway
├── requirements.txt        # Dependencias Python
├── models/
│   ├── models.py           # Modelos SQLAlchemy (Pedido, Venta, Caja, Producto, etc.)
│   └── usuario.py          # Modelo de usuario con roles y permisos
├── routes/
│   ├── auth.py             # Login / logout con migración SHA-256 → bcrypt
│   ├── pedidos.py          # CRUD de pedidos + generación de tickets PDF (ReportLab) + CPCL
│   ├── caja.py             # Control de turno de caja y Blind Close
│   ├── ventas.py           # Historial de ventas
│   ├── productos.py        # Catálogo de productos y sabores + subida de imágenes
│   ├── reportes.py         # Reportes por fecha + exportación PDF/Excel
│   ├── usuarios.py         # Gestión de usuarios y roles
│   ├── cocina.py           # Vista de cocina
│   ├── reporte_diario.py   # Resumen diario automático
│   └── admin.py            # Panel de administración (solo root)
├── static/
│   ├── css/theme.css       # Tema visual Helarte (paleta rosa + menta)
│   └── js/
│       ├── app.js          # Utilidades globales (Toast, mostrarToast)
│       ├── pedidos.js      # Lógica del punto de venta
│       ├── cocina.js       # WebSocket + SpeechSynthesis
│       ├── caja.js         # Control de caja + Blind Close
│       ├── productos.js    # Catálogo + FileReader + FormData
│       ├── reportes.js     # Chart.js + exportación
│       ├── ventas.js       # Historial de ventas
│       ├── usuarios.js     # CRUD de usuarios
│       ├── admin.js        # Panel admin
│       ├── index.js        # Dashboard
│       └── zebra.js        # (Inactivo) Integración impresora térmica Zebra iMZ320
└── templates/              # Plantillas HTML (Jinja2) por módulo
```

---

## Instalación local

```bash
# 1. Clonar el repositorio
git clone https://github.com/cristhianintriago/helarte-pos-system.git
cd helarte-pos-system

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar (SQLite local, sin configuración adicional)
python app.py
```

Abrir `http://127.0.0.1:5000` en el navegador.

**Credenciales iniciales:** `root` / `root123` (se recomienda cambiar la contraseña en producción)

---

## Variables de entorno

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `DATABASE_URL` | URL de conexión a PostgreSQL | `sqlite:///helarte.db` (local) |
| `SECRET_KEY` | Clave para firmar cookies de sesión | `helarte_secret_key` (solo desarrollo) |

Crear un archivo `.env` en la raíz del proyecto para desarrollo local:

```env
SECRET_KEY=tu_clave_secreta_larga_y_aleatoria
DATABASE_URL=postgresql://usuario:password@host/db
```

---

## Despliegue en Railway

El proyecto está listo para Railway. El `Procfile` configura Gunicorn con worker Eventlet para soporte de WebSockets:

```
web: gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:$PORT
```

**Notas importantes de producción:**
- Se usa `NullPool` de SQLAlchemy para evitar conflictos de locking entre Eventlet y PostgreSQL.
- `eventlet.monkey_patch()` es la primera instrucción de `app.py` (requisito crítico).
- La migración de esquema es automática al arrancar (`_sincronizar_esquema_legacy()`), sin necesidad de Flask-Migrate.

---

## Utilidades de mantenimiento

| Script | Uso |
|--------|-----|
| `seed.py` | Carga datos de ejemplo (productos, sabores) |
| `restaurar.py` | Restaura el catálogo de productos desde `productos_backup.json` en la BD de producción |
| `migrate.py` | Migraciones manuales de esquema (complementa el sistema automático) |
| `fix_db.py` | Correcciones puntuales de integridad de datos |
| `debug.py` | Herramientas de depuración local |

---

## Estado del proyecto

| Módulo | Estado |
|--------|--------|
| Base de datos (PostgreSQL + SQLite) | Operativo |
| Backend Flask + Blueprints | Operativo |
| WebSockets (cocina en tiempo real) | Operativo |
| Pedidos (local, delivery, offline queue) | Operativo |
| Ventas e historial | Operativo |
| Caja + Blind Close | Operativo |
| Productos + imágenes + sabores | Operativo |
| Reportes + Chart.js + exportación | Operativo |
| Usuarios + roles + permisos | Operativo |
| Sesión persistente (remember me) | Operativo |
| Despliegue Railway | Operativo |
| Responsive (móvil y escritorio) | Operativo |
| Impresora térmica Zebra iMZ320 | Preparado (inactivo — requiere Zebra Browser Print) |

---

## Autor

Desarrollado por **Cristhian Intriago** — Estudiante de Ingeniería en Software  
Proyecto desarrollado con apoyo de **Klyro** © 2026