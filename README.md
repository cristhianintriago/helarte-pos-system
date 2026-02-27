# 🍦 Helarte System

Sistema web de gestión para heladería. Desarrollado con Python + Flask como proyecto universitario.

## ✨ Funcionalidades

- 📋 **Toma de pedidos** locales y delivery
- 💰 **Registro de ventas** en tiempo real
- 🗃️ **Control de caja** con apertura, egresos y cuadre
- 🍧 **Gestión de productos** con disponibilidad
- 📊 **Reportes** por rango de fechas

## 🛠️ Tecnologías

| Capa | Tecnología |
|------|-----------|
| Backend | Python + Flask |
| Base de datos | SQLite + SQLAlchemy |
| Frontend | HTML + CSS + JavaScript |
| Estilos | Bootstrap 5 |

## 🚀 Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/tuusuario/helarte-system.git
cd helarte-system

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Cargar productos de ejemplo
python seed.py

# 5. Ejecutar
python app.py

Abre http://127.0.0.1:5000 en tu navegador.

##📁 Estructura

helarte-system/
├── 📁 models/          # Modelos de base de datos (SQLAlchemy)
├── 📁 routes/          # Blueprints del backend
├── 📁 static/          # CSS y JavaScript
├── 📁 templates/       # Páginas HTML (Jinja2)
├── app.py              # Punto de entrada
├── seed.py             # Datos de ejemplo
└── requirements.txt    # Dependencias

##👨‍💻 Autor
Desarrollado por [Cristhian Intriago] — Estudiante de Ingeniería en Software

## Estado final del proyecto ✅

| Módulo | Estado |
|--------|--------|
| 🗄️ Base de datos | ✅ |
| ⚙️ Backend Flask | ✅ |
| 📋 Pedidos | ✅ |
| 💰 Ventas | ✅ |
| 🗃️ Caja | ✅ |
| 🍧 Productos | ✅ |
| 📊 Reportes | ✅ |
| 🏠 Inicio | ✅ |
| 📱 Responsive | ✅ |
| 📖 README | ✅ |