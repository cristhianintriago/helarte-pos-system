document.addEventListener('DOMContentLoaded', () => {
    cargarDatos();
    setInterval(cargarDatos, 30000);
});

async function cargarDatos() {
    await Promise.all([
        cargarResumen(),
        cargarPedidosActivos()
    ]);
}

async function cargarResumen() {
    try {
        const respuesta = await fetch('/ventas/');
        const datos = await respuesta.json();

        document.getElementById('total-pedidos').textContent = datos.total_pedidos;
        document.getElementById('total-vendido').textContent = `$${parseFloat(datos.total_vendido).toFixed(2)}`;
        document.getElementById('total-delivery').textContent = datos.total_delivery;
        document.getElementById('total-local').textContent = datos.total_local;

        renderizarVentasCompletadas(datos.ventas);
    } catch (error) {
        console.error('Error al cargar resumen:', error);
    }
}

async function cargarPedidosActivos() {
    try {
        const respuesta = await fetch('/pedidos/?estado=activo');
        const datos = await respuesta.json();
        renderizarPedidosActivos(datos.pedidos || datos);
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
                <p class="mt-2 mb-0">No hay pedidos activos</p>
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

        const botonesEstado = p.estado === 'pendiente'
            ? `<button class="btn btn-sm btn-primary me-1" onclick="cambiarEstado(${p.id}, 'en_proceso')">
                   <i class="bi bi-play-fill"></i> Procesar
               </button>
               <button class="btn btn-sm btn-success" onclick="cambiarEstado(${p.id}, 'entregado')">
                   <i class="bi bi-check-lg"></i> Entregado
               </button>`
            : `<button class="btn btn-sm btn-success" onclick="cambiarEstado(${p.id}, 'entregado')">
                   <i class="bi bi-check-lg"></i> Marcar Entregado
               </button>`;

        return `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                    <div>
                        <strong>${p.cliente_nombre || p.cliente || 'Cliente'}</strong>
                        <span class="ms-2">${badgeTipo}</span>
                        <span class="ms-1">${badgeEstado}</span>
                        <div class="text-muted small mt-1">
                            <i class="bi bi-clock"></i> ${p.hora || p.fecha || ''}
                            &nbsp;·&nbsp;
                            <strong class="text-dark">$${parseFloat(p.total).toFixed(2)}</strong>
                        </div>
                    </div>
                    <div class="d-flex gap-1">
                        ${botonesEstado}
                    </div>
                </div>
            </div>`;
    }).join('');
}

function renderizarVentasCompletadas(ventas) {
    const contenedor = document.getElementById('lista-ventas');

    if (!ventas || ventas.length === 0) {
        contenedor.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-receipt fs-3"></i>
                <p class="mt-2 mb-0">No hay ventas completadas hoy</p>
            </div>`;
        return;
    }

    contenedor.innerHTML = ventas.map(v => {
        const badgeTipo = v.tipo === 'delivery'
            ? '<span class="badge bg-warning text-dark">🛵 Delivery</span>'
            : '<span class="badge bg-info text-dark">🏪 Local</span>';

        return `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                    <strong>${v.cliente}</strong>
                    <span class="ms-2">${badgeTipo}</span>
                    <div class="text-muted small">
                        <i class="bi bi-clock"></i> ${v.fecha}
                    </div>
                </div>
                <span class="fw-bold text-success fs-6">$${parseFloat(v.total).toFixed(2)}</span>
            </div>`;
    }).join('');
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
            mostrarToast(`Pedido actualizado a: ${nuevoEstado} ✅`, 'success');
            cargarDatos();
        } else {
            mostrarToast(datos.error || 'Error al actualizar el estado', 'danger');
        }
    } catch (error) {
        mostrarToast('Error de conexión', 'danger');
    }
}

function mostrarToast(mensaje, tipo = 'success') {
    const toastEl = document.getElementById('toast-global');
    if (toastEl) {
        toastEl.querySelector('.toast-body').textContent = mensaje;
        toastEl.className = `toast align-items-center text-white bg-${tipo} border-0`;
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
        return;
    }

    const div = document.createElement('div');
    div.innerHTML = `
        <div class="position-fixed bottom-0 end-0 p-3" style="z-index: 9999">
            <div class="toast show align-items-center text-white bg-${tipo} border-0">
                <div class="d-flex">
                    <div class="toast-body">${mensaje}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto"
                            data-bs-dismiss="toast"></button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3500);
}
