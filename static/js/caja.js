document.addEventListener('DOMContentLoaded', verificarCaja);


async function verificarCaja() {
    const respuesta = await fetch('/caja/estado');
    const datos = await respuesta.json();

    const divCerrada = document.getElementById('caja-cerrada');
    const divAbierta = document.getElementById('caja-abierta');

    if (datos.estado === 'abierta') {
        divCerrada.style.display = 'none';
        divAbierta.style.display = 'block';
        mostrarCajaAbierta(datos);
        await cargarEgresos();

        // Mostramos la sección admin solo si el usuario tiene permiso
        const seccionAdmin = document.getElementById('seccion-admin');
        if (seccionAdmin) seccionAdmin.style.display = datos.is_admin ? 'block' : 'none';
    } else {
        divCerrada.style.display = 'flex';
        divAbierta.style.display = 'none';
    }
}


function mostrarCajaAbierta(datos) {
    document.getElementById('resumen-inicial').textContent   = `$${datos.monto_inicial.toFixed(2)}`;
    document.getElementById('resumen-ingresos').textContent  = `$${datos.total_ingresos.toFixed(2)}`;
    document.getElementById('resumen-egresos').textContent   = `$${datos.total_egresos.toFixed(2)}`;
    document.getElementById('resumen-balance').textContent   = `$${datos.balance_actual.toFixed(2)}`;
    // ── NUEVO: desglose por forma de pago
    document.getElementById('resumen-efectivo').textContent      = `$${(datos.total_efectivo || 0).toFixed(2)}`;
    document.getElementById('resumen-transferencia').textContent = `$${(datos.total_transferencia || 0).toFixed(2)}`;
    // Ocultado por Blind Close (no se le muestra al cajero cuánto efectivo debería haber)
}


async function abrirCaja() {
    const monto = parseFloat(document.getElementById('monto-inicial').value);
    if (!monto || monto < 0) {
        mostrarToast('Ingresa un monto inicial válido', 'warning');
        return;
    }

    const respuesta = await fetch('/caja/abrir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monto_inicial: monto })
    });

    const datos = await respuesta.json();

    if (respuesta.ok) {
        location.reload();
    } else {
        mostrarToast(datos.error, 'danger');
    }
}


async function registrarEgreso() {
    const descripcion = document.getElementById('egreso-descripcion').value.trim();
    const monto = parseFloat(document.getElementById('egreso-monto').value);

    if (!descripcion || !monto || monto <= 0) {
        mostrarToast('Completa la descripción y el monto', 'warning');
        return;
    }

    const respuesta = await fetch('/caja/egreso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ descripcion, monto })
    });

    const datos = await respuesta.json();

    if (respuesta.ok) {
        document.getElementById('egreso-descripcion').value = '';
        document.getElementById('egreso-monto').value = '';
        mostrarToast('Egreso registrado correctamente', 'success');
        await verificarCaja();
    } else {
        mostrarToast(datos.error || 'Error al registrar egreso', 'danger');
    }
}


async function cargarEgresos() {
    const respuesta = await fetch(`/caja/egresos?t=${Date.now()}`);
    const egresos = await respuesta.json();

    const contenedor = document.getElementById('lista-egresos');
    contenedor.innerHTML = '';

    if (!egresos || egresos.length === 0) {
        contenedor.innerHTML = `
            <p class="text-muted text-center py-3 mb-0">
                Sin egresos registrados
            </p>`;
        return;
    }

    egresos.forEach(e => {
        const div = document.createElement('div');
        div.className = 'list-group-item d-flex justify-content-between align-items-center';
        div.innerHTML = `
            <span>
                <i class="bi bi-arrow-down-circle text-danger"></i>
                ${e.descripcion}
            </span>
            <span class="fw-bold text-danger">-$${parseFloat(e.monto).toFixed(2)}</span>`;
        contenedor.appendChild(div);
    });
}


let blindCloseModal = null;

document.addEventListener('DOMContentLoaded', () => {
    const blindModalEl = document.getElementById('modal-blind-close');
    if (blindModalEl) {
        blindCloseModal = new bootstrap.Modal(blindModalEl);
    }
});

function iniciarCierreCaja() {
    document.getElementById('monto-declarado').value = '';
    if (blindCloseModal) blindCloseModal.show();
}


