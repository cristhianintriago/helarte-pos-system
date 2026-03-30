/**
 * productos.js
 * ------------
 * Logica del modulo de gestion del catalogo de productos y sabores.
 *
 * Este modulo es uno de los mas complejos del frontend porque maneja:
 * - CRUD completo de productos y sabores.
 * - Filtrado y busqueda en tiempo real sobre una lista local.
 * - Vista doble: tabla para escritorio y tarjetas para movil.
 * - Carga de imagenes a Cloudinary usando FormData (multipart/form-data).
 *
 * Estado del modulo (variables globales a este archivo):
 * - todosLosProductos: lista completa de productos del servidor (cache local).
 * - todosLosSabores: lista completa de sabores del servidor (cache local).
 * - idAEliminar: almacena temporalmente el ID del producto a eliminar en el modal.
 * - categoriaActual: filtro de categoria activo en la tabla.
 *
 * Por que cache local:
 * Guardar los datos en memoria permite aplicar filtros y busquedas de forma instantanea,
 * sin tener que hacer una nueva solicitud al servidor cada vez que el usuario escribe.
 */

// Estado local del modulo.
let todosLosProductos = [];
let todosLosSabores   = [];
let idAEliminar       = null;
let categoriaActual   = "todas";

document.addEventListener("DOMContentLoaded", iniciarPantallaProductos);

/**
 * Funcion de inicializacion principal del modulo.
 * Conecta los eventos de la UI y carga los datos del servidor en paralelo.
 * Promise.all espera a que AMBAS cargas terminen antes de continuar.
 */
async function iniciarPantallaProductos() {
    enlazarEventosUI();
    // Promise.all([p1, p2]) ejecuta p1 y p2 al mismo tiempo y espera a que ambas terminen.
    // Esto es mas eficiente que esperar p1 y luego esperar p2 secuencialmente.
    await Promise.all([cargarSabores(), cargarProductos()]);
}

/**
 * Registra los manejadores de eventos de la interfaz.
 * El evento 'input' del buscador se dispara cada vez que el usuario escribe o borra,
 * lo que permite el filtrado en tiempo real sin necesidad de presionar "buscar".
 */
function enlazarEventosUI() {
    const buscador = document.getElementById("buscador-productos");
    if (buscador) {
        buscador.addEventListener("input", aplicarFiltros);
    }

    // Cuando el modal de producto va a mostrarse, limpiamos el formulario.
    // e.relatedTarget es el boton que disparo la apertura del modal.
    // Si es null, el modal se abrio desde codigo (para edicion) y NO limpiamos.
    document.getElementById("modal-producto")
        .addEventListener("show.bs.modal", (e) => {
            if (!e.relatedTarget) return;
            limpiarModal();
        });
}


// ==========================================
// CARGA DE DATOS DESDE EL SERVIDOR
// ==========================================

/**
 * Solicita la lista de productos al servidor y la almacena en el estado local.
 * Luego construye los filtros de categoria y renderiza la tabla.
 */
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

/**
 * Solicita la lista de sabores al servidor y actualiza:
 * - La seccion de chips de gestion de sabores.
 * - El selector de sabores dentro del formulario de producto.
 */
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


// ==========================================
// FILTROS Y BUSQUEDA
// ==========================================

/**
 * Genera dinamicamente los botones de filtro de categoria a partir del catalogo actual.
 * Usa Set para obtener categorias unicas (sin repetidos), luego el spread [...] lo convierte a Array.
 */
function renderizarFiltros() {
    // Set es una estructura de datos que solo almacena valores unicos.
    // Al hacer 'new Set([...])' de un array con duplicados, los duplicados se eliminan.
    const categorias = [...new Set(todosLosProductos.map((p) => p.categoria))];
    const contenedor = document.getElementById("filtros");
    if (!contenedor) return;

    // Eliminamos los botones dinamicos anteriores para no duplicarlos.
    const botones = contenedor.querySelectorAll(".dinamico");
    botones.forEach((b) => b.remove());

    categorias.forEach((cat) => {
        const btn   = document.createElement("button");
        btn.className = "btn btn-sm btn-outline-dark filtro-btn dinamico";
        btn.textContent = cat;
        btn.onclick = () => {
            categoriaActual = cat;
            // Quitamos el estilo activo de todos los botones y lo aplicamos solo al seleccionado.
            document.querySelectorAll(".filtro-btn").forEach((b) => b.classList.remove("activo", "btn-dark"));
            btn.classList.add("activo", "btn-dark");
            aplicarFiltros();
        };
        contenedor.appendChild(btn);
    });
}

