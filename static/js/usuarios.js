let todosLosUsuarios = [];

document.addEventListener("DOMContentLoaded", cargarUsuarios);

async function cargarUsuarios() {
  const respuesta = await fetch("/usuarios/api");
  todosLosUsuarios = await respuesta.json();
  renderizarTabla();
}

function renderizarTabla() {
  const tbody = document.getElementById("tabla-usuarios");
  tbody.innerHTML = "";

  const badges = {
    root: "bg-danger",
    admin: "bg-warning text-dark",
    empleado: "bg-secondary",
  };

  todosLosUsuarios.forEach((u) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
            <td class="fw-bold"><i class="bi bi-person-circle"></i> ${u.username}</td>
            <td><span class="badge ${badges[u.rol]}">${u.rol}</span></td>
            <td>
                ${
                  u.rol !== "root"
                    ? `
                <button class="btn btn-sm btn-outline-dark me-1" onclick="abrirEditar(${u.id})">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="eliminarUsuario(${u.id}, '${u.username}')">
                    <i class="bi bi-trash"></i>
                </button>`
                    : '<span class="text-muted small">Protegido</span>'
                }
            </td>`;
    tbody.appendChild(tr);
  });
}

function abrirEditar(id) {
  const usuario = todosLosUsuarios.find((u) => u.id === id);
  document.getElementById("usuario-id").value = usuario.id;
  document.getElementById("usuario-username").value = usuario.username;
  document.getElementById("usuario-password").value = "";
  document.getElementById("usuario-rol").value = usuario.rol;
  document.getElementById("modal-titulo").textContent = "Editar Usuario";
  new bootstrap.Modal(document.getElementById("modal-usuario")).show();
}

async function guardarUsuario() {
  const id = document.getElementById("usuario-id").value;
  const datos = {
    username: document.getElementById("usuario-username").value.trim(),
    password: document.getElementById("usuario-password").value,
    rol: document.getElementById("usuario-rol").value,
  };

  if (!datos.username) {
    mostrarToast("Ingresa un nombre de usuario", "warning");
    return;
  }
  if (!id && !datos.password) {
    mostrarToast("Ingresa una contraseña", "warning");
    return;
  }

  const url = id ? `/usuarios/api/${id}` : "/usuarios/api";
  const metodo = id ? "PUT" : "POST";

  const respuesta = await fetch(url, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });

  const resultado = await respuesta.json();

  if (respuesta.ok) {
    bootstrap.Modal.getInstance(
      document.getElementById("modal-usuario"),
    ).hide();
    mostrarToast(resultado.mensaje, "success");
    document.getElementById("usuario-id").value = "";
    document.getElementById("modal-titulo").textContent = "Nuevo Usuario";
    cargarUsuarios();
  } else {
    mostrarToast(resultado.error, "danger");
  }
}

async function eliminarUsuario(id, username) {
  if (!confirm(`¿Eliminar al usuario ${username}?`)) return;

  const respuesta = await fetch(`/usuarios/api/${id}`, { method: "DELETE" });
  const resultado = await respuesta.json();

  if (respuesta.ok) {
    mostrarToast(resultado.mensaje, "success");
    cargarUsuarios();
  } else {
    mostrarToast(resultado.error, "danger");
  }
}
