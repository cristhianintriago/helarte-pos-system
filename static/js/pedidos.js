/**
 * pedidos.js
 * ----------
 * Logica del modulo de toma de pedidos (punto de venta).
 *
 * Integracion con impresora termica Zebra iMZ320:
 * El boton "Ticket" en la lista de pedidos activos llama a imprimirTicketZebra(),
 * que esta definida en zebra.js (cargado globalmente en base.html).
 * Si Zebra Browser Print no esta disponible, zebra.js ofrece el PDF como respaldo.
 *
 * Este es el archivo mas complejo del frontend. Gestiona:
 * 1. El catalogo de productos con filtros y busqueda en tiempo real.
 * 2. El carrito activo (pedidoActual) con sabores, cantidades y totales.
 * 3. El flujo de checkout con validaciones por metodo de pago.
 * 4. La impresion del ticket PDF.
 * 5. Una cola de pedidos offline (para cuando no hay conexion a internet).
 *
 * Estado del modulo (variables globales):
 * - pedidoActual: el carrito de compras activo en memoria.
 * - productosCatalogo: lista completa del menu cargada desde el servidor.
 * - categoriaActual: filtro de categoria activo en el catalogo.
 * - itemPendienteSabor: guarda temporalmente el producto cuya seleccion de sabor esta abierta.
 * - formaPagoActual: 'efectivo', 'transferencia' o 'mixto'.
 * - siguienteNumeroPedido: numero visual del proximo ticket a generar.
 * - tapTimers: Map que almacena los timers del detector de doble-tap.
 */

// ==========================================
// ESTADO GLOBAL DEL MODULO
// ==========================================

// pedidoActual es el "carrito" en memoria. Se limpia despues de confirmar cada pedido.
let pedidoActual = {
    tipo: 'local',      // 'local' o 'delivery'.
    productos: []       // Lista de items: { producto_id, nombre, precio, cantidad, sabor }.
};

let productosCatalogo     = [];           // Cache del catalogo de productos del servidor.
let categoriaActual       = 'todas';      // Filtro de categoria activo.
let itemPendienteSabor    = null;         // Producto que espera que el cajero seleccione su sabor.
let formaPagoActual       = 'efectivo';   // Metodo de pago seleccionado en el checkout.
let siguienteNumeroPedido = 1;           // Numero visual del proximo ticket.

// tapTimers: Map que guarda los temporizadores para detectar si un clic es simple o doble.
// Map es una estructura clave-valor de JavaScript, similar a un diccionario en Python.
const tapTimers   = new Map();
const TAP_DELAY_MS = 260;   // Tiempo en ms para esperar y determinar si el tap es doble.


// ==========================================
// INICIALIZACION
// ==========================================

document.addEventListener('DOMContentLoaded', async () => {
    // Conectamos el buscador del catalogo al filtro en tiempo real.
    document.getElementById('buscador-carta')?.addEventListener('input', aplicarFiltrosCatalogo);
    
    // Auto-completado de cliente para facturacion
    const inputIdent = document.getElementById('cliente-identificacion');
    if (inputIdent) {
        inputIdent.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            // Buscar solo cuando tenga longitud valida para Ecuador (10 Cedula, 13 RUC)
            if (val.length === 10 || val.length === 13) {
                buscarDatosCliente(val);
            }
        });
    }

    // Cargamos en paralelo el catalogo, los pedidos activos y el numero del siguiente ticket.
    await Promise.all([
        cargarProductos(),
        cargarPedidosActivos(),
        cargarSiguienteNumeroPedido()
    ]);

    // Refrescamos los pedidos activos cada 5 segundos de forma periodica.
    // Esto sirve como respaldo en caso de que los WebSockets no esten disponibles.
    setInterval(cargarPedidosActivos, 5000);

    // Establecemos los valores de UI por defecto.
    setFormaPago('efectivo');
    setTipo('local');
});


// ==========================================
// CARGA DE DATOS
// ==========================================

/**
 * Obtiene el numero del proximo ticket desde el servidor y lo muestra en la pantalla.
 * Este numero se incrementa en el servidor cada vez que se crea un pedido.
 */
async function cargarSiguienteNumeroPedido() {
    try {
        const respuesta = await fetch('/pedidos/contador');
        if (!respuesta.ok) return;

        const data               = await respuesta.json();
        siguienteNumeroPedido    = Number(data.siguiente_numero || 1);
        actualizarEtiquetaNumeroPedido();
    } catch (error) {
        console.error('No se pudo cargar contador de pedidos', error);
    }
}

/**
 * Busca datos historicos del cliente para autocompletar el modulo de facturacion.
 */
async function buscarDatosCliente(identificacion) {
    try {
        const resp = await fetch(`/pedidos/cliente/${identificacion}`);
        if (!resp.ok) return;
        const data = await resp.json();
        
        if (data.encontrado) {
            if (data.nombre) document.getElementById('cliente-razon-social').value = data.nombre;
            if (data.correo) document.getElementById('cliente-correo').value = data.correo;
            if (data.direccion) document.getElementById('cliente-direccion-sri').value = data.direccion;
            if (data.telefono) document.getElementById('cliente-telefono-sri').value = data.telefono;
            mostrarToast('Datos del cliente cargados del historial', 'success');
        }
    } catch (e) {
        console.error("Error buscando cliente", e);
    }
}

/**
 * Actualiza todos los elementos del DOM que muestran el numero del proximo ticket.
 * Hay dos lugares: la pantalla principal y el modal de checkout.
 */
function actualizarEtiquetaNumeroPedido() {
    const etiquetas = [
        document.getElementById('numero-pedido-actual'),
        document.getElementById('numero-pedido-checkout')
    ];

    etiquetas.forEach((etiqueta) => {
        if (etiqueta) etiqueta.textContent = String(siguienteNumeroPedido);
    });
}

/**
 * Descarga el catalogo de productos del servidor y actualiza la vista del menu.
 */
async function cargarProductos() {
    try {
        const respuesta = await fetch('/productos/');
        if (!respuesta.ok) {
            throw new Error(`No se pudo cargar catalogo (HTTP ${respuesta.status})`);
        }

        productosCatalogo = await respuesta.json();
        renderizarFiltros(productosCatalogo);
        aplicarFiltrosCatalogo();
    } catch (error) {
        console.error(error);
        mostrarToast('No se pudo cargar el catalogo de productos', 'danger');
    }
}


// ==========================================
// FILTROS DEL CATALOGO
// ==========================================

/**
 * Construye dinamicamente los botones de filtro de categoria.
 * Se usa Set para obtener categorias unicas del catalogo sin repetidos.
 */