/**
 * Filtra la lista de productos en memoria segun la categoria activa y el texto del buscador.
 * Este proceso ocurre completamente en el navegador (sin llamadas al servidor).
 * El resultado se renderiza en la tabla y en las tarjetas moviles.
 */
function aplicarFiltros() {
    const texto = (document.getElementById("buscador-productos")?.value || "").trim().toLowerCase();

    const filtrados = todosLosProductos.filter((p) => {
        // Condicion 1: el producto pertenece a la categoria seleccionada (o se muestran todas).
        const coincideCategoria = categoriaActual === "todas" || p.categoria === categoriaActual;

        // Concatenamos los nombres de sabores para poder buscar dentro de ellos.
        const saboresTxt = (p.sabores || []).map((s) => s.nombre).join(" ").toLowerCase();

        // Condicion 2: el texto de busqueda aparece en el nombre, categoria o sabores.
        const coincideTexto =
            !texto ||
            p.nombre.toLowerCase().includes(texto)    ||
            p.categoria.toLowerCase().includes(texto) ||
            saboresTxt.includes(texto);

        return coincideCategoria && coincideTexto;
    });

    renderizarTabla(filtrados);
    renderizarTarjetasMovil(filtrados);
}

/**
 * Cambia el filtro de categoria activo y aplica los filtros.
 * Se llama desde los botones de categoria estaticos del HTML (los que no son dinamicos).
 * @param {string} categoria - Nombre de la categoria o "todas".
 * @param {Event} event      - Evento del clic (para marcar el boton como activo).
 */
function filtrar(categoria, event) {
    categoriaActual = categoria;
    document.querySelectorAll(".filtro-btn").forEach((b) => b.classList.remove("activo", "btn-dark"));
    event.target.classList.add("activo", "btn-dark");
    aplicarFiltros();
}


// ==========================================
// RENDERIZADO DE LA INTERFAZ
// ==========================================

/**
 * Construye y renderiza la tabla de productos para pantallas de escritorio.
 * El interruptor (switch) de disponibilidad llama a toggleDisponible() directamente
 * con un manejador 'onchange' incrustado en el HTML generado.
 *
 * @param {Array} productos - Lista de productos a mostrar (ya filtrada).
 */
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

        // Si el producto tiene imagen, mostramos un miniatura; si no, un icono de texto.
        const imgHtml = p.imagen_url
            ? `<img src="${p.imagen_url}" alt="${p.nombre}" style="width:50px; height:50px; object-fit:cover; border-radius:8px;">`
            : `<span style="font-size:2rem;">&#127846;</span>`;

        const sabores = (p.sabores || []).map((s) => s.nombre).join(", ") || "Sin sabores";
        const limite  = p.max_sabores || 1;

        tr.innerHTML = `
            <td class="text-center align-middle">${imgHtml}</td>
            <td class="fw-bold align-middle">
                ${p.nombre}
                <div class="small text-muted">${sabores}</div>
                <div class="small text-muted">Max. sabores por pedido: ${limite}</div>
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

/**
 * Construye y renderiza las tarjetas de producto para pantallas moviles.
 * Se muestra una lista de tarjetas en lugar de tabla para mejor usabilidad en pantallas pequenas.
 *
 * @param {Array} productos - Lista de productos a mostrar (ya filtrada).
 */
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
        const limite  = p.max_sabores || 1;
        const wrapper = document.createElement("div");
        wrapper.className = "producto-admin-mobile";
        wrapper.innerHTML = `
            <div class="d-flex gap-2 align-items-start">
                <div class="producto-admin-mobile__img">
                    ${p.imagen_url
                        ? `<img src="${p.imagen_url}" alt="${p.nombre}" class="rounded" style="width:56px;height:56px;object-fit:cover;">`
                        : '<span class="fs-4">&#127846;</span>'}
                </div>
                <div class="flex-grow-1">
                    <div class="fw-bold">${p.nombre}</div>
                    <div class="small text-muted">${p.categoria}</div>
                    <div class="small text-muted">${sabores}</div>
                    <div class="small text-muted">Max. sabores: ${limite}</div>
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


