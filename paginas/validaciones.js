document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formContacto');

    if (!form) return;

    const campos = {
        nombre: document.getElementById('nombre'),
        correo: document.getElementById('correo'),
        telefono: document.getElementById('telefono'),
        servicio: document.getElementById('servicio'),
        mensaje: document.getElementById('mensaje')
    };

    // RegEx para validaciones estricta
    const patrones = {
        correo: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
        telefono: /^[267][0-9]{7}$/ // Ejemplo ajustado a 8 dígitos numéricos
    };

    const MOSTRAR_ERROR = (input, mensaje) => {
        const spanError = document.getElementById(`error${input.id.charAt(0).toUpperCase() + input.id.slice(1)}`);
        input.classList.add('input-error');
        if (spanError) spanError.textContent = mensaje;
    };

    const LIMPIAR_ERROR = (input) => {
        const spanError = document.getElementById(`error${input.id.charAt(0).toUpperCase() + input.id.slice(1)}`);
        input.classList.remove('input-error');
        if (spanError) spanError.textContent = '';
    };

    // Validaciones en tiempo real (Blur/Input)
    Object.values(campos).forEach(input => {
        input.addEventListener('input', () => LIMPIAR_ERROR(input));
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        let esValido = true;

        // Validar Nombre
        if (campos.nombre.value.trim().length < 3) {
            MOSTRAR_ERROR(campos.nombre, 'El nombre debe tener al menos 3 caracteres.');
            esValido = false;
        }

        // Validar Correo
        if (!patrones.correo.test(campos.correo.value.trim())) {
            MOSTRAR_ERROR(campos.correo, 'Ingresa un correo electrónico válido.');
            esValido = false;
        }

        // Validar Teléfono
        if (!patrones.telefono.test(campos.telefono.value.trim())) {
            MOSTRAR_ERROR(campos.telefono, 'Ingresa un número de teléfono válido de 8 dígitos.');
            esValido = false;
        }

        // Validar Servicio
        if (campos.servicio.value === '') {
            MOSTRAR_ERROR(campos.servicio, 'Por favor selecciona un servicio.');
            esValido = false;
        }

        // Validar Mensaje
        if (campos.mensaje.value.trim().length < 10) {
            MOSTRAR_ERROR(campos.mensaje, 'El mensaje debe contener al menos 10 caracteres.');
            esValido = false;
        }

        // Si todo es válido
        const feedback = document.getElementById('formFeedback');
        if (esValido) {
            feedback.className = 'form-feedback exito';
            feedback.textContent = '¡Gracias! Tu mensaje ha sido enviado con éxito.';
            form.reset();
        } else {
            feedback.className = 'form-feedback error';
            feedback.textContent = 'Por favor corrige los errores antes de enviar.';
        }
    });
});