/**
 * usuarios.js
 * -----------
 * Logica del modulo de gestion de usuarios del sistema.
 * Permite listar, crear, editar y eliminar cuentas de usuario.
 *
 * La variable 'todosLosUsuarios' actua como un "estado local" del modulo:
 * almacena en memoria la lista de usuarios para poder buscar por ID
 * sin tener que hacer una nueva solicitud al servidor cada vez.
 *
 * Patron CRUD en este modulo:
 * - Read:   GET /usuarios/api          -> cargarUsuarios()
 * - Create: POST /usuarios/api         -> guardarUsuario() (sin ID)
 * - Update: PUT /usuarios/api/<id>     -> guardarUsuario() (con ID)
 * - Delete: DELETE /usuarios/api/<id>  -> eliminarUsuario()
 */

// Estado local del modulo: lista de usuarios cargados desde el servidor.
let todosLosUsuarios = [];

// Cargamos los usuarios al terminar de construir el DOM.
document.addEventListener("DOMContentLoaded", cargarUsuarios);

/**
 * Solicita la lista de usuarios al servidor y la almacena en el estado local.
 * Luego llama a renderizarTabla() para mostrarlos en la pantalla.
 */
async function cargarUsuarios() {
    const respuesta      = await fetch("/usuarios/api");
    todosLosUsuarios     = await respuesta.json();
    renderizarTabla();
}

/**
 * Construye y renderiza la tabla HTML con la lista de usuarios actuales.
 * Por cada usuario se muestran su nombre, rol y botones de accion.
 * El usuario 'root' no tiene botones de edicion/eliminacion (esta protegido).
 */
function renderizarTabla() {
    const tbody = document.getElementById("tabla-usuarios");
    // Vaciamos la tabla antes de renderizar para evitar duplicados.
    tbody.innerHTML = "";

    // Mapa de clases CSS de Bootstrap para colorear el badge de cada rol.
    const badges = {
        root:     "bg-danger",
        admin:    "bg-warning text-dark",
        empleado: "bg-secondary",
    };

    // Por cada usuario creamos una fila <tr> y la agregamos al <tbody>.
    todosLosUsuarios.forEach((u) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="fw-bold"><i class="bi bi-person-circle"></i> ${u.username}</td>
            <td><span class="badge ${badges[u.rol]}">${u.rol}</span></td>
            <td>
                ${u.rol !== "root"
                    // Si no es root, mostramos los botones de edicion y eliminacion.
                    ? `<button class="btn btn-sm btn-outline-dark me-1" onclick="abrirEditar(${u.id})">
                           <i class="bi bi-pencil"></i>
                       </button>
                       <button class="btn btn-sm btn-outline-danger" onclick="eliminarUsuario(${u.id}, '${u.username}')">
                           <i class="bi bi-trash"></i>
                       </button>`
                    // Si es root, mostramos un texto "Protegido" en lugar de botones.
                    : '<span class="text-muted small">Protegido</span>'
                }
            </td>`;
        tbody.appendChild(tr);
    });
}

/**
 * Abre el modal de edicion pre-llenado con los datos del usuario seleccionado.
 * Busca el usuario en el estado local (todosLosUsuarios) por su ID.
 *
 * Array.find() retorna el primer elemento que cumple la condicion,
 * similar a un SELECT WHERE en SQL.
 *
 * @param {number} id - ID del usuario a editar.
 */
function abrirEditar(id) {
    const usuario = todosLosUsuarios.find((u) => u.id === id);
    // Llenamos los campos del formulario con los datos actuales del usuario.
    document.getElementById("usuario-id").value       = usuario.id;
    document.getElementById("usuario-username").value = usuario.username;
    document.getElementById("usuario-password").value = "";  // El campo de clave queda vacio por seguridad.
    document.getElementById("usuario-rol").value      = usuario.rol;
    document.getElementById("modal-titulo").textContent = "Editar Usuario";
    // Instanciamos y mostramos el modal de Bootstrap manualmente desde JavaScript.
    new bootstrap.Modal(document.getElementById("modal-usuario")).show();
}

/**
 * Guarda los datos del formulario del modal como una creacion o edicion segun el contexto.
 * Si el campo 'usuario-id' tiene valor, es una edicion (PUT). Si esta vacio, es una creacion (POST).
 * Esta logica permite reutilizar el mismo formulario para ambas operaciones.
 */
async function guardarUsuario() {
    const id    = document.getElementById("usuario-id").value;
    const datos = {
        username: document.getElementById("usuario-username").value.trim(),
        password: document.getElementById("usuario-password").value,
        rol:      document.getElementById("usuario-rol").value,
    };

    // Validaciones basicas en el frontend antes de enviar al servidor.
    if (!datos.username) {
        mostrarToast("Ingresa un nombre de usuario", "warning");
        return;
    }
    // La contrasena es obligatoria solo al crear un usuario nuevo (cuando no tiene ID).
    if (!id && !datos.password) {
        mostrarToast("Ingresa una contrasena", "warning");
        return;
    }

    // Determinamos la URL y el metodo HTTP segun si estamos creando o editando.
    const url    = id ? `/usuarios/api/${id}` : "/usuarios/api";
    const metodo = id ? "PUT" : "POST";

    const respuesta = await fetch(url, {
        method:  metodo,
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(datos),
    });

    const resultado = await respuesta.json();

    if (respuesta.ok) {
        // Si fue exitoso: cerramos el modal, mostramos confirmacion y recargamos la tabla.
        bootstrap.Modal.getInstance(document.getElementById("modal-usuario")).hide();
        mostrarToast(resultado.mensaje, "success");
        // Limpiamos el campo ID para que el modal quede listo para una nueva creacion.
        document.getElementById("usuario-id").value = "";
        document.getElementById("modal-titulo").textContent = "Nuevo Usuario";
        cargarUsuarios();
    } else {
        // Si el servidor respondio con error, mostramos el mensaje de error.
        mostrarToast(resultado.error, "danger");
    }
}

/**
 * Solicita confirmacion y luego elimina un usuario del sistema.
 *
 * @param {number} id       - ID del usuario a eliminar.
 * @param {string} username - Nombre del usuario (para el mensaje de confirmacion).
 */
async function eliminarUsuario(id, username) {
    // confirm() muestra un cuadro de dialogo nativo del navegador. Retorna true o false.
    if (!confirm(`Eliminar al usuario ${username}?`)) return;

    const respuesta = await fetch(`/usuarios/api/${id}`, { method: "DELETE" });
    const resultado = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(resultado.mensaje, "success");
        cargarUsuarios();  // Recargamos la tabla para que desaparezca el usuario eliminado.
    } else {
        mostrarToast(resultado.error, "danger");
    }
}
