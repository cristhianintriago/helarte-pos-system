// Estado en memoria de la pantalla de pedidos; se sincroniza al confirmar/cargar.
let pedidoActual = {
    tipo: 'local',
    productos: []
};

let productosCatalogo = [];
let categoriaActual = 'todas';
let itemPendienteSabor = null;
let formaPagoActual = 'efectivo';
let siguienteNumeroPedido = 1;
const tapTimers = new Map();
const TAP_DELAY_MS = 260;

// Bootstrap inicial: catalogo, pedidos activos y numerador visual.
document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('buscador-carta')?.addEventListener('input', aplicarFiltrosCatalogo);

    await Promise.all([
        cargarProductos(),
        cargarPedidosActivos(),
        cargarSiguienteNumeroPedido()
    ]);

    setInterval(cargarPedidosActivos, 5000);
    setFormaPago('efectivo');
    setTipo('local');
});

async function cargarSiguienteNumeroPedido() {
    try {
        const respuesta = await fetch('/pedidos/contador');
        if (!respuesta.ok) return;

        const data = await respuesta.json();
        siguienteNumeroPedido = Number(data.siguiente_numero || 1);
        actualizarEtiquetaNumeroPedido();
    } catch (error) {
        console.error('No se pudo cargar contador de pedidos', error);
    }
}

// Refresca ambas etiquetas (pantalla principal y modal checkout).
function actualizarEtiquetaNumeroPedido() {
    const etiquetas = [
        document.getElementById('numero-pedido-actual'),
        document.getElementById('numero-pedido-checkout')
    ];

    etiquetas.forEach((etiqueta) => {
        if (etiqueta) etiqueta.textContent = String(siguienteNumeroPedido);
    });
}

async function cargarProductos() {
    try {
        const respuesta = await fetch('/productos/');
        if (!respuesta.ok) {
            throw new Error(`No se pudo cargar catalogo (HTTP ${respuesta.status})`);
        }

        productosCatalogo = await respuesta.json();
        renderizarFiltros(productosCatalogo);
        aplicarFiltrosCatalogo();
    } catch (error) {
        console.error(error);
        mostrarToast('No se pudo cargar el catalogo de productos', 'danger');
    }
}

// Renderiza filtros dinamicos por categoria segun catalogo recibido.
function renderizarFiltros(productos) {
    const categorias = [...new Set(productos.map((p) => p.categoria))];
    const contenedor = document.getElementById('filtros');
    if (!contenedor) return;

    contenedor.querySelectorAll('.dinamico').forEach((btn) => btn.remove());

    categorias.forEach((cat) => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm filtro-btn dinamico px-3 text-nowrap';
        btn.textContent = cat;
        btn.onclick = (event) => filtrarCategoria(cat, event);
        contenedor.appendChild(btn);
    });
}

function filtrarCategoria(categoria, event) {
    categoriaActual = categoria;
    document.querySelectorAll('.filtro-btn').forEach((b) => {
        b.classList.remove('activo');
    });

    const objetivo = event?.target || document.querySelector(`#filtros .filtro-btn`);
    if (objetivo) {
        objetivo.classList.add('activo');
    }

    aplicarFiltrosCatalogo();
}

function aplicarFiltrosCatalogo() {
    const texto = (document.getElementById('buscador-carta')?.value || '').trim().toLowerCase();

    const productos = productosCatalogo.filter((p) => {
        const coincideCategoria = categoriaActual === 'todas' || p.categoria === categoriaActual;
        const sabores = (p.sabores || []).map((s) => s.nombre).join(' ').toLowerCase();
        const coincideTexto =
            !texto ||
            p.nombre.toLowerCase().includes(texto) ||
            p.categoria.toLowerCase().includes(texto) ||
            sabores.includes(texto);

        return coincideCategoria && coincideTexto;
    });

    renderizarProductos(productos);
}

