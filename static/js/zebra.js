/**
 * zebra.js
 * --------
 * Modulo de integracion con la impresora termica Zebra iMZ320 via USB.
 *
 * La iMZ320 usa el lenguaje CPCL (Comtec Printer Control Language), que es
 * diferente a ESC/POS (impresoras Epson/Star) y ZPL (etiquetas Zebra industriales).
 *
 * Por que no se puede imprimir directamente desde el navegador:
 * Los navegadores web estan aislados del hardware por seguridad. No pueden
 * acceder a puertos USB, Bluetooth o serie directamente. Para salvar esta
 * limitacion, Zebra provee el software "Zebra Browser Print", que es un
 * daemon (servicio en segundo plano) que corre localmente en el PC de caja
 * y expone una API HTTP en localhost:9100.
 *
 * Flujo de impresion:
 * 1. Este modulo consulta el daemon en http://localhost:9100/available para
 *    verificar que esta corriendo y descubrir la impresora conectada.
 * 2. Obtiene el string CPCL del servidor Flask en /pedidos/<id>/ticket/cpcl.
 * 3. Envia el CPCL al daemon con una solicitud POST a http://localhost:9100/write.
 * 4. El daemon reenvía el CPCL a la iMZ320 via USB y la impresora imprime.
 *
 * Requisito en el PC de caja:
 * Instalar "Zebra Browser Print" desde:
 * https://www.zebra.com/us/en/support-downloads/software/printer-software/browser-print.html
 * Una vez instalado, el daemon se inicia automaticamente con Windows.
 */

// URL base del daemon Zebra Browser Print corriendo localmente.
// Puerto 9100 es el estandar de Browser Print.
const ZEBRA_BROWSER_PRINT_URL = 'http://localhost:9100';

// Referencia en memoria a la impresora Zebra descubierta.
// Se cachea para no redescubrir la impresora en cada impresion.
let _impresora_zebra = null;


/**
 * Descubre la primera impresora Zebra conectada al PC via USB.
 * Si ya habia sido descubierta anteriormente, retorna la instancia cacheada.
 *
 * El endpoint /available del daemon retorna un JSON con la lista de impresoras
 * disponibles. Cada impresora tiene un campo 'connection' ('usb', 'network', 'bt').
 *
 * @returns {Object|null} Objeto impresora de Browser Print, o null si no se encontro.
 */
async function _descubrirImpresora() {
    if (_impresora_zebra) return _impresora_zebra;

    try {
        // Solicitamos la lista de impresoras disponibles al daemon local.
        const respuesta = await fetch(`${ZEBRA_BROWSER_PRINT_URL}/available`, {
            // mode: 'cors' es necesario para solicitudes cross-origin (navegador -> localhost).
            mode: 'cors'
        });

        if (!respuesta.ok) return null;

        const datos = await respuesta.json();

        // El daemon puede retornar impresoras en diferentes campos del JSON.
        // 'current' es la impresora por defecto; 'available' es la lista completa.
        const lista = datos.available || [];
        if (lista.length === 0) return null;

        // Preferimos impresoras USB sobre Bluetooth o red para mayor estabilidad.
        const usb = lista.find(p => (p.connection || '').toLowerCase() === 'usb');
        _impresora_zebra = usb || lista[0];
        return _impresora_zebra;

    } catch (err) {
        // Si el fetch falla, el daemon no esta corriendo o hay un bloqueo CORS.
        console.warn('[Zebra] No se pudo contactar a Zebra Browser Print:', err.message);
        return null;
    }
}


/**
 * Obtiene el string CPCL del ticket de un pedido desde el servidor Flask.
 * El endpoint /pedidos/<id>/ticket/cpcl retorna texto plano CPCL.
 *
 * @param {number} pedidoId - ID del pedido.
 * @returns {string|null} String CPCL listo para enviar a la impresora, o null si hubo error.
 */
async function _obtenerCPCL(pedidoId) {
    try {
        const respuesta = await fetch(`/pedidos/${pedidoId}/ticket/cpcl`);
        if (!respuesta.ok) return null;
        // El endpoint retorna text/plain, por lo que usamos .text() en lugar de .json().
        return await respuesta.text();
    } catch (err) {
        console.error('[Zebra] Error al obtener CPCL del servidor:', err);
        return null;
    }
}


/**
 * Envia el string CPCL a la impresora descubierta a traves del daemon.
 * El endpoint /write del daemon acepta un JSON con 'device' y 'data'.
 *
 * @param {Object} impresora - Objeto impresora retornado por _descubrirImpresora().
 * @param {string} cpcl      - String CPCL a enviar.
 * @returns {boolean} true si el envio fue exitoso, false si hubo error.
 */
async function _enviarAImpresora(impresora, cpcl) {
    try {
        const body = JSON.stringify({
            device: impresora,   // Objeto de la impresora descubierta.
            data:   cpcl         // El paquete CPCL a imprimir.
        });

        const respuesta = await fetch(`${ZEBRA_BROWSER_PRINT_URL}/write`, {
            method:  'POST',
            mode:    'cors',
            headers: { 'Content-Type': 'application/json' },
            body
        });

        return respuesta.ok;
    } catch (err) {
        console.error('[Zebra] Error al enviar a la impresora:', err);
        return false;
    }
}


/**
 * Funcion publica principal del modulo.
 * Orquesta el flujo completo: descubrir impresora, obtener CPCL y enviar a imprimir.
 *
 * Si Zebra Browser Print no esta corriendo, ofrece descargar el PDF como respaldo.
 * Esto garantiza que el cajero siempre pueda obtener el ticket aunque la impresora
 * no este disponible (por ejemplo, si la apago por error).
 *
 * @param {number} pedidoId - ID del pedido a imprimir.
 */
async function imprimirTicketZebra(pedidoId) {
    // Paso 1: verificar que el daemon este corriendo y la impresora disponible.
    mostrarToast('Conectando con impresora...', 'info');

    const impresora = await _descubrirImpresora();

    if (!impresora) {
        // El daemon no esta corriendo o no hay impresora USB conectada.
        // Mostramos un mensaje explicativo y ofrecemos el PDF como alternativa.
        const usarPDF = confirm(
            'No se encontro la impresora Zebra.\n\n' +
            'Posibles causas:\n' +
            '- Zebra Browser Print no esta instalado o no esta corriendo.\n' +
            '- La impresora esta apagada o desconectada.\n\n' +
            'Descargar el ticket en PDF?'
        );
        if (usarPDF) {
            window.open(`/pedidos/${pedidoId}/ticket`, '_blank');
        }
        return;
    }

    // Paso 2: obtener el CPCL del servidor Flask.
    const cpcl = await _obtenerCPCL(pedidoId);

    if (!cpcl) {
        mostrarToast('Error al generar el ticket. Intenta de nuevo.', 'danger');
        return;
    }

    // Paso 3: enviar el CPCL a la impresora.
    const exito = await _enviarAImpresora(impresora, cpcl);

    if (exito) {
        mostrarToast('Ticket enviado a la impresora.', 'success');
    } else {
        mostrarToast('Error al imprimir. Verifica que la impresora este encendida.', 'danger');
    }
}
