/**
 * simulador_carrera.js
 * Módulo de Simulación Interactiva de Telemetría GPS y Recorridos Deportivos.
 * Permite reproducir el recorrido real de 1.744 puntos de Malagueño a varias velocidades
 * y saltar a casos de prueba específicos (Largada, Comercios, Desvíos y Meta).
 * Sistema de Ciclismo Municipal de Malagueño
 */

(function (window) {
    'use strict';

    window.modoSimuladorActivo = true;

    let puntosReales = [];
    let indiceActual = 0;
    let simInterval = null;
    let estaCorriendo = false;
    let multiplicadorVelocidad = 5; // 5x por defecto para pruebas fluidas
    let panelVisible = false;

    // Puntos de referencia calculados para Circuito Prueba 1
    const PUNTOS_TEST = {
        largadaPerfecta: { lat: -31.457615, lng: -64.350960, nombre: "Largada (0m exacto)", idx: 0 },
        largadaTolerancia: { lat: -31.457850, lng: -64.351200, nombre: "Largada borde (~32m)", idx: 0 },
        comercioPruebaBar: { lat: -31.443841, lng: -64.346468, nombre: "Comercio: Prueba Bar", idx: 420 },
        desvioRuta: { lat: -31.451000, lng: -64.360000, nombre: "Desvío Fuera de Ruta (~250m)", idx: 750 },
        preMeta: { lat: -31.458000, lng: -64.353200, nombre: "Pre-Meta (98% del circuito)", idx: 1680 },
        cruceMeta: { lat: -31.458271, lng: -64.353634, nombre: "Cruzar Meta Final (Llegada)", idx: 1740 }
    };

    // Crear estilos visuales del panel del simulador
    function inyectarEstilosPanel() {
        if (document.getElementById('simulador-styles')) return;
        const css = `
            .simulador-gps-toggle {
                position: fixed;
                bottom: 84px;
                left: 14px;
                z-index: 99998;
                background: linear-gradient(135deg, #0284c7, #0369a1);
                color: #ffffff;
                border: 2px solid #38bdf8;
                box-shadow: 0 4px 18px rgba(2, 132, 199, 0.5);
                border-radius: 50px;
                padding: 0.55rem 1rem;
                font-family: 'Outfit', sans-serif;
                font-size: 0.85rem;
                font-weight: 800;
                display: flex;
                align-items: center;
                gap: 8px;
                cursor: pointer;
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .simulador-gps-toggle:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 22px rgba(2, 132, 199, 0.65);
            }
            .simulador-gps-toggle .sim-indicator-dot {
                width: 9px;
                height: 9px;
                border-radius: 50%;
                background: #34d399;
                box-shadow: 0 0 10px #34d399;
                animation: pulseSim 1.5s infinite;
            }
            @keyframes pulseSim {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.35; transform: scale(0.85); }
            }

            .simulador-gps-panel {
                position: fixed;
                bottom: 144px;
                left: 14px;
                width: calc(100vw - 28px);
                max-width: 450px;
                background: rgba(15, 23, 42, 0.97);
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                border: 1.5px solid rgba(56, 189, 248, 0.45);
                border-radius: 20px;
                padding: 1.1rem 1.25rem;
                color: #f8fafc;
                font-family: 'Inter', sans-serif;
                z-index: 99999;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65);
                display: none;
                animation: simSlideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1);
            }
            @keyframes simSlideUp {
                from { opacity: 0; transform: translateY(16px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .sim-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid rgba(255, 255, 255, 0.12);
                padding-bottom: 0.65rem;
                margin-bottom: 0.8rem;
            }
            .sim-header-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-family: 'Outfit', sans-serif;
                font-size: 1rem;
                font-weight: 800;
                color: #38bdf8;
            }
            .sim-close-btn {
                background: none;
                border: none;
                color: #94a3b8;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 4px;
                line-height: 1;
            }
            .sim-close-btn:hover { color: #ffffff; }

            .sim-stats-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 8px;
                margin-bottom: 0.85rem;
                background: rgba(30, 41, 59, 0.75);
                border-radius: 12px;
                padding: 0.6rem 0.7rem;
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            .sim-stat-box .sim-stat-lbl {
                font-size: 0.68rem;
                text-transform: uppercase;
                color: #94a3b8;
                font-weight: 700;
            }
            .sim-stat-box .sim-stat-val {
                font-size: 1rem;
                font-weight: 800;
                color: #ffffff;
                font-family: 'Outfit', sans-serif;
            }

            .sim-progress-container {
                margin-bottom: 0.9rem;
            }
            .sim-progress-bar-wrap {
                width: 100%;
                height: 8px;
                background: #334155;
                border-radius: 6px;
                overflow: hidden;
                margin-bottom: 5px;
                cursor: pointer;
                position: relative;
            }
            .sim-progress-fill {
                height: 100%;
                width: 0%;
                background: linear-gradient(90deg, #38bdf8, #10b981);
                transition: width 0.08s linear;
            }
            .sim-progress-meta {
                display: flex;
                justify-content: space-between;
                font-size: 0.72rem;
                color: #94a3b8;
            }

            .sim-controls-row {
                display: flex;
                gap: 8px;
                margin-bottom: 0.85rem;
            }
            .sim-btn-main {
                flex: 1;
                background: #10b981;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 0.65rem 0.85rem;
                font-weight: 800;
                font-size: 0.86rem;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 7px;
                transition: background 0.15s ease, filter 0.15s ease;
            }
            .sim-btn-main.is-pause {
                background: #f59e0b;
            }
            .sim-btn-main:hover { filter: brightness(1.1); }

            .sim-btn-reset {
                background: #334155;
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 0.65rem 0.85rem;
                font-weight: 700;
                font-size: 0.82rem;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 5px;
                transition: background 0.15s ease, color 0.15s ease;
            }
            .sim-btn-reset:hover {
                background: #475569;
                color: #ffffff;
            }

            .sim-speed-selector {
                display: flex;
                background: #1e293b;
                border-radius: 10px;
                padding: 3px;
                gap: 2px;
                margin-bottom: 0.85rem;
            }
            .sim-speed-btn {
                flex: 1;
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 0.75rem;
                font-weight: 700;
                padding: 0.4rem 0.5rem;
                border-radius: 6px;
                cursor: pointer;
                text-align: center;
                transition: background 0.12s ease, color 0.12s ease;
            }
            .sim-speed-btn.active {
                background: #0284c7;
                color: #ffffff;
            }

            .sim-shortcuts-title {
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #94a3b8;
                font-weight: 700;
                margin-bottom: 0.45rem;
            }
            .sim-shortcuts-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 6px;
            }
            .sim-btn-shortcut {
                background: #1e293b;
                border: 1px solid rgba(255, 255, 255, 0.08);
                color: #e2e8f0;
                border-radius: 8px;
                padding: 0.45rem 0.65rem;
                font-size: 0.74rem;
                font-weight: 600;
                text-align: left;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 6px;
                transition: background 0.15s ease, border-color 0.15s ease;
            }
            .sim-btn-shortcut:hover {
                background: #334155;
                border-color: #38bdf8;
                color: #ffffff;
            }
        `;
        const styleEl = document.createElement('style');
        styleEl.id = 'simulador-styles';
        styleEl.textContent = css;
        document.head.appendChild(styleEl);
    }

    // Crear el DOM del panel
    function renderizarPanelSimulador() {
        inyectarEstilosPanel();

        // 1. Botón flotante para abrir/cerrar
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'simulador-gps-toggle';
        toggleBtn.id = 'btn-toggle-simulador';
        toggleBtn.innerHTML = `
            <span class="sim-indicator-dot"></span>
            <span>Simulador GPS</span>
        `;
        document.body.appendChild(toggleBtn);

        // 2. Panel modal flotante
        const panel = document.createElement('div');
        panel.className = 'simulador-gps-panel';
        panel.id = 'panel-simulador-gps';
        panel.innerHTML = `
            <div class="sim-header">
                <div class="sim-header-title">
                    <i class="fa-solid fa-satellite-dish"></i>
                    <span>Simulador GPS Malagueño</span>
                </div>
                <button type="button" class="sim-close-btn" id="btn-cerrar-sim-panel" title="Cerrar panel">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>

            <div class="sim-stats-grid">
                <div class="sim-stat-box">
                    <div class="sim-stat-lbl">Punto GPS</div>
                    <div class="sim-stat-val" id="sim-txt-punto">0 / 1744</div>
                </div>
                <div class="sim-stat-box">
                    <div class="sim-stat-lbl">Velocidad</div>
                    <div class="sim-stat-val" id="sim-txt-vel">0.0 km/h</div>
                </div>
                <div class="sim-stat-box">
                    <div class="sim-stat-lbl">Progreso</div>
                    <div class="sim-stat-val" id="sim-txt-pct">0%</div>
                </div>
            </div>

            <div class="sim-progress-container">
                <div class="sim-progress-bar-wrap" id="sim-progressbar-click" title="Clic para saltar en la ruta">
                    <div class="sim-progress-fill" id="sim-progress-fill"></div>
                </div>
                <div class="sim-progress-meta">
                    <span id="sim-meta-tiempo">00:00</span>
                    <span>Track Real (1.744 pts)</span>
                    <span id="sim-meta-total">00:31:55</span>
                </div>
            </div>

            <div class="sim-controls-row">
                <button type="button" class="sim-btn-main" id="sim-btn-play-pause">
                    <i class="fa-solid fa-play"></i>
                    <span>Iniciar desde Cero</span>
                </button>
                <button type="button" class="sim-btn-reset" id="sim-btn-reset" title="Reiniciar a Km 0">
                    <i class="fa-solid fa-rotate-left"></i>
                    <span>Km 0</span>
                </button>
            </div>

            <div class="sim-speed-selector">
                <button type="button" class="sim-speed-btn" data-speed="1">1x</button>
                <button type="button" class="sim-speed-btn" data-speed="2">2x</button>
                <button type="button" class="sim-speed-btn active" data-speed="5">5x</button>
                <button type="button" class="sim-speed-btn" data-speed="10">10x</button>
                <button type="button" class="sim-speed-btn" data-speed="25">25x</button>
            </div>

            <div class="sim-shortcuts-title">Saltos de Prueba Rápida</div>
            <div class="sim-shortcuts-grid">
                <button type="button" class="sim-btn-shortcut" data-jump="largadaPerfecta">
                    <i class="fa-solid fa-circle-play" style="color:#10b981;"></i>
                    <span>Largada (0m)</span>
                </button>
                <button type="button" class="sim-btn-shortcut" data-jump="largadaTolerancia">
                    <i class="fa-solid fa-triangle-exclamation" style="color:#f59e0b;"></i>
                    <span>Largada Borde (~32m)</span>
                </button>
                <button type="button" class="sim-btn-shortcut" data-jump="comercioPruebaBar">
                    <i class="fa-solid fa-store" style="color:#38bdf8;"></i>
                    <span>Prueba Bar (Comercio)</span>
                </button>
                <button type="button" class="sim-btn-shortcut" data-jump="desvioRuta">
                    <i class="fa-solid fa-route" style="color:#ec4899;"></i>
                    <span>Simular Desvío</span>
                </button>
                <button type="button" class="sim-btn-shortcut" data-jump="preMeta">
                    <i class="fa-solid fa-flag" style="color:#a855f7;"></i>
                    <span>Última Etapa (98%)</span>
                </button>
                <button type="button" class="sim-btn-shortcut" data-jump="cruceMeta">
                    <i class="fa-solid fa-trophy" style="color:#eab308;"></i>
                    <span>Cruzar Meta (Llegada)</span>
                </button>
            </div>
        `;
        document.body.appendChild(panel);

        // Eventos de apertura / cierre
        toggleBtn.addEventListener('click', () => {
            panelVisible = !panelVisible;
            panel.style.display = panelVisible ? 'block' : 'none';
        });

        document.getElementById('btn-cerrar-sim-panel').addEventListener('click', () => {
            panelVisible = false;
            panel.style.display = 'none';
        });

        // Play / Pausa
        const btnPlay = document.getElementById('sim-btn-play-pause');
        btnPlay.addEventListener('click', () => {
            if (estaCorriendo) {
                pausarSimulacion();
            } else {
                iniciarSimulacion();
            }
        });

        // Botón Reiniciar Km 0
        const btnReset = document.getElementById('sim-btn-reset');
        btnReset.addEventListener('click', () => {
            reiniciarDesdeCero();
        });

        // Selector de velocidad
        document.querySelectorAll('.sim-speed-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.sim-speed-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                multiplicadorVelocidad = parseInt(btn.getAttribute('data-speed'), 10) || 1;
                if (estaCorriendo) {
                    pausarSimulacion();
                    iniciarSimulacion();
                }
            });
        });

        // Saltos rápidos de prueba
        document.querySelectorAll('.sim-btn-shortcut').forEach(btn => {
            btn.addEventListener('click', () => {
                const jumpKey = btn.getAttribute('data-jump');
                if (PUNTOS_TEST[jumpKey]) {
                    saltarAPunto(PUNTOS_TEST[jumpKey]);
                }
            });
        });

        // Clic en la barra de progreso
        const barWrap = document.getElementById('sim-progressbar-click');
        barWrap.addEventListener('click', (e) => {
            if (!puntosReales || puntosReales.length === 0) return;
            const rect = barWrap.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const pct = Math.max(0, Math.min(1, clickX / rect.width));
            const nuevoIndice = Math.floor(pct * (puntosReales.length - 1));
            saltarAIndice(nuevoIndice);
        });
    }

    // Inyectar coordenada en el motor de mapa_carrera_gps
    function emitirPuntoGPS(lat, lng, vel = 5.2, acc = 7) {
        if (typeof window.procesarNuevaPosicionGPSMock === 'function') {
            window.procesarNuevaPosicionGPSMock(lat, lng, vel, acc);
        } else if (typeof window.inyectarPosicionGPS === 'function') {
            window.inyectarPosicionGPS(lat, lng, vel, acc);
        }
    }

    function saltarAPunto(pto) {
        pausarSimulacion();
        if (typeof window.forzarInicioCarreraSimulada === 'function') {
            window.forzarInicioCarreraSimulada();
        }
        if (typeof pto.idx === 'number') {
            indiceActual = pto.idx;
        }
        emitirPuntoGPS(pto.lat, pto.lng, 5.5, 6);
        actualizarUI(0, pto.nombre);
    }

    function saltarAIndice(idx) {
        if (!puntosReales || puntosReales.length === 0) return;
        indiceActual = Math.max(0, Math.min(puntosReales.length - 1, idx));
        const p = puntosReales[indiceActual];
        if (typeof window.forzarInicioCarreraSimulada === 'function') {
            window.forzarInicioCarreraSimulada();
        }
        emitirPuntoGPS(p[0], p[1], 5.2, 7);
        actualizarUI(p[2]);
    }

    function actualizarUI(offsetSegundos = 0, etiquetaCustom = null) {
        const txtPunto = document.getElementById('sim-txt-punto');
        const txtVel = document.getElementById('sim-txt-vel');
        const txtPct = document.getElementById('sim-txt-pct');
        const fillBar = document.getElementById('sim-progress-fill');
        const metaTiempo = document.getElementById('sim-meta-tiempo');

        if (!txtPunto) return;

        const total = puntosReales.length || 1744;
        const pct = Math.round((indiceActual / total) * 100);

        txtPunto.textContent = etiquetaCustom ? etiquetaCustom : `${indiceActual} / ${total}`;
        txtPct.textContent = `${pct}%`;
        fillBar.style.width = `${pct}%`;

        // Formatear mm:ss
        const mins = Math.floor(offsetSegundos / 60);
        const segs = Math.floor(offsetSegundos % 60);
        metaTiempo.textContent = `${mins.toString().padStart(2, '0')}:${segs.toString().padStart(2, '0')}`;

        // Velocidad estimada en km/h
        const velEst = (18.2 + Math.sin(indiceActual / 10) * 3).toFixed(1);
        txtVel.textContent = `${velEst} km/h`;
    }

    function pasoSimulacion() {
        if (!puntosReales || puntosReales.length === 0) return;

        if (indiceActual >= puntosReales.length) {
            pausarSimulacion();
            return;
        }

        const p = puntosReales[indiceActual];
        // p = [lat, lng, seconds_offset]
        emitirPuntoGPS(p[0], p[1], 5.2, 7);
        actualizarUI(p[2]);

        indiceActual++;
    }

    function iniciarSimulacion() {
        if (puntosReales.length === 0) {
            cargarDatasetReales(() => iniciarSimulacion());
            return;
        }

        // Si ya llegó al final, rebobinar a 0
        if (indiceActual >= puntosReales.length - 1) {
            reiniciarDesdeCero();
        }

        // Asegurar que la carrera esté en marcha en el motor
        if (typeof window.forzarInicioCarreraSimulada === 'function') {
            window.forzarInicioCarreraSimulada();
        }

        estaCorriendo = true;
        const btnPlay = document.getElementById('sim-btn-play-pause');
        if (btnPlay) {
            btnPlay.classList.add('is-pause');
            btnPlay.innerHTML = `<i class="fa-solid fa-pause"></i> <span>Pausar Simulación</span>`;
        }

        // Frecuencia dinámica según multiplicador de velocidad
        const intervaloMs = Math.max(35, Math.floor(1000 / multiplicadorVelocidad));
        clearInterval(simInterval);
        simInterval = setInterval(pasoSimulacion, intervaloMs);
    }

    function pausarSimulacion() {
        estaCorriendo = false;
        clearInterval(simInterval);
        const btnPlay = document.getElementById('sim-btn-play-pause');
        if (btnPlay) {
            btnPlay.classList.remove('is-pause');
            btnPlay.innerHTML = `<i class="fa-solid fa-play"></i> <span>Continuar Simulación</span>`;
        }
    }

    function reiniciarDesdeCero() {
        pausarSimulacion();
        indiceActual = 0;

        // Resetear motor de mapa_carrera_gps
        if (typeof window.resetearCarreraSimulada === 'function') {
            window.resetearCarreraSimulada();
        }

        const btnPlay = document.getElementById('sim-btn-play-pause');
        if (btnPlay) {
            btnPlay.classList.remove('is-pause');
            btnPlay.innerHTML = `<i class="fa-solid fa-play"></i> <span>Iniciar desde Cero</span>`;
        }

        actualizarUI(0);
    }

    // Cargar dataset de ayer desde el JSON exportado
    function cargarDatasetReales(callback) {
        fetch('/static/data/simulacion_recorrido_real.json')
            .then(res => res.json())
            .then(data => {
                puntosReales = data;
                console.log(`[SimuladorGPS] Dataset cargado con éxito: ${puntosReales.length} puntos reales.`);
                if (callback) callback();
            })
            .catch(err => {
                console.warn('[SimuladorGPS] Error cargando simulacion_recorrido_real.json:', err);
            });
    }

    // Inicialización automática
    document.addEventListener('DOMContentLoaded', () => {
        renderizarPanelSimulador();
        cargarDatasetReales();
    });

    window.SimuladorGPS = {
        iniciar: iniciarSimulacion,
        pausar: pausarSimulacion,
        reiniciar: reiniciarDesdeCero,
        saltarA: saltarAPunto,
        saltarIndice: saltarAIndice
    };
})(window);
