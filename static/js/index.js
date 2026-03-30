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
    // Cargamos el resumen inmediatamente al entrar al dashboard.
    cargarResumen();

    // setInterval ejecuta la funcion cargarResumen cada 30000ms (30 segundos).
    // Esto mantiene los indicadores del dashboard actualizados sin necesidad de recargar la pagina.
    setInterval(cargarResumen, 30000);
});

/**
 * Consulta el endpoint /resumen del servidor y actualiza los indicadores del dashboard.
 * Usa async/await para manejar la llamada HTTP de forma asincrona (sin bloquear el navegador).
 *
 * Por que async/await:
 * Las solicitudes de red (fetch) son operaciones lentas. Si el codigo fuera sincronico,
 * el navegador se congelaria esperando la respuesta. async/await permite que el navegador
 * continue respondiendo al usuario mientras espera la respuesta del servidor.
 */
async function cargarResumen() {
    // fetch() realiza una solicitud HTTP GET al endpoint /resumen.
    // await detiene la ejecucion de esta funcion hasta que llegue la respuesta,
    // pero NO bloquea el resto del navegador.
    const respuesta = await fetch('/resumen');

    // .json() convierte el cuerpo de la respuesta de texto JSON a un objeto JavaScript.
    const datos = await respuesta.json();

    // Actualizamos el contenido de cada indicador con los datos recibidos del servidor.
    document.getElementById('pedidos-activos').textContent = datos.pedidos_activos;
    document.getElementById('total-ventas').textContent = datos.total_ventas;

    // toFixed(2) formatea el numero con exactamente 2 decimales. Ej: 120.5 -> "120.50"
    document.getElementById('total-vendido').textContent = `$${datos.total_vendido.toFixed(2)}`;

    // Actualizamos el indicador visual del estado de la caja segun lo que retorno el servidor.
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
