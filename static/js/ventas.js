document.addEventListener('DOMContentLoaded', () => {
    cargarResumen();
    // Refrescamos el resumen de ventas cada 30 segundos
    setInterval(cargarResumen, 30000);
});

// Refresca los datos automáticamente cada vez que el usuario vuelve a esta pestaña
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        cargarResumen();
    }
});

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
        console.error('Error al cargar resumen de ventas:', error);
    }
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