function renderizarFiltros(productos) {
    const categorias = [...new Set(productos.map((p) => p.categoria))];
    const contenedor = document.getElementById('filtros');
    if (!contenedor) return;

    // Eliminamos los filtros dinamicos anteriores para no acumular duplicados.
    contenedor.querySelectorAll('.dinamico').forEach((btn) => btn.remove());

    categorias.forEach((cat) => {
        const btn     = document.createElement('button');
        btn.className = 'btn btn-sm filtro-btn dinamico px-3 text-nowrap';
        btn.textContent = cat;
        btn.onclick   = (event) => filtrarCategoria(cat, event);
        contenedor.appendChild(btn);
    });
}

/**
 * Cambia la categoria activa y aplica los filtros al catalogo.
 * @param {string} categoria - Nombre de la categoria seleccionada.
 * @param {Event}  event     - Evento del clic para marcar el boton como activo.
 */
function filtrarCategoria(categoria, event) {
    categoriaActual = categoria;
    document.querySelectorAll('.filtro-btn').forEach((b) => {
        b.classList.remove('activo');
    });

    const objetivo = event?.target || document.querySelector(`#filtros .filtro-btn`);
    if (objetivo) {
        objetivo.classList.add('activo');
    }

    aplicarFiltrosCatalogo();
}

/**
 * Filtra el catalogo en memoria segun la categoria activa y el texto del buscador.
 * El filtrado es instantaneo porque se hace sobre los datos ya cargados, sin peticiones al servidor.
 */
function aplicarFiltrosCatalogo() {
    const texto = (document.getElementById('buscador-carta')?.value || '').trim().toLowerCase();

    const productos = productosCatalogo.filter((p) => {
        const coincideCategoria = categoriaActual === 'todas' || p.categoria === categoriaActual;
        const sabores           = (p.sabores || []).map((s) => s.nombre).join(' ').toLowerCase();
        const coincideTexto     =
            !texto ||
            p.nombre.toLowerCase().includes(texto)    ||
            p.categoria.toLowerCase().includes(texto) ||
            sabores.includes(texto);

        return coincideCategoria && coincideTexto;
    });

    renderizarProductos(productos);
}


// ==========================================
// RENDERIZADO DEL MENU
// ==========================================

/**
 * Dibuja las tarjetas del catalogo de productos en la pantalla.
 * Las tarjetas usan el detector de taps para distinguir entre tap simple y doble.
 * Los productos no disponibles aparecen visualmente desactivados (clase CSS 'agotado').
 */
