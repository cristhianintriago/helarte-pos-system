// Al cargar, establecemos el período de "hoy" por defecto
document.addEventListener("DOMContentLoaded", () => {
  setPeriodo("mes");
});

// Establece fechas rápidas
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

  const respuesta = await fetch(`/reportes/?desde=${desde}&hasta=${hasta}`);
  const datos = await respuesta.json();

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
}
// Descarga el PDF del día actual
function descargarPDFHoy() {
    window.open('/reporte-diario/pdf', '_blank');
    mostrarToast('Generando reporte PDF...', 'info');
}

// Abre el modal y carga el historial
document.getElementById('modal-historial')?.addEventListener('show.bs.modal', async () => {
    const respuesta = await fetch('/reporte-diario/historial');
    const historial = await respuesta.json();

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
