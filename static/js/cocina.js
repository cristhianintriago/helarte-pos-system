/**
 * cocina.js
 * ---------
 * Logica del Kitchen Display System (KDS): la pantalla de comandas de la cocina.
 *
 * Esta pantalla se comunica con el servidor usando WebSockets a traves de socket.io.
 *
 * Que es un WebSocket:
 * A diferencia de HTTP (donde el cliente siempre inicia la comunicacion "pide -> recibe"),
 * un WebSocket establece un canal de comunicacion BIDIRECCIONAL y PERSISTENTE.
 * Una vez abierta la conexion, tanto el servidor como el cliente pueden enviar mensajes
 * en cualquier momento, sin necesidad de que el otro lo solicite primero.
 *
 * Flujo:
 * 1. La tableta de cocina se conecta al servidor via WebSocket al cargar la pagina.
 * 2. Cuando un cajero crea un pedido, el servidor emite el evento 'actualizar_cocina'.
 * 3. Este archivo recibe el evento y llama a cargarComandas() de inmediato.
 * 4. La pantalla se actualiza en menos de un segundo sin haber recargado nada.
 */

// Variable para almacenar el HTML de la ultima renderizacion.
// Se compara con el nuevo HTML antes de actualizar el DOM para evitar re-renders innecesarios.
let ultimaSincronizacion = null;
let htmlAnterior = "";

// ==========================================
// CONFIGURACION DE WEBSOCKETS
// ==========================================

// io() crea la conexion WebSocket con el servidor. La URL la detecta automaticamente
// del dominio actual donde esta alojada la aplicacion.
const socket = io();

// El evento 'connect' se dispara cuando la conexion WebSocket se establece correctamente.
// Mostramos un badge verde en la pantalla para que el cocinero sepa que esta en linea.
socket.on('connect', () => {
    const badge = document.getElementById('estado-conexion');
    if (badge) {
        badge.textContent = 'En Linea';
        badge.className = 'badge bg-success fs-6';
    }
});

// El evento 'disconnect' se dispara si se pierde la conexion (corte de red, reinicio del servidor).
// Mostramos un badge rojo para alertar al cocinero.
socket.on('disconnect', () => {
    const badge = document.getElementById('estado-conexion');
    if (badge) {
        badge.textContent = 'Desconectado';
        badge.className = 'badge bg-danger fs-6';
    }
});

// El evento 'actualizar_cocina' es emitido desde el servidor (pedidos.py y caja.py)
// cada vez que hay un cambio relevante: nuevo pedido, cambio de estado o cancelacion.
socket.on('actualizar_cocina', (data) => {
    // Recargamos la lista de comandas desde el servidor para mostrar el estado actualizado.
    cargarComandas();

    // Si el evento corresponde a un pedido nuevo (no a un cambio de estado),
    // lanzamos una alerta verbal usando la API de sintesis de voz del navegador.
    if (data.mensaje === 'Nuevo pedido') {
        // SpeechSynthesisUtterance crea un objeto de "texto para hablar".
        // Es una API nativa del navegador; no requiere instalacion ni archivos de audio.
        // NOTA: los navegadores requieren que el usuario haya interactuado con la pagina
        // al menos una vez antes de permitir reproduccion de audio. El cocinero debe
        // tocar la pantalla al iniciar su turno para habilitar esta funcionalidad.
        const speech = new SpeechSynthesisUtterance("!Llego una nueva orden!");
        speech.lang = 'es-EC';  // Idioma espanol - Ecuador para la pronunciacion correcta.
        speech.rate = 1.1;       // Velocidad de habla ligeramente acelerada.
        window.speechSynthesis.speak(speech);
    }
});


// ==========================================
// INICIALIZACION AL CARGAR LA PAGINA
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    // Actualizamos el reloj al cargar y luego cada 60 segundos.
    actualizarReloj();
    setInterval(actualizarReloj, 60000);

    // Carga inicial de las comandas. Las actualizaciones posteriores
    // son manejadas por los eventos WebSocket (no por polling).
    cargarComandas();
});


// ==========================================
// FUNCIONES DE UTILIDAD
// ==========================================

/**
 * Actualiza el reloj digital visible en la pantalla de cocina.
 * padStart(2, '0') agrega un cero a la izquierda si el numero tiene un solo digito.
 * Ejemplo: 9 -> "09", 14 -> "14".
 */
function actualizarReloj() {
    const reloj = document.getElementById('reloj-cocina');
    if (reloj) {
        const ahora = new Date();
        reloj.textContent =
            ahora.getHours().toString().padStart(2, '0') + ':' +
            ahora.getMinutes().toString().padStart(2, '0');
    }
}


/**
 * Solicita la lista de pedidos activos al servidor y los renderiza en pantalla.
 * Esta funcion se llama una vez al cargar la pagina y luego cada vez que llega
 * un evento WebSocket 'actualizar_cocina'.
 */
async function cargarComandas() {
    try {
        const respuesta = await fetch('/pedidos/');
        if (!respuesta.ok) throw new Error('Error al conectar con el servidor');

        const pedidos = await respuesta.json();
        renderizarComandas(pedidos);
    } catch (err) {
        // Si la solicitud HTTP falla (sin conexion) y el socket tambien esta desconectado,
        // actualizamos el badge de estado para alertar al cocinero.
        const badge = document.getElementById('estado-conexion');
        if (badge && socket.disconnected) {
            badge.textContent = 'Desconectado';
            badge.className = 'badge bg-danger fs-6';
        }
    }
}


