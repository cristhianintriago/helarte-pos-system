let todosLosProductos = [];
let todosLosSabores = [];
let idAEliminar = null;
let categoriaActual = "todas";

document.addEventListener("DOMContentLoaded", iniciarPantallaProductos);

async function iniciarPantallaProductos() {
  enlazarEventosUI();
  await Promise.all([cargarSabores(), cargarProductos()]);
}

function enlazarEventosUI() {
  const buscador = document.getElementById("buscador-productos");
  if (buscador) {
    buscador.addEventListener("input", aplicarFiltros);
  }

  document.getElementById("modal-producto")
    .addEventListener("show.bs.modal", (e) => {
      if (!e.relatedTarget) return;
      limpiarModal();
    });
}

async function cargarProductos() {
  try {
    const respuesta = await fetch("/productos/");
    if (!respuesta.ok) {
      throw new Error(`No se pudo cargar productos (HTTP ${respuesta.status})`);
    }

    todosLosProductos = await respuesta.json();
    renderizarFiltros();
    aplicarFiltros();
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudieron cargar los productos", "danger");
  }
}

async function cargarSabores() {
  try {
    const respuesta = await fetch("/productos/sabores");
    if (!respuesta.ok) {
      throw new Error(`No se pudieron cargar sabores (HTTP ${respuesta.status})`);
    }

    todosLosSabores = await respuesta.json();
    renderizarSaboresGestion();
    renderizarSelectorSabores();
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudieron cargar los sabores", "warning");
  }
}

function renderizarFiltros() {
  const categorias = [...new Set(todosLosProductos.map((p) => p.categoria))];
  const contenedor = document.getElementById("filtros");
  if (!contenedor) return;

  const botones = contenedor.querySelectorAll(".dinamico");
  botones.forEach((b) => b.remove());

  categorias.forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = "btn btn-sm btn-outline-dark filtro-btn dinamico";
    btn.textContent = cat;
    btn.onclick = () => {
      categoriaActual = cat;
      document.querySelectorAll(".filtro-btn")
        .forEach((b) => b.classList.remove("activo", "btn-dark"));
      btn.classList.add("activo", "btn-dark");
      aplicarFiltros();
    };
    contenedor.appendChild(btn);
  });
}

function aplicarFiltros() {
  const texto = (document.getElementById("buscador-productos")?.value || "").trim().toLowerCase();

  const filtrados = todosLosProductos.filter((p) => {
    const coincideCategoria = categoriaActual === "todas" || p.categoria === categoriaActual;
    const saboresTxt = (p.sabores || []).map((s) => s.nombre).join(" ").toLowerCase();
    const coincideTexto =
      !texto ||
      p.nombre.toLowerCase().includes(texto) ||
      p.categoria.toLowerCase().includes(texto) ||
      saboresTxt.includes(texto);

    return coincideCategoria && coincideTexto;
  });

  renderizarTabla(filtrados);
  renderizarTarjetasMovil(filtrados);
}

function filtrar(categoria, event) {
  categoriaActual = categoria;
  document.querySelectorAll(".filtro-btn")
    .forEach((b) => b.classList.remove("activo", "btn-dark"));
  event.target.classList.add("activo", "btn-dark");
  aplicarFiltros();
}