// Dibuja tarjetas de producto respetando disponibilidad y soporte de sabores.
function renderizarProductos(productos) {
    const contenedor = document.getElementById('lista-productos');
    if (!contenedor) return;

    contenedor.innerHTML = '';

    if (!productos.length) {
        contenedor.innerHTML = `
            <div class="col-12">
                <div class="text-center text-muted py-4">No hay productos para este filtro.</div>
            </div>`;
        return;
    }

    productos.forEach((p) => {
        const col = document.createElement('div');
        col.className = 'col-6 col-md-4 col-xl-3';

        const tieneSabores = (p.sabores || []).length > 0;
        const img = p.imagen_url
            ? `<img src="${p.imagen_url}" alt="${p.nombre}" class="producto-img">`
            : '<div class="producto-img-placeholder d-flex align-items-center justify-content-center"><i class="bi bi-image text-muted opacity-25" style="font-size: 2rem;"></i></div>';

        const badgeSabores = tieneSabores ? `<span class="badge-sabor-indicador"><i class="bi bi-stars"></i></span>` : '';
        const nombreSeguro = p.nombre.replace(/'/g, "\\'");

        col.innerHTML = `
            <div class="card producto-card h-100 ${!p.disponible ? 'agotado' : ''}"
                 onclick="${p.disponible ? `handleProductoTap(this, ${p.id}, '${nombreSeguro}', ${p.precio})` : ''}">
                <div class="producto-img-container">
                    ${img}
                    <div class="producto-precio-badge">$${p.precio.toFixed(2)}</div>
                    ${badgeSabores}
                </div>
                <div class="card-body p-2 d-flex flex-column justify-content-center text-center">
                    <h6 class="fw-bold mb-0 lh-sm text-dark" style="font-size: 0.85rem;">${p.nombre}</h6>
                    ${!p.disponible ? '<small class="text-danger fw-bold mt-1">Agotado</small>' : ''}
                </div>
            </div>`;
        contenedor.appendChild(col);
    });
}

function handleProductoTap(cardElement, id, nombre, precio) {
    const key = `${id}`;
    const timer = tapTimers.get(key);

    if (timer) {
        clearTimeout(timer);
        tapTimers.delete(key);
        agregarRapido(id, nombre, precio, cardElement);
        return;
    }

    const newTimer = setTimeout(() => {
        tapTimers.delete(key);
        agregarProducto(id, nombre, precio, cardElement);
    }, TAP_DELAY_MS);

    tapTimers.set(key, newTimer);
}

// Tap simple abre flujo normal; doble tap aplica agregado rapido.
function agregarProducto(id, nombre, precio, cardElement = null) {
    const producto = productosCatalogo.find((p) => p.id === id);
    const sabores = (producto?.sabores || []).map((s) => s.nombre);
    const maxSabores = Number(producto?.max_sabores || 1);

    if (sabores.length > 0) {
        itemPendienteSabor = { id, nombre, precio, sabores, maxSabores };
        abrirModalSabor(itemPendienteSabor);
        return;
    }

    agregarProductoConSabor(id, nombre, precio, null, cardElement);
}

function agregarProductoConSabor(id, nombre, precio, sabor, cardElement = null) {
    const mismaLinea = pedidoActual.productos.find(
        (p) => p.producto_id === id && (p.sabor || null) === (sabor || null)
    );

    if (mismaLinea) {
        mismaLinea.cantidad++;
    } else {
        pedidoActual.productos.push({ producto_id: id, nombre, precio, cantidad: 1, sabor });
    }

    actualizarResumen();
    feedbackAgregar(cardElement);
}

// En productos con sabores, toma sugeridos para acelerar carga en caja.
function agregarRapido(id, nombre, precio, cardElement = null) {
    const producto = productosCatalogo.find((p) => p.id === id);
    if (!producto) return;

    const sabores = (producto.sabores || []).map((s) => s.nombre);
    const maxSabores = Number(producto.max_sabores || 1);

    if (sabores.length > 0) {
        const sugeridos = sabores.slice(0, Math.max(1, maxSabores));
        agregarProductoConSabor(id, nombre, precio, sugeridos.join(', '), cardElement);
        mostrarToast(`Agregado rapido: ${sugeridos.join(', ')}`, 'info');
        return;
    }

    agregarProductoConSabor(id, nombre, precio, null, cardElement);
}

function feedbackAgregar(cardElement) {
    if (navigator.vibrate) {
        navigator.vibrate(20);
    }

    if (cardElement) {
        cardElement.classList.remove('flash-add');
        void cardElement.offsetWidth;
        cardElement.classList.add('flash-add');
    }
}

function abrirModalSabor(item) {
    const label = document.getElementById('sabor-producto-label');
    const regla = document.getElementById('sabor-producto-regla');
    const selector = document.getElementById('selector-sabor-pedido');

    if (!label || !regla || !selector) return;

    label.textContent = `Selecciona sabor para ${item.nombre}`;
    regla.textContent = `Puedes elegir hasta ${item.maxSabores} sabor(es).`;

    window.toggleSaborFeedback = function(input) {
        if (navigator.vibrate) navigator.vibrate(15);
        if (itemPendienteSabor && itemPendienteSabor.maxSabores === 1) {
            setTimeout(confirmarSaborSeleccionado, 150);
        } else if (itemPendienteSabor) {
            const checks = document.querySelectorAll('#selector-sabor-pedido input[type="checkbox"]');
            const checkedCount = Array.from(checks).filter(c => c.checked).length;
            const max = itemPendienteSabor.maxSabores;
            
            checks.forEach(c => {
                if (!c.checked) {
                    c.disabled = (checkedCount >= max);
                    c.parentElement.style.opacity = c.disabled ? '0.4' : '1';
                    c.parentElement.style.pointerEvents = c.disabled ? 'none' : 'auto';
                }
            });
        }
    };

    if (item.maxSabores === 1) {
        selector.innerHTML = item.sabores.map((s) => `
            <label class="sabor-opcion">
                <input class="form-check-input" name="sabor-unico" type="radio" value="${s}" onchange="toggleSaborFeedback(this)">
                <span>${s}</span>
            </label>
        `).join('');
    } else {
        selector.innerHTML = item.sabores.map((s, index) => {
            const isChecked = index < item.maxSabores;
            const isDisabled = !isChecked; // Porque inicialmente seleccionamos el maximo permitido
            const pointerStyle = isDisabled ? 'pointer-events: none;' : '';
            const opacityStyle = isDisabled ? 'opacity: 0.4;' : '';
            return `
            <label class="sabor-opcion" style="${pointerStyle} ${opacityStyle}">
                <input class="form-check-input" type="checkbox" value="${s}" ${isChecked ? 'checked' : ''} ${isDisabled ? 'disabled' : ''} onchange="toggleSaborFeedback(this)">
                <span>${s}</span>
            </label>
            `;
        }).join('');
    }

    new bootstrap.Modal(document.getElementById('modal-sabor')).show();
}

// Aplica validaciones de seleccion antes de persistir sabor en el item.
function confirmarSaborSeleccionado() {
    if (!itemPendienteSabor) return;

    const checks = document.querySelectorAll('#selector-sabor-pedido input:checked');
    const saboresSeleccionados = [...checks].map((c) => c.value);

    if (saboresSeleccionados.length === 0) {
        mostrarToast('Selecciona al menos un sabor', 'warning');
        return;
    }

    if (saboresSeleccionados.length > itemPendienteSabor.maxSabores) {
        mostrarToast(`Maximo ${itemPendienteSabor.maxSabores} sabor(es)`, 'warning');
        return;
    }

    agregarProductoConSabor(
        itemPendienteSabor.id,
        itemPendienteSabor.nombre,
        itemPendienteSabor.precio,
        saboresSeleccionados.join(', ')
    );

    bootstrap.Modal.getInstance(document.getElementById('modal-sabor'))?.hide();
    itemPendienteSabor = null;
}

function actualizarResumen() {
    const contenedor = document.getElementById('items-pedido');
    const contenedorMobile = document.getElementById('items-pedido-mobile-list');
    
    if (contenedor) contenedor.innerHTML = '';
    if (contenedorMobile) contenedorMobile.innerHTML = '';

    if (pedidoActual.productos.length === 0) {
        if (contenedor) {
            contenedor.innerHTML = '<p class="text-muted small" id="pedido-vacio">No hay productos aun</p>';
        }
        if (contenedorMobile) {
            contenedorMobile.innerHTML = '<p class="text-muted small text-center my-4" id="pedido-vacio-mobile">No hay productos aun</p>';
        }
        document.getElementById('total-pedido').textContent = '$0.00';
        actualizarResumenMovil(0, 0);
        actualizarCheckoutTotal(0);
        return;
    }

    let total = 0;
    let items = 0;

    pedidoActual.productos.forEach((item) => {
        const precioUnitario = pedidoActual.tipo === 'delivery' ? item.precio + 0.25 : item.precio;
        const subtotal = precioUnitario * item.cantidad;
        total += subtotal;
        items += item.cantidad;

        const saborSeguro = item.sabor ? item.sabor.replace(/'/g, "\\'") : null;
        const html = `
            <div>
                <span class="fw-bold small">${item.nombre}</span>
                ${item.sabor ? `<span class="badge bg-light text-dark border ms-1">${item.sabor}</span>` : ''}
                <br>
                <small class="text-muted">$${precioUnitario.toFixed(2)} x ${item.cantidad} ${pedidoActual.tipo === 'delivery' ? '<span class="text-warning" style="font-size: 0.65rem;">(+0.25)</span>' : ''}</small>
            </div>
            <div class="d-flex align-items-center gap-2">
                <button class="btn btn-sm btn-outline-secondary py-0 px-2" style="border-color: #e5e7eb;" onclick="editarObservacion(${item.producto_id}, ${saborSeguro ? `'${saborSeguro}'` : 'null'})" title="Añadir Observación">
                    <i class="bi bi-pencil text-muted"></i>
                </button>
                <span class="text-success fw-bold small">$${subtotal.toFixed(2)}</span>
                <button class="btn btn-sm btn-outline-danger py-0" onclick="quitarProducto(${item.producto_id}, ${saborSeguro ? `'${saborSeguro}'` : 'null'})">
                    <i class="bi bi-dash"></i>
                </button>
            </div>`;

        if (contenedor) {
            const div = document.createElement('div');
            div.className = 'd-flex justify-content-between align-items-center mb-2 p-2 bg-white rounded shadow-sm border border-light';
            div.innerHTML = html;
            contenedor.appendChild(div);
        }
        if (contenedorMobile) {
            const divM = document.createElement('div');
            divM.className = 'd-flex justify-content-between align-items-center mb-2 p-2 bg-white rounded shadow-sm border border-light';
            divM.innerHTML = html;
            contenedorMobile.appendChild(divM);
        }
    });

    document.getElementById('total-pedido').textContent = `$${total.toFixed(2)}`;
    actualizarCheckoutTotal(total);
    actualizarResumenMovil(total, items);
}

function actualizarCheckoutTotal(total) {
    const target = document.getElementById('checkout-total');
    if (target) {
        target.textContent = `$${Number(total).toFixed(2)}`;
    }
    if (typeof calcularCambioEfectivo === 'function') {
        calcularCambioEfectivo();
    }
}

// Resume total/items en la barra inferior movil.
function actualizarResumenMovil(total, items) {
    const totalMobile = document.getElementById('total-pedido-mobile');
    const itemsMobile = document.getElementById('items-pedido-mobile');

    if (totalMobile) totalMobile.textContent = `$${Number(total || 0).toFixed(2)}`;
    if (itemsMobile) itemsMobile.textContent = `${items} item${items === 1 ? '' : 's'}`;
}

function quitarProducto(id, sabor = null) {
    if (navigator.vibrate) navigator.vibrate(15);
    const item = pedidoActual.productos.find(
        (p) => p.producto_id === id && (p.sabor || null) === (sabor || null)
    );

    if (!item) return;

    if (item.cantidad > 1) {
        item.cantidad--;
    } else {
        pedidoActual.productos = pedidoActual.productos.filter(
            (p) => !(p.producto_id === id && (p.sabor || null) === (sabor || null))
        );
    }

    actualizarResumen();
}

function editarObservacion(id, sabor = null) {
    if (navigator.vibrate) navigator.vibrate(15);
    const item = pedidoActual.productos.find(
        (p) => p.producto_id === id && (p.sabor || null) === (sabor || null)
    );

    if (!item) return;

    const nuevaNota = prompt(`Detalle / Observación para:\n${item.nombre}`, item.sabor || "");
    
    if (nuevaNota !== null) { 
        item.sabor = nuevaNota.trim() !== "" ? nuevaNota.trim() : null;
        actualizarResumen();
    }
}

function abrirCheckout() {
    if (navigator.vibrate) navigator.vibrate(20);
    if (pedidoActual.productos.length === 0) {
        mostrarToast('Agrega al menos un producto', 'warning');
        return;
    }

    actualizarEtiquetaNumeroPedido();
    const total = pedidoActual.productos.reduce((acc, p) => acc + ((p.precio + (pedidoActual.tipo === 'delivery' ? 0.25 : 0)) * p.cantidad), 0);
    actualizarCheckoutTotal(total);
    new bootstrap.Modal(document.getElementById('modal-checkout')).show();
}

function setTipo(tipo) {
    if (navigator.vibrate) navigator.vibrate(10);
    pedidoActual.tipo = tipo;

    actualizarResumen();
    const total = pedidoActual.productos.reduce((acc, p) => acc + ((p.precio + (pedidoActual.tipo === 'delivery' ? 0.25 : 0)) * p.cantidad), 0);
    actualizarCheckoutTotal(total);

    const btnLocal = document.getElementById('btn-local');
    const btnDelivery = document.getElementById('btn-delivery');
    if (btnLocal) btnLocal.className = `btn btn-sm flex-fill ${tipo === 'local' ? 'btn-dark' : 'btn-outline-dark'}`;
    if (btnDelivery) btnDelivery.className = `btn btn-sm flex-fill ${tipo === 'delivery' ? 'btn-dark' : 'btn-outline-dark'}`;
}

// Controla visibilidad de campos extra segun forma de pago elegida.
function setFormaPago(forma) {
    if (navigator.vibrate) navigator.vibrate(10);
    formaPagoActual = forma;
    ['efectivo', 'transferencia', 'mixto'].forEach((f) => {
        const btn = document.getElementById(`btn-${f}`);
        if (btn) btn.className = `btn btn-sm flex-fill ${f === forma ? 'btn-dark' : 'btn-outline-dark'}`;
    });

    const contenedorExtra = document.getElementById('campos-pago-extra');
    const compComprobante = document.getElementById('campo-comprobante');
    const compMixto = document.getElementById('campos-mixto');
    const compEfectivo = document.getElementById('campos-efectivo');

    if (!contenedorExtra || !compComprobante || !compMixto) return;

    contenedorExtra.style.display = 'block';

    if (forma === 'efectivo') {
        compComprobante.style.display = 'none';
        compMixto.style.display = 'none';
        if (compEfectivo) compEfectivo.style.display = 'flex';
        calcularCambioEfectivo();
    } else if (forma === 'transferencia') {
        compComprobante.style.display = 'block';
        compMixto.style.display = 'none';
        if (compEfectivo) compEfectivo.style.display = 'none';
    } else {
        compComprobante.style.display = 'block';
        compMixto.style.display = 'flex';
        if (compEfectivo) compEfectivo.style.display = 'none';
    }
}

// Calcula el cambio matematico en tiempo real p/ pagos en efectivo
function calcularCambioEfectivo() {
    if (formaPagoActual !== 'efectivo') return;
    
    const subtotalBruto = pedidoActual.productos.reduce((acc, p) => acc + ((p.precio + (pedidoActual.tipo === 'delivery' ? 0.25 : 0)) * p.cantidad), 0);
    const inputRecibido = document.getElementById('monto-recibido');
    const recibido = parseFloat(inputRecibido?.value) || 0;
    const cambioInput = document.getElementById('monto-cambio');
    
    if (!cambioInput) return;

    if (recibido === 0 || inputRecibido.value === '') {
        cambioInput.value = '';
        cambioInput.classList.replace('text-danger', 'text-success');
        return;
    }

    const cambio = recibido - subtotalBruto;
    if (cambio >= 0) {
        cambioInput.value = cambio.toFixed(2);
        cambioInput.classList.replace('text-danger', 'text-success');
    } else {
        cambioInput.value = 'Faltan $' + Math.abs(cambio).toFixed(2);
        cambioInput.classList.replace('text-success', 'text-danger');
    }
}

function limpiarPedido() {
    pedidoActual.productos = [];
    document.getElementById('cliente-nombre').value = 'Consumidor final';
    document.getElementById('numero-comprobante').value = '';
    document.getElementById('monto-efectivo').value = '';
    document.getElementById('monto-transferencia').value = '';
    const mr = document.getElementById('monto-recibido');
    if (mr) mr.value = '';
    const mc = document.getElementById('monto-cambio');
    if (mc) mc.value = '';
    document.getElementById('validacion-montos').style.display = 'none';

    setTipo('local');
    setFormaPago('efectivo');
    actualizarResumen();
}

// Evita doble envio mientras se confirma el pedido.
function setConfirmandoPedido(loading) {
    const boton = document.getElementById('btn-confirmar-final');
    if (!boton) return;

    if (loading) {
        boton.disabled = true;
        boton.dataset.originalHtml = boton.innerHTML;
        boton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Procesando...';
    } else {
        boton.disabled = false;
        if (boton.dataset.originalHtml) boton.innerHTML = boton.dataset.originalHtml;
    }
}

async function confirmarPedido() {
    const nombre = document.getElementById('cliente-nombre').value.trim();

    if (!nombre) {
        mostrarToast('Ingresa el nombre del cliente', 'warning');
        return;
    }
    if (pedidoActual.productos.length === 0) {
        mostrarToast('Agrega al menos un producto', 'warning');
        return;
    }

    const numComprobante = document.getElementById('numero-comprobante').value.trim();
    const mEfectivo = parseFloat(document.getElementById('monto-efectivo').value) || 0;
    const mTransferencia = parseFloat(document.getElementById('monto-transferencia').value) || 0;

    if (formaPagoActual === 'transferencia' && !numComprobante) {
        mostrarToast('Debes ingresar el numero de comprobante', 'warning');
        return;
    }

    if (formaPagoActual === 'efectivo') {
        const recibido = parseFloat(document.getElementById('monto-recibido')?.value) || 0;
        const totalReq = pedidoActual.productos.reduce((acc, p) => acc + ((p.precio + (pedidoActual.tipo === 'delivery' ? 0.25 : 0)) * p.cantidad), 0);
        if (recibido > 0 && recibido < totalReq) {
            mostrarToast(`Faltan $${(totalReq - recibido).toFixed(2)} para completar el pago`, 'warning');
            return;
        }
    }

    if (formaPagoActual === 'mixto') {
        if (!numComprobante) {
            mostrarToast('Debes ingresar el numero de comprobante', 'warning');
            return;
        }

        const totalVal = pedidoActual.productos.reduce((acc, p) => acc + ((p.precio + (pedidoActual.tipo === 'delivery' ? 0.25 : 0)) * p.cantidad), 0);
        if (Math.abs((mEfectivo + mTransferencia) - totalVal) > 0.01) {
            document.getElementById('validacion-montos').style.display = 'block';
            mostrarToast('Los montos no suman el total del pedido', 'warning');
            return;
        }
        document.getElementById('validacion-montos').style.display = 'none';
    }

    setConfirmandoPedido(true);

    // Payload esperado por /pedidos/ conservando compatibilidad de sabores.
    const datos = {
        tipo: pedidoActual.tipo,
        cliente_nombre: nombre || 'Consumidor final',
        cliente_telefono: null,
        cliente_direccion: null,
        plataforma: null,
        forma_pago: formaPagoActual,
        numero_comprobante: ['transferencia', 'mixto'].includes(formaPagoActual) ? numComprobante : null,
        monto_efectivo: formaPagoActual === 'mixto' ? mEfectivo : null,
        monto_transferencia: formaPagoActual === 'mixto' ? mTransferencia : null,
        productos: pedidoActual.productos.map((p) => ({
            producto_id: p.producto_id,
            cantidad: p.cantidad,
            sabor: p.sabor || null,
            sabores: p.sabor ? p.sabor.split(',').map((s) => s.trim()).filter(Boolean) : []
        }))
    };

    if (!navigator.onLine) {
        guardarPedidoOffline(datos);
        mostrarToast('Sin conexión: Pedido guardado localmente (se enviará al reconectar).', 'warning');
        bootstrap.Modal.getInstance(document.getElementById('modal-checkout'))?.hide();
        limpiarPedido();
        siguienteNumeroPedido++;
        actualizarEtiquetaNumeroPedido();
        setConfirmandoPedido(false);
        return;
    }

    try {
        const respuesta = await fetch('/pedidos/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datos)
        });

        const resultado = await respuesta.json();

        if (respuesta.ok) {
            mostrarToast(`Pedido #${resultado.numero_pedido} confirmado. Total: $${resultado.total.toFixed(2)}`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('modal-checkout'))?.hide();
            limpiarPedido();
            await Promise.all([cargarPedidosActivos(), cargarSiguienteNumeroPedido()]);
        } else {
            mostrarToast(resultado.error || 'No se pudo crear el pedido', 'danger');
        }
    } catch (error) {
        console.error(error);
        // Si el fetch falla por timeout o servidor caído, encolamos el pedido
        guardarPedidoOffline(datos);
        mostrarToast('Error en el servidor. Pedido guardado local de forma segura.', 'danger');
        bootstrap.Modal.getInstance(document.getElementById('modal-checkout'))?.hide();
        limpiarPedido();
        siguienteNumeroPedido++;
        actualizarEtiquetaNumeroPedido();
    } finally {
        setConfirmandoPedido(false);
    }
}

// --- LOGICA OFFLINE (PWA QUEUE) ---
function guardarPedidoOffline(pedidoData) {
    let cola = JSON.parse(localStorage.getItem('cola_pedidos') || '[]');
    pedidoData._offline_id = Date.now().toString() + Math.random().toString(36).substring(2, 7);
    cola.push(pedidoData);
    localStorage.setItem('cola_pedidos', JSON.stringify(cola));
}

function sincronizarPedidosOffline() {
    if (!navigator.onLine) return;
    let cola = JSON.parse(localStorage.getItem('cola_pedidos') || '[]');
    if (cola.length === 0) return;

    const pedido = cola[0];
    const offlineId = pedido._offline_id;
    delete pedido._offline_id;

    fetch('/pedidos/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pedido)
    }).then(response => {
        if (response.ok) {
            cola.shift(); // Quitar de la cola
            localStorage.setItem('cola_pedidos', JSON.stringify(cola));
            mostrarToast('Pedido Offline enviado exitosamente.', 'success');
            setTimeout(sincronizarPedidosOffline, 1000);
            cargarPedidosActivos();
            cargarSiguienteNumeroPedido();
        } else {
            pedido._offline_id = offlineId; // Restaurar si hubo un error HTTP (ej: 400 Bad Request)
        }
    }).catch(err => {
        pedido._offline_id = offlineId; // Restaurar si fallo la red durante fetch
    });
}
window.addEventListener('online', sincronizarPedidosOffline);
setInterval(sincronizarPedidosOffline, 15000);
document.addEventListener('DOMContentLoaded', sincronizarPedidosOffline);