function renderizarProductos(productos) {
    const contenedor = document.getElementById('lista-productos');
    if (!contenedor) return;

    contenedor.innerHTML = '';

    if (!productos.length) {
        contenedor.innerHTML = `
            <div class="col-12">
                <div class="text-center text-muted py-4">No hay productos para este filtro.</div>
            </div>`;
        return;
    }

    productos.forEach((p) => {
        const col = document.createElement('div');
        col.className = 'col-6 col-md-4 col-lg-3';

        const tieneSabores = (p.sabores || []).length > 0;

        // Usamos Bootstrap Icon (CSS puro) para el placeholder para evitar conflictos
        // con lucide.createIcons() que puede alterar el DOM y romper los onclick handlers.
        const img = p.imagen_url
            ? `<img src="${p.imagen_url}" alt="${p.nombre}">`
            : `<div class="producto-card__placeholder">
                 <i class="bi bi-cup-straw"></i>
               </div>`;

        const nombreSeguro = p.nombre.replace(/'/g, "\\'");

        col.innerHTML = `
            <div class="producto-card ${!p.disponible ? 'agotado' : ''}"
                 onclick="${p.disponible ? `agregarProducto(${p.id}, '${nombreSeguro}', ${p.precio}, this)` : ''}">
                ${img}
                <div class="card-body">
                    <div>
                        <div class="titulo">${p.nombre}</div>
                        <small class="text-muted" style="font-size: 0.7rem;">${tieneSabores ? 'Sabor personalizable' : 'Sabor estándar'}</small>
                    </div>
                    <div class="d-flex justify-content-between align-items-center mt-2">
                        <span class="precio">$${p.precio.toFixed(2)}</span>
                        ${!p.disponible ? '<span class="badge bg-danger">Agotado</span>' : '<span class="badge" style="background:var(--menta-light);color:var(--menta-dark);">+</span>'}
                    </div>
                </div>
            </div>`;
        contenedor.appendChild(col);
    });
}


// ==========================================
// DETECTOR DE TAP (SIMPLE Y DOBLE)
// ==========================================

/**
 * Manejador de tap para compatibilidad (llama directamente a agregarProducto).
 * El sistema de doble-tap fue eliminado porque causaba latencia perceptible
 * y confusion al requerir multiples clics para registrar la accion.
 *
 * @param {HTMLElement} cardElement - La tarjeta DOM que recibio el tap.
 * @param {number}      id          - ID del producto.
 * @param {string}      nombre      - Nombre del producto.
 * @param {number}      precio      - Precio unitario del producto.
 */
function handleProductoTap(cardElement, id, nombre, precio) {
    agregarProducto(id, nombre, precio, cardElement);
}


// ==========================================
// AGREGAR PRODUCTOS AL CARRITO
// ==========================================

/**
 * Flujo de tap simple: si el producto tiene sabores disponibles, abre el modal de seleccion.
 * Si no tiene sabores, lo agrega directamente sin abrir el modal.
 *
 * @param {number}      id          - ID del producto.
 * @param {string}      nombre      - Nombre del producto.
 * @param {number}      precio      - Precio unitario.
 * @param {HTMLElement} cardElement - Tarjeta DOM (para el feedback visual).
 */
function agregarProducto(id, nombre, precio, cardElement = null) {
    const producto   = productosCatalogo.find((p) => p.id === id);
    const sabores    = (producto?.sabores || []).map((s) => s.nombre);
    const maxSabores = Number(producto?.max_sabores || 1);

    if (sabores.length > 0) {
        // El producto tiene sabores: abrimos el modal para que el cajero elija.
        itemPendienteSabor = { id, nombre, precio, sabores, maxSabores };
        abrirModalSabor(itemPendienteSabor);
        return;
    }

    // Sin sabores: agrego directamente.
    agregarProductoConSabor(id, nombre, precio, null, cardElement);
}

/**
 * Agrega un producto al carrito con un sabor especifico (o sin sabor).
 * Si ya existe una linea con el mismo producto y sabor, incrementa la cantidad.
 * Si no existe, crea una nueva linea en el pedidoActual.
 *
 * @param {number}      id          - ID del producto.
 * @param {string}      nombre      - Nombre del producto.
 * @param {number}      precio      - Precio base del producto.
 * @param {string|null} sabor       - Sabores seleccionados como string, o null.
 * @param {HTMLElement} cardElement - Tarjeta DOM (para el feedback visual).
 */
function agregarProductoConSabor(id, nombre, precio, sabor, cardElement = null) {
    // Buscamos si ya hay una linea igual en el carrito (mismo producto Y mismo sabor).
    let mismaLinea = null;
    for (let i = 0; i < pedidoActual.productos.length; i++) {
        let saborActual = pedidoActual.productos[i].sabor;
        if (saborActual == null) saborActual = null;
        
        let saborParam = sabor;
        if (saborParam == null) saborParam = null;
        
        if (pedidoActual.productos[i].producto_id === id && saborActual === saborParam) {
            mismaLinea = pedidoActual.productos[i];
            break;
        }
    }

    if (mismaLinea != null) {
        // Ya existe: sumamos uno a la cantidad.
        mismaLinea.cantidad = mismaLinea.cantidad + 1;
    } else {
        // No existe: creamos una nueva linea en el carrito.
        pedidoActual.productos.push({ producto_id: id, nombre: nombre, precio: precio, cantidad: 1, sabor: sabor });
    }

    actualizarResumen();
    feedbackAgregar(cardElement);
}

/**
 * Flujo de double-tap (modo rapido): agrega el producto sin abrir el modal.
 * Si el producto tiene sabores, selecciona automaticamente los primeros N sugeridos
 * donde N es el maximo de sabores permitidos por item.
 * Util para cajeros experimentados que conocen el pedido.
 *
 * @param {number}      id          - ID del producto.
 * @param {string}      nombre      - Nombre del producto.
 * @param {number}      precio      - Precio base.
 * @param {HTMLElement} cardElement - Tarjeta DOM para el feedback visual.
 */
function agregarRapido(id, nombre, precio, cardElement = null) {
    let producto = null;
    for (let i = 0; i < productosCatalogo.length; i++) {
        if (productosCatalogo[i].id === id) {
            producto = productosCatalogo[i];
            break;
        }
    }

    if (producto == null) return;

    let arrSabores = [];
    if (producto.sabores != null) {
        for (let i = 0; i < producto.sabores.length; i++) {
            arrSabores.push(producto.sabores[i].nombre);
        }
    }

    let axSabores = Number(producto.max_sabores);
    if (isNaN(axSabores)) {
        axSabores = 1;
    }

    if (arrSabores.length > 0) {
        let sugeridos = [];
        let limite = axSabores;
        if (limite < 1) {
            limite = 1;
        }

        for (let i = 0; i < arrSabores.length; i++) {
            if (i < limite) {
                sugeridos.push(arrSabores[i]);
            }
        }
        
        let stringSugeridos = sugeridos.join(', ');
        agregarProductoConSabor(id, nombre, precio, stringSugeridos, cardElement);
        mostrarToast(`Agregado rapido: ${stringSugeridos}`, 'info');
        return;
    }

    agregarProductoConSabor(id, nombre, precio, null, cardElement);
}

/**
 * Aplica retroalimentacion visual y tactil al agregar un producto.
 * - navigator.vibrate(20): vibracion de 20ms en dispositivos que lo soporten.
 * - La clase CSS 'flash-add' dispara una animacion de destello en la tarjeta.
 * - void cardElement.offsetWidth: fuerza al navegador a recalcular el layout,
 *   lo que permite que la animacion se reinicie aunque ya este activa.
 */
function feedbackAgregar(cardElement) {
    if (navigator.vibrate) {
        navigator.vibrate(20);
    }

    if (cardElement) {
        cardElement.classList.remove('flash-add');
        void cardElement.offsetWidth;  // Trick para reiniciar la animacion CSS.
        cardElement.classList.add('flash-add');
    }
}


// ==========================================
// MODAL DE SELECCION DE SABORES
// ==========================================

/**
 * Abre el modal de seleccion de sabores para el producto pendiente.
 * Construye los controles segun el numero maximo de sabores permitidos:
 * - max = 1: muestra botones de radio (solo uno seleccionable).
 * - max > 1: muestra checkboxes (multiples seleccionables hasta el maximo).
 *
 * La funcion 'toggleSaborFeedback' se define dentro de este scope porque necesita
 * acceder a 'itemPendienteSabor', que cambia con cada producto seleccionado.
 * Se asigna a window para que el HTML inline (onchange="toggleSaborFeedback(this)") pueda accederla.
 *
 * @param {Object} item - { id, nombre, precio, sabores, maxSabores }
 */
function abrirModalSabor(item) {
    const label    = document.getElementById('sabor-producto-label');
    const regla    = document.getElementById('sabor-producto-regla');
    const selector = document.getElementById('selector-sabor-pedido');

    if (!label || !selector) return;  // regla es opcional

    label.textContent = `Selecciona sabor para ${item.nombre}`;
    if (regla) regla.textContent = `Puedes elegir hasta ${item.maxSabores} sabor(es).`;

    /**
     * Callback que se ejecuta cuando el usuario selecciona o deselecciona un sabor.
     * Para max = 1 (radio): confirma la seleccion automaticamente tras 150ms.
     * Para max > 1 (checkboxes): desactiva los checkboxes no marcados cuando se alcanza el limite.
     */
    window.toggleSaborFeedback = function(input) {
        if (navigator.vibrate) navigator.vibrate(15);

        // Fallback para browsers sin CSS :has() - añadir/quitar clase .seleccionado
        const allOpciones = document.querySelectorAll('#selector-sabor-pedido .sabor-opcion');
        allOpciones.forEach(opcion => {
            const inp = opcion.querySelector('input');
            opcion.classList.toggle('seleccionado', inp && inp.checked);
        });

        if (itemPendienteSabor && itemPendienteSabor.maxSabores === 1) {
            // Con radio buttons, confirmamos automaticamente tras un pequeno delay para mejor UX.
            setTimeout(confirmarSaborSeleccionado, 150);
        } else if (itemPendienteSabor) {
            // Con checkboxes, desactivamos los que no estan marcados si ya se alcanzo el limite.
            const checks      = document.querySelectorAll('#selector-sabor-pedido input[type="checkbox"]');
            const checkedCount = Array.from(checks).filter(c => c.checked).length;
            const max         = itemPendienteSabor.maxSabores;

            checks.forEach(c => {
                if (!c.checked) {
                    c.disabled = (checkedCount >= max);
                    c.parentElement.style.opacity      = c.disabled ? '0.4' : '1';
                    c.parentElement.style.pointerEvents = c.disabled ? 'none' : 'auto';
                }
            });
        }
    };

    if (item.maxSabores === 1) {
        // Un solo sabor: radio buttons (mutuamente excluyentes).
        selector.innerHTML = item.sabores.map((s) => `
            <label class="sabor-opcion">
                <input class="form-check-input" name="sabor-unico" type="radio" value="${s}" onchange="toggleSaborFeedback(this)">
                <span>${s}</span>
            </label>
        `).join('');
    } else {
        // Multiples sabores: checkboxes.
        // Pre-seleccionamos automaticamente los primeros maxSabores para guiar al cajero.
        selector.innerHTML = item.sabores.map((s, index) => {
            const isChecked  = index < item.maxSabores;
            const isDisabled = !isChecked;
            const pointerStyle = isDisabled ? 'pointer-events: none;' : '';
            const opacityStyle = isDisabled ? 'opacity: 0.4;' : '';
            return `
                <label class="sabor-opcion" style="${pointerStyle} ${opacityStyle}">
                    <input class="form-check-input" type="checkbox" value="${s}" ${isChecked ? 'checked' : ''} ${isDisabled ? 'disabled' : ''} onchange="toggleSaborFeedback(this)">
                    <span>${s}</span>
                </label>
            `;
        }).join('');
    }

    new bootstrap.Modal(document.getElementById('modal-sabor')).show();
}

/**
 * Valida la seleccion de sabores y agrega el producto al carrito.
 * Se llama cuando el usuario presiona "Confirmar" en el modal de sabores.
 */
function confirmarSaborSeleccionado() {
    if (!itemPendienteSabor) return;

    const checks = document.querySelectorAll('#selector-sabor-pedido input:checked');
    // Hacemos un for para ver cuales estan chequeados
    let saboresSeleccionados = [];
    for (let i = 0; i < checks.length; i++) {
        saboresSeleccionados.push(checks[i].value);
    }

    if (saboresSeleccionados.length === 0) {
        mostrarToast('Selecciona al menos un sabor', 'warning');
        return;
    }

    if (saboresSeleccionados.length > itemPendienteSabor.maxSabores) {
        mostrarToast(`Maximo ${itemPendienteSabor.maxSabores} sabor(es)`, 'warning');
        return;
    }

    agregarProductoConSabor(
        itemPendienteSabor.id,
        itemPendienteSabor.nombre,
        itemPendienteSabor.precio,
        // Los sabores se almacenan como un string separado por comas.
        saboresSeleccionados.join(', ')
    );

    // Cerramos el modal de Bootstrap
    let modalElement = document.getElementById('modal-sabor');
    if (modalElement) {
        let instancia = bootstrap.Modal.getInstance(modalElement);
        if (instancia) {
            instancia.hide();
        }
    }
    itemPendienteSabor = null;
}


// ==========================================
// RESUMEN DEL CARRITO
// ==========================================

/**
 * Calcula el total consolidado del pedido aplicando recargos de delivery y +15% si es factura SRI.
 */
function calcularTotalActual() {
    // SUMAR EL SUBTOTAL DE CADA PRODUCTO
    let subtotal = 0;
    for (let i = 0; i < pedidoActual.productos.length; i++) {
        let p = pedidoActual.productos[i];
        let recargo = 0;
        if (pedidoActual.tipo === 'delivery') {
            recargo = 0.25;
        }
        subtotal = subtotal + ((p.precio + recargo) * p.cantidad);
    }
    if (pedidoActual.requiereFactura) {
        subtotal = subtotal * 1.15;
    }
    // Retornamos sin redondeo estricto aquí, se redondeará al mostrar
    return subtotal;
}

/**
 * Reconstruye y actualiza la vista del carrito activo (lista de items y total).
 * Esta funcion se llama cada vez que se agrega, quita o edita un producto.
 * Actualiza tanto la vista de escritorio como la de movil.
 */
function actualizarResumen() {
    const contenedor       = document.getElementById('items-pedido');
    const contenedorMobile = document.getElementById('items-pedido-mobile-list');

    if (contenedor)       contenedor.innerHTML = '';
    if (contenedorMobile) contenedorMobile.innerHTML = '';

    if (pedidoActual.productos.length === 0) {
        if (contenedor)       contenedor.innerHTML = '<p class="text-muted small" id="pedido-vacio">No hay productos aun</p>';
        if (contenedorMobile) contenedorMobile.innerHTML = '<p class="text-muted small text-center my-4" id="pedido-vacio-mobile">No hay productos aun</p>';
        document.getElementById('total-pedido').textContent = '$0.00';
        actualizarResumenMovil(0, 0);
        actualizarCheckoutTotal(0);
        return;
    }

    let total = 0;
    let items = 0;

    for (let i = 0; i < pedidoActual.productos.length; i++) {
        let item = pedidoActual.productos[i];

        // Los pedidos delivery tienen un recargo de $0.25 por producto.
        let precioUnitario = item.precio;
        if (pedidoActual.tipo === 'delivery') {
            precioUnitario = item.precio + 0.25;
        }

        let subtotal = precioUnitario * item.cantidad;
        total = total + subtotal;
        items = items + item.cantidad;

        // Escapamos las comillas simples del sabor para el atributo onclick.
        let saborSeguro = null;
        if (item.sabor) {
            saborSeguro = item.sabor.replace(/'/g, "\\'");
        }

        // Armamos los pedacitos de HTML con if clasicos
        let badgeSabor = '';
        if (item.sabor) {
            badgeSabor = `<span class="badge bg-light text-dark border ms-1">${item.sabor}</span>`;
        }

        let avisoDelivery = '';
        if (pedidoActual.tipo === 'delivery') {
            avisoDelivery = '<span class="text-warning" style="font-size: 0.65rem;">(+0.25)</span>';
        }

        let parametroClick = 'null';
        if (saborSeguro) {
            parametroClick = `'${saborSeguro}'`;
        }

        const html = `
            <div class="flex-grow-1">
                <div class="d-flex align-items-center gap-1">
                   <span class="fw-800 small text-dark">${item.nombre}</span>
                   ${badgeSabor}
                </div>
                <small class="text-muted" style="font-size: 0.75rem;">$${precioUnitario.toFixed(2)} x ${item.cantidad} ${avisoDelivery}</small>
            </div>
            <div class="d-flex align-items-center gap-3">
                <span class="text-dark fw-800 small">$${subtotal.toFixed(2)}</span>
                <div class="d-flex align-items-center bg-light rounded-pill p-1">
                    <button class="btn btn-sm btn-white shadow-sm p-1 rounded-circle" onclick="editarObservacion(${item.producto_id}, ${parametroClick})" style="width: 28px; height: 28px; background: white;">
                        <i class="bi bi-pencil" style="font-size: 0.7rem;"></i>
                    </button>
                    <button class="btn btn-sm btn-white shadow-sm p-1 rounded-circle ms-1" onclick="quitarProducto(${item.producto_id}, ${parametroClick})" style="width: 28px; height: 28px; background: white;">
                        <i class="bi bi-dash" style="font-size: 0.8rem;"></i>
                    </button>
                </div>
            </div>`;

        // Agregamos el HTML a escritorio si existe
        if (contenedor) {
            let div1 = document.createElement('div');
            div1.className = 'd-flex justify-content-between align-items-center mb-2 p-2 bg-white rounded shadow-sm border border-light';
            div1.innerHTML = html;
            contenedor.appendChild(div1);
        }
        
        // Agregamos a celular si existe
        if (contenedorMobile) {
            let div2 = document.createElement('div');
            div2.className = 'd-flex justify-content-between align-items-center mb-2 p-2 bg-white rounded shadow-sm border border-light';
            div2.innerHTML = html;
            contenedorMobile.appendChild(div2);
        }
    }

    const total_con_iva = calcularTotalActual();
    document.getElementById('total-pedido').textContent = `$${total_con_iva.toFixed(2)}`;
    actualizarCheckoutTotal(total_con_iva);
    actualizarResumenMovil(total_con_iva, items);
}

/**
 * Actualiza el total que se muestra en el modal de checkout y recalcula el cambio.
 * @param {number} total - Monto total del pedido.
 */
function actualizarCheckoutTotal(total) {
    const target = document.getElementById('checkout-total');
    if (target) {
        target.textContent = `$${Number(total).toFixed(2)}`;
    }
    // Si la funcion de cambio existe y el pago es efectivo, la disparamos.
    if (typeof calcularCambioEfectivo === 'function') {
        calcularCambioEfectivo();
    }
}

/**
 * Actualiza la barra flotante del resumen en la vista movil.
 * Muestra el total y la cantidad de items en la parte inferior de la pantalla.
 */
function actualizarResumenMovil(total, items) {
    const totalMobile = document.getElementById('total-pedido-mobile');
    const itemsMobile = document.getElementById('items-pedido-mobile');

    if (totalMobile) totalMobile.textContent = `$${Number(total || 0).toFixed(2)}`;
    // Pluralizacion simple: si hay exactamente 1 item, no usamos la 's' final.
    if (itemsMobile) itemsMobile.textContent = `${items} item${items === 1 ? '' : 's'}`;
}

/**
 * Reduce la cantidad de un item en 1. Si llega a 0, lo elimina del carrito.
 * La comparacion de sabor usa '|| null' para que null y undefined sean equivalentes.
 */
function quitarProducto(id, sabor = null) {
    if (navigator.vibrate) navigator.vibrate(15);
    const item = pedidoActual.productos.find(
        (p) => p.producto_id === id && (p.sabor || null) === (sabor || null)
    );

    if (!item) return;

    if (item.cantidad > 1) {
        item.cantidad--;
    } else {
        // Eliminamos el item del array usando .filter() que retorna un nuevo array sin el elemento.
        pedidoActual.productos = pedidoActual.productos.filter(
            (p) => !(p.producto_id === id && (p.sabor || null) === (sabor || null))
        );
    }

    actualizarResumen();
}

/**
 * Permite agregar una nota u observacion libre a un item del carrito.
 * Usa prompt() del navegador (cuadro de texto nativo) por simplicidad.
 * Si el cajero cancela el prompt, no se hace ningun cambio.
 */
function editarObservacion(id, sabor = null) {
    if (navigator.vibrate) navigator.vibrate(15);
    const item = pedidoActual.productos.find(
        (p) => p.producto_id === id && (p.sabor || null) === (sabor || null)
    );

    if (!item) return;

    const nuevaNota = prompt(`Detalle / Observacion para:\n${item.nombre}`, item.sabor || "");

    // prompt() retorna null si el usuario presiona "Cancelar".
    if (nuevaNota !== null) {
        // Si la nota queda vacia, la eliminamos (null); si tiene contenido, la guardamos.
        item.sabor = nuevaNota.trim() !== "" ? nuevaNota.trim() : null;
        actualizarResumen();
    }
}


// ==========================================
// CHECKOUT Y FORMULARIO DE PAGO
// ==========================================

/**
 * Abre el modal de checkout con los totales actualizados.
 * Valida primero que el carrito no este vacio.
 */
function abrirCheckout() {
    if (navigator.vibrate) navigator.vibrate(20);
    if (pedidoActual.productos.length === 0) {
        mostrarToast('Agrega al menos un producto', 'warning');
        return;
    }

    actualizarEtiquetaNumeroPedido();
    const total = calcularTotalActual();
    actualizarCheckoutTotal(total);
    new bootstrap.Modal(document.getElementById('modal-checkout')).show();
}

/**
 * Cambia el tipo de pedido (local/delivery) y recalcula los totales.
 * El tipo de pedido afecta el precio: el delivery agrega $0.25 por item.
 * Tambien actualiza el estilo visual de los botones de tipo.
 */
function setTipo(tipo) {
    if (navigator.vibrate) navigator.vibrate(10);
    pedidoActual.tipo = tipo;

    actualizarResumen();
    const total = calcularTotalActual();
    actualizarCheckoutTotal(total);

    // Los botones de tipo ahora son radio buttons (tipo-local, tipo-delivery).
    // Bootstrap se encarga de la clase activa con .btn-check y .btn-outline-dark.
}

/**
 * Cambia el metodo de pago activo y muestra/oculta los campos correspondientes.
 * - efectivo: muestra el campo de monto recibido y calculo de cambio.
 * - transferencia: muestra el campo de numero de comprobante.
 * - mixto: muestra ambos (comprobante + montos parciales).
 */
function setFormaPago(forma) {
    if (navigator.vibrate) navigator.vibrate(10);
    formaPagoActual = forma;

    // Actualizamos el estilo de los 3 botones de forma de pago.
    ['efectivo', 'transferencia', 'mixto'].forEach((f) => {
        const btn = document.getElementById(`btn-${f}`);
        if (btn) btn.className = `btn btn-sm flex-fill ${f === forma ? 'btn-dark' : 'btn-outline-dark'}`;
    });

    const contenedorExtra  = document.getElementById('campos-pago-extra');
    const compComprobante  = document.getElementById('campo-comprobante');
    const compMixto        = document.getElementById('campos-mixto');
    const compEfectivo     = document.getElementById('campos-efectivo');

    if (!contenedorExtra || !compComprobante || !compMixto) return;

    contenedorExtra.style.display = 'block';

    if (forma === 'efectivo') {
        compComprobante.style.display = 'none';
        compMixto.style.display       = 'none';
        if (compEfectivo) compEfectivo.style.display = 'flex';
        calcularCambioEfectivo();
    } else if (forma === 'transferencia') {
        compComprobante.style.display = 'block';
        compMixto.style.display       = 'none';
        if (compEfectivo) compEfectivo.style.display = 'none';
    } else {
        // Mixto: efectivo + transferencia.
        compMixto.style.display       = 'flex';
        compComprobante.style.display = 'none';
        if (compEfectivo) compEfectivo.style.display = 'none';
    }
}

/**
 * Cambia el estado de facturacion (Consumidor Final vs SRI).
 */
function setFacturacion(esSRI) {
    if (navigator.vibrate) navigator.vibrate(10);
    pedidoActual.requiereFactura = esSRI;
    
    document.getElementById('btn-consfinal').className = `btn btn-sm py-2 fs-6 flex-fill fw-bold ${!esSRI ? 'btn-dark' : 'btn-outline-dark'}`;
    document.getElementById('btn-sri').className = `btn btn-sm py-2 fs-6 flex-fill fw-bold ${esSRI ? 'btn-dark' : 'btn-outline-dark'}`;
    
    document.getElementById('datos-consfinal').style.display = !esSRI ? 'block' : 'none';
    document.getElementById('datos-sri').style.display = esSRI ? 'block' : 'none';
    
    const badgeIva = document.getElementById('badge-iva-checkout');
    if (badgeIva) badgeIva.style.display = esSRI ? 'inline-block' : 'none';
    
    // Recalcular porque aplicar IVA cambia el precio final
    actualizarResumen();
}

/**
 * Calcula y muestra el vuelto en tiempo real cuando el cajero ingresa el monto recibido.
 * Solo se ejecuta si el metodo de pago es efectivo.
 * Muestra "Faltan $X.XX" si el monto recibido es insuficiente.
 */
function calcularCambioEfectivo() {
    if (formaPagoActual !== 'efectivo') return;

    const subtotalFinal = calcularTotalActual();

    const inputRecibido = document.getElementById('monto-recibido');
    const recibido      = parseFloat(inputRecibido?.value) || 0;
    const cambioDisplay = document.getElementById('display-cambio');

    if (!cambioDisplay) return;

    // Si el campo esta vacio, limpiamos el cambio.
    if (recibido === 0 || inputRecibido.value === '') {
        cambioDisplay.textContent = '$0.00';
        cambioDisplay.className = 'h3 fw-800 text-menta-dark';
        return;
    }

    const subTotalRounded = parseFloat(subtotalFinal.toFixed(2));
    const recibidoRounded = parseFloat(recibido.toFixed(2));
    const cambio = recibidoRounded - subTotalRounded;
    if (cambio >= 0) {
        cambioDisplay.textContent = '$' + cambio.toFixed(2);
        cambioDisplay.className = 'h3 fw-800 text-success';
    } else {
        cambioDisplay.textContent = 'Faltan $' + Math.abs(cambio).toFixed(2);
        cambioDisplay.className = 'h3 fw-800 text-danger';
    }
}

/**
 * Reinicia todos los campos del formulario de pedido para la siguiente venta.
 * Se llama automaticamente despues de confirmar un pedido exitosamente.
 */
function limpiarPedido() {
    pedidoActual.productos = [];

    // Limpiar todos los campos del formulario de forma segura
    const todosLosCampos = [
        'cliente-nombre', 'numero-comprobante', 'numero-comprobante-mixto',
        'monto-efectivo', 'monto-transferencia',
        'cliente-direccion-basica', 'cliente-telefono-basico',
        'cliente-identificacion', 'cliente-razon-social',
        'cliente-correo', 'cliente-direccion-sri', 'cliente-telefono-sri'
    ];
    todosLosCampos.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = id === 'cliente-nombre' ? 'Consumidor final' : '';
    });

    const mr = document.getElementById('monto-recibido');
    if (mr) mr.value = '';
    const dc = document.getElementById('display-cambio');
    if (dc) {
        dc.textContent = '$0.00';
        dc.className = 'h3 fw-800 text-menta-dark';
    }
    const vm = document.getElementById('validacion-montos');
    if (vm) vm.style.display = 'none';

    setTipo('local');
    setFormaPago('efectivo');
    setFacturacion(false);
    actualizarResumen();
}

