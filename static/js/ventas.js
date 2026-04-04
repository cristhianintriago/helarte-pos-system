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
                <div class="d-flex align-items-center">
                    <span class="fw-bold text-success fs-6 me-3">$${parseFloat(v.total).toFixed(2)}</span>
                    <button class="btn btn-sm btn-outline-primary" onclick="verDetalleVenta(${v.id})">
                        <i class="bi bi-eye"></i>
                    </button>
                </div>
            </div>`;
    }).join('');
}

/**
 * Consulta los productos y sabores de una venta especifica y los muestra en un modal.
 * @param {number} ventaId - ID de la venta a consultar.
 */
async function verDetalleVenta(ventaId) {
    const contenedor = document.getElementById('contenido-detalle-venta');
    contenedor.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p>Cargando detalle...</p></div>';
    
    // Mostramos el modal de una vez para dar feedback de carga
    const modal = new bootstrap.Modal(document.getElementById('modal-detalle-venta'));
    modal.show();

    try {
        const respuesta = await fetch(`/ventas/detalle/${ventaId}`);
        if (!respuesta.ok) throw new Error('No se pudo obtener el detalle');
        
        const v = await respuesta.json();

        // Construimos la tabla de productos
        let tablaProductos = v.productos.map(p => `
            <tr>
                <td>
                    <div class="fw-bold">${p.producto}</div>
                    <div class="small text-muted">${p.sabor !== 'N/A' ? 'Sabores: ' + p.sabor : ''}</div>
                </td>
                <td class="text-center">${p.cantidad}</td>
                <td class="text-end">$${parseFloat(p.subtotal).toFixed(2)}</td>
            </tr>
        `).join('');

        contenedor.innerHTML = `
            <div class="p-4">
                <div class="row mb-4">
                    <div class="col-6">
                        <h6 class="text-muted mb-1 text-uppercase small fw-bold">Cliente</h6>
                        <div class="fs-5 fw-bold text-dark">${v.cliente || 'Consumidor Final'}</div>
                    </div>
                    <div class="col-6 text-end">
                        <h6 class="text-muted mb-1 text-uppercase small fw-bold">Fecha y Hora</h6>
                        <div class="text-dark">${v.fecha}</div>
                    </div>
                </div>
                
                <div class="table-responsive">
                    <table class="table table-borderless align-middle">
                        <thead class="bg-light">
                            <tr>
                                <th class="py-2">Producto / Sabores</th>
                                <th class="py-2 text-center">Cant.</th>
                                <th class="py-2 text-end">Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${tablaProductos}
                        </tbody>
                        <tfoot class="border-top">
                            <tr class="fs-5">
                                <td colspan="2" class="pt-3 fw-bold">TOTAL VENTA</td>
                                <td class="pt-3 text-end fw-bold text-success">$${parseFloat(v.total).toFixed(2)}</td>
                            </tr>
                            <tr>
                                <td colspan="2" class="text-muted small">Método de Pago</td>
                                <td class="text-end text-muted small text-capitalize">${v.forma_pago}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>`;
    } catch (error) {
        console.error(error);
        contenedor.innerHTML = `
            <div class="alert alert-danger m-4">
                <i class="bi bi-exclamation-triangle"></i> No se pudo cargar la información del pedido.
            </div>`;
    }
}

/**
 * Funcion de acceso directo para ver la ultima venta del dia.
 */
async function verUltimaVenta() {
    try {
        const r = await fetch('/ventas/ultimo');
        if (!r.ok) {
            mostrarToast('No hay ventas registradas todavía hoy', 'info');
            return;
        }
        const datos = await r.json();
        if (datos.id) {
            verDetalleVenta(datos.id);
        }
    } catch (e) {
        console.error(e);
        mostrarToast('Error al buscar el último pedido', 'danger');
    }
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
