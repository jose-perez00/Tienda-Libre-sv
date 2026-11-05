// script.js

document.addEventListener('DOMContentLoaded', () => {
    actualizarContadorCarrito();
});

// Función para obtener los productos del carrito desde el almacenamiento local
function obtenerCarrito() {
    // Se prefieren las claves del carrito actual y se cae a la heredada.
    const claves = ['carritoCompras', 'carrito'];
    for (const clave of claves) {
        const crudo = localStorage.getItem(clave);
        if (!crudo) continue;
        try {
            const datos = JSON.parse(crudo);
            if (Array.isArray(datos)) return datos;
        } catch (error) {
            console.warn(`No se pudo leer el carrito en ${clave}:`, error);
        }
    }
    return [];
}

// Función para actualizar el número en la barra de navegación
function actualizarContadorCarrito() {
    const carrito = obtenerCarrito();
    // Sumamos la cantidad total de productos, tolerando ítems sin cantidad.
    const totalItems = carrito.reduce((acumulador, producto) => {
        const cantidad = Number(producto && producto.cantidad);
        return acumulador + (Number.isFinite(cantidad) && cantidad > 0 ? cantidad : 1);
    }, 0);

    const spanContador = document.getElementById('cart-count');
    if (spanContador) {
        spanContador.textContent = totalItems;
    }
}

// Función de ejemplo para agregar un producto al carrito (por si deseas usarla en botones)
function agregarAlCarrito(id, nombre, precio, imagen) {
    const carrito = obtenerCarrito();

    // Verificamos si el producto ya existe en el carrito
    const index = carrito.findIndex(item => item.id === id);

    if (index > -1) {
        carrito[index].cantidad = Number(carrito[index].cantidad || 1) + 1;
    } else {
        carrito.push({
            id: id,
            nombre: nombre,
            titulo: nombre,
            precio: Number(precio) || 0,
            imagen: imagen,
            cantidad: 1
        });
    }

    // Guardamos de nuevo en el navegador (ambas claves para mantener compatibilidad)
    localStorage.setItem('carritoCompras', JSON.stringify(carrito));
    localStorage.setItem('carrito', JSON.stringify(carrito));
    
    // Actualizamos el contador visual en la barra de navegación
    actualizarContadorCarrito();
    
    alert(`¡"${nombre}" se ha agregado al carrito!`);
}