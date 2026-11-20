/**
 * session_timeout.js
 * Cierre automático de sesión por inactividad tras 1 hora (3600 segundos).
 * Monitorea eventos de usuario (mouse, teclado, touch, scroll) y renueva el temporizador.
 */
(function() {
    const TIEMPO_INACTIVIDAD_MS = 60 * 60 * 1000; // 1 hora exacta (3600 seg)
    let temporizadorInactividad = null;

    function reiniciarTemporizador() {
        if (temporizadorInactividad) {
            clearTimeout(temporizadorInactividad);
        }
        temporizadorInactividad = setTimeout(cerrarSesionPorInactividad, TIEMPO_INACTIVIDAD_MS);
    }

    function cerrarSesionPorInactividad() {
        console.warn('[Seguridad] Sesión expirada tras 1 hora de inactividad.');
        const esPanel = window.location.pathname.startsWith('/panel');
        if (esPanel) {
            window.location.href = '/panel/logout/?inactividad=1';
        } else {
            window.location.href = '/logout/?inactividad=1';
        }
    }

    // Eventos que indican actividad humana real
    const eventosActividad = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];
    
    // Throttle de eventos para no sobrecargar el navegador
    let ultimaMarcaTiempo = Date.now();
    eventosActividad.forEach(function(evento) {
        window.addEventListener(evento, function() {
            const ahora = Date.now();
            if (ahora - ultimaMarcaTiempo > 5000) { // Actualiza cada 5 segundos de interacción
                ultimaMarcaTiempo = ahora;
                reiniciarTemporizador();
            }
        }, { passive: true });
    });

    // Iniciar el temporizador al cargar la página
    reiniciarTemporizador();
})();
