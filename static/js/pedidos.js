// ==========================================
// Variables globales del pedido actual
// ==========================================
let pedidoActual = {
    tipo: 'local',
    productos: []  // [{producto_id, nombre, precio, cantidad}]
};

// Forma de pago seleccionada actualmente
let formaPagoActual = 'efectivo';


// ==========================================
// INICIALIZACIÓN: Al cargar la página
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    cargarProductos();
    cargarPedidosActivos();
    // Refrescamos la cola de pedidos activos cada 20 segundos
    setInterval(cargarPedidosActivos, 20000);
});


// ==========================================
// CATÁLOGO DE PRODUCTOS
// ==========================================

async function cargarProductos() {
    const respuesta = await fetch('/productos/');
    const productos = await respuesta.json();
    renderizarFiltros(productos);
    renderizarProductos(productos);
}

function renderizarFiltros(productos) {
    const categorias = [...new Set(productos.map(p => p.categoria))];
    const contenedor = document.getElementById('filtros');

    categorias.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-dark filtro-btn';
        btn.textContent = cat;
        btn.onclick = () => filtrarCategoria(cat);
        contenedor.appendChild(btn);
    });
}

function renderizarProductos(productos) {
    const contenedor = document.getElementById('lista-productos');
    contenedor.innerHTML = '';

    productos.forEach(p => {
        const col = document.createElement('div');
        col.className = 'col-6 col-md-4';
        col.innerHTML = `
            <div class="card producto-card ${!p.disponible ? 'agotado' : ''}"
                 onclick="${p.disponible ? `agregarProducto(${p.id}, '${p.nombre}', ${p.precio})` : ''}">
                <div class="card-body text-center p-2">
                    <div class="fs-3">🍦</div>
                    <p class="fw-bold mb-1 small">${p.nombre}</p>
                    <span class="badge bg-dark">$${p.precio.toFixed(2)}</span>
                    ${!p.disponible ? '<br><small class="text-danger">Agotado</small>' : ''}
                </div>
            </div>`;
        contenedor.appendChild(col);
    });
}

function filtrarCategoria(categoria) {
    document.querySelectorAll('.filtro-btn').forEach(b => b.classList.remove('activo'));
    event.target.classList.add('activo');

    fetch('/productos/')
        .then(r => r.json())
        .then(productos => {
            const filtrados = categoria === 'todas'
                ? productos
                : productos.filter(p => p.categoria === categoria);
            renderizarProductos(filtrados);
        });
}


// ==========================================
// CARRITO DEL PEDIDO ACTUAL
// ==========================================

function agregarProducto(id, nombre, precio) {
    const existente = pedidoActual.productos.find(p => p.producto_id === id);
    if (existente) {
        existente.cantidad++;
    } else {
        pedidoActual.productos.push({ producto_id: id, nombre, precio, cantidad: 1 });
    }
    actualizarResumen();
}

function actualizarResumen() {
    const contenedor = document.getElementById('items-pedido');
    contenedor.innerHTML = '';

    if (pedidoActual.productos.length === 0) {
        // Recreamos el elemento en lugar de reutilizar una referencia desanclada del DOM
        const vacio = document.createElement('p');
        vacio.className = 'text-muted small';
        vacio.id = 'pedido-vacio';
        vacio.textContent = 'No hay productos aún';
        contenedor.appendChild(vacio);
        document.getElementById('total-pedido').textContent = '$0.00';
        return;
    }

    let total = 0;
    pedidoActual.productos.forEach(item => {
        const subtotal = item.precio * item.cantidad;
        total += subtotal;

        const div = document.createElement('div');
        div.className = 'list-group-item d-flex justify-content-between align-items-center px-0 py-1';
        div.innerHTML = `
            <div>
                <span class="fw-bold small">${item.nombre}</span><br>
                <small class="text-muted">$${item.precio.toFixed(2)} × ${item.cantidad}</small>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="text-success fw-bold small">$${subtotal.toFixed(2)}</span>
                <button class="btn btn-sm btn-outline-danger py-0" onclick="quitarProducto(${item.producto_id})">
                    <i class="bi bi-dash"></i>
                </button>
            </div>`;
        contenedor.appendChild(div);
    });

    document.getElementById('total-pedido').textContent = `$${total.toFixed(2)}`;
}

