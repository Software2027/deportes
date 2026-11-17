/**
 * audio_carrera.js
 * Sistema de Retroalimentación Sonora para Telemetría y Eventos de Carrera.
 * Utiliza Web Audio API nativo (100% offline, cero dependencias, sin archivos de audio externos).
 * Municipalidad de Malagueño - Sistema de Ciclismo
 */

(function (window) {
    'use strict';

    let audioCtx = null;
    let audioHabilitado = true;

    // Inicializar AudioContext tras la primera interacción del usuario (política de navegadores móviles)
    function getAudioContext() {
        if (!audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                audioCtx = new AudioContextClass();
            }
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume().catch(() => {});
        }
        return audioCtx;
    }

    // Desbloquear audio en el primer touch o click en la pantalla
    function desbloquearAudioEnInteraccion() {
        const desbloquear = () => {
            getAudioContext();
            document.removeEventListener('touchstart', desbloquear);
            document.removeEventListener('click', desbloquear);
        };
        document.addEventListener('touchstart', desbloquear, { passive: true });
        document.addEventListener('click', desbloquear, { passive: true });
    }
    desbloquearAudioEnInteraccion();

    /**
     * Toca un tono simple senoidal o triangular con curva ADSR suave
     */
    function reproducirTono(frecuencia, inicioSec, duracionSec, tipo = 'sine', volumenMax = 0.22) {
        const ctx = getAudioContext();
        if (!ctx) return;

        try {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = tipo;
            osc.frequency.setValueAtTime(frecuencia, ctx.currentTime + inicioSec);

            // Ataque y decaimiento suave para evitar clics acústicos
            const t0 = ctx.currentTime + inicioSec;
            gain.gain.setValueAtTime(0.0001, t0);
            gain.gain.exponentialRampToValueAtTime(volumenMax, t0 + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duracionSec);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(t0);
            osc.stop(t0 + duracionSec);
        } catch (e) {
            console.warn('[AudioCarrera] Error reproduciendo tono:', e);
        }
    }

    const AudioCarrera = {
        habilitar(val = true) {
            audioHabilitado = !!val;
        },

        estaHabilitado() {
            return audioHabilitado;
        },

        /**
         * Sonido de Largada: Tono de confirmación y arranque
         */
        playLargada() {
            if (!audioHabilitado) return;
            getAudioContext();
            // Dos tonos cortos y uno largo de salida (Beep-Beep-GO!)
            reproducirTono(523.25, 0.0, 0.12, 'triangle', 0.25); // C5
            reproducirTono(659.25, 0.15, 0.12, 'triangle', 0.25); // E5
            reproducirTono(1046.50, 0.32, 0.40, 'triangle', 0.30); // C6
        },

        /**
         * Sonido de Etapa / Tramo Completado: Melodía ascendente positiva de triunfo
         */
        playEtapaCompletada() {
            if (!audioHabilitado) return;
            getAudioContext();
            reproducirTono(587.33, 0.0, 0.14, 'sine', 0.25); // D5
            reproducirTono(739.99, 0.14, 0.14, 'sine', 0.25); // F#5
            reproducirTono(880.00, 0.28, 0.28, 'sine', 0.28); // A5
            reproducirTono(1174.66, 0.45, 0.45, 'triangle', 0.28); // D6
        },

        /**
         * Sonido de Comercio Adherido / Checkpoint de hidratación
         * Campanilla doble amigable de validación comercial
         */
        playComercioAdherido() {
            if (!audioHabilitado) return;
            getAudioContext();
            reproducirTono(987.77, 0.0, 0.12, 'sine', 0.22); // B5
            reproducirTono(1318.51, 0.12, 0.35, 'sine', 0.25); // E6
        },

        /**
         * Sonido de Cruce de Meta / Finalización Exitosa
         * Acorde triunfal brillante
         */
        playMetaVictoria() {
            if (!audioHabilitado) return;
            getAudioContext();
            reproducirTono(523.25, 0.0, 0.15, 'triangle', 0.25); // C5
            reproducirTono(659.25, 0.12, 0.15, 'triangle', 0.25); // E5
            reproducirTono(783.99, 0.24, 0.18, 'triangle', 0.28); // G5
            reproducirTono(1046.50, 0.38, 0.70, 'triangle', 0.32); // C6 sostenido
        },

        /**
         * Sonido de Precaución / Desvío Fuera de Ruta
         * Tono suave de alerta deportiva
         */
        playDesvioAlerta() {
            if (!audioHabilitado) return;
            getAudioContext();
            reproducirTono(440.00, 0.0, 0.18, 'sawtooth', 0.18); // A4
            reproducirTono(369.99, 0.20, 0.25, 'sawtooth', 0.18); // F#4
        },

        /**
         * Sonido de Pausa de Recorrido
         */
        playPausa() {
            if (!audioHabilitado) return;
            getAudioContext();
            reproducirTono(659.25, 0.0, 0.12, 'sine', 0.20);
            reproducirTono(493.88, 0.14, 0.22, 'sine', 0.20);
        }
    };

    window.AudioCarrera = AudioCarrera;
})(window);