async function cargarPedidosActivos() {
    try {
        const respuesta = await fetch('/pedidos/');
        if (!respuesta.ok) {
            throw new Error(`No se pudieron cargar pedidos (HTTP ${respuesta.status})`);
        }

        const pedidos = await respuesta.json();
        renderizarPedidosActivos(pedidos);
    } catch (error) {
        console.error('Error al cargar pedidos activos:', error);
    }
}

// Render compartido para escritorio y movil.
function renderizarPedidosActivos(pedidos) {
    const contenedores = [
        document.getElementById('lista-pedidos-activos'),
        document.getElementById('lista-pedidos-activos-mobile')
    ].filter(Boolean);

    if (!contenedores.length) return;

    if (!pedidos || pedidos.length === 0) {
        const htmlVacio = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-inbox fs-3"></i>
                <p class="mt-2 mb-0">No hay pedidos activos en este momento</p>
            </div>`;

        contenedores.forEach((contenedor) => {
            contenedor.innerHTML = htmlVacio;
        });
        return;
    }

    const html = pedidos.map((p) => {
        const badgeTipo = p.tipo === 'delivery'
            ? '<span class="badge bg-warning text-dark">Delivery</span>'
            : '<span class="badge bg-info text-dark">Local</span>';

        let badgeEstado = '';
        if (p.estado === 'pendiente') {
            badgeEstado = '<span class="badge bg-secondary">Pendiente</span>';
        } else if (p.estado === 'en_proceso') {
            badgeEstado = '<span class="badge bg-primary">En Cocina</span>';
        } else if (p.estado === 'preparado') {
            badgeEstado = '<span class="badge bg-success">Listo p/ Entregar</span>';
        }

        const badgePago = p.forma_pago === 'transferencia'
            ? `<span class="badge bg-light text-dark border">Transf. #${p.numero_comprobante || '—'}</span>`
            : p.forma_pago === 'mixto'
                ? `<span class="badge bg-light text-dark border">Mixto #${p.numero_comprobante || '—'}</span>`
                : p.forma_pago === 'pago_pedidosya'
                    ? `<span class="badge bg-light text-dark border">Pago PedidosYa</span>`
                : '';

        const plataformaTxt = p.tipo === 'delivery' && p.plataforma
            ? `<div class="small text-muted">Plataforma: ${p.plataforma}</div>`
            : '';

        return `
            <div class="list-group-item py-2">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                    <div>
                        <strong>Pedido #${p.numero_pedido || '-'}</strong>
                        <div><strong>${p.cliente_nombre || 'Cliente'}</strong></div>
                        ${plataformaTxt}
                        <span class="ms-0">${badgeTipo}</span>
                        <span class="ms-1">${badgeEstado}</span>
                        ${badgePago ? `<span class="ms-1">${badgePago}</span>` : ''}
                        <div class="text-muted small mt-1">
                            <i class="bi bi-clock"></i> ${p.fecha}
                            &nbsp;·&nbsp;
                            <strong class="text-dark">$${parseFloat(p.total).toFixed(2)}</strong>
                        </div>
                    </div>
                    <div class="d-flex gap-1">
                        <button class="btn btn-sm btn-outline-dark" onclick="imprimirTicketPedido(${p.id})">
                            <i class="bi bi-printer"></i> Ticket
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="eliminarPedido(${p.id})">
                            <i class="bi bi-trash"></i> Eliminar
                        </button>
                        ${p.estado === 'preparado' 
                            ? `<button class="btn btn-sm btn-success" onclick="cambiarEstado(${p.id}, 'entregado')">
                                 <i class="bi bi-check-lg"></i> Entregar al Cliente
                               </button>`
                            : `<button class="btn btn-sm btn-secondary" disabled>
                                 <i class="bi bi-hourglass"></i> Esperando Cocina
                               </button>`
                        }
                    </div>
                </div>
            </div>`;
    }).join('');

    contenedores.forEach((contenedor) => {
        contenedor.innerHTML = html;
    });
}

