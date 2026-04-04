/**
 * caja.js
 * -------
 * Logica del modulo de gestion de caja del turno actual.
 *
 * Responsabilidades de este modulo:
 * 1. Verificar el estado de la caja al cargar la pagina (abierta/cerrada).
 * 2. Mostrar el resumen de saldos si la caja esta abierta.
 * 3. Gestionar el registro de egresos y mostrar su historial.
 * 4. Ejecutar el flujo de Cierre Ciego (Blind Close).
 * 5. Mostrar el historial de cajas de los ultimos 30 dias en un modal.
 *
 * El Cierre Ciego (Blind Close):
 * El cajero declara el dinero que tiene fisicamente en la gaveta.
 * El sistema compara ese monto con lo que DEBERIA haber y calcula el descuadre.
 * El nombre "ciego" (blind) se debe a que el cajero no ve la cifra esperada
 * antes de declarar la suya, lo que evita que "ajuste" su cuenta a la esperada.
 */

// ==========================================
// INICIALIZACION
// ==========================================

// Al terminar de cargar el DOM, verificamos el estado de la caja.
document.addEventListener('DOMContentLoaded', verificarCaja);

// Instancia del modal de Cierre Ciego. Se guarda fuera de la funcion para
// poder abrir y cerrar el modal desde diferentes funciones sin reinstanciar.
let blindCloseModal = null;

document.addEventListener('DOMContentLoaded', () => {
    const blindModalEl = document.getElementById('modal-blind-close');
    if (blindModalEl) {
        // Instanciamos el modal de Bootstrap una sola vez y lo reutilizamos.
        blindCloseModal = new bootstrap.Modal(blindModalEl);
    }
});


// ==========================================
// ESTADO DE LA CAJA
// ==========================================

/**
 * Consulta el estado actual de la caja al servidor y actualiza la interfaz.
 * Si hay una caja abierta: muestra la seccion de operacion y carga los saldos.
 * Si no hay caja abierta: muestra la seccion de apertura.
 */
async function verificarCaja() {
    const respuesta = await fetch('/caja/estado');
    const datos     = await respuesta.json();

    const divCerrada = document.getElementById('caja-cerrada');
    const divAbierta = document.getElementById('caja-abierta');

    if (datos.estado === 'abierta') {
        divCerrada.style.display = 'none';
        divAbierta.style.display = 'block';
        // Llenamos los campos del resumen con los saldos actuales.
        mostrarCajaAbierta(datos);
        // Cargamos el historial visual de egresos del turno.
        await cargarEgresos();

        // La seccion de admin (boton de reinicio) solo se muestra si el usuario tiene permiso.
        // El servidor nos indica este permiso con el campo 'is_admin' en la respuesta.
        const seccionAdmin = document.getElementById('seccion-admin');
        if (seccionAdmin) seccionAdmin.style.display = datos.is_admin ? 'block' : 'none';
    } else {
        divCerrada.style.display = 'flex';
        divAbierta.style.display = 'none';
    }
}

/**
 * Actualiza los elementos del resumen de caja con los datos recibidos del servidor.
 * El campo 'efectivo_en_caja' NO se muestra en la interfaz por diseno del Cierre Ciego:
 * no queremos que el cajero sepa cuanto efectivo esperamos antes de que declare el suyo.
 *
 * @param {Object} datos - Objeto con los saldos de la caja activa.
 */
function mostrarCajaAbierta(datos) {
    document.getElementById('resumen-inicial').textContent       = `$${datos.monto_inicial.toFixed(2)}`;
    document.getElementById('resumen-ingresos').textContent      = `$${datos.total_ingresos.toFixed(2)}`;
    document.getElementById('resumen-egresos').textContent       = `$${datos.total_egresos.toFixed(2)}`;
    document.getElementById('resumen-balance').textContent       = `$${datos.balance_actual.toFixed(2)}`;
    // Desglose de ingresos por metodo de pago.
    document.getElementById('resumen-efectivo').textContent      = `$${(datos.total_efectivo || 0).toFixed(2)}`;
    document.getElementById('resumen-transferencia').textContent = `$${(datos.total_transferencia || 0).toFixed(2)}`;
}


// ==========================================
// APERTURA DE CAJA
// ==========================================

/**
 * Envia la solicitud para abrir una nueva caja con el monto inicial declarado.
 * Si la solicitud es exitosa, recarga la pagina para mostrar la vista de caja abierta.
 */