// ==========================================
// GESTION DE SABORES
// ==========================================

/**
 * Renderiza los chips (pastillas visuales) de sabores activos en el panel de gestion.
 * Cada chip tiene un boton 'x' que llama a desactivarSabor() para ocultarlo del catalogo.
 */
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
        const chip   = document.createElement("span");
        chip.className = "badge text-bg-light border d-inline-flex align-items-center gap-2 p-2";
        chip.innerHTML = `
            ${sabor.nombre}
            <button type="button" class="btn btn-sm btn-link text-danger p-0" onclick="desactivarSabor(${sabor.id})" title="Desactivar sabor">
                <i class="bi bi-x-circle"></i>
            </button>`;
        contenedor.appendChild(chip);
    });
}

/**
 * Renderiza los checkboxes de seleccion de sabores en el formulario de producto.
 * Los sabores ya asignados al producto se muestran pre-marcados.
 *
 * @param {Array} saborIdsSeleccionados - Lista de IDs de sabores que ya tiene el producto.
 */
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
        // Array.includes() busca si el valor existe en el array. Retorna true o false.
        const checked = saborIdsSeleccionados.includes(sabor.id) ? "checked" : "";
        const html = `
            <div class="form-check form-check-inline me-0">
                <input class="form-check-input" type="checkbox" id="${idInput}" value="${sabor.id}" ${checked}>
                <label class="form-check-label" for="${idInput}">${sabor.nombre}</label>
            </div>`;

        const wrapper   = document.createElement("div");
        wrapper.className = "px-2 py-1 border rounded-pill bg-light";
        wrapper.innerHTML = html;
        contenedor.appendChild(wrapper);
    });
}

/** Marca todos los checkboxes de sabores del selector del formulario. */
function seleccionarTodosSabores() {
    document.querySelectorAll("#selector-sabores input[type='checkbox']").forEach((check) => {
        check.checked = true;
    });
}

/** Desmarca todos los checkboxes de sabores del selector del formulario. */
function limpiarSeleccionSabores() {
    document.querySelectorAll("#selector-sabores input[type='checkbox']").forEach((check) => {
        check.checked = false;
    });
}

/**
 * Crea un nuevo sabor enviandolo al servidor.
 * Si el sabor ya existe pero estaba desactivado, el servidor lo reactiva.
 */
async function crearSabor() {
    const input  = document.getElementById("nuevo-sabor");
    const nombre = (input?.value || "").trim();

    if (!nombre) {
        mostrarToast("Escribe un nombre de sabor", "warning");
        return;
    }

    try {
        const respuesta = await fetch("/productos/sabores", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ nombre }),
        });
        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(datos.error || "No se pudo crear sabor");
        }

        input.value = "";
        mostrarToast("Sabor guardado", "success");
        // Recargamos los sabores para que el nuevo aparezca en la lista y en el selector.
        await cargarSabores();
    } catch (error) {
        console.error(error);
        mostrarToast(error.message || "No se pudo crear sabor", "danger");
    }
}

/**
 * Desactiva un sabor (borrado logico): sigue en la BD pero no aparece en el catalogo.
 * Luego recarga productos y sabores para que la interfaz refleje el cambio.
 *
 * @param {number} saborId - ID del sabor a desactivar.
 */
async function desactivarSabor(saborId) {
    try {
        const respuesta = await fetch(`/productos/sabores/${saborId}`, {
            method:  "PUT",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ activo: false }),
        });
        const datos = await respuesta.json();
        if (!respuesta.ok) {
            throw new Error(datos.error || "No se pudo desactivar sabor");
        }

        mostrarToast("Sabor desactivado", "info");
        // Recargamos ambas listas porque desactivar un sabor puede cambiar los productos que lo usan.
        await Promise.all([cargarSabores(), cargarProductos()]);
    } catch (error) {
        console.error(error);
        mostrarToast(error.message || "No se pudo desactivar sabor", "danger");
    }
}


// ==========================================
// FORMULARIO DE PRODUCTO (MODAL)
// ==========================================

/**
 * Muestra una vista previa de la imagen seleccionada antes de subirla.
 * FileReader es una API del navegador que lee archivos locales del usuario.
 * readAsDataURL() convierte el archivo a una URL de datos (base64) para mostrarla en un <img>.
 *
 * @param {HTMLInputElement} input - El elemento <input type="file"> que contiene el archivo.
 */
