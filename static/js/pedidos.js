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

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('buscador-carta')?.addEventListener('input', aplicarFiltrosCatalogo);

    await Promise.all([
        cargarProductos(),
        cargarPedidosActivos(),
        cargarSiguienteNumeroPedido()
    ]);

    setInterval(cargarPedidosActivos, 20000);
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

function renderizarFiltros(productos) {
    const categorias = [...new Set(productos.map((p) => p.categoria))];
    const contenedor = document.getElementById('filtros');
    if (!contenedor) return;

    contenedor.querySelectorAll('.dinamico').forEach((btn) => btn.remove());

    categorias.forEach((cat) => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-dark filtro-btn dinamico';
        btn.textContent = cat;
        btn.onclick = (event) => filtrarCategoria(cat, event);
        contenedor.appendChild(btn);
    });
}

function filtrarCategoria(categoria, event) {
    categoriaActual = categoria;
    document.querySelectorAll('.filtro-btn').forEach((b) => {
        b.classList.remove('activo', 'btn-dark');
        if (!b.classList.contains('btn-outline-dark')) {
            b.classList.add('btn-outline-dark');
        }
    });

    const objetivo = event?.target || document.querySelector(`#filtros .filtro-btn`);
    if (objetivo) {
        objetivo.classList.add('activo', 'btn-dark');
        objetivo.classList.remove('btn-outline-dark');
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
        col.className = 'col-6 col-md-4';

        const tieneSabores = (p.sabores || []).length > 0;
        const img = p.imagen_url
            ? `<img src="${p.imagen_url}" alt="${p.nombre}" style="width:52px;height:52px;object-fit:cover;border-radius:10px;">`
            : '<div class="fs-3">🍦</div>';

        const nombreSeguro = p.nombre.replace(/'/g, "\\'");

        col.innerHTML = `
            <div class="card producto-card ${!p.disponible ? 'agotado' : ''}"
                 onclick="${p.disponible ? `handleProductoTap(this, ${p.id}, '${nombreSeguro}', ${p.precio})` : ''}">
                <div class="card-body text-center p-2">
                    ${img}
                    <p class="fw-bold mb-1 small">${p.nombre}</p>
                    ${tieneSabores ? '<small class="text-muted d-block">Con sabores</small>' : '<small class="text-muted d-block">Sabor fijo</small>'}
                    <span class="badge bg-dark">$${p.precio.toFixed(2)}</span>
                    ${!p.disponible ? '<br><small class="text-danger">Agotado</small>' : ''}
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

    if (item.maxSabores === 1) {
        selector.innerHTML = item.sabores.map((s, index) => `
            <label class="sabor-opcion">
                <input class="form-check-input" name="sabor-unico" type="radio" value="${s}" ${index === 0 ? 'checked' : ''}>
                <span>${s}</span>
            </label>
        `).join('');
    } else {
        selector.innerHTML = item.sabores.map((s, index) => `
            <label class="sabor-opcion">
                <input class="form-check-input" type="checkbox" value="${s}" ${index < item.maxSabores ? 'checked' : ''}>
                <span>${s}</span>
            </label>
        `).join('');
    }

    new bootstrap.Modal(document.getElementById('modal-sabor')).show();
}

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
    if (!contenedor) return;

    contenedor.innerHTML = '';

    if (pedidoActual.productos.length === 0) {
        const vacio = document.createElement('p');
        vacio.className = 'text-muted small';
        vacio.id = 'pedido-vacio';
        vacio.textContent = 'No hay productos aun';
        contenedor.appendChild(vacio);
        document.getElementById('total-pedido').textContent = '$0.00';
        actualizarResumenMovil(0, 0);
        actualizarCheckoutTotal(0);
        return;
    }

    let total = 0;
    let items = 0;

    pedidoActual.productos.forEach((item) => {
        const subtotal = item.precio * item.cantidad;
        total += subtotal;
        items += item.cantidad;

        const saborSeguro = item.sabor ? item.sabor.replace(/'/g, "\\'") : null;
        const div = document.createElement('div');
        div.className = 'list-group-item d-flex justify-content-between align-items-center px-0 py-2';
        div.innerHTML = `
            <div>
                <span class="fw-bold small">${item.nombre}</span>
                ${item.sabor ? `<span class="badge bg-light text-dark border ms-1">${item.sabor}</span>` : ''}
                <br>
                <small class="text-muted">$${item.precio.toFixed(2)} x ${item.cantidad}</small>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="text-success fw-bold small">$${subtotal.toFixed(2)}</span>
                <button class="btn btn-sm btn-outline-danger py-0" onclick="quitarProducto(${item.producto_id}, ${saborSeguro ? `'${saborSeguro}'` : 'null'})">
                    <i class="bi bi-dash"></i>
                </button>
            </div>`;
        contenedor.appendChild(div);
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
}

function actualizarResumenMovil(total, items) {
    const totalMobile = document.getElementById('total-pedido-mobile');
    const itemsMobile = document.getElementById('items-pedido-mobile');

    if (totalMobile) totalMobile.textContent = `$${Number(total || 0).toFixed(2)}`;
    if (itemsMobile) itemsMobile.textContent = `${items} item${items === 1 ? '' : 's'}`;
}

function quitarProducto(id, sabor = null) {
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

function abrirCheckout() {
    if (pedidoActual.productos.length === 0) {
        mostrarToast('Agrega al menos un producto', 'warning');
        return;
    }

    actualizarEtiquetaNumeroPedido();
    const total = pedidoActual.productos.reduce((acc, p) => acc + (p.precio * p.cantidad), 0);
    actualizarCheckoutTotal(total);
    new bootstrap.Modal(document.getElementById('modal-checkout')).show();
}

function setTipo(tipo) {
    pedidoActual.tipo = tipo;
    const camposDelivery = document.getElementById('campos-delivery');
    if (camposDelivery) camposDelivery.style.display = tipo === 'delivery' ? 'block' : 'none';

    const btnTransferencia = document.getElementById('btn-transferencia');
    const btnMixto = document.getElementById('btn-mixto');
    const btnPagoPedidosYa = document.getElementById('btn-pago-pedidosya');

    if (btnTransferencia) btnTransferencia.style.display = tipo === 'delivery' ? 'none' : 'inline-block';
    if (btnMixto) btnMixto.style.display = tipo === 'delivery' ? 'none' : 'inline-block';
    if (btnPagoPedidosYa) btnPagoPedidosYa.style.display = tipo === 'delivery' ? 'inline-block' : 'none';

    if (tipo === 'delivery' && !['efectivo', 'pago_pedidosya'].includes(formaPagoActual)) {
        setFormaPago('efectivo');
    }
    if (tipo === 'local' && formaPagoActual === 'pago_pedidosya') {
        setFormaPago('efectivo');
    }

    const btnLocal = document.getElementById('btn-local');
    const btnDelivery = document.getElementById('btn-delivery');
    if (btnLocal) btnLocal.className = `btn btn-sm flex-fill ${tipo === 'local' ? 'btn-dark' : 'btn-outline-dark'}`;
    if (btnDelivery) btnDelivery.className = `btn btn-sm flex-fill ${tipo === 'delivery' ? 'btn-dark' : 'btn-outline-dark'}`;
}

function setFormaPago(forma) {
    formaPagoActual = forma;
    ['efectivo', 'transferencia', 'mixto', 'pago_pedidosya'].forEach((f) => {
        const btn = document.getElementById(`btn-${f}`);
        const btnAliasPedidosYa = document.getElementById('btn-pago-pedidosya');
        if (f === 'pago_pedidosya' && btnAliasPedidosYa) {
            btnAliasPedidosYa.className = `btn btn-sm flex-fill ${f === forma ? 'btn-dark' : 'btn-outline-dark'}`;
            return;
        }
        if (btn) btn.className = `btn btn-sm flex-fill ${f === forma ? 'btn-dark' : 'btn-outline-dark'}`;
    });

    const contenedorExtra = document.getElementById('campos-pago-extra');
    const compComprobante = document.getElementById('campo-comprobante');
    const compMixto = document.getElementById('campos-mixto');

    if (!contenedorExtra || !compComprobante || !compMixto) return;

    if (forma === 'efectivo') {
        contenedorExtra.style.display = 'none';
        compComprobante.style.display = 'none';
        compMixto.style.display = 'none';
    } else if (forma === 'transferencia') {
        contenedorExtra.style.display = 'block';
        compComprobante.style.display = 'block';
        compMixto.style.display = 'none';
    } else if (forma === 'pago_pedidosya') {
        contenedorExtra.style.display = 'none';
        compComprobante.style.display = 'none';
        compMixto.style.display = 'none';
    } else {
        contenedorExtra.style.display = 'block';
        compComprobante.style.display = 'block';
        compMixto.style.display = 'flex';
    }
}

function limpiarPedido() {
    pedidoActual.productos = [];
    document.getElementById('cliente-nombre').value = 'Consumidor final';
    const plataforma = document.getElementById('cliente-plataforma');
    if (plataforma) plataforma.value = 'PedidosYa';
    document.getElementById('numero-comprobante').value = '';
    document.getElementById('monto-efectivo').value = '';
    document.getElementById('monto-transferencia').value = '';
    document.getElementById('validacion-montos').style.display = 'none';

    setTipo('local');
    setFormaPago('efectivo');
    actualizarResumen();
}

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

    if (formaPagoActual === 'mixto') {
        if (!numComprobante) {
            mostrarToast('Debes ingresar el numero de comprobante', 'warning');
            return;
        }

        const totalVal = pedidoActual.productos.reduce((acc, p) => acc + (p.precio * p.cantidad), 0);
        if (Math.abs((mEfectivo + mTransferencia) - totalVal) > 0.01) {
            document.getElementById('validacion-montos').style.display = 'block';
            mostrarToast('Los montos no suman el total del pedido', 'warning');
            return;
        }
        document.getElementById('validacion-montos').style.display = 'none';
    }

    setConfirmandoPedido(true);

    const datos = {
        tipo: pedidoActual.tipo,
        cliente_nombre: nombre || 'Consumidor final',
        cliente_telefono: null,
        cliente_direccion: null,
        plataforma: pedidoActual.tipo === 'delivery'
            ? (document.getElementById('cliente-plataforma')?.value || 'PedidosYa')
            : null,
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
        mostrarToast('Error de conexion al guardar el pedido', 'danger');
    } finally {
        setConfirmandoPedido(false);
    }
}

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

        const badgeEstado = p.estado === 'pendiente'
            ? '<span class="badge bg-secondary">Pendiente</span>'
            : '<span class="badge bg-primary">En Proceso</span>';

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
                        <button class="btn btn-sm btn-success" onclick="cambiarEstado(${p.id}, 'entregado')">
                            <i class="bi bi-check-lg"></i> Entregado
                        </button>
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