/**
 * Activa/desactiva el estado de carga del boton de confirmar para evitar doble envio.
 * Guarda el HTML original en un atributo data-* para poder restaurarlo despues.
 */
function setConfirmandoPedido(loading) {
    const boton = document.getElementById('btn-confirmar-final');
    if (!boton) return;

    if (loading) {
        boton.disabled = true;
        boton.dataset.originalHtml = boton.innerHTML;
        boton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Procesando...';
    } else {
        boton.disabled = false;
        if (boton.dataset.originalHtml) boton.innerHTML = boton.dataset.originalHtml;
    }
}


// ==========================================
// CONFIRMACION DEL PEDIDO
// ==========================================

/**
 * Valida todos los campos del checkout y envia el pedido al servidor.
 * Si no hay conexion a internet, guarda el pedido en la cola offline.
 *
 * Validaciones que realiza ANTES de enviar:
 * 1. El nombre del cliente no puede estar vacio.
 * 2. El carrito debe tener al menos un producto.
 * 3. Las transferencias requieren numero de comprobante.
 * 4. En efectivo, el monto recibido no puede ser menor al total.
 * 5. En pagos mixtos, la suma de montos debe ser igual al total.
 *
 * El bloque try/catch/finally garantiza que el boton siempre se reactive
 * incluso si hay un error inesperado en el proceso.
 */