function quitarProducto(id) {
    const item = pedidoActual.productos.find(p => p.producto_id === id);
    if (item.cantidad > 1) {
        item.cantidad--;
    } else {
        pedidoActual.productos = pedidoActual.productos.filter(p => p.producto_id !== id);
    }
    actualizarResumen();
}


// ==========================================
// CONTROLES DE TIPO Y FORMA DE PAGO
// ==========================================

function setTipo(tipo) {
    pedidoActual.tipo = tipo;
    document.getElementById('campos-delivery').style.display = tipo === 'delivery' ? 'block' : 'none';
    document.getElementById('btn-local').className = `btn btn-sm flex-fill ${tipo === 'local' ? 'btn-dark' : 'btn-outline-dark'}`;
    document.getElementById('btn-delivery').className = `btn btn-sm flex-fill ${tipo === 'delivery' ? 'btn-dark' : 'btn-outline-dark'}`;
}

function setFormaPago(forma) {
    formaPagoActual = forma;
    ['efectivo', 'transferencia', 'mixto'].forEach(f => {
        const btn = document.getElementById(`btn-${f}`);
        if (btn) btn.className = `btn btn-sm flex-fill ${f === forma ? 'btn-dark' : 'btn-outline-dark'}`;
    });

    const contenedorExtra = document.getElementById('campos-pago-extra');
    const compComprobante = document.getElementById('campo-comprobante');
    const compMixto = document.getElementById('campos-mixto');

    if (contenedorExtra) {
        if (forma === 'efectivo') {
            contenedorExtra.style.display = 'none';
            compComprobante.style.display = 'none';
            compMixto.style.display = 'none';
        } else if (forma === 'transferencia') {
            contenedorExtra.style.display = 'block';
            compComprobante.style.display = 'block';
            compMixto.style.display = 'none';
        } else if (forma === 'mixto') {
            contenedorExtra.style.display = 'block';
            compComprobante.style.display = 'block';
            compMixto.style.display = 'flex';
        }
    }
}

function limpiarPedido() {
    pedidoActual.productos = [];
    document.getElementById('cliente-nombre').value = 'Consumidor final';
    document.getElementById('cliente-telefono').value = '';
    document.getElementById('cliente-direccion').value = '';
    document.getElementById('numero-comprobante').value = '';
    document.getElementById('monto-efectivo').value = '';
    document.getElementById('monto-transferencia').value = '';
    document.getElementById('validacion-montos').style.display = 'none';
    setFormaPago('efectivo');
    actualizarResumen();
}


// ==========================================
// CONFIRMAR PEDIDO (POST al backend)
// ==========================================

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

    let num_comprobante = document.getElementById('numero-comprobante').value.trim();
    let m_efectivo = parseFloat(document.getElementById('monto-efectivo').value) || 0;
    let m_transf = parseFloat(document.getElementById('monto-transferencia').value) || 0;

    if (formaPagoActual === 'transferencia' && !num_comprobante) {
        mostrarToast('Debes ingresar el número de comprobante', 'warning');
        return;
    }

    if (formaPagoActual === 'mixto') {
        if (!num_comprobante) {
            mostrarToast('Debes ingresar el número de comprobante', 'warning');
            return;
        }
        let totalVal = pedidoActual.productos.reduce((acc, p) => acc + (p.precio * p.cantidad), 0);
        if (Math.abs((m_efectivo + m_transf) - totalVal) > 0.01) {
            document.getElementById('validacion-montos').style.display = 'block';
            mostrarToast('Los montos no suman el total del pedido', 'warning');
            return;
        } else {
            document.getElementById('validacion-montos').style.display = 'none';
        }
    }

    const datos = {
        tipo: pedidoActual.tipo,
        cliente_nombre: nombre || 'Consumidor final',
        cliente_telefono: document.getElementById('cliente-telefono').value || null,
        cliente_direccion: document.getElementById('cliente-direccion').value || null,
        forma_pago: formaPagoActual,
        numero_comprobante: (formaPagoActual !== 'efectivo') ? num_comprobante : null,
        monto_efectivo: (formaPagoActual === 'mixto') ? m_efectivo : null,
        monto_transferencia: (formaPagoActual === 'mixto') ? m_transf : null,
        productos: pedidoActual.productos.map(p => ({
            producto_id: p.producto_id,
            cantidad: p.cantidad
        }))
    };

    const respuesta = await fetch('/pedidos/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(datos)
    });

    const resultado = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(`Pedido confirmado. Total: $${resultado.total.toFixed(2)}`, 'success');
        limpiarPedido();
        // Refrescamos la cola de activos inmediatamente para que aparezca el nuevo pedido
        cargarPedidosActivos();
    } else {
        mostrarToast(resultado.error, 'danger');
    }
}


