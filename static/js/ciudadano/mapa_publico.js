/**
 * mapa_publico.js
 * Renderizado interactivo y dinámico de Circuitos Municipales para el index de Ciclismo Malagueño.
 * Permite cambiar de circuito en tiempo real sin recargar la página,
 * consumiendo /api/circuitos/activo/?circuito_id=X y sincronizando el mapa Leaflet y la card flotante.
 */

document.addEventListener('DOMContentLoaded', () => {
    const mapElement = document.getElementById('mapa-publico');
    if (!mapElement) return;

    // Coordenadas oficiales de Malagueño, Córdoba
    const MALAGUENO_LAT = -31.4589;
    const MALAGUENO_LNG = -64.3644;
    const DEFAULT_ZOOM = 14;

    // Inicializar mapa de Leaflet
    const map = L.map('mapa-publico', {
        zoomControl: true,
        scrollWheelZoom: false,
    }).setView([MALAGUENO_LAT, MALAGUENO_LNG], DEFAULT_ZOOM);

    // Capa base OpenStreetMap HOT optimizada
    L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
        maxZoom: 18,
        minZoom: 11,
        subdomains: 'abc',
        keepBuffer: 6,
        updateWhenIdle: true,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles style by <a href="https://www.hotosm.org/" target="_blank">HOT</a> | Muni Malagueño'
    }).addTo(map);

    map.on('focus', () => { map.scrollWheelZoom.enable(); });
    map.on('blur', () => { map.scrollWheelZoom.disable(); });

    // Grupo de capas activo para poder limpiar y redibujar trazados sin recargar el mapa
    const capasCircuitos = L.layerGroup().addTo(map);

    // Íconos SVG para comercios y puntos de control usando FontAwesome
    function getComercioIcon(categoria) {
        let iconHtml = '<i class="fa-solid fa-location-dot" style="color:#ffffff;"></i>';
        let bg = '#16a34a';

        const catUpper = String(categoria || '').toUpperCase();
        if (catUpper.includes('HIDRATAC')) {
            iconHtml = '<i class="fa-solid fa-droplet" style="color:#ffffff;"></i>';
            bg = '#0284c7';
        } else if (catUpper.includes('TALLER') || catUpper.includes('MECANIC') || catUpper.includes('REPUEST')) {
            iconHtml = '<i class="fa-solid fa-wrench" style="color:#ffffff;"></i>';
            bg = '#f59e0b';
        } else if (catUpper.includes('GASTRONOM') || catUpper.includes('ALIMENT') || catUpper.includes('RESTAURANT') || catUpper.includes('BAR')) {
            iconHtml = '<i class="fa-solid fa-utensils" style="color:#ffffff;"></i>';
            bg = '#e11d48';
        } else if (catUpper.includes('CONTROL') || catUpper.includes('META') || catUpper.includes('LARGADA')) {
            iconHtml = '<i class="fa-solid fa-flag-checkered" style="color:#ffffff;"></i>';
            bg = '#7c3aed';
        } else if (catUpper.includes('SALUD') || catUpper.includes('MEDIC') || catUpper.includes('PRIMEROS')) {
            iconHtml = '<i class="fa-solid fa-kit-medical" style="color:#ffffff;"></i>';
            bg = '#dc2626';
        } else {
            iconHtml = '<i class="fa-solid fa-store" style="color:#ffffff;"></i>';
            bg = '#16a34a';
        }

        return L.divIcon({
            className: 'custom-comercio-marker',
            html: `
                <div style="
                    background: ${bg};
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                    border: 2px solid #ffffff;
                ">
                    ${iconHtml}
                </div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16]
        });
    }

    // Circuito Demo de Respaldo alrededor de Malagueño si no hay datos en BD
    function renderizarDemoMalagueno() {
        capasCircuitos.clearLayers();

        const demoRuta = [
            [-31.4530, -64.3720],
            [-31.4520, -64.3610],
            [-31.4580, -64.3540],
            [-31.4640, -64.3590],
            [-31.4650, -64.3680],
            [-31.4530, -64.3720]
        ];

        const polyline = L.polyline(demoRuta, {
            color: '#16a34a',
            weight: 6,
            opacity: 0.9,
            lineJoin: 'round'
        }).addTo(capasCircuitos);

        L.marker(demoRuta[0], {
            icon: L.divIcon({
                className: 'start-marker',
                html: '<div style="background:#16a34a; width:16px; height:16px; border-radius:50%; border:3px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,0.4);"></div>',
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            })
        }).addTo(capasCircuitos).bindPopup('<b>Punto de Partida / Llegada</b>');

        map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
    }

    /**
     * Carga y renderiza dinámicamente un circuito por ID en el mapa de Leaflet
     * y actualiza los elementos UI (card flotante, botones GPS y nombres).
     */
    function cargarCircuitoEnMapa(circuitoId, scrollHaciaMapa = false) {
        capasCircuitos.clearLayers();

        const urlParams = new URLSearchParams(window.location.search);
        const idFinal = circuitoId || urlParams.get('circuito_id') || mapElement.getAttribute('data-circuito-id') || '';

        const apiUrl = idFinal ? `/api/circuitos/activo/?circuito_id=${encodeURIComponent(idFinal)}` : '/api/circuitos/activo/';

        fetch(apiUrl)
            .then(res => {
                if (!res.ok) throw new Error('No se encontró el circuito');
                return res.json();
            })
            .then(data => {
                const bounds = L.latLngBounds([]);
                let totalPuntos = 0;
                let primerPunto = null;
                let ultimoPunto = null;

                // 1. Dibujar subcircuitos / etapas
                if (data.subcircuitos && data.subcircuitos.length > 0) {
                    // Ordenar etapas estrictamente por número de orden
                    const subsOrdenados = [...data.subcircuitos].sort((a, b) => (Number(a.orden) || 0) - (Number(b.orden) || 0));

                    subsOrdenados.forEach((sub, sIdx) => {
                        const puntos = sub.trazado || [];
                        if (puntos.length > 0) {
                            totalPuntos += puntos.length;
                            const latlngs = puntos.map(p => [parseFloat(p.latitud), parseFloat(p.longitud)]);
                            latlngs.forEach(ll => bounds.extend(ll));

                            if (!primerPunto && latlngs.length > 0) {
                                primerPunto = latlngs[0];
                            }
                            if (sIdx === subsOrdenados.length - 1 && latlngs.length > 0) {
                                ultimoPunto = latlngs[latlngs.length - 1];
                            }

                            const distKmSub = (sub.distancia_km !== undefined && sub.distancia_km !== null)
                                ? parseFloat(sub.distancia_km).toFixed(2)
                                : (sub.distancia_metros ? (sub.distancia_metros / 1000).toFixed(2) : '0.00');

                            const polyline = L.polyline(latlngs, {
                                color: sub.color_capa || '#16a34a',
                                weight: 6,
                                opacity: 0.9,
                                lineJoin: 'round'
                            }).addTo(capasCircuitos);

                            polyline.bindTooltip(`
                                <div style="font-family:'Outfit',sans-serif; font-size:12px; line-height:1.35;">
                                    <span style="font-weight:800; color:${sub.color_capa || '#16a34a'}; text-transform:uppercase; font-size:10px; letter-spacing:0.5px;">Etapa ${sub.orden}</span><br>
                                    <strong style="color:#0f172a; font-size:13px;">${sub.nombre}</strong><br>
                                    <span style="color:#16a34a; font-weight:700;"><i class="fa-solid fa-road"></i> ${distKmSub} km</span>
                                </div>
                            `, { sticky: true });

                            polyline.bindPopup(`
                                <div style="font-family:'Outfit',sans-serif; padding:4px 2px; min-width:190px;">
                                    <span style="background:${sub.color_capa || '#16a34a'}; color:#ffffff; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:800; display:inline-block; letter-spacing:0.4px;">Etapa ${sub.orden}</span>
                                    <h4 style="margin:8px 0 4px 0; font-size:15px; font-weight:800; color:#0f172a; line-height:1.25;">${sub.nombre}</h4>
                                    <div style="font-size:13px; color:#475569; margin-top:6px; padding-top:6px; border-top:1px dashed #e2e8f0; display:flex; justify-content:space-between; align-items:baseline;">
                                        <span style="font-weight:600;">Longitud del Tramo:</span>
                                        <div>
                                            <strong style="color:#16a34a; font-size:15px; font-weight:800;">${distKmSub} km</strong>
                                            ${sub.distancia_metros ? `<span style="color:#94a3b8; font-size:11px;"> (${Math.round(sub.distancia_metros)} m)</span>` : ''}
                                        </div>
                                    </div>
                                </div>
                            `);
                        }
                    });
                }

                // Detectar si la largada y la meta coinciden (circuito circular / cerrado)
                let esCircuitoCerrado = false;
                if (primerPunto && ultimoPunto) {
                    const diffLat = Math.abs(primerPunto[0] - ultimoPunto[0]);
                    const diffLng = Math.abs(primerPunto[1] - ultimoPunto[1]);
                    // ~0.00045 grados equivalen a ~50 metros
                    if (diffLat < 0.00045 && diffLng < 0.00045) {
                        esCircuitoCerrado = true;
                    }
                }

                if (esCircuitoCerrado && primerPunto) {
                    // Marcador Unificado para Circuitos Cerrados / Bucles
                    L.marker(primerPunto, {
                        icon: L.divIcon({
                            className: 'start-finish-marker-circle',
                            html: `
                                <div style="
                                    background: linear-gradient(135deg, #16a34a 0%, #0f172a 100%);
                                    color: #ffffff;
                                    width: 36px;
                                    height: 36px;
                                    border-radius: 50%;
                                    border: 3px solid #ffffff;
                                    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 15px;
                                ">
                                    <i class="fa-solid fa-flag-checkered"></i>
                                </div>
                            `,
                            iconSize: [36, 36],
                            iconAnchor: [18, 18],
                            popupAnchor: [0, -18]
                        })
                    }).addTo(capasCircuitos).bindPopup(`
                        <div style="font-family:'Outfit', sans-serif; font-size:13px; text-align:center;">
                            <b style="font-size:14px; color:#16a34a;"><i class="fa-solid fa-flag-checkered" style="margin-right:4px;"></i> Largada y Meta</b><br>
                            <span style="color:#64748b; font-size:12px;">Circuito Cerrado (Salida y Llegada)</span><br>
                            <strong>${data.nombre}</strong>
                        </div>
                    `).bindTooltip('<b><i class="fa-solid fa-flag-checkered" style="color:#16a34a; margin-right:3px;"></i> Largada y Meta</b>', { permanent: false, direction: 'top', offset: [0, -18] });
                } else {
                    // 1.1 Marcador Oficial de LARGADA (Inicio)
                    if (primerPunto) {
                        L.marker(primerPunto, {
                            icon: L.divIcon({
                                className: 'start-marker-flag',
                                html: `
                                    <div style="
                                        background: #16a34a;
                                        color: #ffffff;
                                        width: 32px;
                                        height: 32px;
                                        border-radius: 50%;
                                        border: 2.5px solid #ffffff;
                                        box-shadow: 0 3px 10px rgba(22, 163, 74, 0.45);
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        font-size: 14px;
                                    ">
                                        <i class="fa-solid fa-play" style="margin-left: 2px;"></i>
                                    </div>
                                `,
                                iconSize: [32, 32],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            })
                        }).addTo(capasCircuitos).bindPopup(`
                            <div style="font-family:'Outfit', sans-serif; font-size:13px;">
                                <b style="font-size:14px; color:#16a34a;"><i class="fa-solid fa-circle-play" style="margin-right:4px;"></i> Largada Oficial (Km 0)</b><br>
                                <span style="color:#64748b;">Punto de partida del circuito</span><br>
                                <strong>${data.nombre}</strong>
                            </div>
                        `).bindTooltip('<b><i class="fa-solid fa-circle-play" style="color:#16a34a; margin-right:3px;"></i> Largada (Km 0)</b>', { permanent: false, direction: 'top', offset: [0, -16] });
                    }

                    // 1.2 Marcador Oficial de META (Final / Llegada)
                    if (ultimoPunto) {
                        L.marker(ultimoPunto, {
                            icon: L.divIcon({
                                className: 'finish-marker-flag',
                                html: `
                                    <div style="
                                        background: #dc2626;
                                        color: #ffffff;
                                        width: 32px;
                                        height: 32px;
                                        border-radius: 50%;
                                        border: 2.5px solid #ffffff;
                                        box-shadow: 0 3px 10px rgba(220, 38, 38, 0.45);
                                        display: flex;
                                        align-items: center;
                                        justify-content: center;
                                        font-size: 15px;
                                    ">
                                        <i class="fa-solid fa-flag-checkered"></i>
                                    </div>
                                `,
                                iconSize: [32, 32],
                                iconAnchor: [16, 16],
                                popupAnchor: [0, -16]
                            })
                        }).addTo(capasCircuitos).bindPopup(`
                            <div style="font-family:'Outfit', sans-serif; font-size:13px;">
                                <b style="font-size:14px; color:#dc2626;"><i class="fa-solid fa-flag-checkered" style="margin-right:4px;"></i> Meta / Final del Circuito</b><br>
                                <span style="color:#64748b;">Punto de llegada oficial y toma de tiempo</span><br>
                                <strong>${data.nombre}</strong>
                            </div>
                        `).bindTooltip('<b><i class="fa-solid fa-flag-checkered" style="color:#dc2626; margin-right:3px;"></i> Meta / Final</b>', { permanent: false, direction: 'top', offset: [0, -16] });
                    }
                }

                // 2. Dibujar comercios adheridos
                if (data.comercios && data.comercios.length > 0) {
                    data.comercios.forEach(com => {
                        const lat = parseFloat(com.latitud);
                        const lng = parseFloat(com.longitud);
                        bounds.extend([lat, lng]);

                        L.circle([lat, lng], {
                            radius: com.radio_tolerancia_metros || 30,
                            color: '#16a34a',
                            fillColor: '#16a34a',
                            fillOpacity: 0.15,
                            weight: 1
                        }).addTo(capasCircuitos);

                        const marker = L.marker([lat, lng], {
                            icon: getComercioIcon(com.categoria)
                        }).addTo(capasCircuitos);

                        const imgHtml = com.imagen ? `<img src="${com.imagen}" style="width:100%; border-radius:6px; margin-top:6px; max-height:120px; object-fit:cover;" alt="${com.nombre}">` : '';
                        marker.bindPopup(`
                            <div style="font-family:'Inter', sans-serif; font-size:13px; max-width:200px;">
                                <b style="font-size:14px; color:#0f172a;">${com.nombre}</b><br>
                                <span style="color:#16a34a; font-weight:700;">${com.categoria_display || com.categoria}</span><br>
                                <span style="color:#64748b; font-size:11px;">Radio de asistencia: ${com.radio_tolerancia_metros || 20}m</span>
                                ${imgHtml}
                            </div>
                        `);
                    });
                }

                // 3. Ajustar zoom y encuadre
                if (bounds.isValid()) {
                    map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
                } else {
                    renderizarDemoMalagueno();
                }

                // 4. Actualizar textos en la UI
                const titleEl = document.getElementById('map-circuito-nombre');
                if (titleEl) titleEl.innerText = data.nombre;

                const floatingNombre = document.getElementById('floating-circuito-nombre');
                if (floatingNombre) floatingNombre.innerText = `Circuito: ${data.nombre}`;

                const floatingDist = document.getElementById('floating-distancia');
                if (floatingDist) {
                    const distKm = data.distancia_total_km || '0.0';
                    floatingDist.innerText = `${distKm} KM`;
                }

                const floatingEtapas = document.getElementById('floating-controles');
                if (floatingEtapas) {
                    const cantEtapas = (data.subcircuitos || []).length;
                    floatingEtapas.innerText = `${cantEtapas} etapa${cantEtapas !== 1 ? 's' : ''}`;
                }

                const floatingComercios = document.getElementById('floating-comercios');
                if (floatingComercios) {
                    const cantCom = (data.comercios || []).length;
                    floatingComercios.innerText = `${cantCom} punto${cantCom !== 1 ? 's' : ''}`;
                }

                // 4.1 Actualizar Desglose de KM por Tramo en la Card Flotante
                const tramosListEl = document.getElementById('floating-tramos-list');
                if (tramosListEl && data.subcircuitos && data.subcircuitos.length > 0) {
                    const subsOrdenados = [...data.subcircuitos].sort((a, b) => (Number(a.orden) || 0) - (Number(b.orden) || 0));
                    tramosListEl.innerHTML = subsOrdenados.map(sub => {
                        const dKm = (sub.distancia_km !== undefined && sub.distancia_km !== null)
                            ? parseFloat(sub.distancia_km).toFixed(2)
                            : (sub.distancia_metros ? (sub.distancia_metros / 1000).toFixed(2) : '0.00');
                        return `
                            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.78rem; background:#f8fafc; padding:0.25rem 0.5rem; border-radius:6px; border-left:3px solid ${sub.color_capa || '#16a34a'};">
                                <span style="color:#334155; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:140px;" title="Etapa ${sub.orden}: ${sub.nombre}">E${sub.orden}: ${sub.nombre}</span>
                                <strong style="color:#0f172a; margin-left:0.5rem;">${dKm} km</strong>
                            </div>
                        `;
                    }).join('');
                } else if (tramosListEl) {
                    tramosListEl.innerHTML = '<span style="font-size:0.74rem; color:#94a3b8; font-style:italic;">Sin tramos registrados</span>';
                }

                // 5. Actualizar botones de acción GPS y Pantalla Completa
                const btnGps = document.getElementById('btn-pedalear-gps');
                if (btnGps) {
                    const currentHref = btnGps.getAttribute('href') || '';
                    if (currentHref.includes('circuito_id=')) {
                        btnGps.setAttribute('href', currentHref.replace(/circuito_id=\d+/, `circuito_id=${data.id}`));
                    } else if (currentHref.includes('?')) {
                        btnGps.setAttribute('href', `${currentHref}&circuito_id=${data.id}`);
                    } else {
                        btnGps.setAttribute('href', `${currentHref}?circuito_id=${data.id}`);
                    }
                }

                const btnFull = document.getElementById('btn-fullscreen-map');
                if (btnFull) {
                    btnFull.setAttribute('href', `/mapa-carrera/?circuito_id=${data.id}`);
                }

                // 6. Actualizar selector de pastillas superior
                document.querySelectorAll('.btn-circuito-pill').forEach(pill => {
                    const pillId = pill.getAttribute('data-circuito-id');
                    if (String(pillId) === String(data.id)) {
                        pill.style.background = '#16a34a';
                        pill.style.borderColor = '#16a34a';
                        pill.style.color = '#ffffff';
                    } else {
                        pill.style.background = '#ffffff';
                        pill.style.borderColor = '#cbd5e1';
                        pill.style.color = '#334155';
                    }
                });

                // 7. Actualizar card activa inferior
                document.querySelectorAll('.circuit-single-card').forEach(card => {
                    const cardId = card.getAttribute('data-circuito-id');
                    if (String(cardId) === String(data.id)) {
                        card.classList.add('card-is-current');
                    } else {
                        card.classList.remove('card-is-current');
                    }
                });

                // 8. Scroll suave hacia la sección del mapa si se solicitó
                if (scrollHaciaMapa) {
                    const mapSection = document.getElementById('circuito');
                    if (mapSection) {
                        mapSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
            })
            .catch(() => {
                renderizarDemoMalagueno();
            });
    }

    // Exponer globalmente para permitir llamados programáticos
    window.cargarCircuitoEnMapa = cargarCircuitoEnMapa;

    // Carga inicial del circuito actual
    const urlParams = new URLSearchParams(window.location.search);
    const inicialId = urlParams.get('circuito_id') || mapElement.getAttribute('data-circuito-id') || '';
    cargarCircuitoEnMapa(inicialId, false);

    // Interceptar clics en cualquier botón "Ver Recorrido" para cambiar en vivo sin recargar
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-ver-recorrido');
        if (btn) {
            const circuitoId = btn.getAttribute('data-circuito-id');
            if (circuitoId) {
                e.preventDefault();
                cargarCircuitoEnMapa(circuitoId, true);

                // Actualizar la URL en el historial para compartir o recargar
                try {
                    window.history.pushState(null, '', `?circuito_id=${circuitoId}#circuito`);
                } catch (err) {}
            }
        }
    });

    // Escuchar cambios de navegación atrás/adelante del navegador
    window.addEventListener('popstate', () => {
        const params = new URLSearchParams(window.location.search);
        const cId = params.get('circuito_id') || '';
        cargarCircuitoEnMapa(cId, false);
    });
});