async function abrirCaja() {
    const monto = parseFloat(document.getElementById('monto-inicial').value);
    if (!monto || monto < 0) {
        mostrarToast('Ingresa un monto inicial valido', 'warning');
        return;
    }

    const respuesta = await fetch('/caja/abrir', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ monto_inicial: monto })
    });

    const datos = await respuesta.json();

    if (respuesta.ok) {
        // location.reload() recarga la pagina completa para reiniciar el estado de la UI.
        location.reload();
    } else {
        mostrarToast(datos.error, 'danger');
    }
}


// ==========================================
// EGRESOS
// ==========================================

/**
 * Registra un gasto del turno actual y actualiza la vista de la caja.
 * Despues de registrar, llama a verificarCaja() para recargar los saldos actualizados.
 */
async function registrarEgreso() {
    const descripcion = document.getElementById('egreso-descripcion').value.trim();
    const monto       = parseFloat(document.getElementById('egreso-monto').value);

    if (!descripcion || !monto || monto <= 0) {
        mostrarToast('Completa la descripcion y el monto', 'warning');
        return;
    }

    const respuesta = await fetch('/caja/egreso', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ descripcion, monto })
    });

    const datos = await respuesta.json();

    if (respuesta.ok) {
        // Limpiamos los campos del formulario tras el exito.
        document.getElementById('egreso-descripcion').value = '';
        document.getElementById('egreso-monto').value       = '';
        mostrarToast('Egreso registrado correctamente', 'success');
        // Recargamos el estado de la caja para que el total de egresos se actualice.
        await verificarCaja();
    } else {
        mostrarToast(datos.error || 'Error al registrar egreso', 'danger');
    }
}

/**
 * Carga y renderiza la lista de egresos del turno activo.
 * Se agrega un parametro de tiempo '?t=...' a la URL para evitar que el navegador
 * use una version cacheada de la respuesta (cache-busting).
 */
async function cargarEgresos() {
    const respuesta = await fetch(`/caja/egresos?t=${Date.now()}`);
    const egresos   = await respuesta.json();

    const contenedor = document.getElementById('lista-egresos');
    contenedor.innerHTML = '';

    if (!egresos || egresos.length === 0) {
        contenedor.innerHTML = `
            <p class="text-muted text-center py-3 mb-0">
                Sin egresos registrados
            </p>`;
        return;
    }

    // Construimos un elemento HTML por cada egreso y lo agregamos al contenedor.
    for (let i = 0; i < egresos.length; i++) {
        let e = egresos[i];
        let div = document.createElement('div');
        div.className = 'list-group-item d-flex justify-content-between align-items-center';
        div.innerHTML = `
            <span>
                <i class="bi bi-arrow-down-circle text-danger"></i>
                ${e.descripcion}
            </span>
            <span class="fw-bold text-danger">-$${parseFloat(e.monto).toFixed(2)}</span>`;
        contenedor.appendChild(div);
    }
}


// ==========================================
// CIERRE CIEGO (BLIND CLOSE)
// ==========================================

/**
 * Abre el modal del Cierre Ciego limpiando el campo de monto declarado.
 * Este modal NO muestra ningun monto esperado al cajero, garantizando la imparcialidad.
 */
function iniciarCierreCaja() {
    document.getElementById('monto-declarado').value = '';
    if (blindCloseModal) blindCloseModal.show();
}

/**
 * Ejecuta el Cierre Ciego:
 * 1. Valida que el monto declarado sea numerico y no negativo.
 * 2. Pide confirmacion explicita al usuario.
 * 3. Envia el monto al servidor, que calcula el descuadre.
 * 4. Muestra el resultado del cuadre en un modal de resumen.
 *
 * El boton de confirmacion se desactiva durante el proceso para evitar doble envio.
 * finally {} garantiza que el boton se reactive siempre, incluso si hay un error.
 */