async function confirmarPedido() {
    const nombre = document.getElementById('cliente-nombre').value.trim();

    if (!nombre) {
        mostrarToast('Ingresa el nombre del cliente', 'warning');
        return;
    }
    if (pedidoActual.productos.length === 0) {
        mostrarToast('Agrega al menos un producto', 'warning');
        return;
    }

    // Leer comprobante del campo correcto según el método de pago
    const numComprobanteTransf = document.getElementById('numero-comprobante')?.value.trim() || '';
    const numComprobanteMixto  = document.getElementById('numero-comprobante-mixto')?.value.trim() || '';
    const numComprobante = formaPagoActual === 'mixto' ? numComprobanteMixto : numComprobanteTransf;

    const mEfectivo      = parseFloat(document.getElementById('monto-efectivo')?.value) || 0;
    const mTransferencia = parseFloat(document.getElementById('monto-transferencia')?.value) || 0;

    if (formaPagoActual === 'transferencia' && !numComprobante) {
        mostrarToast('Debes ingresar el numero de comprobante', 'warning');
        return;
    }

    if (formaPagoActual === 'efectivo') {
        const recibido = parseFloat(document.getElementById('monto-recibido')?.value) || 0;
        const totalReq = parseFloat(calcularTotalActual().toFixed(2));
        const recibidoRounded = parseFloat(recibido.toFixed(2));
        
        if (recibidoRounded > 0 && recibidoRounded < totalReq) {
            mostrarToast(`Faltan $${(totalReq - recibidoRounded).toFixed(2)} para completar el pago`, 'warning');
            return;
        }
    }

    if (formaPagoActual === 'mixto') {
        if (!numComprobante) {
            mostrarToast('Debes ingresar el numero de comprobante', 'warning');
            return;
        }

        const totalVal = calcularTotalActual();
        if (Math.abs((mEfectivo + mTransferencia) - totalVal) > 0.01) {
            const vm = document.getElementById('validacion-montos');
            if (vm) vm.style.display = 'block';
            mostrarToast('Los montos no suman el total del pedido', 'warning');
            return;
        }
        const vm = document.getElementById('validacion-montos');
        if (vm) vm.style.display = 'none';
    }

    setConfirmandoPedido(true);
    
    const reqFact = !!pedidoActual.requiereFactura;
    
    let dbNombre, dbIdentificacion, dbCorreo, dbDireccion, dbTelefono;
    
    if (reqFact) {
        dbIdentificacion = document.getElementById('cliente-identificacion').value.trim();
        dbNombre = document.getElementById('cliente-razon-social').value.trim();
        dbCorreo = document.getElementById('cliente-correo').value.trim();
        dbDireccion = document.getElementById('cliente-direccion-sri').value.trim();
        dbTelefono = document.getElementById('cliente-telefono-sri').value.trim();
        
        if (!dbIdentificacion || !dbNombre || !dbCorreo || !dbDireccion) {
            mostrarToast('Faltan campos obligatorios para la Factura SRI', 'warning');
            setConfirmandoPedido(false);
            return;
        }
    } else {
        dbNombre = document.getElementById('cliente-nombre').value.trim() || 'Consumidor final';
        dbDireccion = document.getElementById('cliente-direccion-basica').value.trim() || null;
        dbTelefono = document.getElementById('cliente-telefono-basico').value.trim() || null;
        dbIdentificacion = '9999999999999'; // Consumidor final ID por defecto
        dbCorreo = null;
    }

    // Construimos el objeto JSON que esperan los endpoints de pedidos.
    const datos = {
        tipo:            pedidoActual.tipo,
        cliente_nombre:  dbNombre,
        cliente_telefono: dbTelefono,
        cliente_direccion: dbDireccion,
        cliente_identificacion: dbIdentificacion,
        cliente_correo:  dbCorreo,
        requiere_factura: reqFact,
        plataforma:      null,
        forma_pago:      formaPagoActual,
        numero_comprobante: ['transferencia', 'mixto'].includes(formaPagoActual) ? numComprobante : null,
        monto_efectivo:    formaPagoActual === 'mixto' ? mEfectivo : null,
        monto_transferencia: formaPagoActual === 'mixto' ? mTransferencia : null,
        productos: pedidoActual.productos.map((p) => ({
            producto_id: p.producto_id,
            cantidad:    p.cantidad,
            sabor:       p.sabor || null,
            // Convertimos el string "Vainilla, Chocolate" al array ["Vainilla", "Chocolate"].
            sabores:     p.sabor ? p.sabor.split(',').map((s) => s.trim()).filter(Boolean) : []
        }))
    };

    // Si no hay conexion a internet, guardamos el pedido en localStorage para enviarlo despues.
    if (!navigator.onLine) {
        guardarPedidoOffline(datos);
        mostrarToast('Sin conexion: Pedido guardado localmente (se enviara al reconectar).', 'warning');
        bootstrap.Modal.getInstance(document.getElementById('modal-checkout'))?.hide();
        limpiarPedido();
        siguienteNumeroPedido++;
        actualizarEtiquetaNumeroPedido();
        setConfirmandoPedido(false);
        return;
    }

    try {
        const respuesta = await fetch('/pedidos/', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(datos)
        });

        const resultado = await respuesta.json();

        if (respuesta.ok) {
            mostrarToast(`Pedido #${resultado.numero_pedido} confirmado. Total: $${resultado.total.toFixed(2)}`, 'success');
            bootstrap.Modal.getInstance(document.getElementById('modal-checkout'))?.hide();
            limpiarPedido();
            await Promise.all([cargarPedidosActivos(), cargarSiguienteNumeroPedido()]);
        } else {
            mostrarToast(resultado.error || 'No se pudo crear el pedido', 'danger');
        }
    } catch (error) {
        console.error(error);
        // Si el servidor no responde, encolamos el pedido offline.
        guardarPedidoOffline(datos);
        mostrarToast('Error en el servidor. Pedido guardado local de forma segura.', 'danger');
        bootstrap.Modal.getInstance(document.getElementById('modal-checkout'))?.hide();
        limpiarPedido();
        siguienteNumeroPedido++;
        actualizarEtiquetaNumeroPedido();
    } finally {
        // finally siempre se ejecuta, exista error o no, garantizando que el boton se reactive.
        setConfirmandoPedido(false);
    }
}


