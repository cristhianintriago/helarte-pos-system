// Función global de toast reutilizable en todas las páginas
// tipo: 'success' | 'danger' | 'warning' | 'info'
function mostrarToast(mensaje, tipo = "success") {
  const colores = {
    success: "bg-success text-white",
    danger: "bg-danger text-white",
    warning: "bg-warning text-dark",
    info: "bg-dark text-white",
  };

  const iconos = {
    success: "✅",
    danger: "❌",
    warning: "⚠️",
    info: "ℹ️",
  };

  const toastEl = document.getElementById("toast-notif");
  const mensajeEl = document.getElementById("toast-mensaje");

  // Limpiamos clases anteriores y aplicamos el color nuevo
  toastEl.className = `toast align-items-center border-0 ${colores[tipo]}`;
  mensajeEl.textContent = `${iconos[tipo]} ${mensaje}`;

  // Mostramos el toast con Bootstrap
  const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
  toast.show();
}
