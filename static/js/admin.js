/**
 * admin.js
 * --------
 * Logica del panel de administracion exclusivo para el usuario root.
 * Permite gestionar y eliminar registros historicos de caja y ventas,
 * y exportar / importar el catalogo de productos y sabores.
 *
 * Este modulo es critico: las operaciones de eliminacion son irreversibles.
 * Por eso se solicita confirmacion del usuario antes de cada operacion destructiva.
 *
 * Patron de seleccion multiple:
 * Cada fila de la tabla tiene un checkbox. El usuario puede seleccionar
 * varias filas y luego eliminar todas las seleccionadas en una sola operacion.
 * Este patron reduce el numero de solicitudes al servidor y mejora la experiencia.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Cargamos ambas tablas al iniciar la pagina.
    cargarCajas();
    cargarVentas();
});


/**
 * Reinicia el contador visual de tickets de pedido.
 * El siguiente pedido que se cree comenzara con el numero #1.
 * Solo el usuario root puede ejecutar esta accion.
 */
async function reiniciarContadorPedidos() {
    const ok = confirm('Se reiniciara la numeracion visual de pedidos. Deseas continuar?');
    if (!ok) return;

    try {
        const respuesta = await fetch('/pedidos/contador/reiniciar', { method: 'POST' });
        const datos     = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(datos.error || 'No se pudo reiniciar el contador');
        }

        mostrarToast(datos.mensaje || 'Contador reiniciado', 'success');
    } catch (error) {
        mostrarToast(error.message || 'Error al reiniciar contador', 'danger');
    }
}


// ==========================================
// GESTION DE REGISTROS DE CAJA
// ==========================================

/**
 * Carga y renderiza el historial de cajas cerradas en la tabla del panel.
 * Cada fila incluye un checkbox para poder seleccionarla para eliminacion.
 */
async function cargarCajas() {
    const respuesta = await fetch('/caja/historial');
    const cajas     = await respuesta.json();
    const tbody     = document.getElementById('tabla-cajas');

    if (!cajas || cajas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay registros de caja</td></tr>';
        return;
    }

    // Construimos una fila HTML por cada caja usando .map() y .join('').
    tbody.innerHTML = cajas.map(c => `
        <tr>
            <td><input type="checkbox" class="check-caja" value="${c.id}"></td>
            <td class="fw-bold">${c.fecha}</td>
            <td>$${(c.monto_inicial || 0).toFixed(2)}</td>
            <td class="text-success fw-bold">+$${(c.total_ingresos || 0).toFixed(2)}</td>
            <td class="text-danger fw-bold">-$${(c.total_egresos || 0).toFixed(2)}</td>
            <td class="text-primary fw-bold">$${(c.efectivo_esperado || 0).toFixed(2)}</td>
        </tr>`
    ).join('');
}

/**
 * Marca o desmarca todos los checkboxes de la tabla de cajas.
 * Se llama cuando el usuario hace clic en el checkbox del encabezado de la tabla.
 *
 * @param {HTMLInputElement} checkbox - El checkbox "seleccionar todo" del encabezado.
 */
function toggleTodosCajas(checkbox) {
    // querySelectorAll retorna una NodeList (no un Array) de todos los elementos que coinciden.
    // forEach itera sobre cada uno para cambiar su estado.
    document.querySelectorAll('.check-caja').forEach(c => c.checked = checkbox.checked);
}

/**
 * Invierte el estado del checkbox global de cajas.
 * Alternativa al clic directo en el encabezado, usada por un boton externo.
 */
function seleccionarTodoCajas() {
    const checkAll = document.getElementById('check-all-cajas');
    checkAll.checked = !checkAll.checked;
    toggleTodosCajas(checkAll);
}

/**
 * Elimina los registros de caja seleccionados y sus datos asociados (egresos y ventas).
 * Pide confirmacion explicita antes de ejecutar la operacion irreversible.
 */
async function eliminarCajasSeleccionadas() {
    // Recopilamos los IDs de los checkboxes marcados.
    // El spread [...] convierte la NodeList a un Array real para poder usar .map().
    // parseInt() convierte el valor del checkbox (string) a numero entero.
    const seleccionados = [...document.querySelectorAll('.check-caja:checked')].map(c => parseInt(c.value));

    if (seleccionados.length === 0) {
        mostrarToast('Selecciona al menos un registro', 'warning');
        return;
    }

    // Mensaje de advertencia explicito sobre las consecuencias irreversibles.
    const ok = confirm(
        `ADVERTENCIA\n\nSe eliminaran ${seleccionados.length} registro(s) de caja junto con todos sus egresos y ventas asociadas.\n\nConfirmas? Esta accion es IRREVERSIBLE.`
    );
    if (!ok) return;

    const respuesta = await fetch('/caja/registros', {
        method:  'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ids: seleccionados })
    });
    const datos = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(datos.mensaje, 'success');
        // Reiniciamos el checkbox global para que quede desmarcado despues de la operacion.
        document.getElementById('check-all-cajas').checked = false;
        cargarCajas();
        // Tambien recargamos las ventas porque la eliminacion de caja las elimina en cascada.
        cargarVentas();
    } else {
        mostrarToast(datos.error, 'danger');
    }
}


