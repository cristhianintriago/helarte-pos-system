document.addEventListener('DOMContentLoaded', () => {
    cargarCajas();
    cargarVentas();
});


// ==========================================
// SECCIÓN: REGISTROS DE CAJA
// ==========================================

async function cargarCajas() {
    const respuesta = await fetch('/caja/historial');
    const cajas = await respuesta.json();
    const tbody = document.getElementById('tabla-cajas');

    if (!cajas || cajas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay registros de caja</td></tr>';
        return;
    }

    tbody.innerHTML = cajas.map(c => `
        <tr>
            <td><input type="checkbox" class="check-caja" value="${c.id}"></td>
            <td class="fw-bold">${c.fecha}</td>
            <td>$${c.monto_inicial.toFixed(2)}</td>
            <td class="text-success fw-bold">+$${c.total_ingresos.toFixed(2)}</td>
            <td class="text-danger fw-bold">-$${c.total_egresos.toFixed(2)}</td>
            <td class="text-primary fw-bold">$${c.monto_final.toFixed(2)}</td>
        </tr>`
    ).join('');
}

function toggleTodosCajas(checkbox) {
    document.querySelectorAll('.check-caja').forEach(c => c.checked = checkbox.checked);
}

function seleccionarTodoCajas() {
    const checkAll = document.getElementById('check-all-cajas');
    checkAll.checked = !checkAll.checked;
    toggleTodosCajas(checkAll);
}

async function eliminarCajasSeleccionadas() {
    const seleccionados = [...document.querySelectorAll('.check-caja:checked')].map(c => parseInt(c.value));

    if (seleccionados.length === 0) {
        mostrarToast('Selecciona al menos un registro', 'warning');
        return;
    }

    const ok = confirm(
        `⚠️ ADVERTENCIA\n\nSe eliminarán ${seleccionados.length} registro(s) de caja junto con todos sus egresos y ventas asociadas.\n\n¿Confirmas? Esta acción es IRREVERSIBLE.`
    );
    if (!ok) return;

    const respuesta = await fetch('/caja/registros', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: seleccionados })
    });
    const datos = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(datos.mensaje, 'success');
        document.getElementById('check-all-cajas').checked = false;
        cargarCajas();
        cargarVentas(); // Refresca ventas porque pueden haberse eliminado en cascada
    } else {
        mostrarToast(datos.error, 'danger');
    }
}


// ==========================================
// SECCIÓN: REGISTROS DE VENTAS
// ==========================================

async function cargarVentas() {
    const respuesta = await fetch('/reportes/ventas/lista');
    const ventas = await respuesta.json();
    const tbody = document.getElementById('tabla-ventas');

    if (!ventas || ventas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay registros de ventas</td></tr>';
        return;
    }

    const badgePago = (forma) => {
        if (forma === 'transferencia') return '<span class="badge bg-info text-dark">📲 Transf.</span>';
        if (forma === 'mixto') return '<span class="badge bg-secondary">🔀 Mixto</span>';
        return '<span class="badge bg-success">💵 Efectivo</span>';
    };

    const badgeTipo = (tipo) => tipo === 'delivery'
        ? '<span class="badge bg-warning text-dark">🛵</span>'
        : '<span class="badge bg-light text-dark border">🏪</span>';

    tbody.innerHTML = ventas.map(v => `
        <tr>
            <td><input type="checkbox" class="check-venta" value="${v.id}"></td>
            <td class="small text-muted">${v.fecha}</td>
            <td class="fw-bold">${v.cliente}</td>
            <td>${badgeTipo(v.tipo)}</td>
            <td>${badgePago(v.forma_pago)}</td>
            <td class="text-success fw-bold">$${parseFloat(v.total).toFixed(2)}</td>
        </tr>`
    ).join('');
}

function toggleTodosVentas(checkbox) {
    document.querySelectorAll('.check-venta').forEach(c => c.checked = checkbox.checked);
}

function seleccionarTodoVentas() {
    const checkAll = document.getElementById('check-all-ventas');
    checkAll.checked = !checkAll.checked;
    toggleTodosVentas(checkAll);
}

async function eliminarVentasSeleccionadas() {
    const seleccionados = [...document.querySelectorAll('.check-venta:checked')].map(c => parseInt(c.value));

    if (seleccionados.length === 0) {
        mostrarToast('Selecciona al menos una venta', 'warning');
        return;
    }

    const ok = confirm(
        `⚠️ ADVERTENCIA\n\nSe eliminarán ${seleccionados.length} venta(s) del historial. Esto afectará los reportes.\n\n¿Confirmas? Esta acción es IRREVERSIBLE.`
    );
    if (!ok) return;

    const respuesta = await fetch('/reportes/ventas/eliminar', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: seleccionados })
    });
    const datos = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(datos.mensaje, 'success');
        document.getElementById('check-all-ventas').checked = false;
        cargarVentas();
    } else {
        mostrarToast(datos.error, 'danger');
    }
}


// ==========================================
// Toast helper (compartido con el resto de la app)
// ==========================================
function mostrarToast(mensaje, tipo = 'success') {
    const toastEl = document.getElementById('toast-global');
    if (toastEl) {
        toastEl.querySelector('.toast-body').textContent = mensaje;
        toastEl.className = `toast align-items-center text-white bg-${tipo} border-0`;
        new bootstrap.Toast(toastEl).show();
        return;
    }
    const div = document.createElement('div');
    div.innerHTML = `
        <div class="position-fixed bottom-0 end-0 p-3" style="z-index: 9999">
            <div class="toast show align-items-center text-white bg-${tipo} border-0">
                <div class="d-flex">
                    <div class="toast-body">${mensaje}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3500);
}