function previewImagen(input) {
    const preview = document.getElementById("preview-imagen");
    const img     = document.getElementById("img-preview");

    if (input.files && input.files[0]) {
        const reader = new FileReader();
        // onload se ejecuta cuando el archivo termina de leerse.
        reader.onload = (e) => {
            img.src = e.target.result;     // e.target.result es la URL base64 del archivo.
            preview.style.display = "block";
        };
        reader.readAsDataURL(input.files[0]);
    }
}

/**
 * Reinicia todos los campos del formulario de producto para una nueva creacion.
 * Solo se llama si el modal se abre con el boton "Nuevo Producto" (no desde codigo).
 */
function limpiarModal() {
    document.getElementById("producto-id").value        = "";
    document.getElementById("producto-nombre").value    = "";
    document.getElementById("producto-categoria").value = "";
    document.getElementById("producto-precio").value    = "";
    document.getElementById("producto-disponible").checked   = true;
    document.getElementById("producto-imagen").value    = "";
    document.getElementById("producto-imagen-url").value     = "";
    document.getElementById("preview-imagen").style.display  = "none";
    document.getElementById("modal-titulo").textContent      = "Nuevo Producto";
    document.getElementById("producto-max-sabores").value    = 1;
    renderizarSelectorSabores([]);  // Mostramos todos los sabores sin marcar.
}

/**
 * Pre-llena el formulario del modal con los datos del producto a editar y lo abre.
 * Busca el producto en el estado local por su ID para evitar una solicitud extra al servidor.
 *
 * @param {number} id - ID del producto a editar.
 */
function abrirEditar(id) {
    const producto = todosLosProductos.find((p) => p.id === id);
    if (!producto) return;

    document.getElementById("producto-id").value              = producto.id;
    document.getElementById("producto-nombre").value          = producto.nombre;
    document.getElementById("producto-categoria").value       = producto.categoria;
    document.getElementById("producto-precio").value          = producto.precio;
    document.getElementById("producto-disponible").checked    = producto.disponible;
    document.getElementById("producto-imagen-url").value      = producto.imagen_url || "";
    document.getElementById("producto-max-sabores").value     = producto.max_sabores || 1;
    document.getElementById("modal-titulo").textContent       = "Editar Producto";

    // Pre-visualizamos la imagen actual del producto.
    if (producto.imagen_url) {
        document.getElementById("img-preview").src            = producto.imagen_url;
        document.getElementById("preview-imagen").style.display = "block";
    } else {
        document.getElementById("preview-imagen").style.display = "none";
    }

    // Pasamos los IDs de los sabores asignados para que aparezcan marcados en el selector.
    const ids = (producto.sabores || []).map((s) => s.id);
    renderizarSelectorSabores(ids);

    new bootstrap.Modal(document.getElementById("modal-producto")).show();
}

/**
 * Obtiene los IDs de los sabores marcados en el selector del formulario.
 * Number() convierte el valor del checkbox (string) a numero entero.
 * @returns {Array<number>} - Lista de IDs seleccionados.
 */
function obtenerSaboresSeleccionados() {
    const checks = document.querySelectorAll("#selector-sabores input[type='checkbox']:checked");
    return [...checks].map((c) => Number(c.value));
}

/**
 * Guarda un producto nuevo o actualiza uno existente.
 *
 * Flujo:
 * 1. Valida los campos del formulario.
 * 2. Si habia un archivo de imagen, lo sube a Cloudinary y obtiene la URL.
 * 3. Envia el JSON con los datos del producto al servidor (POST o PUT segun el caso).
 * 4. Cierra el modal y recarga la lista.
 *
 * FormData: objeto especial para enviar datos de formulario con archivos (multipart/form-data).
 * No se puede usar JSON para subir archivos, por eso se usa FormData para el upload de imagen.
 */