/**
 * Construye y actualiza el HTML con las tarjetas de comandas visibles en cocina.
 * Solo muestra pedidos en estado 'pendiente' o 'en_proceso' (los que requieren accion).
 *
 * Optimizacion: compara el HTML nuevo con el anterior antes de actualizar el DOM.
 * Modificar el DOM es una operacion costosa en el navegador. Si nada cambio,
 * no hacemos el reemplazo para evitar parpadeos y consumo de recursos innecesario.
 *
 * @param {Array} pedidos - Lista de objetos pedido retornada por el servidor.
 */
function renderizarComandas(pedidos) {
    const contenedor = document.getElementById('lista-comandas');
    if (!contenedor) return;

    // Filtramos: solo pedidos que requieren atencion de la cocina.
    const pedidosCocina = pedidos.filter(p => ['pendiente', 'en_proceso'].includes(p.estado));

    // Si no hay pedidos activos, mostramos un mensaje de "todo limpio".
    if (pedidosCocina.length === 0) {
        const htmlVacio = `
            <div class="col-12 text-center text-muted" style="margin-top: 15vh;">
                <i class="bi bi-check-circle" style="font-size: 5rem; color: var(--borde);"></i>
                <h4 class="mt-3">Todo limpio</h4>
                <p>No hay pedidos pendientes por preparar.</p>
            </div>
        `;
        if (htmlAnterior !== htmlVacio) {
            contenedor.innerHTML = htmlVacio;
            htmlAnterior = htmlVacio;
        }
        return;
    }

    // Ordenamos: los pedidos 'en_proceso' aparecen primero (tienen prioridad visual),
    // y dentro del mismo estado, el que lleva mas tiempo (ID menor) va primero.
    pedidosCocina.sort((a, b) => {
        if (a.estado === b.estado) return a.id - b.id;
        if (a.estado === 'en_proceso') return -1;
        return 1;
    });

    // Construimos el HTML de cada tarjeta de comanda usando template literals (backticks).
    // Los template literals permiten incrustar expresiones JavaScript con ${} dentro de strings.
    const html = pedidosCocina.map(p => {
        // Generamos la lista de items del pedido (detalles).
        const detalles = p.detalles.map(d => `
            <li class="list-group-item px-2 py-1 d-flex justify-content-between border-0 bg-transparent">
                <span class="fw-bold fs-5 text-dark">${d.cantidad}x ${d.producto}</span>
            </li>
            ${d.sabor ? `<li class="list-group-item px-2 py-0 border-0 text-muted ms-3 bg-transparent" style="font-size: 1.1rem;"><i class="bi bi-arrow-return-right"></i> ${d.sabor}</li>` : ''}
        `).join('');

        // Configuramos el color y texto del boton segun el estado actual del pedido.
        const isPendiente  = p.estado === 'pendiente';
        const colorHeader  = isPendiente ? 'bg-dark text-white'    : 'bg-primary text-white';
        const txtBoton     = isPendiente ? 'Empezar a Preparar'    : 'Marcar Listo';
        const iconoBoton   = isPendiente ? 'bi-hand-index-thumb'   : 'bi-check-all';
        const colorBoton   = isPendiente ? 'btn-outline-primary'   : 'btn-success';
        // El siguiente estado en el flujo: pendiente -> en_proceso -> preparado.
        const nuevoEstado  = isPendiente ? 'en_proceso'            : 'preparado';

        return `
            <div class="col">
                <div class="card h-100 shadow-sm border-0" style="border-radius: 16px; overflow: hidden; background: #fff;">
                    <div class="card-header ${colorHeader} d-flex justify-content-between align-items-center py-3 border-0">
                        <h3 class="mb-0 fw-bold">#${p.numero_pedido || p.id}</h3>
                        <span class="badge bg-light text-dark fs-6">${p.tipo.toUpperCase()}</span>
                    </div>
                    <div class="card-body p-2" style="background: #f9f9f9;">
                        <div class="text-muted small mb-2 ps-2 fs-6"><i class="bi bi-person"></i> ${p.cliente_nombre || 'Cliente'}</div>
                        <ul class="list-group list-group-flush mb-3">
                            ${detalles}
                        </ul>
                    </div>
                    <div class="card-footer bg-white border-0 pt-0 pb-3 px-3">
                        <button class="btn ${colorBoton} w-100 fs-5 py-3 fw-bold" onclick="cambiarEstadoKDS(${p.id}, '${nuevoEstado}')" style="border-radius: 12px;">
                            <i class="bi ${iconoBoton}"></i> ${txtBoton}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Solo actualizamos el DOM si el HTML es diferente al anterior.
    if (htmlAnterior !== html) {
        contenedor.innerHTML = html;
        htmlAnterior = html;
    }
}


/**
 * Actualiza el estado de un pedido al presionar uno de los botones de la comanda.
 * Si el nuevo estado es 'preparado', pide confirmacion antes de enviar.
 *
 * navigator.vibrate(20): genera una vibracion corta en dispositivos moviles o tablets
 * como retroalimentacion tactil al presionar el boton.
 *
 * @param {number} pedidoId   - ID del pedido a actualizar.
 * @param {string} nuevoEstado - El estado al que se quiere mover el pedido.
 */
async function cambiarEstadoKDS(pedidoId, nuevoEstado) {
    if (nuevoEstado === 'preparado') {
        const confirmar = confirm('Confirmas que este pedido ya esta preparado?');
        if (!confirmar) return;
    }

    // Vibracion de retroalimentacion en dispositivos que lo soporten (tablets Android).
    if (navigator.vibrate) navigator.vibrate(20);

    try {
        // Enviamos la solicitud PUT con el nuevo estado en el cuerpo JSON.
        await fetch(`/pedidos/${pedidoId}/estado`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ estado: nuevoEstado })
        });
        // Recargamos las comandas para reflejar el cambio inmediatamente.
        cargarComandas();
    } catch (err) {
        console.error('No se pudo actualizar estado', err);
    }
}