function renderizarTabla(productos) {
  const tbody = document.getElementById("tabla-productos");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (productos.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center text-muted py-4">
          No hay productos que coincidan con los filtros
        </td>
      </tr>`;
    return;
  }

  productos.forEach((p) => {
    const tr = document.createElement("tr");

    const imgHtml = p.imagen_url
      ? `<img src="${p.imagen_url}" alt="${p.nombre}" style="width:50px; height:50px; object-fit:cover; border-radius:8px;">`
      : `<span style="font-size:2rem;">🍦</span>`;

    const sabores = (p.sabores || []).map((s) => s.nombre).join(", ") || "Sin sabores";
    const limite = p.max_sabores || 1;

    tr.innerHTML = `
      <td class="text-center align-middle">${imgHtml}</td>
      <td class="fw-bold align-middle">
        ${p.nombre}
        <div class="small text-muted">${sabores}</div>
        <div class="small text-muted">Máx. sabores por pedido: ${limite}</div>
      </td>
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
        <button class="btn btn-sm btn-outline-danger" onclick="abrirEliminar(${p.id}, '${p.nombre.replace(/'/g, "\\'")}')">
          <i class="bi bi-trash"></i>
        </button>
      </td>`;
    tbody.appendChild(tr);
  });
}

function renderizarTarjetasMovil(productos) {
  const contenedor = document.getElementById("lista-productos-mobile");
  if (!contenedor) return;

  contenedor.innerHTML = "";
  if (productos.length === 0) {
    contenedor.innerHTML = '<div class="text-center text-muted py-3">No hay productos que coincidan con los filtros</div>';
    return;
  }

  productos.forEach((p) => {
    const sabores = (p.sabores || []).map((s) => s.nombre).join(", ") || "Sin sabores";
    const limite = p.max_sabores || 1;
    const wrapper = document.createElement("div");
    wrapper.className = "producto-admin-mobile";
    wrapper.innerHTML = `
      <div class="d-flex gap-2 align-items-start">
        <div class="producto-admin-mobile__img">
          ${p.imagen_url
            ? `<img src="${p.imagen_url}" alt="${p.nombre}" class="rounded" style="width:56px;height:56px;object-fit:cover;">`
            : '<span class="fs-4">🍦</span>'}
        </div>
        <div class="flex-grow-1">
          <div class="fw-bold">${p.nombre}</div>
          <div class="small text-muted">${p.categoria}</div>
          <div class="small text-muted">${sabores}</div>
          <div class="small text-muted">Máx. sabores: ${limite}</div>
        </div>
        <div class="text-end">
          <div class="text-success fw-bold">$${p.precio.toFixed(2)}</div>
          <div class="form-check form-switch d-flex justify-content-end mt-1">
            <input class="form-check-input" type="checkbox" ${p.disponible ? "checked" : ""}
              onchange="toggleDisponible(${p.id}, this.checked)">
          </div>
        </div>
      </div>
      <div class="d-flex gap-2 mt-2">
        <button class="btn btn-sm btn-outline-dark flex-fill" onclick="abrirEditar(${p.id})">
          <i class="bi bi-pencil"></i> Editar
        </button>
        <button class="btn btn-sm btn-outline-danger flex-fill" onclick="abrirEliminar(${p.id}, '${p.nombre.replace(/'/g, "\\'")}')">
          <i class="bi bi-trash"></i> Eliminar
        </button>
      </div>
    `;
    contenedor.appendChild(wrapper);
  });
}

function renderizarSaboresGestion() {
  const contenedor = document.getElementById("lista-sabores");
  if (!contenedor) return;

  contenedor.innerHTML = "";
  const saboresActivos = todosLosSabores.filter((s) => s.activo);

  if (saboresActivos.length === 0) {
    contenedor.innerHTML = '<span class="text-muted small">Aun no hay sabores configurados.</span>';
    return;
  }

  saboresActivos.forEach((sabor) => {
    const chip = document.createElement("span");
    chip.className = "badge text-bg-light border d-inline-flex align-items-center gap-2 p-2";
    chip.innerHTML = `
      ${sabor.nombre}
      <button type="button" class="btn btn-sm btn-link text-danger p-0" onclick="desactivarSabor(${sabor.id})" title="Desactivar sabor">
        <i class="bi bi-x-circle"></i>
      </button>`;
    contenedor.appendChild(chip);
  });
}

function renderizarSelectorSabores(saborIdsSeleccionados = []) {
  const contenedor = document.getElementById("selector-sabores");
  if (!contenedor) return;

  const activos = todosLosSabores.filter((s) => s.activo);
  contenedor.innerHTML = "";

  if (!activos.length) {
    contenedor.innerHTML = '<span class="text-muted small">No hay sabores activos.</span>';
    return;
  }

  activos.forEach((sabor) => {
    const idInput = `sabor-${sabor.id}`;
    const checked = saborIdsSeleccionados.includes(sabor.id) ? "checked" : "";
    const html = `
      <div class="form-check form-check-inline me-0">
        <input class="form-check-input" type="checkbox" id="${idInput}" value="${sabor.id}" ${checked}>
        <label class="form-check-label" for="${idInput}">${sabor.nombre}</label>
      </div>`;

    const wrapper = document.createElement("div");
    wrapper.className = "px-2 py-1 border rounded-pill bg-light";
    wrapper.innerHTML = html;
    contenedor.appendChild(wrapper);
  });
}

function seleccionarTodosSabores() {
  document.querySelectorAll("#selector-sabores input[type='checkbox']").forEach((check) => {
    check.checked = true;
  });
}

function limpiarSeleccionSabores() {
  document.querySelectorAll("#selector-sabores input[type='checkbox']").forEach((check) => {
    check.checked = false;
  });
}

async function crearSabor() {
  const input = document.getElementById("nuevo-sabor");
  const nombre = (input?.value || "").trim();

  if (!nombre) {
    mostrarToast("Escribe un nombre de sabor", "warning");
    return;
  }

  try {
    const respuesta = await fetch("/productos/sabores", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre }),
    });
    const datos = await respuesta.json();

    if (!respuesta.ok) {
      throw new Error(datos.error || "No se pudo crear sabor");
    }

    input.value = "";
    mostrarToast("Sabor guardado", "success");
    await cargarSabores();
  } catch (error) {
    console.error(error);
    mostrarToast(error.message || "No se pudo crear sabor", "danger");
  }
}

async function desactivarSabor(saborId) {
  try {
    const respuesta = await fetch(`/productos/sabores/${saborId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activo: false }),
    });
    const datos = await respuesta.json();
    if (!respuesta.ok) {
      throw new Error(datos.error || "No se pudo desactivar sabor");
    }

    mostrarToast("Sabor desactivado", "info");
    await Promise.all([cargarSabores(), cargarProductos()]);
  } catch (error) {
    console.error(error);
    mostrarToast(error.message || "No se pudo desactivar sabor", "danger");
  }
}