async function guardarProducto() {
    const id          = document.getElementById("producto-id").value;
    const nombre      = document.getElementById("producto-nombre").value.trim();
    const categoria   = document.getElementById("producto-categoria").value.trim();
    const precio      = parseFloat(document.getElementById("producto-precio").value);
    const disponible  = document.getElementById("producto-disponible").checked;
    const archivoImagen = document.getElementById("producto-imagen").files[0];
    const sabor_ids   = obtenerSaboresSeleccionados();
    // parseInt(..., 10) convierte el string a entero en base decimal.
    const max_sabores = parseInt(document.getElementById("producto-max-sabores").value, 10);

    // Validaciones basicas del lado del cliente.
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

        // Si el usuario selecciono un nuevo archivo de imagen, lo subimos a Cloudinary primero.
        if (archivoImagen) {
            mostrarToast("Subiendo imagen...", "info");
            // FormData encapsula el archivo para enviarlo como multipart/form-data.
            const formData = new FormData();
            formData.append("imagen", archivoImagen);

            const uploadResp = await fetch("/productos/upload-imagen", {
                method: "POST",
                body:   formData   // No se incluye Content-Type: el navegador lo establece automaticamente con el boundary.
            });
            const uploadData = await uploadResp.json();

            if (!uploadResp.ok) {
                throw new Error(uploadData.error || "Error al subir imagen");
            }
            imagen_url = uploadData.imagen_url;
        }

        // Enviamos el JSON con todos los datos del producto al servidor.
        const datos  = { nombre, categoria, precio, disponible, imagen_url, sabor_ids, max_sabores };
        const url    = id ? `/productos/${id}` : "/productos/";
        const metodo = id ? "PUT" : "POST";

        const respuesta = await fetch(url, {
            method:  metodo,
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(datos),
        });

        // .catch(() => ({})) evita un error si la respuesta no es JSON valido.
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

/**
 * Cambia rapidamente el estado de disponibilidad de un producto sin abrir el editor.
 * Usa el operador spread (...producto) para copiar todos los campos del producto
 * y sobreescribir solo el campo 'disponible' con el nuevo valor.
 *
 * @param {number}  id         - ID del producto.
 * @param {boolean} disponible - Nuevo estado de disponibilidad del producto.
 */
async function toggleDisponible(id, disponible) {
    const producto = todosLosProductos.find((p) => p.id === id);
    if (!producto) return;

    try {
        const respuesta = await fetch(`/productos/${id}`, {
            method:  "PUT",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({
                // El spread operator copia todos los campos del producto.
                // El campo 'disponible' se sobreescribe con el nuevo valor.
                ...producto,
                sabor_ids:   (producto.sabores || []).map((s) => s.id),
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


// ==========================================
// ELIMINACION DE PRODUCTO
// ==========================================

/**
 * Muestra el modal de confirmacion de eliminacion.
 * El ID se guarda en la variable global idAEliminar para
 * que confirmarEliminar() sepa que producto borrar cuando el usuario confirme.
 *
 * @param {number} id     - ID del producto a eliminar.
 * @param {string} nombre - Nombre del producto (para mostrarlo en el mensaje de confirmacion).
 */
function abrirEliminar(id, nombre) {
    idAEliminar = id;
    document.getElementById("nombre-eliminar").textContent = nombre;
    new bootstrap.Modal(document.getElementById("modal-eliminar")).show();
}

/**
 * Ejecuta la eliminacion del producto despues de que el usuario confirmo en el modal.
 * Maneja el cierre del modal en un try/catch separado para evitar que un error
 * en el cierre oculte el error real de la operacion.
 */
async function confirmarEliminar() {
    const modalEl    = document.getElementById("modal-eliminar");
    // Funcion auxiliar para cerrar el modal de forma segura.
    const cerrarModal = () => {
        if (!modalEl) return;
        // getOrCreateInstance garantiza que siempre haya una instancia del modal para cerrar.
        const instancia = bootstrap.Modal.getInstance(modalEl) || bootstrap.Modal.getOrCreateInstance(modalEl);
        instancia.hide();
    };

    try {
        const respuesta = await fetch(`/productos/${idAEliminar}`, { method: "DELETE" });
        let datos = {};

        // Intentamos parsear el JSON de la respuesta. Si el servidor no devuelve JSON, usamos {}.
        try {
            datos = await respuesta.json();
        } catch {
            datos = {};
        }

        cerrarModal();

        if (respuesta.ok) {
            mostrarToast(datos.mensaje || "Producto eliminado", "success");
            await cargarProductos();
        } else {
            mostrarToast(datos.error || "No se pudo eliminar el producto", "danger");
        }
    } catch (error) {
        console.error(error);
        cerrarModal();
        mostrarToast("Error de conexion al eliminar producto", "danger");
    }
}