// ==========================================
// COLA OFFLINE (MODO SIN CONEXION)
// ==========================================
/**
 * Este sistema guarda pedidos en localStorage cuando no hay conexion al servidor.
 * localStorage es un almacenamiento clave-valor del navegador que persiste entre sesiones.
 * JSON.stringify() convierte el objeto a string para guardarlo. JSON.parse() lo convierte de vuelta.
 *
 * Cuando la conexion se recupera, sincronizarPedidosOffline() los envia uno por uno al servidor.
 */

/**
 * Agrega un pedido a la cola local de pedidos offline.
 * Se le asigna un ID unico basado en el timestamp y un string aleatorio
 * para evitar colisiones si se guardan multiples pedidos sin conexion.
 */
function guardarPedidoOffline(pedidoData) {
    let cola = JSON.parse(localStorage.getItem('cola_pedidos') || '[]');
    // Generamos un ID unico combinando el timestamp actual y un string aleatorio.
    pedidoData._offline_id = Date.now().toString() + Math.random().toString(36).substring(2, 7);
    cola.push(pedidoData);
    localStorage.setItem('cola_pedidos', JSON.stringify(cola));
}

/**
 * Intenta enviar el primer pedido de la cola offline al servidor.
 * Si tiene exito, lo elimina de la cola y espera 1 segundo para enviar el siguiente.
 * Si falla, restaura el _offline_id para que pueda reintentarse despues.
 */