async function cerrarCaja() {
    const montoDeclarado = parseFloat(document.getElementById('monto-declarado').value);

    if (isNaN(montoDeclarado) || montoDeclarado < 0) {
        mostrarToast('Debes ingresar la cantidad de dinero exacta que tienes contada', 'warning');
        return;
    }

    if (!confirm(`Confirmas disponer exactamente de $${montoDeclarado.toFixed(2)} fisicos en la caja? Esta accion auditara y cerrara el turno.`)) return;

    // Desactivamos el boton para evitar multiples clics mientras se procesa.
    const btnClose    = document.querySelector('#modal-blind-close .btn-danger');
    const originalText = btnClose.innerHTML;
    btnClose.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Auditando...';
    btnClose.disabled  = true;

    try {
        const respuesta = await fetch('/caja/cerrar', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ monto_declarado: montoDeclarado })
        });

        const datos = await respuesta.json();

        if (respuesta.ok) {
            if (blindCloseModal) blindCloseModal.hide();

            // Construimos el HTML del resultado del descuadre segun si hay sobrante, faltante o cuadre perfecto.
            let descuadreHTML = '';
            if (datos.descuadre === 0) {
                descuadreHTML = `<strong class="text-success"><i class="bi bi-check-circle-fill"></i> Cuadre Perfecto ($0.00)</strong>`;
            } else if (datos.descuadre > 0) {
                descuadreHTML = `<strong class="text-primary"><i class="bi bi-arrow-up-circle-fill"></i> Sobrante (+$${datos.descuadre.toFixed(2)})</strong>`;
            } else {
                descuadreHTML = `<strong class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Faltante (-$${Math.abs(datos.descuadre).toFixed(2)})</strong>`;
            }

            // Inyectamos el resumen de cierre en el modal de cuadre.
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
                        <span class="text-muted small">Efectivo</span>
                        <strong class="text-success small">$${(datos.total_efectivo || 0).toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex justify-content-between ps-4 pt-1">
                        <span class="text-muted small">Transferencia</span>
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
                        <span class="fw-bold">Efectivo Declarado (Tu)</span>
                        <strong class="fs-5">$${(datos.monto_declarado || 0).toFixed(2)}</strong>
                    </li>
                    <li class="list-group-item d-flex mt-2 justify-content-between fs-5 shadow-sm rounded border-0 bg-white">
                        <span class="fw-bold text-dark">Diferencia Auditada</span>
                        ${descuadreHTML}
                    </li>
                </ul>`;

            // Al cerrar el modal de cuadre, recargamos la pagina para mostrar la vista de caja cerrada.
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
        // Siempre reactivamos el boton, incluso si hubo un error.
        btnClose.innerHTML = originalText;
        btnClose.disabled  = false;
    }
}


// ==========================================
// REINICIO DE CAJA (ADMIN)
// ==========================================

/**
 * Reinicia todos los contadores de la caja a cero y la reabre si estaba cerrada.
 * Es una operacion destructiva exclusiva para administradores, por lo que
 * se muestra un mensaje de advertencia explicito antes de ejecutar.
 */
async function confirmarReiniciarCaja() {
    const ok = confirm(
        'ADVERTENCIA\n\n' +
        'Esta accion reiniciara TODOS los contadores de la caja a cero (ingresos, egresos, efectivo, transferencia), ' +
        'manteniendo el monto inicial y reabriendo la caja si estaba cerrada.\n\n' +
        'Estas seguro/a de que deseas continuar?'
    );
    if (!ok) return;

    const respuesta = await fetch('/caja/reiniciar', {
        method:  'POST',
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


// ==========================================
// HISTORIAL DE CAJAS (MODAL)
// ==========================================

/**
 * Carga y renderiza el historial de cajas cerradas de los ultimos 30 dias
 * cuando el usuario abre el modal de historial.
 *
 * El operador '?.' (optional chaining) previene un error si el elemento no existe en el DOM.
 * El evento 'show.bs.modal' de Bootstrap se dispara justo antes de mostrar el modal.
 */
let modalElemento = document.getElementById('modal-historial');
if (modalElemento != null) {
    modalElemento.addEventListener('show.bs.modal', async () => {
        const respuesta = await fetch('/caja/historial');
        const cajas     = await respuesta.json();

        const contenedor = document.getElementById('tabla-historial-caja');

        if (cajas.length === 0) {
            contenedor.innerHTML = `
                <p class="text-muted text-center py-4 mb-0">
                    No hay cajas cerradas en los ultimos 30 dias
                </p>`;
            return;
        }

        // Hacemos un for para meter las filas de historial a lo bruto en un string
        let filas = "";
        for (let i = 0; i < cajas.length; i++) {
            let c = cajas[i];
            filas = filas + `
            <tr>
                <td class="fw-bold">${c.fecha}</td>
                <td>$${c.monto_inicial.toFixed(2)}</td>
                <td class="text-success fw-bold">+$${c.total_ingresos.toFixed(2)}</td>
                <td class="text-danger fw-bold">-$${c.total_egresos.toFixed(2)}</td>
                <td class="text-primary fw-bold">$${c.monto_final.toFixed(2)}</td>
            </tr>`;
        }

        // Insertamos la tabla completa con encabezados en el contenedor del modal.
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
}
