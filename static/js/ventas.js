/**
 * ventas.js
 * ---------
 * Logica del modulo de historial de ventas del dia.
 * Muestra un resumen de todas las ventas completadas y los indicadores del dia.
 *
 * Se actualiza automaticamente cada 30 segundos y tambien cuando el usuario
 * vuelve a esta pestana del navegador (evento 'visibilitychange').
 */

document.addEventListener('DOMContentLoaded', () => {
    cargarResumen();
    // Refresco automatico cada 30 segundos.
    setInterval(cargarResumen, 30000);
});

/**
 * El evento 'visibilitychange' se dispara cuando el usuario regresa a esta pestana
 * del navegador (por ejemplo, si estaba en otra app o en otro tab).
 * Al detectar que la pagina vuelve a ser visible, recargamos los datos
 * para asegurarnos de que el vendedor ve informacion actualizada sin esperar al siguiente intervalo.
 */
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        cargarResumen();
    }
});

/**
 * Obtiene el resumen de ventas del dia desde el servidor y actualiza la interfaz.
 * Usa try/catch para manejar errores de red sin que la pagina se rompa silenciosamente.
 */
async function cargarResumen() {
    try {
        const respuesta = await fetch('/ventas/');
        const datos     = await respuesta.json();

        // Actualizamos los indicadores numericos del encabezado del modulo.
        document.getElementById('total-pedidos').textContent  = datos.total_pedidos;
        document.getElementById('total-vendido').textContent  = `$${parseFloat(datos.total_vendido).toFixed(2)}`;
        document.getElementById('total-delivery').textContent = datos.total_delivery;
        document.getElementById('total-local').textContent    = datos.total_local;

        // Renderizamos la lista detallada de ventas completadas.
        renderizarVentasCompletadas(datos.ventas);
    } catch (error) {
        console.error('Error al cargar resumen de ventas:', error);
    }
}

/**
 * Construye dinamicamente el HTML de la lista de ventas y lo inserta en el DOM.
 * Si no hay ventas, muestra un estado vacio informativo.
 *
 * @param {Array} ventas - Lista de objetos de venta retornada por el servidor.
 */
function renderizarVentasCompletadas(ventas) {
    const contenedor = document.getElementById('lista-ventas');

    if (!ventas || ventas.length === 0) {
        // Estado vacio: no hay ventas registradas aun en el dia.
        contenedor.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-receipt fs-3"></i>
                <p class="mt-2 mb-0">No hay ventas completadas hoy</p>
            </div>`;
        return;
    }

    // Construimos una fila HTML por cada venta usando el metodo .map() y .join('').
    // .map() transforma cada elemento del array en un string HTML.
    // .join('') concatena todos los strings en uno solo sin separadores.
    contenedor.innerHTML = ventas.map(v => {
        // Badge visual que indica si fue un pedido delivery o local.
        const badgeTipo = v.tipo === 'delivery'
            ? '<span class="badge bg-warning text-dark">Delivery</span>'
            : '<span class="badge bg-info text-dark">Local</span>';

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

/**
 * Muestra una notificacion Toast de respaldo para este modulo.
 * Si existe el elemento global 'toast-global' en el HTML, lo usa.
 * Si no, crea un toast temporal directamente en el body del documento.
 *
 * @param {string} mensaje - Texto de la notificacion.
 * @param {string} tipo    - Categoria de color Bootstrap: 'success', 'danger', etc.
 */
function mostrarToast(mensaje, tipo = 'success') {
    const toastEl = document.getElementById('toast-global');
    if (toastEl) {
        toastEl.querySelector('.toast-body').textContent = mensaje;
        toastEl.className = `toast align-items-center text-white bg-${tipo} border-0`;
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
        return;
    }

    // Fallback: si no hay elemento toast en el HTML, lo creamos e inyectamos dinamicamente.
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
    // setTimeout programa la eliminacion del elemento despues de 3.5 segundos.
    setTimeout(() => div.remove(), 3500);
}