function sincronizarPedidosOffline() {
    if (!navigator.onLine) return;

    let cola = JSON.parse(localStorage.getItem('cola_pedidos') || '[]');
    if (cola.length === 0) return;

    const pedido    = cola[0];
    const offlineId = pedido._offline_id;
    // Eliminamos el campo interno antes de enviar al servidor (no es parte del contrato de la API).
    delete pedido._offline_id;

    fetch('/pedidos/', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(pedido)
    }).then(response => {
        if (response.ok) {
            // Exito: eliminamos el primer elemento de la cola y guardamos.
            cola.shift();  // shift() remueve y retorna el primer elemento del array.
            localStorage.setItem('cola_pedidos', JSON.stringify(cola));
            mostrarToast('Pedido Offline enviado exitosamente.', 'success');
            // Esperamos 1 segundo y procesamos el siguiente pedido de la cola.
            setTimeout(sincronizarPedidosOffline, 1000);
            cargarPedidosActivos();
            cargarSiguienteNumeroPedido();
        } else {
            // Error HTTP (ej: 400): restauramos el ID para poder reintentarlo.
            pedido._offline_id = offlineId;
        }
    }).catch(err => {
        // Error de red: restauramos el ID.
        pedido._offline_id = offlineId;
    });
}

// Sincronizamos cuando el dispositivo recupera la conexion.
window.addEventListener('online', sincronizarPedidosOffline);
// Tambien lo intentamos periodicamente cada 15 segundos.
setInterval(sincronizarPedidosOffline, 15000);
// Y al cargar la pagina, por si habia pedidos pendientes de la sesion anterior.
document.addEventListener('DOMContentLoaded', sincronizarPedidosOffline);


// ==========================================
// HISTORIAL DE PEDIDOS ACTIVOS
// ==========================================

/**
 * Descarga y renderiza los pedidos activos (no entregados aun) en la seccion lateral.
 * Esta lista se actualiza automaticamente cada 5 segundos via setInterval.
 */
