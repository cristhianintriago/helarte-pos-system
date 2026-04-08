/**
 * reportes.js
 * -----------
 * Logica del dashboard analitico de reportes de ventas.
 *
 * Este modulo hace dos tipos de consultas al servidor:
 * 1. /reportes/dashboard-hoy: datos del dia actual para el grafico de ventas por hora.
 * 2. /reportes/?desde=...&hasta=...: datos del periodo seleccionado para los graficos de
 *    top productos y desglose de pagos.
 *
 * Chart.js: libreria JavaScript para crear graficos interactivos en un elemento <canvas>.
 * El elemento <canvas> es una etiqueta HTML que permite dibujar graficos y animaciones.
 *
 * Patron importante - destruir y recrear graficos:
 * Chart.js adjunta el grafico al elemento canvas. Si se intenta crear un segundo grafico
 * en el mismo canvas sin destruir el anterior, lanza un error. Por eso, antes de crear
 * cada grafico, verificamos si ya existe y lo destruimos con .destroy().
 */

// ==========================================
// ESTADO GLOBAL DEL MODULO
// ==========================================

// Referencias a los graficos activos. Se guardan para poder destruirlos antes de recrearlos.
let graficoHoy          = null;
let graficoTopProductos = null;
let graficoPagos        = null;

// Paleta de colores con transparencia (rgba). Los valores son Rojo, Verde, Azul, Alfa (opacidad).
// Se reutilizan en los graficos de dona y pastel para mantener consistencia visual.
const baseColors = [
    'rgba(255, 99, 132, 0.8)',   // Rosa
    'rgba(54, 162, 235, 0.8)',   // Azul
    'rgba(255, 206, 86, 0.8)',   // Amarillo
    'rgba(75, 192, 192, 0.8)',   // Verde menta
    'rgba(153, 102, 255, 0.8)'   // Purpura
];


// ==========================================
// INICIALIZACION
// ==========================================

/**
 * Al terminar de cargar el DOM, cargamos ambos bloques del dashboard:
 * - El resumen del dia de hoy (grafico de lineas por hora).
 * - El reporte del mes actual (por defecto).
 */
document.addEventListener("DOMContentLoaded", () => {
    cargarDashboardHoy();
    // setPeriodo() calcula automaticamente las fechas del periodo y llama a cargarReporte().
    setPeriodo("mes");
});


// ==========================================
// SELECTOR DE PERIODO
// ==========================================

/**
 * Calcula las fechas de inicio y fin segun el periodo seleccionado y dispara la carga del reporte.
 * Los botones "Hoy", "Semana" y "Mes" en el HTML llaman a esta funcion con el argumento correspondiente.
 *
 * @param {string} periodo - Puede ser "hoy", "semana" o "mes".
 */
