let todosLosProductos = [];
let idAEliminar = null;

document.addEventListener("DOMContentLoaded", cargarProductos);

async function cargarProductos() {
  try {
    const respuesta = await fetch("/productos/");
    if (!respuesta.ok) {
      throw new Error(`No se pudo cargar productos (HTTP ${respuesta.status})`);
    }

    todosLosProductos = await respuesta.json();

    renderizarFiltros();
    renderizarTabla(todosLosProductos);
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudieron cargar los productos", "danger");
  }
}

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

function filtrar(categoria, event) {
  document.querySelectorAll(".filtro-btn")
    .forEach((b) => b.classList.remove("activo", "btn-dark"));
  event.target.classList.add("activo", "btn-dark");

  const filtrados = categoria === "todas"
    ? todosLosProductos
    : todosLosProductos.filter((p) => p.categoria === categoria);

  renderizarTabla(filtrados);
}

function renderizarTabla(productos) {
  const tbody = document.getElementById("tabla-productos");
  tbody.innerHTML = "";

  if (productos.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center text-muted py-4">
          No hay productos registrados
        </td>
      </tr>`;
    return;
  }

  productos.forEach((p) => {
    const tr = document.createElement("tr");

    // ── NUEVO: imagen o emoji por defecto
    const imgHtml = p.imagen_url
      ? `<img src="${p.imagen_url}" alt="${p.nombre}"
              style="width:50px; height:50px; object-fit:cover; border-radius:8px;">`
      : `<span style="font-size:2rem;">🍦</span>`;

    tr.innerHTML = `
      <td class="text-center align-middle">${imgHtml}</td>
      <td class="fw-bold align-middle">${p.nombre}</td>
      <td class="align-middle"><span class="badge bg-secondary">${p.categoria}</span></td>
      <td class="text-success fw-bold align-middle">$${p.precio.toFixed(2)}</td>
      <td class="align-middle">
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox"
                 ${p.disponible ? "checked" : ""}
                 onchange="toggleDisponible(${p.id}, this.checked)">
          <label class="form-check-label ${p.disponible ? "text-success" : "text-danger"}">
            ${p.disponible ? "Disponible" : "Agotado"}
          </label>
        </div>
      </td>
      <td class="align-middle">
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

// ── NUEVO: preview de imagen antes de subir
function previewImagen(input) {
  const preview = document.getElementById('preview-imagen');
  const img = document.getElementById('img-preview');

  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = (e) => {
      img.src = e.target.result;
      preview.style.display = 'block';
    };
    reader.readAsDataURL(input.files[0]);
  }
}

// ==========================================
// CREAR / EDITAR
// ==========================================

document.getElementById("modal-producto")
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
  document.getElementById("producto-imagen").value = "";
  document.getElementById("producto-imagen-url").value = "";
  document.getElementById("preview-imagen").style.display = "none";
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
  document.getElementById("producto-imagen-url").value = producto.imagen_url || "";
  document.getElementById("modal-titulo").textContent = "Editar Producto";

  // ── Muestra la imagen actual si tiene
  if (producto.imagen_url) {
    document.getElementById("img-preview").src = producto.imagen_url;
    document.getElementById("preview-imagen").style.display = "block";
  } else {
    document.getElementById("preview-imagen").style.display = "none";
  }

  new bootstrap.Modal(document.getElementById("modal-producto")).show();
}

async function guardarProducto() {
  const id = document.getElementById("producto-id").value;
  const nombre = document.getElementById("producto-nombre").value.trim();
  const categoria = document.getElementById("producto-categoria").value.trim();
  const precio = parseFloat(document.getElementById("producto-precio").value);
  const disponible = document.getElementById("producto-disponible").checked;
  const archivoImagen = document.getElementById("producto-imagen").files[0];

  if (!nombre || !categoria || !precio) {
    mostrarToast("Completa todos los campos obligatorios", "warning");
    return;
  }

  // ── NUEVO: sube la imagen a Cloudinary si se seleccionó una
  let imagen_url = document.getElementById("producto-imagen-url").value;
  try {
    if (archivoImagen) {
      mostrarToast("Subiendo imagen...", "secondary");
      const formData = new FormData();
      formData.append("imagen", archivoImagen);

      const uploadResp = await fetch("/productos/upload-imagen", {
        method: "POST",
        body: formData
      });
      const uploadData = await uploadResp.json();

      if (!uploadResp.ok) {
        mostrarToast(uploadData.error || "Error al subir imagen", "danger");
        return;
      }
      imagen_url = uploadData.imagen_url;
    }

    const datos = { nombre, categoria, precio, disponible, imagen_url };
    const url = id ? `/productos/${id}` : "/productos/";
    const metodo = id ? "PUT" : "POST";

    const respuesta = await fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });

    let payload = {};
    try {
      payload = await respuesta.json();
    } catch (_) {
      payload = {};
    }

    if (!respuesta.ok) {
      throw new Error(payload.error || `No se pudo guardar el producto (HTTP ${respuesta.status})`);
    }

    bootstrap.Modal.getInstance(document.getElementById("modal-producto")).hide();
    mostrarToast(id ? "Producto actualizado ✅" : "Producto creado ✅", "success");
    cargarProductos();
  } catch (error) {
    console.error(error);
    mostrarToast(error.message || "No se pudo guardar el producto", "danger");
  }
}

async function toggleDisponible(id, disponible) {
  const producto = todosLosProductos.find((p) => p.id === id);
  try {
    const respuesta = await fetch(`/productos/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...producto, disponible }),
    });

    if (!respuesta.ok) {
      throw new Error(`No se pudo actualizar disponibilidad (HTTP ${respuesta.status})`);
    }
    cargarProductos();
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudo actualizar disponibilidad", "danger");
  }
}

// ==========================================
// ELIMINAR
// ==========================================

function abrirEliminar(id, nombre) {
  idAEliminar = id;
  document.getElementById("nombre-eliminar").textContent = nombre;
  new bootstrap.Modal(document.getElementById("modal-eliminar")).show();
}

async function confirmarEliminar() {
  const respuesta = await fetch(`/productos/${idAEliminar}`, { method: "DELETE" });
  const datos = await respuesta.json();

  bootstrap.Modal.getInstance(document.getElementById("modal-eliminar")).hide();

  if (respuesta.ok) {
    mostrarToast(datos.mensaje || "Producto eliminado ✅", "success");
    cargarProductos();
  } else {
    mostrarToast(datos.error || "No se pudo eliminar el producto", "danger");
  }
}
