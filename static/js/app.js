/**
 * app.js
 * ------
 * Archivo de utilidades globales compartidas entre todas las paginas del sistema.
 * Se carga en el layout base (base.html), por lo que sus funciones estan disponibles
 * en cualquier modulo (caja.js, pedidos.js, reportes.js, etc.).
 *
 * Un "Toast" es una notificacion emergente pequena y temporal que aparece
 * brevemente en la pantalla para informar al usuario del resultado de una accion,
 * sin interrumpir su flujo de trabajo (a diferencia de un alert() que bloquea la pantalla).
 */

/**
 * Muestra una notificacion tipo Toast con un mensaje y un color segun el tipo.
 *
 * @param {string} mensaje - Texto que se mostrara en la notificacion.
 * @param {string} tipo    - Categoria visual: 'success', 'danger', 'warning' o 'info'.
 *
 * Funcionamiento:
 * 1. Se selecciona la clase CSS de Bootstrap y el icono segun el tipo.
 * 2. Se actualiza el elemento HTML del toast con el mensaje y las clases.
 * 3. Se instancia el componente Bootstrap.Toast y se llama a .show().
 * 4. Bootstrap oculta el toast automaticamente despues de 3000ms (3 segundos).
 */
function mostrarToast(mensaje, tipo = "success") {
  // Mapa de clases CSS de Bootstrap para cada tipo de notificacion.
  const colores = {
    success: "bg-success text-white",
    danger:  "bg-danger text-white",
    warning: "bg-warning text-dark",
    info:    "bg-dark text-white",
  };

  // Iconos visuales complementarios para cada tipo de notificacion.
  const iconos = {
    success: "✅",
    danger:  "❌",
    warning: "⚠️",
    info:    "ℹ️",
  };

  // Obtenemos referencias a los elementos HTML del toast definidos en base.html.
  const toastEl   = document.getElementById("toast-notif");
  const mensajeEl = document.getElementById("toast-mensaje");

  // Reemplazamos las clases CSS del toast para aplicar el color correcto.
  // Esto limpia cualquier color de una notificacion anterior.
  toastEl.className = `toast align-items-center border-0 ${colores[tipo]}`;

  // Actualizamos el texto del mensaje combinando el icono y el mensaje recibido.
  mensajeEl.textContent = `${iconos[tipo]} ${mensaje}`;

  // Instanciamos el componente Toast de Bootstrap y lo mostramos.
  // delay: 3000 indica que desaparecera a los 3 segundos automaticamente.
  const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
  toast.show();
}