async function cerrarCaja() {
    const montoDeclarado = parseFloat(document.getElementById('monto-declarado').value);
    
    if (isNaN(montoDeclarado) || montoDeclarado < 0) {
        mostrarToast('Debes ingresar la cantidad de dinero exacta que tienes contada', 'warning');
        return;
    }

    if (!confirm(`¿Confirmas disponer exactamente de $${montoDeclarado.toFixed(2)} físicos en la caja? Esta acción auditará y cerrará el turno.`)) return;

    const btnClose = document.querySelector('#modal-blind-close .btn-danger');
    const originalText = btnClose.innerHTML;
    btnClose.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Auditando...';
    btnClose.disabled = true;

    try {
        const respuesta = await fetch('/caja/cerrar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monto_declarado: montoDeclarado })
        });

        const datos = await respuesta.json();

        if (respuesta.ok) {
            if (blindCloseModal) blindCloseModal.hide();
            
            let descuadreHTML = '';
            if (datos.descuadre === 0) {
                descuadreHTML = `<strong class="text-success"><i class="bi bi-check-circle-fill"></i> Cuadre Perfecto ($0.00)</strong>`;
            } else if (datos.descuadre > 0) {
                descuadreHTML = `<strong class="text-primary"><i class="bi bi-arrow-up-circle-fill"></i> Sobrante (+$${datos.descuadre.toFixed(2)})</strong>`;
            } else {
                descuadreHTML = `<strong class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Faltante (-$${Math.abs(datos.descuadre).toFixed(2)})</strong>`;
            }

            const contenido = document.getElementById('contenido-cuadre');
            contenido.innerHTML = `
                <ul class="list-group list-group-flush">
                    <li class="list-group-item d-flex justify-content-between">
                        <span>Monto inicial</span>
                        <strong>$${datos.monto_inicial.toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>Total ingresos</span>
                        <strong class="text-success">+$${datos.total_ingresos.toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between ps-4 border-0 pb-0">
                        <span class="text-muted small">💵 Efectivo</span>
                        <strong class="text-success small">$${(datos.total_efectivo || 0).toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between ps-4 pt-1">
                        <span class="text-muted small">📲 Transferencia</span>
                        <strong class="text-info small">$${(datos.total_transferencia || 0).toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between">
                        <span>Total egresos</span>
                        <strong class="text-danger">-$${datos.total_egresos.toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between fs-6 bg-light text-muted">
                        <span>Sistema (Efectivo Esperado)</span>
                        <strong>$${(datos.efectivo_esperado || 0).toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between fs-6" style="background-color: #fff3cd;">
                        <span class="fw-bold">Efectivo Declarado (Tú)</span>
                        <strong class="fs-5">$${(datos.monto_declarado || 0).toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex mt-2 justify-content-between fs-5 shadow-sm rounded border-0 bg-white">
                        <span class="fw-bold text-dark">Diferencia Auditada</span>
                        ${descuadreHTML}
                    </li>
                </ul>`;
            
            // Añadir listener para cuando se cierre el modal de cuadre se refresque
            const modalCuadre = document.getElementById('modal-cuadre');
            if (modalCuadre) {
                modalCuadre.addEventListener('hidden.bs.modal', function () {
                    location.reload();
                });
            }

            new bootstrap.Modal(document.getElementById('modal-cuadre')).show();
        } else {
            mostrarToast(datos.error, 'danger');
        }
    } finally {
        btnClose.innerHTML = originalText;
        btnClose.disabled = false;
    }
}


async function confirmarReiniciarCaja() {
    const ok = confirm(
        '⚠️ ADVERTENCIA\n\n' +
        'Esta acción reiniciará TODOS los contadores de la caja a cero (ingresos, egresos, efectivo, transferencia), ' +
        'manteniendo el monto inicial y reabriendo la caja si estaba cerrada.\n\n' +
        '¿Estás seguro/a de que deseas continuar?'
    );
    if (!ok) return;

    const respuesta = await fetch('/caja/reiniciar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    });
    const datos = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(datos.mensaje, 'success');
        location.reload();
    } else {
        mostrarToast(datos.error || 'Error al reiniciar la caja', 'danger');
    }
}

document.getElementById('modal-historial')
    ?.addEventListener('show.bs.modal', async () => {
    const respuesta = await fetch('/caja/historial');
    const cajas = await respuesta.json();

    const contenedor = document.getElementById('tabla-historial-caja');

    if (cajas.length === 0) {
        contenedor.innerHTML = `
            <p class="text-muted text-center py-4 mb-0">
                No hay cajas cerradas en los últimos 30 días
            </p>`;
        return;
    }

    let filas = cajas.map(c => {
        return `
            <tr>
                <td class="fw-bold">${c.fecha}</td>
                <td>$${c.monto_inicial.toFixed(2)}</td>
                <td class="text-success fw-bold">+$${c.total_ingresos.toFixed(2)}</td>
                <td class="text-danger fw-bold">-$${c.total_egresos.toFixed(2)}</td>
                <td class="text-primary fw-bold">$${c.monto_final.toFixed(2)}</td>
            </tr>`;
    }).join('');

    contenedor.innerHTML = `
        <table class="table table-hover mb-0">
            <thead class="table-dark">
                <tr>
                    <th>Fecha</th>
                    <th>Inicial</th>
                    <th>Ingresos</th>
                    <th>Egresos</th>
                    <th>Final</th>
                </tr>
            </thead>
            <tbody>${filas}</tbody>
        </table>`;
});