function previewImagen(input) {
  const preview = document.getElementById("preview-imagen");
  const img = document.getElementById("img-preview");

  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = (e) => {
      img.src = e.target.result;
      preview.style.display = "block";
    };
    reader.readAsDataURL(input.files[0]);
  }
}

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
  document.getElementById("producto-max-sabores").value = 1;
  renderizarSelectorSabores([]);
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
  document.getElementById("producto-max-sabores").value = producto.max_sabores || 1;
  document.getElementById("modal-titulo").textContent = "Editar Producto";

  if (producto.imagen_url) {
    document.getElementById("img-preview").src = producto.imagen_url;
    document.getElementById("preview-imagen").style.display = "block";
  } else {
    document.getElementById("preview-imagen").style.display = "none";
  }

  const ids = (producto.sabores || []).map((s) => s.id);
  renderizarSelectorSabores(ids);
  new bootstrap.Modal(document.getElementById("modal-producto")).show();
}

function obtenerSaboresSeleccionados() {
  const checks = document.querySelectorAll("#selector-sabores input[type='checkbox']:checked");
  return [...checks].map((c) => Number(c.value));
}

async function guardarProducto() {
  const id = document.getElementById("producto-id").value;
  const nombre = document.getElementById("producto-nombre").value.trim();
  const categoria = document.getElementById("producto-categoria").value.trim();
  const precio = parseFloat(document.getElementById("producto-precio").value);
  const disponible = document.getElementById("producto-disponible").checked;
  const archivoImagen = document.getElementById("producto-imagen").files[0];
  const sabor_ids = obtenerSaboresSeleccionados();
  const max_sabores = parseInt(document.getElementById("producto-max-sabores").value, 10);

  if (!nombre || !categoria || Number.isNaN(precio) || precio <= 0) {
    mostrarToast("Completa los campos obligatorios con valores validos", "warning");
    return;
  }

  if (Number.isNaN(max_sabores) || max_sabores < 1 || max_sabores > 5) {
    mostrarToast("El limite de sabores debe estar entre 1 y 5", "warning");
    return;
  }

  if (sabor_ids.length > 0 && max_sabores > sabor_ids.length) {
    mostrarToast("El limite no puede ser mayor al numero de sabores seleccionados", "warning");
    return;
  }

  try {
    let imagen_url = document.getElementById("producto-imagen-url").value;
    if (archivoImagen) {
      mostrarToast("Subiendo imagen...", "info");
      const formData = new FormData();
      formData.append("imagen", archivoImagen);

      const uploadResp = await fetch("/productos/upload-imagen", {
        method: "POST",
        body: formData
      });
      const uploadData = await uploadResp.json();

      if (!uploadResp.ok) {
        throw new Error(uploadData.error || "Error al subir imagen");
      }
      imagen_url = uploadData.imagen_url;
    }

    const datos = { nombre, categoria, precio, disponible, imagen_url, sabor_ids, max_sabores };
    const url = id ? `/productos/${id}` : "/productos/";
    const metodo = id ? "PUT" : "POST";

    const respuesta = await fetch(url, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });

    const payload = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
      throw new Error(payload.error || `No se pudo guardar (HTTP ${respuesta.status})`);
    }

    bootstrap.Modal.getInstance(document.getElementById("modal-producto")).hide();
    mostrarToast(id ? "Producto actualizado" : "Producto creado", "success");
    await cargarProductos();
  } catch (error) {
    console.error(error);
    mostrarToast(error.message || "No se pudo guardar el producto", "danger");
  }
}

async function toggleDisponible(id, disponible) {
  const producto = todosLosProductos.find((p) => p.id === id);
  if (!producto) return;

  try {
    const respuesta = await fetch(`/productos/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...producto,
        sabor_ids: (producto.sabores || []).map((s) => s.id),
        max_sabores: producto.max_sabores || 1,
        disponible,
      }),
    });

    if (!respuesta.ok) {
      throw new Error(`No se pudo actualizar disponibilidad (HTTP ${respuesta.status})`);
    }

    await cargarProductos();
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudo actualizar disponibilidad", "danger");
  }
}

function abrirEliminar(id, nombre) {
  idAEliminar = id;
  document.getElementById("nombre-eliminar").textContent = nombre;
  new bootstrap.Modal(document.getElementById("modal-eliminar")).show();
}

async function confirmarEliminar() {
  try {
    const respuesta = await fetch(`/productos/${idAEliminar}`, { method: "DELETE" });
    const datos = await respuesta.json();

    bootstrap.Modal.getInstance(document.getElementById("modal-eliminar")).hide();

    if (respuesta.ok) {
      mostrarToast(datos.mensaje || "Producto eliminado", "success");
      await cargarProductos();
    } else {
      mostrarToast(datos.error || "No se pudo eliminar el producto", "danger");
    }
  } catch (error) {
    console.error(error);
    mostrarToast("Error de conexion al eliminar producto", "danger");
  }
}