// ==========================================
// GESTION DE REGISTROS DE VENTAS
// ==========================================

/**
 * Carga y renderiza el historial completo de ventas en la tabla del panel.
 * Muestra badges de color para el tipo de pedido y forma de pago.
 */
async function cargarVentas() {
    const respuesta = await fetch('/reportes/ventas/lista');
    const ventas    = await respuesta.json();
    const tbody     = document.getElementById('tabla-ventas');

    if (!ventas || ventas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No hay registros de ventas</td></tr>';
        return;
    }

    // Funciones auxiliares que generan el HTML del badge segun el tipo de dato.
    // Las funciones de flecha de una linea retornan implicitamente el resultado de la expresion.
    const badgePago = (forma) => {
        if (forma === 'transferencia') return '<span class="badge bg-info text-dark">Transf.</span>';
        if (forma === 'mixto')         return '<span class="badge bg-secondary">Mixto</span>';
        return '<span class="badge bg-success">Efectivo</span>';
    };

    const badgeTipo = (tipo) => tipo === 'delivery'
        ? '<span class="badge bg-warning text-dark">Delivery</span>'
        : '<span class="badge bg-light text-dark border">Local</span>';

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

/**
 * Marca o desmarca todos los checkboxes de la tabla de ventas.
 * @param {HTMLInputElement} checkbox - El checkbox del encabezado.
 */
function toggleTodosVentas(checkbox) {
    document.querySelectorAll('.check-venta').forEach(c => c.checked = checkbox.checked);
}

/**
 * Invierte el estado del checkbox global de ventas.
 */
function seleccionarTodoVentas() {
    const checkAll = document.getElementById('check-all-ventas');
    checkAll.checked = !checkAll.checked;
    toggleTodosVentas(checkAll);
}

/**
 * Elimina las ventas seleccionadas del historial del sistema.
 * Esta operacion afecta los reportes historicos y es irreversible.
 */
async function eliminarVentasSeleccionadas() {
    const seleccionados = [...document.querySelectorAll('.check-venta:checked')].map(c => parseInt(c.value));

    if (seleccionados.length === 0) {
        mostrarToast('Selecciona al menos una venta', 'warning');
        return;
    }

    const ok = confirm(
        `ADVERTENCIA\n\nSe eliminaran ${seleccionados.length} venta(s) del historial. Esto afectara los reportes.\n\nConfirmas? Esta accion es IRREVERSIBLE.`
    );
    if (!ok) return;

    const respuesta = await fetch('/reportes/ventas/eliminar', {
        method:  'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ids: seleccionados })
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
// EXPORTAR / IMPORTAR CATALOGO
// ==========================================

/**
 * Descarga el catalogo completo de productos y sabores como un archivo JSON.
 * Llama a GET /admin/exportar-catalogo; el servidor responde con Content-Disposition
 * attachment, lo que hace que el navegador lo guarde automaticamente.
 *
 * Tecnica: creamos un <a> invisible con la URL del endpoint, simulamos el click
 * y lo eliminamos. De esta forma el fetch no es necesario: el navegador gestiona
 * la descarga directamente igual que cuando el usuario hace clic en un enlace.
 */
async function exportarCatalogo() {
    const btn = document.getElementById('btn-exportar-catalogo');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generando...';
    }

    try {
        // Hacemos un fetch para poder detectar errores HTTP antes de la descarga.
        const respuesta = await fetch('/admin/exportar-catalogo');
        if (!respuesta.ok) {
            const datos = await respuesta.json().catch(() => ({}));
            throw new Error(datos.error || `Error HTTP ${respuesta.status}`);
        }

        // Convertimos la respuesta en un Blob (Binary Large Object) y creamos
        // una URL temporal para que el navegador pueda descargar el contenido.
        const blob     = await respuesta.blob();
        const urlBlob  = URL.createObjectURL(blob);

        // Extraemos el nombre del archivo del header Content-Disposition.
        const disposition = respuesta.headers.get('Content-Disposition') || '';
        const match       = disposition.match(/filename="([^"]+)"/);
        const nombreArchivo = match ? match[1] : 'catalogo_helarte.json';

        // Creamos un enlace invisible, lo activamos para descargar y lo destruimos.
        const enlace = document.createElement('a');
        enlace.href     = urlBlob;
        enlace.download = nombreArchivo;
        document.body.appendChild(enlace);
        enlace.click();
        document.body.removeChild(enlace);

        // Liberamos la URL temporal de memoria.
        URL.revokeObjectURL(urlBlob);

        mostrarToast(`Catalogo exportado: ${nombreArchivo}`, 'success');
    } catch (error) {
        mostrarToast(error.message || 'Error al exportar el catalogo', 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-download me-1"></i> Descargar JSON';
        }
    }
}


/**
 * Importa el catalogo desde un archivo JSON seleccionado por el usuario.
 * Envia el archivo como multipart/form-data a POST /admin/importar-catalogo.
 * Muestra un resumen detallado del resultado (creados, actualizados, errores).
 *
 * @param {HTMLInputElement} inputEl - El elemento <input type="file"> que disparo el evento.
 */
async function importarCatalogo(inputEl) {
    const archivo = inputEl.files[0];
    if (!archivo) return;

    // Reseteamos el input para que el usuario pueda volver a elegir el mismo archivo.
    inputEl.value = '';

    if (!archivo.name.endsWith('.json')) {
        mostrarToast('El archivo debe tener extension .json', 'warning');
        return;
    }

    const confirmado = confirm(
        `Importar catálogo desde: "${archivo.name}"\n\n` +
        `Esta operación creará o actualizará productos y sabores.\n` +
        `Los registros existentes NO se eliminarán.\n\n` +
        `¿Continuar?`
    );
    if (!confirmado) return;

    // Ocultamos el resultado anterior y mostramos indicador de carga.
    const contenedorResultado = document.getElementById('resultado-importacion');
    const divResumen          = document.getElementById('resumen-importacion');
    contenedorResultado.classList.add('d-none');

    mostrarToast('Importando catálogo, aguarda...', 'info');

    try {
        // FormData permite enviar archivos binarios como multipart/form-data.
        const formData = new FormData();
        formData.append('archivo', archivo);

        const respuesta = await fetch('/admin/importar-catalogo', {
            method: 'POST',
            body:   formData
            // No ponemos Content-Type: el navegador lo setea automaticamente con el boundary correcto.
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(datos.error || `Error HTTP ${respuesta.status}`);
        }

        // Construimos el HTML del resumen de la importacion.
        const hayErrores = datos.errores && datos.errores.length > 0;
        const erroresHtml = hayErrores
            ? `<div class="alert alert-warning py-2 mt-2 small">
                <strong><i class="bi bi-exclamation-triangle me-1"></i>Advertencias:</strong>
                <ul class="mb-0 mt-1">${datos.errores.map(e => `<li>${e}</li>`).join('')}</ul>
               </div>`
            : '';

        divResumen.innerHTML = `
            <div class="row g-2 text-center">
                <div class="col-6 col-md-3">
                    <div class="bg-success bg-opacity-10 border border-success rounded p-2">
                        <div class="fs-4 fw-bold text-success">${datos.sabores_creados}</div>
                        <div class="small text-muted">Sabores creados</div>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="bg-info bg-opacity-10 border border-info rounded p-2">
                        <div class="fs-4 fw-bold text-info">${datos.sabores_actualizados}</div>
                        <div class="small text-muted">Sabores actualizados</div>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="bg-success bg-opacity-10 border border-success rounded p-2">
                        <div class="fs-4 fw-bold text-success">${datos.productos_creados}</div>
                        <div class="small text-muted">Productos creados</div>
                    </div>
                </div>
                <div class="col-6 col-md-3">
                    <div class="bg-info bg-opacity-10 border border-info rounded p-2">
                        <div class="fs-4 fw-bold text-info">${datos.productos_actualizados}</div>
                        <div class="small text-muted">Productos actualizados</div>
                    </div>
                </div>
            </div>
            ${erroresHtml}`;

        contenedorResultado.classList.remove('d-none');
        mostrarToast(datos.mensaje || 'Importacion completada', hayErrores ? 'warning' : 'success');

    } catch (error) {
        mostrarToast(error.message || 'Error al importar el catalogo', 'danger');
    }
}


// ==========================================
// TOAST DE NOTIFICACION
// ==========================================

/**
 * Muestra una notificacion Toast de respaldo para este modulo.
 * Identica en logica a la de ventas.js: si existe el elemento global, lo usa;
 * si no, crea uno temporal e inyectado directamente en el body.
 *
 * @param {string} mensaje - Texto de la notificacion.
 * @param {string} tipo    - Categoria de color Bootstrap.
 */
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
