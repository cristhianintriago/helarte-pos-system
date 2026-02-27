// Variables globales del pedido actual
let pedidoActual = {
    tipo: 'local',
    productos: []  // [{producto_id, nombre, precio, cantidad}]
};

// ── NUEVO: forma de pago por defecto
let formaPagoActual = 'efectivo';


// Al cargar la página traemos los productos de la API
document.addEventListener('DOMContentLoaded', () => {
    cargarProductos();
});


async function cargarProductos() {
    const respuesta = await fetch('/productos/');
    const productos = await respuesta.json();

    renderizarFiltros(productos);
    renderizarProductos(productos);
}


function renderizarFiltros(productos) {
    const categorias = [...new Set(productos.map(p => p.categoria))];
    const contenedor = document.getElementById('filtros');

    categorias.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-dark filtro-btn';
        btn.textContent = cat;
        btn.onclick = () => filtrarCategoria(cat);
        contenedor.appendChild(btn);
    });
}


function renderizarProductos(productos) {
    const contenedor = document.getElementById('lista-productos');
    contenedor.innerHTML = '';

    productos.forEach(p => {
        const col = document.createElement('div');
        col.className = 'col-6 col-md-4';
        col.innerHTML = `
            <div class="card producto-card ${!p.disponible ? 'agotado' : ''}"
                 onclick="${p.disponible ? `agregarProducto(${p.id}, '${p.nombre}', ${p.precio})` : ''}">
                <div class="card-body text-center p-3">
                    <div class="fs-2">🍦</div>
                    <p class="fw-bold mb-1 small">${p.nombre}</p>
                    <span class="badge bg-dark">$${p.precio.toFixed(2)}</span>
                    ${!p.disponible ? '<br><small class="text-danger">Agotado</small>' : ''}
                </div>
            </div>`;
        contenedor.appendChild(col);
    });
}


function filtrarCategoria(categoria) {
    document.querySelectorAll('.filtro-btn').forEach(b => b.classList.remove('activo'));
    event.target.classList.add('activo');

    fetch('/productos/')
        .then(r => r.json())
        .then(productos => {
            const filtrados = categoria === 'todas'
                ? productos
                : productos.filter(p => p.categoria === categoria);
            renderizarProductos(filtrados);
        });
}


function agregarProducto(id, nombre, precio) {
    const existente = pedidoActual.productos.find(p => p.producto_id === id);
    if (existente) {
        existente.cantidad++;
    } else {
        pedidoActual.productos.push({ producto_id: id, nombre, precio, cantidad: 1 });
    }
    actualizarResumen();
}


function actualizarResumen() {
    const contenedor = document.getElementById('items-pedido');
    const vacioBanner = document.getElementById('pedido-vacio');
    contenedor.innerHTML = '';

    if (pedidoActual.productos.length === 0) {
        contenedor.appendChild(vacioBanner);
        document.getElementById('total-pedido').textContent = '$0.00';
        return;
    }

    let total = 0;
    pedidoActual.productos.forEach(item => {
        const subtotal = item.precio * item.cantidad;
        total += subtotal;

        const div = document.createElement('div');
        div.className = 'list-group-item d-flex justify-content-between align-items-center px-0';
        div.innerHTML = `
            <div>
                <span class="fw-bold">${item.nombre}</span><br>
                <small class="text-muted">$${item.precio.toFixed(2)} × ${item.cantidad}</small>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="text-success fw-bold">$${subtotal.toFixed(2)}</span>
                <button class="btn btn-sm btn-outline-danger" onclick="quitarProducto(${item.producto_id})">
                    <i class="bi bi-dash"></i>
                </button>
            </div>`;
        contenedor.appendChild(div);
    });

    document.getElementById('total-pedido').textContent = `$${total.toFixed(2)}`;
}


function quitarProducto(id) {
    const item = pedidoActual.productos.find(p => p.producto_id === id);
    if (item.cantidad > 1) {
        item.cantidad--;
    } else {
        pedidoActual.productos = pedidoActual.productos.filter(p => p.producto_id !== id);
    }
    actualizarResumen();
}


function setTipo(tipo) {
    pedidoActual.tipo = tipo;
    document.getElementById('campos-delivery').style.display = tipo === 'delivery' ? 'block' : 'none';
    document.getElementById('btn-local').className = `btn flex-fill ${tipo === 'local' ? 'btn-dark' : 'btn-outline-dark'}`;
    document.getElementById('btn-delivery').className = `btn flex-fill ${tipo === 'delivery' ? 'btn-dark' : 'btn-outline-dark'}`;
}


// ── NUEVO: setFormaPago con botones activos
function setFormaPago(forma) {
    formaPagoActual = forma;
    ['efectivo', 'transferencia', 'mixto'].forEach(f => {
        const btn = document.getElementById(`btn-${f}`);
        btn.className = `btn flex-fill ${f === forma ? 'btn-dark' : 'btn-outline-dark'}`;
    });
}


function limpiarPedido() {
    pedidoActual.productos = [];
    // ── NUEVO: restaura nombre por defecto al limpiar
    document.getElementById('cliente-nombre').value = 'Consumidor final';
    document.getElementById('cliente-telefono').value = '';
    document.getElementById('cliente-direccion').value = '';
    // ── NUEVO: restaura forma de pago a efectivo
    setFormaPago('efectivo');
    actualizarResumen();
}


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

    const datos = {
        tipo: pedidoActual.tipo,
        cliente_nombre: nombre || 'Consumidor final',
        cliente_telefono: document.getElementById('cliente-telefono').value || null,
        cliente_direccion: document.getElementById('cliente-direccion').value || null,
        forma_pago: formaPagoActual,  // ── NUEVO
        productos: pedidoActual.productos.map(p => ({
            producto_id: p.producto_id,
            cantidad: p.cantidad
        }))
    };

    const respuesta = await fetch('/pedidos/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(datos)
    });

    const resultado = await respuesta.json();

    if (respuesta.ok) {
        mostrarToast(`Pedido confirmado. Total: $${resultado.total.toFixed(2)}`, 'success');
        limpiarPedido();
    } else {
        mostrarToast(resultado.error, 'danger');
    }
}