function imprimirTicketPedido(pedidoId) {
    window.open(`/pedidos/${pedidoId}/ticket`, '_blank');
}

async function eliminarPedido(pedidoId) {
    const confirmar = confirm('Este pedido se eliminara de la cola. Deseas continuar?');
    if (!confirmar) return;

    try {
        const respuesta = await fetch(`/pedidos/${pedidoId}`, { method: 'DELETE' });

        let datos = {};
        const contentType = respuesta.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            datos = await respuesta.json();
        }

        if (respuesta.ok) {
            mostrarToast('Pedido eliminado correctamente', 'success');
            await Promise.all([cargarPedidosActivos(), cargarSiguienteNumeroPedido()]);
        } else {
            mostrarToast(datos.error || 'No se pudo eliminar el pedido', 'warning');
        }
    } catch (error) {
        mostrarToast('Error de conexion al eliminar pedido', 'danger');
    }
}

async function cambiarEstado(pedidoId, nuevoEstado) {
    if (nuevoEstado === 'entregado') {
        const confirmar = confirm('Confirmas que este pedido fue entregado al cliente?');
        if (!confirmar) return;
    }

    try {
        const respuesta = await fetch(`/pedidos/${pedidoId}/estado`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });

        const datos = await respuesta.json();

        if (respuesta.ok) {
            mostrarToast(`Estado actualizado: ${nuevoEstado}`, 'success');
            cargarPedidosActivos();
        } else {
            mostrarToast(datos.error || 'Error al actualizar el estado', 'danger');
        }
    } catch (error) {
        mostrarToast('Error de conexion', 'danger');
    }
}
