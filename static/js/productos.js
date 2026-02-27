// Guardamos todos los productos para filtrar sin llamar al backend cada vez
let todosLosProductos = [];
let idAEliminar = null;

document.addEventListener("DOMContentLoaded", cargarProductos);

// Trae todos los productos del backend
async function cargarProductos() {
  const respuesta = await fetch("/productos/");
  todosLosProductos = await respuesta.json();

  renderizarFiltros();
  renderizarTabla(todosLosProductos);
}

// Crea botones de filtro por categoría
function renderizarFiltros() {
  const categorias = [...new Set(todosLosProductos.map((p) => p.categoria))];
  const contenedor = document.getElementById("filtros");

  const botones = contenedor.querySelectorAll(".dinamico");
  botones.forEach((b) => b.remove());

  categorias.forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = "btn btn-sm btn-outline-dark filtro-btn dinamico";
    btn.textContent = cat;
    btn.onclick = (e) => filtrar(cat, e);
    contenedor.appendChild(btn);
  });
}

// Filtra la tabla por categoría
function filtrar(categoria, event) {
  document
    .querySelectorAll(".filtro-btn")
    .forEach((b) => b.classList.remove("activo", "btn-dark"));
  event.target.classList.add("activo", "btn-dark");

  const filtrados =
    categoria === "todas"
      ? todosLosProductos
      : todosLosProductos.filter((p) => p.categoria === categoria);

  renderizarTabla(filtrados);
}

// Renderiza la tabla de productos
function renderizarTabla(productos) {
  const tbody = document.getElementById("tabla-productos");
  tbody.innerHTML = "";

  if (productos.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center text-muted py-4">
          No hay productos registrados
        </td>
      </tr>`;
    return;
  }

  productos.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="fw-bold">🍦 ${p.nombre}</td>
      <td><span class="badge bg-secondary">${p.categoria}</span></td>
      <td class="text-success fw-bold">$${p.precio.toFixed(2)}</td>
      <td>
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox"
                 ${p.disponible ? "checked" : ""}
                 onchange="toggleDisponible(${p.id}, this.checked)">
          <label class="form-check-label ${p.disponible ? "text-success" : "text-danger"}">
            ${p.disponible ? "Disponible" : "Agotado"}
          </label>
        </div>
      </td>
      <td>
        <button class="btn btn-sm btn-outline-dark me-1" onclick="abrirEditar(${p.id})">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger" onclick="abrirEliminar(${p.id}, '${p.nombre}')">
          <i class="bi bi-trash"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });
}

// ==========================================
// CREAR / EDITAR
// ==========================================

document
  .getElementById("modal-producto")
  .addEventListener("show.bs.modal", (e) => {
    if (!e.relatedTarget) return;
    limpiarModal();
  });

function limpiarModal() {
  document.getElementById("producto-id").value = "";
  document.getElementById("producto-nombre").value = "";
  document.getElementById("producto-categoria").value = "";
  document.getElementById("producto-precio").value = "";
  document.getElementById("producto-disponible").checked = true;
  document.getElementById("modal-titulo").textContent = "Nuevo Producto";
}

function abrirEditar(id) {
  const producto = todosLosProductos.find((p) => p.id === id);
  if (!producto) return;

  document.getElementById("producto-id").value = producto.id;
  document.getElementById("producto-nombre").value = producto.nombre;
  document.getElementById("producto-categoria").value = producto.categoria;
  document.getElementById("producto-precio").value = producto.precio;
  document.getElementById("producto-disponible").checked = producto.disponible;
  document.getElementById("modal-titulo").textContent = "Editar Producto";

  new bootstrap.Modal(document.getElementById("modal-producto")).show();
}

async function guardarProducto() {
  const id = document.getElementById("producto-id").value;
  const datos = {
    nombre: document.getElementById("producto-nombre").value.trim(),
    categoria: document.getElementById("producto-categoria").value.trim(),
    precio: parseFloat(document.getElementById("producto-precio").value),
    disponible: document.getElementById("producto-disponible").checked,
  };

  if (!datos.nombre || !datos.categoria || !datos.precio) {
    mostrarToast("Completa todos los campos obligatorios", "warning");
    return;
  }

  const url = id ? `/productos/${id}` : "/productos/";
  const metodo = id ? "PUT" : "POST";

  await fetch(url, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });

  bootstrap.Modal.getInstance(document.getElementById("modal-producto")).hide();
  mostrarToast(id ? "Producto actualizado ✅" : "Producto creado ✅", "success");
  cargarProductos();
}

async function toggleDisponible(id, disponible) {
  const producto = todosLosProductos.find((p) => p.id === id);
  await fetch(`/productos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...producto, disponible }),
  });
  cargarProductos();
}

// ==========================================
// ELIMINAR
// ==========================================

function abrirEliminar(id, nombre) {
  idAEliminar = id;
  document.getElementById("nombre-eliminar").textContent = nombre;
  new bootstrap.Modal(document.getElementById("modal-eliminar")).show();
}

// ── CAMBIO: ahora valida si el producto tiene pedidos activos
async function confirmarEliminar() {
  const respuesta = await fetch(`/productos/${idAEliminar}`, { method: "DELETE" });
  const datos = await respuesta.json();

  bootstrap.Modal.getInstance(document.getElementById("modal-eliminar")).hide();

  if (respuesta.ok) {
    mostrarToast(datos.mensaje || "Producto eliminado ✅", "success");
    cargarProductos();
  } else {
    // Muestra el error si tiene pedidos activos
    mostrarToast(datos.error || "No se pudo eliminar el producto", "danger");
  }
}