function setPeriodo(periodo) {
    const hoy   = new Date();
    // toISOString() retorna la fecha en formato ISO 8601: "2024-01-31T00:00:00.000Z".
    // split("T")[0] toma solo la parte de la fecha: "2024-01-31".
    const hasta = hoy.toISOString().split("T")[0];
    let desde;

    if (periodo === "hoy") {
        desde = hasta;  // Mismo dia: inicio y fin son iguales.
    } else if (periodo === "semana") {
        const inicioSemana = new Date(hoy);
        // setDate modifica el dia del mes. Restar 7 nos da hace una semana.
        inicioSemana.setDate(hoy.getDate() - 7);
        desde = inicioSemana.toISOString().split("T")[0];
    } else if (periodo === "mes") {
        // Primer dia del mes actual. padStart asegura que el mes tenga dos digitos (ej: "01").
        desde = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-01`;
    }

    // Escribimos las fechas en los campos del formulario.
    document.getElementById("fecha-desde").value = desde;
    document.getElementById("fecha-hasta").value = hasta;

    // Cargamos el reporte con el nuevo rango de fechas.
    cargarReporte();
}


// ==========================================
// CARGA DE REPORTE POR RANGO DE FECHAS
// ==========================================

/**
 * Consulta el reporte del servidor para el rango de fechas seleccionado y actualiza:
 * - Las tarjetas de resumen (total vendido, pedidos, ticket promedio, top producto).
 * - La lista de ventas por dia.
 * - La lista de top productos.
 * - El grafico de dona (top productos).
 * - El grafico de pastel (desglose de pagos).
 */
async function cargarReporte() {
    const desde = document.getElementById("fecha-desde").value;
    const hasta = document.getElementById("fecha-hasta").value;

    if (!desde || !hasta) {
        alert("Selecciona un rango de fechas");
        return;
    }

    let datos;
    try {
        // Construimos la URL con los parametros de query: ?desde=...&hasta=...
        const respuesta = await fetch(`/reportes/?desde=${desde}&hasta=${hasta}`);
        if (!respuesta.ok) {
            throw new Error(`No se pudo generar reporte (HTTP ${respuesta.status})`);
        }
        datos = await respuesta.json();
    } catch (error) {
        console.error(error);
        mostrarToast("No se pudo cargar el reporte", "danger");
        return;
    }

    // Actualizamos las tarjetas de resumen con los KPIs del periodo.
    document.getElementById("rep-pedidos").textContent = datos.total_pedidos;
    document.getElementById("rep-total").textContent   = `$${datos.total_vendido.toFixed(2)}`;
    document.getElementById("rep-top").textContent     = datos.producto_top || "Sin datos";

    // Ticket promedio: total dividido entre la cantidad de pedidos.
    // Se evita la division por cero con el operador ternario (condicion ? si_true : si_false).
    document.getElementById("rep-promedio").textContent = datos.total_pedidos > 0
        ? `$${(datos.total_vendido / datos.total_pedidos).toFixed(2)}`
        : "$0.00";

    // ---- Lista de ventas por dia ----
    const listaDia = document.getElementById("lista-por-dia");
    listaDia.innerHTML = "";
    if (datos.ventas_por_dia.length === 0) {
        listaDia.innerHTML = '<p class="text-muted text-center py-3 mb-0">Sin datos</p>';
    } else {
        datos.ventas_por_dia.forEach((d) => {
            const div       = document.createElement("div");
            div.className   = "list-group-item d-flex justify-content-between";
            div.innerHTML   = `
                <span>${d.fecha}</span>
                <div>
                    <span class="badge bg-secondary me-2">${d.cantidad} ventas</span>
                    <span class="fw-bold text-success">$${d.total.toFixed(2)}</span>
                </div>`;
            listaDia.appendChild(div);
        });
    }

    // ---- Lista de top productos ----
    const listaTop = document.getElementById("lista-top-productos");
    listaTop.innerHTML = "";
    if (datos.top_productos.length === 0) {
        listaTop.innerHTML = '<p class="text-muted text-center py-3 mb-0">Sin datos</p>';
    } else {
        datos.top_productos.forEach((p, i) => {
            // El indice 'i' nos sirve para asignar la medalla correspondiente (oro, plata, bronce).
            const medallas  = ["Primero", "Segundo", "Tercero"];
            const div       = document.createElement("div");
            div.className   = "list-group-item d-flex justify-content-between align-items-center";
            div.innerHTML   = `
                <span>${medallas[i] || "-"} ${p.nombre}</span>
                <span class="badge bg-dark">${p.cantidad} vendidos</span>`;
            listaTop.appendChild(div);
        });
    }

    // ---- Grafico de dona: Top Productos ----
    // Un grafico de dona (doughnut) muestra proporciones de un total, similar al pastel
    // pero con un hueco en el centro. Es util para comparar partes de un todo.
    const ctxTop = document.getElementById('grafico-top-productos');
    if (ctxTop) {
        // Destruimos el grafico anterior si existe para poder crear uno nuevo en el mismo canvas.
        if (graficoTopProductos) graficoTopProductos.destroy();
        graficoTopProductos = new Chart(ctxTop, {
            type: 'doughnut',
            data: {
                labels: datos.top_productos.map(p => p.nombre),
                datasets: [{
                    data:            datos.top_productos.map(p => p.cantidad),
                    backgroundColor: baseColors,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right' }
                }
            }
        });
    }

    // ---- Grafico de pastel: Desglose de Pagos ----
    // Un grafico de pastel (pie) muestra la proporcion de cada metodo de pago sobre el total.
    const ctxPagos = document.getElementById('grafico-pagos');
    if (ctxPagos && datos.desglose_pagos) {
        if (graficoPagos) graficoPagos.destroy();
        graficoPagos = new Chart(ctxPagos, {
            type: 'pie',
            data: {
                labels: ['Efectivo', 'Transferencia'],
                datasets: [{
                    data: [datos.desglose_pagos.efectivo, datos.desglose_pagos.transferencia],
                    backgroundColor: ['rgba(75, 192, 192, 0.8)', 'rgba(54, 162, 235, 0.8)'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }
}


// ==========================================
// DASHBOARD DE HOY (GRAFICO DE LINEAS)
// ==========================================

/**
 * Carga los datos de ventas del dia actual y dibuja el grafico de lineas por hora.
 * Este grafico muestra las horas pico de ventas, util para planificar el personal.
 * Un grafico de lineas (line) conecta puntos de datos con una linea, ideal para
 * mostrar tendencias a lo largo del tiempo.
 */
async function cargarDashboardHoy() {
    let datos;
    try {
        const respuesta = await fetch('/reportes/dashboard-hoy');
        if (!respuesta.ok) {
            throw new Error(`No se pudo cargar dashboard (HTTP ${respuesta.status})`);
        }
        datos = await respuesta.json();
    } catch (error) {
        console.error(error);
        mostrarToast('No se pudo cargar el dashboard de hoy', 'danger');
        return;
    }

    // Actualizamos los indicadores del bloque "hoy".
    document.getElementById('dash-fecha').textContent       = datos.fecha;
    document.getElementById('dash-total-hoy').textContent   = `$${datos.total_vendido_hoy.toFixed(2)}`;
    document.getElementById('dash-tickets-hoy').textContent = datos.total_tickets_hoy;

    const canvas = document.getElementById('grafico-hoy');
    // Verificamos que el canvas exista y que Chart.js haya cargado correctamente.
    if (!canvas || typeof Chart === 'undefined') return;

    if (graficoHoy) {
        graficoHoy.destroy();
    }

    graficoHoy = new Chart(canvas, {
        type: 'line',
        data: {
            labels: datos.labels,  // Array de etiquetas de hora: ["00:00", "01:00", ..., "23:00"]
            datasets: [{
                label: 'Ventas ($)',
                data: datos.ventas_por_hora,
                borderColor: '#0d6efd',            // Color de la linea en hex.
                backgroundColor: 'rgba(13, 110, 253, 0.15)', // Relleno semitransparente bajo la linea.
                fill: true,                        // fill: true activa el relleno bajo la curva.
                tension: 0.35,                     // tension: 0 = linea recta, 1 = muy curva.
                pointRadius: 2,                    // Tamano de los puntos de datos.
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        // callback personaliza como se muestra cada etiqueta del eje Y.
                        callback: (value) => `$${value}`
                    }
                }
            }
        }
    });
}


// ==========================================
// EXPORTACION DE DATOS
// ==========================================

/**
 * Abre el reporte CSV en una nueva pestana del navegador, iniciando la descarga.
 * window.open() le indica al navegador que abra la URL en una nueva ventana o pestana.
 */
function exportarCSV() {
    const desde = document.getElementById('fecha-desde').value;
    const hasta = document.getElementById('fecha-hasta').value;
    if (!desde || !hasta) { alert('Selecciona un rango de fechas para exportar'); return; }
    window.open(`/reportes/export/csv?desde=${desde}&hasta=${hasta}`, '_blank');
}

/**
 * Abre el reporte Excel en una nueva pestana del navegador, iniciando la descarga.
 */
function exportarExcel() {
    const desde = document.getElementById('fecha-desde').value;
    const hasta = document.getElementById('fecha-hasta').value;
    if (!desde || !hasta) { alert('Selecciona un rango de fechas para exportar'); return; }
    window.open(`/reportes/export/excel?desde=${desde}&hasta=${hasta}`, '_blank');
}

/**
 * Descarga el corte de reporte PDF del dia actual.
 * Primero verifica que haya caja disponible antes de abrir la ventana.
 */
async function descargarPDFHoy() {
    const desde = document.getElementById('fecha-desde').value;
    const hasta = document.getElementById('fecha-hasta').value;

    // Determinamos qué fecha usar para el PDF:
    // Si se seleccionó un rango de un solo dia (desde == hasta), usamos esa fecha.
    // Si el rango es "hoy" (o vacío), usamos la ruta sin fecha.
    const hoy = new Date().toISOString().split('T')[0];
    const esHoy      = (!desde && !hasta) || (desde === hoy && hasta === hoy);
    const esSoloDia  = desde && hasta && desde === hasta;
    const fechaTarget = esSoloDia ? desde : null;

    // Cambiamos el boton para indicar que se esta procesando
    let btn = document.querySelector('[onclick="descargarPDFHoy()"]');
    let textoOriginal = '';
    if (btn) {
        textoOriginal = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generando...';
        btn.disabled = true;
    }

    try {
        // Para reportes del dia actual verificamos si hay caja abierta.
        // Para reportes históricos no es necesaria esa validación.
        if (esHoy) {
            let respuesta = await fetch('/caja/estado');
            let datos = await respuesta.json();
            if (datos.estado !== 'abierta') {
                mostrarToast('No hay caja abierta hoy. Abre la caja para generar el reporte.', 'warning');
                return;
            }
        }

        // Construimos la URL correcta segun la fecha
        const url = fechaTarget
            ? `/reporte-diario/pdf/${fechaTarget}`
            : '/reporte-diario/pdf';

        mostrarToast('Generando corte PDF...', 'info');
        window.open(url, '_blank');

    } catch (error) {
        console.error(error);
        mostrarToast('Error al generar el reporte PDF', 'danger');
    } finally {
        if (btn) {
            btn.innerHTML = textoOriginal;
            btn.disabled = false;
        }
    }
}


// ==========================================
// HISTORIAL DE REPORTES
// ==========================================

/**
 * El operador '?.' (optional chaining) llama a addEventListener solo si el elemento existe.
 * Si 'modal-historial' no esta en el DOM (pagina diferente), no lanza error.
 *
 * El evento 'show.bs.modal' es disparado por Bootstrap cuando el modal va a aparecer.
 * Lo usamos para cargar el historial justo antes de que sea visible al usuario.
 */
document.getElementById('modal-historial')?.addEventListener('show.bs.modal', async () => {
    let historial = [];
    try {
        const respuesta = await fetch('/reporte-diario/historial');
        if (!respuesta.ok) {
            throw new Error(`No se pudo cargar historial (HTTP ${respuesta.status})`);
        }
        historial = await respuesta.json();
    } catch (error) {
        console.error(error);
        mostrarToast('No se pudo cargar el historial de reportes', 'danger');
        return;
    }

    const lista = document.getElementById('lista-historial');
    lista.innerHTML = '';

    if (historial.length === 0) {
        lista.innerHTML = '<p class="text-muted text-center py-4">No hay reportes disponibles</p>';
        return;
    }

    historial.forEach(item => {
        // Construimos el objeto Date agregando la hora para evitar problemas de zona horaria.
        // Sin 'T00:00:00', JavaScript interpreta la fecha como UTC y puede mostrar el dia anterior.
        const fecha = new Date(item.fecha + 'T00:00:00');
        const div   = document.createElement('div');
        div.className = 'list-group-item d-flex justify-content-between align-items-center';
        div.innerHTML = `
            <div>
                <strong>${fecha.toLocaleDateString('es-EC', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</strong>
                <br>
                <small class="text-muted">Total: $${item.total_vendido.toFixed(2)}</small>
            </div>
            <button class="btn btn-sm btn-outline-danger" onclick="descargarPDFFecha('${item.fecha}')">
                <i class="bi bi-download"></i> PDF
            </button>`;
        lista.appendChild(div);
    });
});

/**
 * Descarga el PDF del reporte de una fecha especifica.
 * @param {string} fecha - Fecha en formato 'YYYY-MM-DD'.
 */
function descargarPDFFecha(fecha) {
    window.open(`/reporte-diario/pdf/${fecha}`, '_blank');
    mostrarToast('Generando reporte PDF...', 'info');
}
