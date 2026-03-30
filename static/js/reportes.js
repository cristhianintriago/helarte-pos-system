// Al cargar, establecemos el período de "hoy" por defecto
document.addEventListener("DOMContentLoaded", () => {
  cargarDashboardHoy();
  setPeriodo("mes");
});

let graficoHoy = null;
let graficoTopProductos = null;
let graficoPagos = null;

// Colores UI Premium Helarte
const baseColors = [
  'rgba(255, 99, 132, 0.8)',   // Rosa/Rojo
  'rgba(54, 162, 235, 0.8)',   // Azul
  'rgba(255, 206, 86, 0.8)',   // Amarillo
  'rgba(75, 192, 192, 0.8)',   // Verde menta
  'rgba(153, 102, 255, 0.8)'   // Púrpura
];
function setPeriodo(periodo) {
  const hoy = new Date();
  const hasta = hoy.toISOString().split("T")[0];
  let desde;

  if (periodo === "hoy") {
    desde = hasta;
  } else if (periodo === "semana") {
    const inicioSemana = new Date(hoy);
    inicioSemana.setDate(hoy.getDate() - 7);
    desde = inicioSemana.toISOString().split("T")[0];
  } else if (periodo === "mes") {
    desde = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-01`;
  }

  document.getElementById("fecha-desde").value = desde;
  document.getElementById("fecha-hasta").value = hasta;
  cargarReporte();
}

// Carga el reporte del backend con las fechas seleccionadas
async function cargarReporte() {
  const desde = document.getElementById("fecha-desde").value;
  const hasta = document.getElementById("fecha-hasta").value;

  if (!desde || !hasta) {
    alert("⚠️ Selecciona un rango de fechas");
    return;
  }

  let datos;
  try {
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

  // Actualizamos tarjetas de resumen
  document.getElementById("rep-pedidos").textContent = datos.total_pedidos;
  document.getElementById("rep-total").textContent =
    `$${datos.total_vendido.toFixed(2)}`;
  document.getElementById("rep-top").textContent =
    datos.producto_top || "Sin datos";
  document.getElementById("rep-promedio").textContent =
    datos.total_pedidos > 0
      ? `$${(datos.total_vendido / datos.total_pedidos).toFixed(2)}`
      : "$0.00";

  // Ventas por día
  const listaDia = document.getElementById("lista-por-dia");
  listaDia.innerHTML = "";
  if (datos.ventas_por_dia.length === 0) {
    listaDia.innerHTML =
      '<p class="text-muted text-center py-3 mb-0">Sin datos</p>';
  } else {
    datos.ventas_por_dia.forEach((d) => {
      const div = document.createElement("div");
      div.className = "list-group-item d-flex justify-content-between";
      div.innerHTML = `
                <span>${d.fecha}</span>
                <div>
                    <span class="badge bg-secondary me-2">${d.cantidad} ventas</span>
                    <span class="fw-bold text-success">$${d.total.toFixed(2)}</span>
                </div>`;
      listaDia.appendChild(div);
    });
  }

  // Top productos
  const listaTop = document.getElementById("lista-top-productos");
  listaTop.innerHTML = "";
  if (datos.top_productos.length === 0) {
    listaTop.innerHTML =
      '<p class="text-muted text-center py-3 mb-0">Sin datos</p>';
  } else {
    datos.top_productos.forEach((p, i) => {
      const medallas = ["🥇", "🥈", "🥉"];
      const div = document.createElement("div");
      div.className =
        "list-group-item d-flex justify-content-between align-items-center";
      div.innerHTML = `
                <span>${medallas[i] || "🍦"} ${p.nombre}</span>
                <span class="badge bg-dark">${p.cantidad} vendidos</span>`;
      listaTop.appendChild(div);
    });
  }

  // 1. Dibuja el Gráfico de Top Productos
  const ctxTop = document.getElementById('grafico-top-productos');
  if (ctxTop) {
    if (graficoTopProductos) graficoTopProductos.destroy();
    graficoTopProductos = new Chart(ctxTop, {
      type: 'doughnut',
      data: {
        labels: datos.top_productos.map(p => p.nombre),
        datasets: [{
          data: datos.top_productos.map(p => p.cantidad),
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

  // 2. Dibuja el Gráfico de Desglose de Pagos
  const ctxPagos = document.getElementById('grafico-pagos');
  if (ctxPagos && datos.desglose_pagos) {
    if (graficoPagos) graficoPagos.destroy();
    graficoPagos = new Chart(ctxPagos, {
      type: 'pie',
      data: {
        labels: ['Efectivo', 'Transferencia'],
        datasets: [{
          data: [datos.desglose_pagos.efectivo, datos.desglose_pagos.transferencia],
          backgroundColor: ['rgba(75, 192, 192, 0.8)', 'rgba(54, 162, 235, 0.8)'], // Verde y Azul
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

  document.getElementById('dash-fecha').textContent = datos.fecha;
  document.getElementById('dash-total-hoy').textContent = `$${datos.total_vendido_hoy.toFixed(2)}`;
  document.getElementById('dash-tickets-hoy').textContent = datos.total_tickets_hoy;

  const canvas = document.getElementById('grafico-hoy');
  if (!canvas || typeof Chart === 'undefined') return;

  if (graficoHoy) {
    graficoHoy.destroy();
  }

  graficoHoy = new Chart(canvas, {
    type: 'line',
    data: {
      labels: datos.labels,
      datasets: [
        {
          label: 'Ventas ($)',
          data: datos.ventas_por_hora,
          borderColor: '#0d6efd',
          backgroundColor: 'rgba(13, 110, 253, 0.15)',
          fill: true,
          tension: 0.35,
          pointRadius: 2,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: (value) => `$${value}`
          }
        }
      }
    }
  });
}

function exportarCSV() {
  const desde = document.getElementById('fecha-desde').value;
  const hasta = document.getElementById('fecha-hasta').value;
  if (!desde || !hasta) {
    alert('Selecciona un rango de fechas para exportar');
    return;
  }
  window.open(`/reportes/export/csv?desde=${desde}&hasta=${hasta}`, '_blank');
}

function exportarExcel() {
  const desde = document.getElementById('fecha-desde').value;
  const hasta = document.getElementById('fecha-hasta').value;
  if (!desde || !hasta) {
    alert('Selecciona un rango de fechas para exportar');
    return;
  }
  window.open(`/reportes/export/excel?desde=${desde}&hasta=${hasta}`, '_blank');
}
// Descarga el PDF del día actual
function descargarPDFHoy() {
    window.open('/reporte-diario/pdf', '_blank');
    mostrarToast('Generando reporte PDF...', 'info');
}

// Abre el modal y carga el historial
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
        const fecha = new Date(item.fecha + 'T00:00:00');
        const div = document.createElement('div');
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

// Descarga el PDF de una fecha específica
function descargarPDFFecha(fecha) {
    window.open(`/reporte-diario/pdf/${fecha}`, '_blank');
    mostrarToast('Generando reporte PDF...', 'info');
}
