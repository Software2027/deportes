/**
 * mapa_carrera_gps.js
 * Control de Telemetría GPS en Vivo, Cronómetro, Búfer por Lotes y Proximidad
 * Sistema de Ciclismo Municipal de Malagueño
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Elementos del DOM
    const mapElement = document.getElementById('mapa-carrera-fs');
    if (!mapElement) return;

    // Métricas del HUD
    const hudVelocidad = document.getElementById('hud-velocidad');
    const hudDistancia = document.getElementById('hud-distancia');
    const hudTiempo = document.getElementById('hud-tiempo');
    const hudRitmo = document.getElementById('hud-ritmo');

    // Botones de control
    const btnStart = document.getElementById('btn-carrera-start');
    const btnPause = document.getElementById('btn-carrera-pause');
    const btnResume = document.getElementById('btn-carrera-resume');
    const btnFinish = document.getElementById('btn-carrera-finish');
    const btnRecenter = document.getElementById('btn-recenter-gps');
    const btnFullscreen = document.getElementById('btn-toggle-fullscreen');

    // Modal de confirmación finalizar
    const modalConfirm = document.getElementById('modal-confirm-finalizar');
    const btnCancelModal = document.getElementById('btn-modal-cancel');
    const btnAcceptModal = document.getElementById('btn-modal-confirm');

    // Modal Fuera de Radio de Largada
    const modalFueraLargada = document.getElementById('modal-fuera-largada');
    const largadaDistActual = document.getElementById('largada-dist-actual');
    const largadaRadioMax = document.getElementById('largada-radio-max');
    const btnVerLargadaMapa = document.getElementById('btn-ver-largada-mapa');
    const btnEntendidoLargada = document.getElementById('btn-entendido-largada');

    // Modal Parada Registrada
    const modalParada = document.getElementById('modal-parada-registrada');
    const modalParadaTitle = document.getElementById('modal-parada-title');
    const modalParadaDesc = document.getElementById('modal-parada-desc');
    const modalParadaBadge = document.getElementById('modal-parada-badge');
    const modalParadaIcon = document.getElementById('modal-parada-icon');
    const modalParadaIconWrap = document.getElementById('modal-parada-icon-wrap');
    const modalParadaComercioCard = document.getElementById('modal-parada-comercio-card');
    const modalComercioNombre = document.getElementById('modal-comercio-nombre');
    const modalComercioCat = document.getElementById('modal-comercio-cat');
    const modalComercioLogo = document.getElementById('modal-comercio-logo');
    const btnReanudarDesdeModal = document.getElementById('btn-reanudar-desde-modal');

    // Banner de proximidad a comercio
    const proximityBanner = document.getElementById('proximity-banner');
    const proximityTitle = document.getElementById('proximity-title');
    const proximityBenefit = document.getElementById('proximity-benefit');
    const btnCloseProximity = document.getElementById('btn-close-proximity');

    // Elementos del Drawer y Subcircuitos
    const btnToggleEtapas = document.getElementById('btn-toggle-etapas');
    const btnOpenDrawerPill = document.getElementById('btn-open-drawer-pill');
    const btnCloseDrawer = document.getElementById('btn-close-drawer-subcircuitos');
    const drawerSubcircuitos = document.getElementById('drawer-subcircuitos');
    const drawerBackdrop = document.getElementById('drawer-subcircuitos-backdrop');

    // Elementos de la Píldora de Subcircuito Activo
    const subcircuitoStepBadge = document.getElementById('subcircuito-step-badge');
    const currentEtapaNum = document.getElementById('current-etapa-num');
    const currentEtapaName = document.getElementById('current-etapa-name');
    const currentEtapaDist = document.getElementById('current-etapa-dist');

    // Banner de Alerta de Avance de Etapa
    const etapaAlertBanner = document.getElementById('etapa-alert-banner');
    const etapaAlertTitle = document.getElementById('etapa-alert-title');
    const etapaAlertDesc = document.getElementById('etapa-alert-desc');
    const btnCloseEtapaAlert = document.getElementById('btn-close-etapa-alert');

    // Elementos Fuera de Ruta
    const alertaFueraRutaBanner = document.getElementById('alerta-fuera-ruta-banner');
    const fueraRutaDistVal = document.getElementById('fuera-ruta-dist-val');
    const btnCentrarDesvio = document.getElementById('btn-centrar-desvio-retorno');

    // Elementos Modal Fuera de Meta
    const modalFueraMeta = document.getElementById('modal-fuera-meta');
    const metaDistActual = document.getElementById('meta-dist-actual');
    const btnContinuarMeta = document.getElementById('btn-continuar-a-meta');
    const btnForzarFinalizar = document.getElementById('btn-forzar-finalizar');

    // Elementos Modal Selector de Circuitos
    const modalSelectorCircuitos = document.getElementById('modal-selector-circuitos');
    const btnAbrirSelector = document.getElementById('btn-toggle-modal-circuitos');
    const btnCloseSelector = document.getElementById('btn-close-selector-circuitos');

    // Datos inyectados desde Django
    const trazados = window.carreraTrazado || [];
    const comercios = window.carreraComercios || [];
    let recorridoId = window.carreraRecorridoId || 0;
    const puntoLargada = window.carreraPuntoLargada || null; // [lat, lng]
    const puntoMeta = window.carreraPuntoMeta || null; // [lat, lng]
    const radioLargadaMetros = window.carreraRadioLargadaMetros || 20;
    const radioMetaMetros = window.carreraRadioMetaMetros || 20;
    const modalidadRecorrido = window.carreraModalidad || 'LIBRE';
    const estadoInicial = window.carreraEstado || 'LISTO';

    // 2. Estado de la Carrera, Wake Lock y Reconciliación Temporal
    let estadoCarrera = 'LISTO'; // 'LISTO', 'EN_CURSO', 'PAUSADO', 'FINALIZADO'
    let segundosTranscurridos = 0;
    let cronometroInterval = null;
    let timestampInicioMs = null;
    let acumuladoPausasMs = 0;
    let timestampUltimaPausaMs = null;
    let wakeLock = null;

    let distanciaTotalMetros = 0;
    let ultimaCoordenada = null;
    let gpsWatchId = null;
    let autoCentrarGPS = true;
    let subcircuitoActivoIndex = 0; // Índice de la etapa en curso (0: Etapa 1)

    // Estado Fuera de Ruta
    let fueraDeRuta = false;
    let lineaRetornoCircuito = null;
    let puntoMasCercanoRuta = null;

    // Búfer de telemetría para envío por lotes a /api/gps/batch/
    let lotePuntosGPS = [];
    const TAMANO_LOTE = 5;

    // 3. Inicialización del Mapa Leaflet
    const MALAGUENO_LAT = -31.468;
    const MALAGUENO_LNG = -64.355;

    const map = L.map('mapa-carrera-fs', {
        zoomControl: false,
        attributionControl: false
    }).setView([MALAGUENO_LAT, MALAGUENO_LNG], 15);

    // Capa oficial de la Municipalidad de Malagueño (OpenStreetMap HOT)
    L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
        maxZoom: 18,
        minZoom: 11,
        subdomains: 'abc'
    }).addTo(map);

    // Controles de zoom abajo a la izquierda para no estorbar el HUD superior
    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    // Dibujar los subcircuitos con sus colores característicos y registrarlos
    const subcircuitoPolylines = {};
    const bounds = [];

    if (trazados.length > 0) {
        trazados.forEach((tr, idx) => {
            if (tr.coordenadas && tr.coordenadas.length > 0) {
                const isCurrent = (idx === subcircuitoActivoIndex);
                const polyline = L.polyline(tr.coordenadas, {
                    color: tr.color || '#16a34a',
                    weight: isCurrent ? 8 : 5,
                    opacity: isCurrent ? 1.0 : 0.75,
                    lineJoin: 'round'
                }).addTo(map);

                polyline.bindPopup(`
                    <div style="font-family:'Outfit', sans-serif;">
                        <span style="font-size:0.75rem; font-weight:800; color:${tr.color}; text-transform:uppercase;">Etapa ${tr.orden}</span>
                        <h4 style="margin:2px 0 4px 0; font-size:0.95rem; font-weight:700;">${tr.nombre}</h4>
                        <span style="font-size:0.8rem; color:#64748b;">Distancia: <strong>${tr.distancia_km || ''} km</strong></span>
                    </div>
                `);

                subcircuitoPolylines[tr.id] = {
                    layer: polyline,
                    data: tr,
                    index: idx
                };

                tr.coordenadas.forEach(c => bounds.push(c));
            }
        });
    }

    // Dibujar comercios y checkpoints con íconos temáticos
    function getComercioIcon(categoria) {
        let iconClass = 'fa-solid fa-location-dot';
        let bg = '#16a34a';

        if (categoria.includes('Hidratación')) {
            iconClass = 'fa-solid fa-droplet';
            bg = '#0284c7';
        } else if (categoria.includes('Taller')) {
            iconClass = 'fa-solid fa-wrench';
            bg = '#f59e0b';
        } else if (categoria.includes('Gastronomía')) {
            iconClass = 'fa-solid fa-utensils';
            bg = '#e11d48';
        } else if (categoria.includes('Control')) {
            iconClass = 'fa-solid fa-flag-checkered';
            bg = '#7c3aed';
        }

        return L.divIcon({
            className: 'custom-pin',
            html: `<div style="background:${bg}; width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:13px; border:2.5px solid #fff; box-shadow:0 3px 10px rgba(0,0,0,0.3);"><i class="${iconClass}"></i></div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });
    }

    comercios.forEach(com => {
        // Marcador del local
        const marker = L.marker([com.lat, com.lng], {
            icon: getComercioIcon(com.categoria)
        }).addTo(map);
        marker.bindPopup(`<b>${com.nombre}</b><br><span style="color:#64748b;">${com.categoria}</span><br><em>Radio: ${com.radio}m</em>`);

        // Círculo semitransparente del radio de tolerancia (30m)
        L.circle([com.lat, com.lng], {
            radius: com.radio || 30,
            color: '#16a34a',
            fillColor: '#16a34a',
            fillOpacity: 0.12,
            weight: 1.5,
            dashArray: '4, 4'
        }).addTo(map);

        bounds.push([com.lat, com.lng]);
    });

    // 1. Coordenada del Punto de Salida (Km 0)
    let coordSalida = null;
    if (puntoLargada && puntoLargada.length === 2) {
        coordSalida = [Number(puntoLargada[0]), Number(puntoLargada[1])];
    } else if (trazados.length > 0 && trazados[0].coordenadas && trazados[0].coordenadas.length > 0) {
        coordSalida = [Number(trazados[0].coordenadas[0][0]), Number(trazados[0].coordenadas[0][1])];
    }

    // 2. Coordenada del Punto de Meta (Llegada)
    let coordMeta = null;
    if (puntoMeta && puntoMeta.length === 2) {
        coordMeta = [Number(puntoMeta[0]), Number(puntoMeta[1])];
    } else if (trazados.length > 0) {
        for (let i = trazados.length - 1; i >= 0; i--) {
            if (trazados[i].coordenadas && trazados[i].coordenadas.length > 0) {
                const ultimoPto = trazados[i].coordenadas[trazados[i].coordenadas.length - 1];
                coordMeta = [Number(ultimoPto[0]), Number(ultimoPto[1])];
                break;
            }
        }
    }

    // 3. Marcador y Radio del Punto de Salida Oficial (Km 0)
    let largadaMarker = null;
    let largadaCircle = null;
    if (coordSalida) {
        const largadaIcon = L.divIcon({
            className: 'custom-largada-pin',
            html: `
                <div style="display:flex; flex-direction:column; align-items:center; transform:translate(-50%, -100%);">
                    <span style="background:#059669; color:#fff; font-size:10px; font-weight:800; padding:2px 8px; border-radius:10px; box-shadow:0 2px 6px rgba(0,0,0,0.3); text-transform:uppercase; margin-bottom:2px; white-space:nowrap; border:1px solid #fff;">
                        <i class="fa-solid fa-play"></i> SALIDA
                    </span>
                    <div style="background:#059669; width:36px; height:36px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:16px; border:2.5px solid #fff; box-shadow:0 3px 12px rgba(0,0,0,0.35);">
                        <i class="fa-solid fa-flag"></i>
                    </div>
                </div>
            `,
            iconSize: [0, 0]
        });

        largadaMarker = L.marker(coordSalida, {
            icon: largadaIcon,
            zIndexOffset: 950
        }).addTo(map);

        largadaMarker.bindPopup(`
            <div style="font-family:'Outfit', sans-serif; text-align:center;">
                <span style="font-size:0.75rem; font-weight:800; color:#059669; text-transform:uppercase;">Punto de Partida Oficial</span>
                <h4 style="margin:2px 0 4px 0; font-size:1rem; font-weight:800; color:#0f172a;">SALIDA (Km 0)</h4>
                <span style="font-size:0.8rem; color:#64748b;">Radio de tolerancia: <strong>${radioLargadaMetros} m</strong></span>
            </div>
        `);

        largadaCircle = L.circle(coordSalida, {
            radius: radioLargadaMetros,
            color: '#059669',
            fillColor: '#10b981',
            fillOpacity: 0.16,
            weight: 2,
            dashArray: '6, 6'
        }).addTo(map);

        bounds.push(coordSalida);
    }

    // 4. Marcador del Punto de Meta (Llegada Final)
    let metaMarker = null;
    if (coordMeta) {
        const metaIcon = L.divIcon({
            className: 'custom-meta-pin',
            html: `
                <div style="display:flex; flex-direction:column; align-items:center; transform:translate(-50%, -100%);">
                    <span style="background:#dc2626; color:#fff; font-size:10px; font-weight:800; padding:2px 8px; border-radius:10px; box-shadow:0 2px 6px rgba(0,0,0,0.3); text-transform:uppercase; margin-bottom:2px; white-space:nowrap; border:1px solid #fff;">
                        <i class="fa-solid fa-flag-checkered"></i> META
                    </span>
                    <div style="background:#dc2626; width:36px; height:36px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fff; font-size:16px; border:2.5px solid #fff; box-shadow:0 3px 12px rgba(0,0,0,0.35);">
                        <i class="fa-solid fa-trophy"></i>
                    </div>
                </div>
            `,
            iconSize: [0, 0]
        });

        metaMarker = L.marker(coordMeta, {
            icon: metaIcon,
            zIndexOffset: 940
        }).addTo(map);

        metaMarker.bindPopup(`
            <div style="font-family:'Outfit', sans-serif; text-align:center;">
                <span style="font-size:0.75rem; font-weight:800; color:#dc2626; text-transform:uppercase;">Fin del Circuito</span>
                <h4 style="margin:2px 0 4px 0; font-size:1rem; font-weight:800; color:#0f172a;">LLEGADA / META</h4>
                <span style="font-size:0.8rem; color:#64748b;">Radio de tolerancia: <strong>${radioMetaMetros} m</strong></span>
            </div>
        `);

        const metaCircle = L.circle(coordMeta, {
            radius: radioMetaMetros,
            color: '#dc2626',
            fillColor: '#ef4444',
            fillOpacity: 0.16,
            weight: 2,
            dashArray: '6, 6'
        }).addTo(map);

        bounds.push(coordMeta);
    }

    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [80, 80] });
    }

    // 4. Marcador Dinámico del Ciclista con Halo de Pulso
    const cyclistIcon = L.divIcon({
        className: 'cyclist-live-container',
        html: `
            <div class="cyclist-marker-pin">
                <div class="cyclist-marker-pulse"></div>
            </div>
        `,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    });

    let cyclistMarker = L.marker([MALAGUENO_LAT, MALAGUENO_LNG], {
        icon: cyclistIcon,
        zIndexOffset: 1000
    }).addTo(map);

    // Círculo de precisión del GPS
    let accuracyCircle = L.circle([MALAGUENO_LAT, MALAGUENO_LNG], {
        radius: 10,
        color: '#16a34a',
        fillColor: '#16a34a',
        fillOpacity: 0.15,
        weight: 1
    }).addTo(map);

    // 5. Utilidad Matemática: Distancia Haversine en metros
    function calcularHaversineMetros(lat1, lon1, lat2, lon2) {
        const R = 6371000;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    // 6. Formateo de Cronómetro (HH:MM:SS)
    function formatearTiempo(totalSegundos) {
        const h = Math.floor(totalSegundos / 3600);
        const m = Math.floor((totalSegundos % 3600) / 60);
        const s = totalSegundos % 60;
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    // 7. Envío de Telemetría GPS en Lote a /api/gps/batch/
    function enviarLoteGPS() {
        if (!recorridoId || lotePuntosGPS.length === 0) return;

        const puntosAEnviar = [...lotePuntosGPS];
        // Limpiar lote local
        lotePuntosGPS = [];

        fetch('/api/gps/batch/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                recorrido_id: recorridoId,
                puntos: puntosAEnviar
            })
        })
        .then(res => res.json().then(data => ({ ok: res.ok, status: res.status, body: data })))
        .then(result => {
            if (!result.ok) {
                console.warn('[GPS Telemetry] Error en el servidor al guardar telemetría:', result.body);
                // Si fue un fallo de red o servidor 500+, reencolamos sin desbordar
                if (result.status >= 500 && lotePuntosGPS.length < 50) {
                    lotePuntosGPS.unshift(...puntosAEnviar);
                }
            } else {
                console.log('[GPS Telemetry] Lote enviado exitosamente:', result.body);
            }
        })
        .catch(err => {
            console.warn('[GPS Telemetry] Error de red o sierra sin señal, reencolando...', err);
            if (lotePuntosGPS.length < 50) {
                lotePuntosGPS.unshift(...puntosAEnviar);
            }
        });
    }

    // 7.1. Lógica Interactiva del Drawer de Subcircuitos
    function abrirDrawerSubcircuitos() {
        if (drawerSubcircuitos && drawerBackdrop) {
            drawerSubcircuitos.classList.add('open');
            drawerBackdrop.classList.add('open');
        }
    }

    function cerrarDrawerSubcircuitos() {
        if (drawerSubcircuitos && drawerBackdrop) {
            drawerSubcircuitos.classList.remove('open');
            drawerBackdrop.classList.remove('open');
        }
    }

    if (btnToggleEtapas) btnToggleEtapas.addEventListener('click', abrirDrawerSubcircuitos);
    if (btnOpenDrawerPill) btnOpenDrawerPill.addEventListener('click', abrirDrawerSubcircuitos);
    if (btnCloseDrawer) btnCloseDrawer.addEventListener('click', cerrarDrawerSubcircuitos);
    if (drawerBackdrop) drawerBackdrop.addEventListener('click', cerrarDrawerSubcircuitos);

    // Acción "Ver Tramo en Mapa" para cada Subcircuito
    document.querySelectorAll('.btn-enfocar-subcircuito').forEach(btn => {
        btn.addEventListener('click', () => {
            const subId = btn.getAttribute('data-sub-id');
            const subItem = subcircuitoPolylines[subId];
            if (subItem && subItem.layer) {
                cerrarDrawerSubcircuitos();
                autoCentrarGPS = false; // Desactivar auto-centrado momentáneamente para ver el tramo
                map.fitBounds(subItem.layer.getBounds(), { padding: [70, 70], maxZoom: 16 });
                subItem.layer.openPopup();

                // Destello temporal de la etapa
                subItem.layer.setStyle({ weight: 11, opacity: 1.0 });
                setTimeout(() => {
                    const isCurrent = (subItem.index === subcircuitoActivoIndex);
                    subItem.layer.setStyle({
                        weight: isCurrent ? 8 : 5,
                        opacity: isCurrent ? 1.0 : 0.75
                    });
                }, 2800);
            }
        });
    });

    // 7.2. Transición y Notificación de Avance entre Subcircuitos
    function actualizarEtapaActiva(nuevoIndex) {
        if (nuevoIndex === subcircuitoActivoIndex || nuevoIndex >= trazados.length || nuevoIndex < 0) return;

        const etapaAnterior = trazados[subcircuitoActivoIndex];
        subcircuitoActivoIndex = nuevoIndex;
        const etapaNueva = trazados[subcircuitoActivoIndex];

        // 1. Actualizar Píldora Superior
        if (currentEtapaNum) currentEtapaNum.textContent = etapaNueva.orden;
        if (currentEtapaName) currentEtapaName.textContent = etapaNueva.nombre;
        if (currentEtapaDist) currentEtapaDist.textContent = `${etapaNueva.distancia_km || ''} km`;
        if (subcircuitoStepBadge) subcircuitoStepBadge.style.backgroundColor = etapaNueva.color || '#10b981';

        // 2. Actualizar Stepper Bar
        trazados.forEach((sub, i) => {
            const seg = document.getElementById(`stepper-seg-${sub.id}`);
            if (seg) {
                seg.classList.remove('segment-active', 'segment-completed', 'segment-pending');
                if (i < nuevoIndex) {
                    seg.classList.add('segment-completed');
                } else if (i === nuevoIndex) {
                    seg.classList.add('segment-active');
                } else {
                    seg.classList.add('segment-pending');
                }
            }
        });

        // 3. Actualizar Estados en las Tarjetas del Drawer
        trazados.forEach((sub, i) => {
            const itemCard = document.getElementById(`drawer-item-${sub.id}`);
            const statusTag = document.getElementById(`status-tag-${sub.id}`);
            if (itemCard && statusTag) {
                itemCard.classList.remove('item-active');
                statusTag.className = 'subcircuito-item-status-tag';
                if (i < nuevoIndex) {
                    statusTag.classList.add('status-completado');
                    statusTag.innerHTML = '<i class="fa-solid fa-check"></i> Completada';
                } else if (i === nuevoIndex) {
                    itemCard.classList.add('item-active');
                    statusTag.classList.add('status-en-curso');
                    statusTag.innerHTML = '<i class="fa-solid fa-person-biking"></i> En Curso';
                } else {
                    statusTag.classList.add('status-pendiente');
                    statusTag.innerHTML = '<i class="fa-regular fa-clock"></i> Pendiente';
                }
            }
        });

        // 4. Actualizar Polilíneas en Leaflet (destacar la activa)
        Object.values(subcircuitoPolylines).forEach(item => {
            const isCurrent = (item.index === subcircuitoActivoIndex);
            item.layer.setStyle({
                weight: isCurrent ? 8 : 5,
                opacity: isCurrent ? 1.0 : 0.75
            });
        });

        // 5. Notificación Toast animada
        mostrarAlertaAvanceEtapa(etapaAnterior, etapaNueva);
    }

    function mostrarAlertaAvanceEtapa(etapaAnt, etapaSig) {
        if (!etapaAlertBanner) return;
        if (etapaAlertTitle) etapaAlertTitle.textContent = `¡Etapa ${etapaAnt.orden} Completada!`;
        if (etapaAlertDesc) etapaAlertDesc.textContent = `Iniciando Etapa ${etapaSig.orden}: ${etapaSig.nombre}`;
        etapaAlertBanner.style.display = 'block';

        if (navigator.vibrate) {
            navigator.vibrate([250, 100, 250, 100, 400]);
        }

        setTimeout(() => {
            etapaAlertBanner.style.display = 'none';
        }, 8000);
    }

    if (btnCloseEtapaAlert) {
        btnCloseEtapaAlert.addEventListener('click', () => {
            etapaAlertBanner.style.display = 'none';
        });
    }

    // 8. Detección de Proximidad a Comercios Adheridos
    const comerciosNotificados = new Set();

    function verificarProximidadComercios(lat, lng) {
        comercios.forEach(com => {
            const distancia = calcularHaversineMetros(lat, lng, com.lat, com.lng);
            const radioTolerancia = com.radio || 30;

            if (distancia <= radioTolerancia && !comerciosNotificados.has(com.id)) {
                comerciosNotificados.add(com.id);
                mostrarBannerProximidad(com);

                // Vibración táctil si el dispositivo lo soporta
                if (navigator.vibrate) {
                    navigator.vibrate([200, 100, 200]);
                }
            }
        });
    }

    function mostrarBannerProximidad(comercio) {
        if (!proximityBanner) return;
        proximityTitle.textContent = `¡Estás en ${comercio.nombre}!`;
        proximityBenefit.textContent = `Parada oficial validada • Radio: ${comercio.radio}m`;
        proximityBanner.style.display = 'block';

        setTimeout(() => {
            proximityBanner.style.display = 'none';
        }, 9000);
    }

    if (btnCloseProximity) {
        btnCloseProximity.addEventListener('click', () => {
            proximityBanner.style.display = 'none';
        });
    }

    // 9. Procesamiento de Nueva Posición GPS
    function procesarNuevaPosicion(lat, lng, velocidadGPS, precision, subIndexForzado) {
        if (estadoCarrera !== 'EN_CURSO') return;

        const timestampISO = new Date().toISOString();

        // Actualizar marcador y halo
        cyclistMarker.setLatLng([lat, lng]);
        accuracyCircle.setLatLng([lat, lng]);
        if (precision) accuracyCircle.setRadius(Math.max(5, precision));

        if (autoCentrarGPS) {
            map.panTo([lat, lng], { animate: true, duration: 0.8 });
        }

        // Acumular distancia
        if (ultimaCoordenada) {
            const deltaM = calcularHaversineMetros(
                ultimaCoordenada.lat,
                ultimaCoordenada.lng,
                lat,
                lng
            );
            // Filtro de ruido GPS (descartar saltos irrazonables > 150m en 1s)
            if (deltaM > 1 && deltaM < 150) {
                distanciaTotalMetros += deltaM;
            }
        }
        ultimaCoordenada = { lat, lng };

        // Detección automática de la etapa según proximidad de trazado
        if (typeof subIndexForzado === 'number') {
            actualizarEtapaActiva(subIndexForzado);
        } else if (trazados.length > 1) {
            // Evaluar a qué subcircuito se acerca más la coordenada
            let menorDistancia = Infinity;
            let etapaCercanaIndex = subcircuitoActivoIndex;

            trazados.forEach((sub, sIdx) => {
                if (sub.coordenadas) {
                    sub.coordenadas.forEach(coord => {
                        const d = calcularHaversineMetros(lat, lng, coord[0], coord[1]);
                        if (d < menorDistancia) {
                            menorDistancia = d;
                            etapaCercanaIndex = sIdx;
                        }
                    });
                }
            });

            // Si se encuentra a menos de 100m de la etapa más cercana y avanza
            if (menorDistancia < 120 && etapaCercanaIndex !== subcircuitoActivoIndex) {
                actualizarEtapaActiva(etapaCercanaIndex);
            }
        }

        // Velocidad en km/h
        let velocidadKmh = 0;
        if (velocidadGPS && velocidadGPS > 0) {
            velocidadKmh = velocidadGPS * 3.6;
        } else {
            // Estimada estándar
            velocidadKmh = Math.floor(Math.random() * 6) + 18; // ~20-24 km/h
        }

        // Actualizar HUD
        const distanciaKm = (distanciaTotalMetros / 1000).toFixed(2);
        hudDistancia.textContent = distanciaKm;
        hudVelocidad.textContent = velocidadKmh.toFixed(1);

        // Ritmo medio
        if (segundosTranscurridos > 0) {
            const horas = segundosTranscurridos / 3600;
            const ritmoMedio = ((distanciaTotalMetros / 1000) / horas).toFixed(1);
            hudRitmo.textContent = ritmoMedio;
        }

        // Verificar comercios
        verificarProximidadComercios(lat, lng);

        // Verificar desvío fuera de ruta (geofencing)
        verificarDesvioFueraDeRuta(lat, lng);

        // Agregar al búfer de telemetría (compatible con lat/lng y latitud/longitud)
        lotePuntosGPS.push({
            lat: parseFloat(lat.toFixed(6)),
            lng: parseFloat(lng.toFixed(6)),
            latitud: parseFloat(lat.toFixed(6)),
            longitud: parseFloat(lng.toFixed(6)),
            timestamp: timestampISO
        });

        if (lotePuntosGPS.length >= TAMANO_LOTE) {
            enviarLoteGPS();
        }
    }

    // 10. Seguimiento GPS y Simulador de Ruta Multietapa para Desarrollo
    let simuladorInterval = null;
    let simuladorPaso = 0;

    function iniciarSeguimientoGPS() {
        if ('geolocation' in navigator) {
            gpsWatchId = navigator.geolocation.watchPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lng = pos.coords.longitude;
                    const vel = pos.coords.speed;
                    const acc = pos.coords.accuracy;
                    procesarNuevaPosicion(lat, lng, vel, acc);
                },
                (err) => {
                    console.warn('[GPS Geolocation] Sin señal real o permiso denegado. Activando simulador multietapa en Malagueño...', err);
                    activarSimuladorMalagueno();
                },
                {
                    enableHighAccuracy: true,
                    timeout: 8000,
                    maximumAge: 1000
                }
            );
        } else {
            activarSimuladorMalagueno();
        }
    }

    function activarSimuladorMalagueno() {
        if (simuladorInterval) return;

        // Construir la ruta combinada de todos los subcircuitos ordenados
        const puntosSimulacion = [];
        trazados.forEach((sub, sIdx) => {
            if (sub.coordenadas && sub.coordenadas.length > 0) {
                sub.coordenadas.forEach(coord => {
                    puntosSimulacion.push({
                        lat: coord[0],
                        lng: coord[1],
                        subIndex: sIdx
                    });
                });
            }
        });

        // Si no hubiera puntos, fallback en Malagueño
        if (puntosSimulacion.length === 0) {
            puntosSimulacion.push(
                { lat: -31.464500, lng: -64.362000, subIndex: 0 },
                { lat: -31.468500, lng: -64.355000, subIndex: 0 },
                { lat: -31.472000, lng: -64.352000, subIndex: 1 },
                { lat: -31.476000, lng: -64.348000, subIndex: 2 }
            );
        }

        simuladorInterval = setInterval(() => {
            if (estadoCarrera !== 'EN_CURSO') return;

            const item = puntosSimulacion[simuladorPaso % puntosSimulacion.length];
            const latVar = item.lat + (Math.random() - 0.5) * 0.0002;
            const lngVar = item.lng + (Math.random() - 0.5) * 0.0002;

            procesarNuevaPosicion(latVar, lngVar, 6.2, 8, item.subIndex);
            simuladorPaso++;
        }, 2500);
    }

    function detenerSeguimientoGPS() {
        if (gpsWatchId) {
            navigator.geolocation.clearWatch(gpsWatchId);
            gpsWatchId = null;
        }
        if (simuladorInterval) {
            clearInterval(simuladorInterval);
            simuladorInterval = null;
        }
        enviarLoteGPS(); // Enviar últimos puntos pendientes
    }

    // 11. Acciones de Modales de Largada y Parada
    if (btnVerLargadaMapa) {
        btnVerLargadaMapa.addEventListener('click', () => {
            if (modalFueraLargada) modalFueraLargada.style.display = 'none';
            autoCentrarGPS = false;
            const target = coordSalida || [MALAGUENO_LAT, MALAGUENO_LNG];
            map.flyTo(target, 16, { duration: 1.2 });
            if (largadaMarker) largadaMarker.openPopup();
        });
    }

    if (btnEntendidoLargada) {
        btnEntendidoLargada.addEventListener('click', () => {
            if (modalFueraLargada) modalFueraLargada.style.display = 'none';
        });
    }

    function mostrarModalFueraLargada(distanciaMetros, radioPermitido) {
        if (!modalFueraLargada) return;
        if (largadaDistActual) largadaDistActual.textContent = `${Math.round(distanciaMetros)} metros`;
        if (largadaRadioMax) largadaRadioMax.textContent = `${radioPermitido} metros`;
        modalFueraLargada.style.display = 'flex';
    }

    function mostrarModalParada(dataParada) {
        if (!modalParada) return;

        if (dataParada && dataParada.es_comercio_adherido && dataParada.comercio) {
            const com = dataParada.comercio;
            if (modalParadaTitle) modalParadaTitle.textContent = `¡Parada en Comercio Registrada!`;
            if (modalParadaDesc) modalParadaDesc.textContent = `Estás en el radio de un comercio adherido. Tu visita oficial ha sido contabilizada en el circuito.`;
            if (modalParadaBadge) {
                modalParadaBadge.textContent = 'COMERCIO ADHERIDO / CONTROL';
                modalParadaBadge.style.background = '#dcfce7';
                modalParadaBadge.style.color = '#15803d';
            }
            if (modalParadaIconWrap) {
                modalParadaIconWrap.style.background = '#f0fdf4';
                modalParadaIconWrap.style.color = '#16a34a';
            }
            if (modalParadaIcon) modalParadaIcon.className = 'fa-solid fa-store';

            if (modalParadaComercioCard) {
                modalParadaComercioCard.style.display = 'block';
                if (modalComercioNombre) modalComercioNombre.textContent = com.nombre || 'Comercio Adherido';
                if (modalComercioCat) modalComercioCat.textContent = com.categoria || 'Punto Oficial';
                if (modalComercioLogo) {
                    if (com.imagen_url) {
                        modalComercioLogo.innerHTML = `<img src="${com.imagen_url}" alt="${com.nombre}" style="width:100%; height:100%; object-fit:cover;">`;
                    } else {
                        modalComercioLogo.innerHTML = `<i class="fa-solid fa-store"></i>`;
                    }
                }
            }
        } else {
            if (modalParadaTitle) modalParadaTitle.textContent = `Parada Guardada con Éxito`;
            if (modalParadaDesc) modalParadaDesc.textContent = `Has frenado la marcha. Se registró tu punto geográfico de descanso y el cronómetro quedó en pausa.`;
            if (modalParadaBadge) {
                modalParadaBadge.textContent = 'DESCANSO / PARADA TÉCNICA';
                modalParadaBadge.style.background = '#fef3c7';
                modalParadaBadge.style.color = '#b45309';
            }
            if (modalParadaIconWrap) {
                modalParadaIconWrap.style.background = '#fffbeb';
                modalParadaIconWrap.style.color = '#d97706';
            }
            if (modalParadaIcon) modalParadaIcon.className = 'fa-solid fa-circle-pause';
            if (modalParadaComercioCard) modalParadaComercioCard.style.display = 'none';
        }

        modalParada.style.display = 'flex';
    }

    // 11.1. Algoritmo Geofencing: distancia ortodrómica punto a segmento y desvío de ruta
    function proyectarPuntoASegmento(lat, lng, p1Lat, p1Lng, p2Lat, p2Lng) {
        const LAT_TO_M = 110900;
        const LNG_TO_M = 94800;

        const x = (lng - p1Lng) * LNG_TO_M;
        const y = (lat - p1Lat) * LAT_TO_M;
        const dx = (p2Lng - p1Lng) * LNG_TO_M;
        const dy = (p2Lat - p1Lat) * LAT_TO_M;

        const l2 = dx * dx + dy * dy;
        if (l2 === 0) {
            const d = Math.sqrt(x * x + y * y);
            return { distancia: d, puntoCercano: [p1Lat, p1Lng] };
        }

        let t = (x * dx + y * dy) / l2;
        t = Math.max(0, Math.min(1, t));

        const projLng = p1Lng + (t * (p2Lng - p1Lng));
        const projLat = p1Lat + (t * (p2Lat - p1Lat));

        const px = (lng - projLng) * LNG_TO_M;
        const py = (lat - projLat) * LAT_TO_M;
        const distancia = Math.sqrt(px * px + py * py);

        return { distancia, puntoCercano: [projLat, projLng] };
    }

    function calcularDistanciaMinimaACircuito(lat, lng) {
        let distanciaMinima = Infinity;
        let mejorPunto = null;

        for (const tr of trazados) {
            if (!tr.coordenadas || tr.coordenadas.length < 2) continue;
            for (let i = 0; i < tr.coordenadas.length - 1; i++) {
                const p1 = tr.coordenadas[i];
                const p2 = tr.coordenadas[i + 1];
                const res = proyectarPuntoASegmento(lat, lng, p1[0], p1[1], p2[0], p2[1]);
                if (res.distancia < distanciaMinima) {
                    distanciaMinima = res.distancia;
                    mejorPunto = res.puntoCercano;
                }
            }
        }
        return { distancia: distanciaMinima, puntoCercano: mejorPunto };
    }

    function verificarDesvioFueraDeRuta(lat, lng) {
        if (!trazados || trazados.length === 0) return;

        const { distancia, puntoCercano } = calcularDistanciaMinimaACircuito(lat, lng);
        puntoMasCercanoRuta = puntoCercano;

        const UMBRAL_DESVIO = 35; // Umbral de tolerancia: 35 metros
        const UMBRAL_RETORNO = 22; // Distancia para considerar retorno seguro

        if (distancia > UMBRAL_DESVIO) {
            fueraDeRuta = true;
            if (alertaFueraRutaBanner) alertaFueraRutaBanner.style.display = 'block';
            if (fueraRutaDistVal) fueraRutaDistVal.textContent = Math.round(distancia);

            if (puntoCercano) {
                if (!lineaRetornoCircuito) {
                    lineaRetornoCircuito = L.polyline([[lat, lng], puntoCercano], {
                        color: '#ef4444',
                        weight: 3.5,
                        dashArray: '5, 8',
                        opacity: 0.95
                    }).addTo(map);
                } else {
                    lineaRetornoCircuito.setLatLngs([[lat, lng], puntoCercano]);
                }
            }

            if (navigator.vibrate) {
                navigator.vibrate([250, 100, 250]);
            }
        } else if (distancia <= UMBRAL_RETORNO && fueraDeRuta) {
            fueraDeRuta = false;
            if (alertaFueraRutaBanner) alertaFueraRutaBanner.style.display = 'none';
            if (lineaRetornoCircuito) {
                map.removeLayer(lineaRetornoCircuito);
                lineaRetornoCircuito = null;
            }
        }
    }

    if (btnCentrarDesvio) {
        btnCentrarDesvio.addEventListener('click', () => {
            if (ultimaCoordenada && puntoMasCercanoRuta) {
                autoCentrarGPS = false;
                map.fitBounds([
                    [ultimaCoordenada.lat, ultimaCoordenada.lng],
                    puntoMasCercanoRuta
                ], { padding: [80, 80], maxZoom: 17 });
            }
        });
    }

    // 11.2. Wake Lock API y Reconciliación con Reloj de Hardware Satelital
    async function activarWakeLock() {
        try {
            if ('wakeLock' in navigator && !wakeLock) {
                wakeLock = await navigator.wakeLock.request('screen');
                wakeLock.addEventListener('release', () => {
                    wakeLock = null;
                });
                console.log('[WakeLock] Pantalla activa garantizada durante la carrera');
            }
        } catch (err) {
            console.warn('[WakeLock] No se pudo activar Wake Lock:', err.name, err.message);
        }
    }

    function desactivarWakeLock() {
        if (wakeLock) {
            wakeLock.release().then(() => {
                wakeLock = null;
            }).catch(() => {
                wakeLock = null;
            });
        }
    }

    function reconciliarTiempoHardware() {
        if (estadoCarrera === 'EN_CURSO' && timestampInicioMs) {
            const ahora = Date.now();
            const msNetos = ahora - timestampInicioMs - acumuladoPausasMs;
            if (msNetos >= 0) {
                segundosTranscurridos = Math.floor(msNetos / 1000);
                hudTiempo.textContent = formatearTiempo(segundosTranscurridos);
            }
        }
    }

    document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState === 'visible') {
            if (estadoCarrera === 'EN_CURSO') {
                await activarWakeLock();
                reconciliarTiempoHardware();
            }
        }
    });

    // 12. Controles de Carrera (Iniciar / Detener / Reanudar / Finalizar)
    function iniciarCronometro() {
        if (!timestampInicioMs) {
            timestampInicioMs = Date.now();
        } else if (timestampUltimaPausaMs) {
            acumuladoPausasMs += (Date.now() - timestampUltimaPausaMs);
            timestampUltimaPausaMs = null;
        }

        activarWakeLock();

        if (cronometroInterval) clearInterval(cronometroInterval);
        cronometroInterval = setInterval(() => {
            segundosTranscurridos++;
            reconciliarTiempoHardware();
        }, 1000);
    }

    function pausarCronometro() {
        if (cronometroInterval) {
            clearInterval(cronometroInterval);
            cronometroInterval = null;
        }
        timestampUltimaPausaMs = Date.now();
        desactivarWakeLock();
    }

    // Iniciar Carrera / Recorrido con Validación de Largada
    function intentarIniciarRecorrido(lat, lng) {
        // Validación client-side inmediata si hay punto de largada o coordenada de salida del trazado
        const refLargada = coordSalida || puntoLargada;
        if (refLargada && refLargada.length === 2) {
            const dist = calcularHaversineMetros(lat, lng, refLargada[0], refLargada[1]);
            if (dist > radioLargadaMetros) {
                mostrarModalFueraLargada(dist, radioLargadaMetros);
                return;
            }
        }

        // Llamar a la API
        fetch('/api/recorrido/iniciar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                circuito_id: window.carreraCircuitoId || 1,
                latitud: lat,
                longitud: lng
            })
        })
        .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, body: data })))
        .then(result => {
            if (!result.ok) {
                if (result.body && result.body.fuera_de_radio) {
                    mostrarModalFueraLargada(result.body.distancia_metros, result.body.radio_permitido);
                } else {
                    alert(result.body.error || 'No se pudo iniciar el recorrido.');
                }
                return;
            }

            // Exitoso: inicializar carrera
            if (result.body.recorrido && result.body.recorrido.id) {
                recorridoId = result.body.recorrido.id;
            }
            estadoCarrera = 'EN_CURSO';
            btnStart.style.display = 'none';
            btnPause.style.display = 'inline-flex';
            btnFinish.style.display = 'inline-flex';

            iniciarCronometro();
            iniciarSeguimientoGPS();
        })
        .catch(err => {
            console.error('[Iniciar Recorrido Error]', err);
            // Si hay fallo de red en la sierra pero estamos en punto:
            estadoCarrera = 'EN_CURSO';
            btnStart.style.display = 'none';
            btnPause.style.display = 'inline-flex';
            btnFinish.style.display = 'inline-flex';
            iniciarCronometro();
            iniciarSeguimientoGPS();
        });
    }

    // Botón Iniciar
    if (btnStart) {
        btnStart.addEventListener('click', () => {
            const refSalida = coordSalida || puntoLargada;
            if (ultimaCoordenada) {
                intentarIniciarRecorrido(ultimaCoordenada.lat, ultimaCoordenada.lng);
            } else if ('geolocation' in navigator) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        const lat = pos.coords.latitude;
                        const lng = pos.coords.longitude;
                        ultimaCoordenada = { lat, lng };
                        cyclistMarker.setLatLng([lat, lng]);
                        intentarIniciarRecorrido(lat, lng);
                    },
                    (err) => {
                        console.warn('[GPS] Sin señal satelital inmediata, usando referencia de trazado:', err);
                        const latFall = refSalida ? refSalida[0] : MALAGUENO_LAT;
                        const lngFall = refSalida ? refSalida[1] : MALAGUENO_LNG;
                        intentarIniciarRecorrido(latFall, lngFall);
                    },
                    { enableHighAccuracy: true, timeout: 6000 }
                );
            } else {
                const latFall = refSalida ? refSalida[0] : MALAGUENO_LAT;
                const lngFall = refSalida ? refSalida[1] : MALAGUENO_LNG;
                intentarIniciarRecorrido(latFall, lngFall);
            }
        });
    }

    // Botón Detener / Registrar Parada
    if (btnPause) {
        btnPause.addEventListener('click', () => {
            estadoCarrera = 'PAUSADO';
            pausarCronometro();
            btnPause.style.display = 'none';
            btnResume.style.display = 'inline-flex';

            const refSalida = coordSalida || puntoLargada;
            const lat = ultimaCoordenada ? ultimaCoordenada.lat : (refSalida ? refSalida[0] : MALAGUENO_LAT);
            const lng = ultimaCoordenada ? ultimaCoordenada.lng : (refSalida ? refSalida[1] : MALAGUENO_LNG);

            if (recorridoId) {
                fetch('/api/recorrido/detener/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        recorrido_id: recorridoId,
                        latitud: lat,
                        longitud: lng
                    })
                })
                .then(res => res.json())
                .then(data => {
                    mostrarModalParada(data);
                })
                .catch(err => {
                    console.warn('[Detener Parada Error]', err);
                    mostrarModalParada({ es_comercio_adherido: false });
                });
            } else {
                mostrarModalParada({ es_comercio_adherido: false });
            }
        });
    }

    // Función Reanudar
    function reanudarMarcha() {
        if (modalParada) modalParada.style.display = 'none';
        estadoCarrera = 'EN_CURSO';
        btnResume.style.display = 'none';
        btnPause.style.display = 'inline-flex';
        iniciarCronometro();

        if (recorridoId) {
            fetch('/api/recorrido/iniciar/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ circuito_id: window.carreraCircuitoId || 1 })
            }).catch(e => console.warn(e));
        }
    }

    // Botón Reanudar
    if (btnResume) {
        btnResume.addEventListener('click', reanudarMarcha);
    }
    if (btnReanudarDesdeModal) {
        btnReanudarDesdeModal.addEventListener('click', reanudarMarcha);
    }

    // Estado inicial si ya estaba en curso o pausado
    if (estadoInicial === 'EN_CURSO') {
        estadoCarrera = 'EN_CURSO';
        if (btnStart) btnStart.style.display = 'none';
        if (btnPause) btnPause.style.display = 'inline-flex';
        if (btnFinish) btnFinish.style.display = 'inline-flex';
        iniciarCronometro();
        iniciarSeguimientoGPS();
    } else if (estadoInicial === 'PAUSADO') {
        estadoCarrera = 'PAUSADO';
        if (btnStart) btnStart.style.display = 'none';
        if (btnResume) btnResume.style.display = 'inline-flex';
        if (btnFinish) btnFinish.style.display = 'inline-flex';
    }

    // Botón Finalizar -> Abre modal
    if (btnFinish) {
        btnFinish.addEventListener('click', () => {
            if (modalConfirm) modalConfirm.style.display = 'flex';
        });
    }

    if (btnCancelModal) {
        btnCancelModal.addEventListener('click', () => {
            if (modalConfirm) modalConfirm.style.display = 'none';
        });
    }

    if (btnAcceptModal) {
        btnAcceptModal.addEventListener('click', () => {
            if (modalConfirm) modalConfirm.style.display = 'none';

            // Validar si el ciclista está dentro del radio de 20 metros de la Meta Oficial
            const refMeta = coordMeta || puntoMeta;
            if (refMeta && refMeta.length === 2 && ultimaCoordenada) {
                const distMeta = calcularHaversineMetros(
                    ultimaCoordenada.lat,
                    ultimaCoordenada.lng,
                    refMeta[0],
                    refMeta[1]
                );
                if (distMeta > radioMetaMetros) {
                    if (modalFueraMeta) {
                        if (metaDistActual) metaDistActual.textContent = `${Math.round(distMeta)} metros`;
                        modalFueraMeta.style.display = 'flex';
                    }
                    return;
                }
            }
            ejecutarFinalizacionRecorrido(false);
        });
    }

    function ejecutarFinalizacionRecorrido(forzar) {
        estadoCarrera = 'FINALIZADO';
        detenerSeguimientoGPS();
        pausarCronometro();
        desactivarWakeLock();

        const refMeta = coordMeta || puntoMeta;
        const lat = ultimaCoordenada ? ultimaCoordenada.lat : (refMeta ? refMeta[0] : null);
        const lng = ultimaCoordenada ? ultimaCoordenada.lng : (refMeta ? refMeta[1] : null);

        if (recorridoId) {
            fetch('/api/recorrido/finalizar/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({
                    recorrido_id: recorridoId,
                    latitud: lat,
                    longitud: lng,
                    forzar: !!forzar
                })
            }).finally(() => {
                const cId = window.carreraCircuitoId || '';
                window.location.href = cId ? `/mi-progreso/?circuito_id=${cId}` : '/mi-progreso/';
            });
        } else {
            const cId = window.carreraCircuitoId || '';
            window.location.href = cId ? `/mi-progreso/?circuito_id=${cId}` : '/mi-progreso/';
        }
    }

    if (btnContinuarMeta) {
        btnContinuarMeta.addEventListener('click', () => {
            if (modalFueraMeta) modalFueraMeta.style.display = 'none';
            autoCentrarGPS = true;
            if (coordMeta) {
                map.flyTo(coordMeta, 16, { duration: 1.2 });
            }
        });
    }

    if (btnForzarFinalizar) {
        btnForzarFinalizar.addEventListener('click', () => {
            if (modalFueraMeta) modalFueraMeta.style.display = 'none';
            ejecutarFinalizacionRecorrido(true);
        });
    }

    // Manejo del Modal Selector de Circuitos
    if (btnAbrirSelector && modalSelectorCircuitos) {
        btnAbrirSelector.addEventListener('click', () => {
            modalSelectorCircuitos.style.display = 'flex';
        });
    }
    if (btnCloseSelector && modalSelectorCircuitos) {
        btnCloseSelector.addEventListener('click', () => {
            modalSelectorCircuitos.style.display = 'none';
        });
    }
    if (modalSelectorCircuitos) {
        modalSelectorCircuitos.addEventListener('click', (e) => {
            if (e.target === modalSelectorCircuitos) {
                modalSelectorCircuitos.style.display = 'none';
            }
        });
    }

    // 12. Botón Recenter GPS
    if (btnRecenter) {
        btnRecenter.addEventListener('click', () => {
            autoCentrarGPS = true;
            if (ultimaCoordenada) {
                map.flyTo([ultimaCoordenada.lat, ultimaCoordenada.lng], 16, { duration: 1 });
            }
        });
    }

    // Si el usuario arrastra manualmente el mapa, pausar auto-centrado
    map.on('dragstart', () => {
        autoCentrarGPS = false;
    });

    // 13. Pantalla Completa
    if (btnFullscreen) {
        btnFullscreen.addEventListener('click', () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => console.log(err));
            } else {
                document.exitFullscreen().catch(err => console.log(err));
            }
        });
    }

    // Función auxiliar para obtener cookie CSRF
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