async function cargarPedidosActivos() {
    try {
        const respuesta = await fetch('/pedidos/');
        if (!respuesta.ok) {
            throw new Error(`No se pudieron cargar pedidos (HTTP ${respuesta.status})`);
        }

        const pedidos = await respuesta.json();
        renderizarPedidosActivos(pedidos);
    } catch (error) {
        console.error('Error al cargar pedidos activos:', error);
    }
}

/**
 * Construye el HTML de la lista de pedidos activos y lo inserta en el DOM.
 * La lista se renderiza tanto en la vista de escritorio como en la de movil.
 * Muestra el estado actual de cada pedido con badges de color diferente.
 *
 * @param {Array} pedidos - Lista de pedidos activos retornada por el servidor.
 */
function renderizarPedidosActivos(pedidos) {
    // Obtenemos todos los contenedores validos (escritorio y movil).
    const contenedores = [
        document.getElementById('lista-pedidos-activos'),
        document.getElementById('lista-pedidos-activos-mobile')
    ].filter(Boolean);  // filter(Boolean) elimina los null/undefined si alguno no existe.

    if (!contenedores.length) return;

    if (!pedidos || pedidos.length === 0) {
        const htmlVacio = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-inbox fs-3"></i>
                <p class="mt-2 mb-0">No hay pedidos activos en este momento</p>
            </div>`;

        contenedores.forEach((contenedor) => {
            contenedor.innerHTML = htmlVacio;
        });
        return;
    }

    const html = pedidos.map((p) => {
        // Generamos los badges segun el tipo, estado y forma de pago de cada pedido.
        const badgeTipo = p.tipo === 'delivery'
            ? '<span class="badge bg-warning text-dark">Delivery</span>'
            : '<span class="badge bg-info text-dark">Local</span>';

        let badgeEstado = '';
        if (p.estado === 'pendiente')  badgeEstado = '<span class="badge bg-secondary">Pendiente</span>';
        else if (p.estado === 'en_proceso') badgeEstado = '<span class="badge bg-primary">En Cocina</span>';
        else if (p.estado === 'preparado')  badgeEstado = '<span class="badge bg-success">Listo p/ Entregar</span>';

        const badgePago = p.forma_pago === 'transferencia'
            ? `<span class="badge bg-light text-dark border">Transf. #${p.numero_comprobante || '—'}</span>`
            : p.forma_pago === 'mixto'
                ? `<span class="badge bg-light text-dark border">Mixto #${p.numero_comprobante || '—'}</span>`
                : p.forma_pago === 'pago_pedidosya'
                    ? `<span class="badge bg-light text-dark border">Pago PedidosYa</span>`
                : '';

        // Informacion de plataforma solo para pedidos delivery.
        const plataformaTxt = p.tipo === 'delivery' && p.plataforma
            ? `<div class="small text-muted">Plataforma: ${p.plataforma}</div>`
            : '';

        return `
            <div class="list-group-item py-2">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                    <div>
                        <strong>Pedido #${p.numero_pedido || '-'}</strong>
                        <div><strong>${p.cliente_nombre || 'Cliente'}</strong></div>
                        ${plataformaTxt}
                        <span class="ms-0">${badgeTipo}</span>
                        <span class="ms-1">${badgeEstado}</span>
                        ${badgePago ? `<span class="ms-1">${badgePago}</span>` : ''}
                        <div class="text-muted small mt-1">
                            <i class="bi bi-clock"></i> ${p.fecha}
                            &nbsp;·&nbsp;
                            <strong class="text-dark">$${parseFloat(p.total).toFixed(2)}</strong>
                        </div>
                    </div>
                    <div class="d-flex gap-1">
                        <button class="btn btn-sm btn-outline-dark" onclick="imprimirTicketPedido(${p.id})">
                            <i class="bi bi-printer"></i> Ticket
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="eliminarPedido(${p.id})">
                            <i class="bi bi-trash"></i> Eliminar
                        </button>
                        ${p.estado === 'preparado'
                            ? `<button class="btn btn-sm btn-success" onclick="cambiarEstado(${p.id}, 'entregado')">
                                 <i class="bi bi-check-lg"></i> Entregar al Cliente
                               </button>`
                            : `<button class="btn btn-sm btn-secondary" disabled>
                                 <i class="bi bi-hourglass"></i> Esperando Cocina
                               </button>`
                        }
                    </div>
                </div>
            </div>`;
    }).join('');

    // Actualizamos todos los contenedores con el mismo HTML.
    contenedores.forEach((contenedor) => {
        contenedor.innerHTML = html;
    });
}

/**
 * Abre el ticket PDF del pedido en una nueva pestana del navegador para imprimir.
 * @param {number} pedidoId - ID del pedido cuyo ticket se va a imprimir.
 */
function imprimirTicketPedido(pedidoId) {
    window.open(`/pedidos/${pedidoId}/ticket`, '_blank');
}

/**
 * Cancela y elimina un pedido de la cola activa.
 * Pide confirmacion antes de enviar la solicitud de eliminacion.
 * Si el servidor devuelve exito, recarga la lista de pedidos activos.
 */
async function eliminarPedido(pedidoId) {
    const confirmar = confirm('Este pedido se eliminara de la cola. Deseas continuar?');
    if (!confirmar) return;

    try {
        const respuesta = await fetch(`/pedidos/${pedidoId}`, { method: 'DELETE' });

        let datos = {};
        // Verificamos que la respuesta sea JSON antes de parsear.
        const contentType = respuesta.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            datos = await respuesta.json();
        }

        if (respuesta.ok) {
            mostrarToast('Pedido eliminado correctamente', 'success');
            await Promise.all([cargarPedidosActivos(), cargarSiguienteNumeroPedido()]);
        } else {
            mostrarToast(datos.error || 'No se pudo eliminar el pedido', 'warning');
        }
    } catch (error) {
        mostrarToast('Error de conexion al eliminar pedido', 'danger');
    }
}

/**
 * Actualiza el estado de un pedido a 'entregado' cuando el cajero lo entrega al cliente.
 * Pide confirmacion antes de marcar como entregado.
 */
async function cambiarEstado(pedidoId, nuevoEstado) {
    if (nuevoEstado === 'entregado') {
        const confirmar = confirm('Confirmas que este pedido fue entregado al cliente?');
        if (!confirmar) return;
    }

    try {
        const respuesta = await fetch(`/pedidos/${pedidoId}/estado`, {
            method:  'PUT',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ estado: nuevoEstado })
        });

        const datos = await respuesta.json();

        if (respuesta.ok) {
            mostrarToast(`Estado actualizado: ${nuevoEstado}`, 'success');
            cargarPedidosActivos();
        } else {
            mostrarToast(datos.error || 'Error al actualizar el estado', 'danger');
        }
    } catch (error) {
        mostrarToast('Error de conexion', 'danger');
    }
}
