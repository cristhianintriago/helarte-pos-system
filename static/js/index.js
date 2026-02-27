document.addEventListener('DOMContentLoaded', () => {
    cargarResumen();
    setInterval(cargarResumen, 30000);
});

async function cargarResumen() {
    const respuesta = await fetch('/resumen');
    const datos = await respuesta.json();

    document.getElementById('pedidos-activos').textContent = datos.pedidos_activos;
    document.getElementById('total-ventas').textContent = datos.total_ventas;
    document.getElementById('total-vendido').textContent = `$${datos.total_vendido.toFixed(2)}`;

    if (datos.caja_abierta) {
        document.getElementById('estado-caja').textContent = 'Abierta ✅';
        document.getElementById('estado-caja').className = 'fw-bold text-success';
        document.getElementById('caja-icono').textContent = '🔓';
    } else {
        document.getElementById('estado-caja').textContent = 'Cerrada';
        document.getElementById('estado-caja').className = 'fw-bold text-danger';
        document.getElementById('caja-icono').textContent = '🔒';
    }
}
