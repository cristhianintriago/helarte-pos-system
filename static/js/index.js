/**
 * index.js
 * --------
 * Logica del dashboard principal (pagina de inicio del sistema).
 * Su unica responsabilidad es cargar y mostrar el resumen operativo del dia
 * actualizandolo automaticamente cada 30 segundos sin recargar la pagina.
 */

/**
 * El evento 'DOMContentLoaded' se dispara cuando el navegador ha terminado de
 * construir el arbol de elementos HTML (DOM). Envolver el codigo en este evento
 * garantiza que los elementos como document.getElementById() existan antes de
 * intentar acceder a ellos.
 * 
 * La funcion flecha '() => {}' es una forma moderna y compacta de definir funciones en JavaScript.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Inicializamos los iconos de Lucide al cargar la pagina.
    lucide.createIcons();

    // Cargamos el resumen inmediatamente al entrar al dashboard.
    cargarResumen();

    // setInterval ejecuta la funcion cargarResumen cada 30000ms (30 segundos).
    setInterval(cargarResumen, 30000);
});

async function cargarResumen() {
    try {
        const respuesta = await fetch('/resumen');
        const datos = await respuesta.json();

        // Actualizamos el contenido de cada indicador.
        document.getElementById('pedidos-activos').textContent = datos.pedidos_activos;
        document.getElementById('total-ventas').textContent = datos.total_ventas;
        document.getElementById('total-vendido').textContent = `$${datos.total_vendido.toFixed(2)}`;

        const estadoCaja = document.getElementById('estado-caja');
        const cajaCard = document.getElementById('caja-card-bg');
        const cajaIconWrapper = document.getElementById('caja-icono-wrapper');
        const cajaIcon = document.getElementById('caja-lucide-icon');

        if (datos.caja_abierta) {
            estadoCaja.textContent = 'Abierta';
            estadoCaja.className = 'fw-800 mb-0 mt-2 text-success';
            cajaCard.style.background = 'linear-gradient(135deg, #fff 0%, var(--menta-light) 100%)';
            cajaIconWrapper.className = 'p-3 rounded-4 bg-white shadow-sm text-success';
            cajaIcon.setAttribute('data-lucide', 'unlock');
        } else {
            estadoCaja.textContent = 'Cerrada';
            estadoCaja.className = 'fw-800 mb-0 mt-2 text-danger';
            cajaCard.style.background = 'linear-gradient(135deg, #fff 0%, #fee2e2 100%)';
            cajaIconWrapper.className = 'p-3 rounded-4 bg-white shadow-sm text-danger';
            cajaIcon.setAttribute('data-lucide', 'lock');
        }

        // Importante: Refrescamos los iconos de Lucide porque cambiamos atributos data-lucide
        // o cargamos contenido nuevo dinamicamente.
        lucide.createIcons();
    } catch (error) {
        console.error('Error al cargar resumen:', error);
    }
}