// ==========================================
// COLA DE PEDIDOS ACTIVOS
// ==========================================

async function cargarPedidosActivos() {
    try {
        const respuesta = await fetch('/pedidos/');
        const pedidos = await respuesta.json();
        renderizarPedidosActivos(pedidos);
    } catch (error) {
        console.error('Error al cargar pedidos activos:', error);
    }
}

function renderizarPedidosActivos(pedidos) {
    const contenedor = document.getElementById('lista-pedidos-activos');

    if (!pedidos || pedidos.length === 0) {
        contenedor.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-inbox fs-3"></i>
                <p class="mt-2 mb-0">No hay pedidos activos en este momento</p>
            </div>`;
        return;
    }

    contenedor.innerHTML = pedidos.map(p => {
        const badgeTipo = p.tipo === 'delivery'
            ? '<span class="badge bg-warning text-dark">🛵 Delivery</span>'
            : '<span class="badge bg-info text-dark">🏪 Local</span>';

        const badgeEstado = p.estado === 'pendiente'
            ? '<span class="badge bg-secondary">Pendiente</span>'
            : '<span class="badge bg-primary">En Proceso</span>';

        const badgePago = p.forma_pago === 'transferencia'
            ? `<span class="badge bg-light text-dark border">📲 Transf. #${p.numero_comprobante || '—'}</span>`
            : p.forma_pago === 'mixto'
            ? `<span class="badge bg-light text-dark border">🔀 Mixto #${p.numero_comprobante || '—'}</span>`
            : '';

        const botonesEstado = `<button class="btn btn-sm btn-success" onclick="cambiarEstado(${p.id}, 'entregado')">
                   <i class="bi bi-check-lg"></i> Entregado
               </button>`;

        const botonTicket = `
            <button class="btn btn-sm btn-outline-dark" onclick="imprimirTicketPedido(${p.id})">
                <i class="bi bi-printer"></i> Ticket
            </button>`;

        const botonEliminar = `
            <button class="btn btn-sm btn-outline-danger" onclick="eliminarPedido(${p.id})">
                <i class="bi bi-trash"></i> Eliminar
            </button>`;

        return `
            <div class="list-group-item py-2">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                    <div>
                        <strong>${p.cliente_nombre || 'Cliente'}</strong>
                        <span class="ms-1">${badgeTipo}</span>
                        <span class="ms-1">${badgeEstado}</span>
                        ${badgePago ? `<span class="ms-1">${badgePago}</span>` : ''}
                        <div class="text-muted small mt-1">
                            <i class="bi bi-clock"></i> ${p.fecha}
                            &nbsp;·&nbsp;
                            <strong class="text-dark">$${parseFloat(p.total).toFixed(2)}</strong>
                        </div>
                    </div>
                    <div class="d-flex gap-1">
                        ${botonTicket}
                        ${botonEliminar}
                        ${botonesEstado}
                    </div>
                </div>
            </div>`;
    }).join('');
}

function imprimirTicketPedido(pedidoId) {
    window.open(`/pedidos/${pedidoId}/ticket`, '_blank');
}

async function eliminarPedido(pedidoId) {
    const confirmar = confirm('Este pedido se eliminará de la cola. ¿Deseas continuar?');
    if (!confirmar) return;

    try {
        const respuesta = await fetch(`/pedidos/${pedidoId}`, {
            method: 'DELETE'
        });

        const datos = await respuesta.json();

        if (respuesta.ok) {
            mostrarToast('Pedido eliminado correctamente', 'success');
            cargarPedidosActivos();
        } else {
            mostrarToast(datos.error || 'No se pudo eliminar el pedido', 'danger');
        }
    } catch (error) {
        mostrarToast('Error de conexión al eliminar pedido', 'danger');
    }
}

async function cambiarEstado(pedidoId, nuevoEstado) {
    if (nuevoEstado === 'entregado') {
        const confirmar = confirm('¿Confirmas que este pedido fue entregado al cliente?');
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
        mostrarToast('Error de conexión', 'danger');
    }
}
