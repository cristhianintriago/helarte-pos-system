let ultimaSincronizacion = null;
let htmlAnterior = "";

document.addEventListener('DOMContentLoaded', () => {
    actualizarReloj();
    setInterval(actualizarReloj, 60000);

    cargarComandas();
    setInterval(cargarComandas, 3000);
});

function actualizarReloj() {
    const reloj = document.getElementById('reloj-cocina');
    if (reloj) {
        const ahora = new Date();
        reloj.textContent = ahora.getHours().toString().padStart(2, '0') + ':' + ahora.getMinutes().toString().padStart(2, '0');
    }
}

async function cargarComandas() {
    try {
        const respuesta = await fetch('/pedidos/');
        if (!respuesta.ok) throw new Error('Error al conectar');
        
        const pedidos = await respuesta.json();
        renderizarComandas(pedidos);
        
        const badge = document.getElementById('estado-conexion');
        if (badge && badge.textContent !== 'En Línea') {
            badge.textContent = 'En Línea';
            badge.className = 'badge bg-success fs-6';
        }
    } catch (err) {
        const badge = document.getElementById('estado-conexion');
        if (badge) {
            badge.textContent = 'Desconectado';
            badge.className = 'badge bg-danger fs-6';
        }
    }
}

function renderizarComandas(pedidos) {
    const contenedor = document.getElementById('lista-comandas');
    if (!contenedor) return;

    // La cocina solo debe ver los pedidos que les falta preparar
    const pedidosCocina = pedidos.filter(p => ['pendiente', 'en_proceso'].includes(p.estado));

    if (pedidosCocina.length === 0) {
        const htmlVacio = `
            <div class="col-12 text-center text-muted" style="margin-top: 15vh;">
                <i class="bi bi-check-circle" style="font-size: 5rem; color: var(--borde);"></i>
                <h4 class="mt-3">¡Todo limpio!</h4>
                <p>No hay pedidos pendientes por preparar.</p>
            </div>
        `;
        if (htmlAnterior !== htmlVacio) {
            contenedor.innerHTML = htmlVacio;
            htmlAnterior = htmlVacio;
        }
        return;
    }

    pedidosCocina.sort((a,b) => {
        if (a.estado === b.estado) return a.id - b.id;
        if (a.estado === 'en_proceso') return -1;
        return 1;
    });

    const html = pedidosCocina.map(p => {
        const detalles = p.detalles.map(d => `
            <li class="list-group-item px-2 py-1 d-flex justify-content-between border-0 bg-transparent">
                <span class="fw-bold fs-5 text-dark">${d.cantidad}x ${d.producto}</span>
            </li>
            ${d.sabor ? `<li class="list-group-item px-2 py-0 border-0 text-muted ms-3 bg-transparent" style="font-size: 1.1rem;"><i class="bi bi-arrow-return-right"></i> ${d.sabor}</li>` : ''}
        `).join('');

        const isPendiente = p.estado === 'pendiente';
        const colorHeader = isPendiente ? 'bg-dark text-white' : 'bg-primary text-white';
        const txtBoton = isPendiente ? 'Empezar a Preparar' : 'Marcar Listo';
        const iconoBoton = isPendiente ? 'bi-hand-index-thumb' : 'bi-check-all';
        const colorBoton = isPendiente ? 'btn-outline-primary' : 'btn-success';
        const nuevoEstado = isPendiente ? 'en_proceso' : 'preparado';

        return `
            <div class="col">
                <div class="card h-100 shadow-sm border-0" style="border-radius: 16px; overflow: hidden; background: #fff;">
                    <div class="card-header ${colorHeader} d-flex justify-content-between align-items-center py-3 border-0">
                        <h3 class="mb-0 fw-bold">#${p.numero_pedido || p.id}</h3>
                        <span class="badge bg-light text-dark fs-6">${p.tipo.toUpperCase()}</span>
                    </div>
                    <div class="card-body p-2" style="background: #f9f9f9;">
                        <div class="text-muted small mb-2 ps-2 fs-6"><i class="bi bi-person"></i> ${p.cliente_nombre || 'Cliente'}</div>
                        <ul class="list-group list-group-flush mb-3">
                            ${detalles}
                        </ul>
                    </div>
                    <div class="card-footer bg-white border-0 pt-0 pb-3 px-3">
                        <button class="btn ${colorBoton} w-100 fs-5 py-3 fw-bold" onclick="cambiarEstadoKDS(${p.id}, '${nuevoEstado}')" style="border-radius: 12px;">
                            <i class="bi ${iconoBoton}"></i> ${txtBoton}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    if (htmlAnterior !== html) {
        contenedor.innerHTML = html;
        htmlAnterior = html;
    }
}

async function cambiarEstadoKDS(pedidoId, nuevoEstado) {
    if (nuevoEstado === 'preparado') {
        const confirmar = confirm('¿Confirmas que este pedido ya está preparado?');
        if (!confirmar) return;
    }
    
    if (navigator.vibrate) navigator.vibrate(20);
    
    try {
        await fetch(`/pedidos/${pedidoId}/estado`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        cargarComandas();
    } catch (err) {
        console.error('No se pudo actualizar estado', err);
    }
}
