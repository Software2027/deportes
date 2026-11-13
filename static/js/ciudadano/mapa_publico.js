/**
 * mapa_publico.js
 * Renderizado interactivo del Circuito Activo para el index de Ciclismo Malagueño.
 * Consume /api/circuitos/activo/ y actualiza la tarjeta flotante de telemetría.
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

    // Capa de mapa optimizada de la Municipalidad de Malagueño (OpenStreetMap HOT)
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

    // Íconos SVG para comercios y paradas
    function getComercioIcon(categoria) {
        let iconHtml = '📍';
        let bg = '#2e7d32';

        switch (categoria) {
            case 'HIDRATACION':
                iconHtml = '💧';
                bg = '#0284c7';
                break;
            case 'TALLER':
                iconHtml = '🔧';
                bg = '#f59e0b';
                break;
            case 'GASTRONOMIA':
                iconHtml = '🍔';
                bg = '#e11d48';
                break;
            case 'CONTROL':
                iconHtml = '🏁';
                bg = '#7c3aed';
                break;
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
                    font-size: 15px;
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
        const demoRuta = [
            [-31.4530, -64.3720],
            [-31.4520, -64.3610],
            [-31.4580, -64.3540],
            [-31.4640, -64.3590],
            [-31.4650, -64.3680],
            [-31.4530, -64.3720]
        ];

        const polyline = L.polyline(demoRuta, {
            color: '#4f46e5',
            weight: 6,
            opacity: 0.9,
            lineJoin: 'round'
        }).addTo(map);

        // Marcador Inicio/Fin
        L.marker(demoRuta[0], {
            icon: L.divIcon({
                className: 'start-marker',
                html: '<div style="background:#ef4444; width:16px; height:16px; border-radius:50%; border:3px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,0.4);"></div>',
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            })
        }).addTo(map).bindPopup('<b>Punto de Partida / Llegada</b>');

        // Puestos de ejemplo
        const comerciosDemo = [
            { lat: -31.4525, lng: -64.3640, nombre: 'Hidratación Plaza Central', cat: 'HIDRATACION', radio: 30 },
            { lat: -31.4590, lng: -64.3560, nombre: 'Taller CicloRayo', cat: 'TALLER', radio: 40 },
            { lat: -31.4645, lng: -64.3620, nombre: 'Punto de Control Sur', cat: 'CONTROL', radio: 30 }
        ];

        comerciosDemo.forEach(c => {
            L.circle([c.lat, c.lng], {
                radius: c.radio,
                color: '#3b82f6',
                fillColor: '#3b82f6',
                fillOpacity: 0.15,
                weight: 1
            }).addTo(map);

            L.marker([c.lat, c.lng], { icon: getComercioIcon(c.cat) })
                .addTo(map)
                .bindPopup(`<b>${c.nombre}</b><br><span style="font-size:12px; color:#64748b;">Radio: ${c.radio}m</span>`);
        });

        map.fitBounds(polyline.getBounds(), { padding: [50, 50] });
    }

    // Cargar circuito oficial de la API
    fetch('/api/circuitos/activo/')
        .then(res => {
            if (!res.ok) throw new Error('Sin circuito activo');
            return res.json();
        })
        .then(data => {
            const bounds = L.latLngBounds([]);
            let totalPuntos = 0;

            if (data.subcircuitos && data.subcircuitos.length > 0) {
                data.subcircuitos.forEach(sub => {
                    const puntos = sub.trazado || [];
                    if (puntos.length > 0) {
                        totalPuntos += puntos.length;
                        const latlngs = puntos.map(p => [parseFloat(p.latitud), parseFloat(p.longitud)]);
                        latlngs.forEach(ll => bounds.extend(ll));

                        const polyline = L.polyline(latlngs, {
                            color: sub.color_capa || '#4f46e5',
                            weight: 6,
                            opacity: 0.9,
                            lineJoin: 'round'
                        }).addTo(map);

                        polyline.bindTooltip(`<b>${sub.nombre}</b>`, { sticky: true });
                    }
                });
            }

            if (data.comercios && data.comercios.length > 0) {
                const floatingComercios = document.getElementById('floating-comercios');
                if (floatingComercios) floatingComercios.innerText = data.comercios.length;

                data.comercios.forEach(com => {
                    const lat = parseFloat(com.latitud);
                    const lng = parseFloat(com.longitud);
                    bounds.extend([lat, lng]);

                    L.circle([lat, lng], {
                        radius: com.radio_tolerancia_metros || 30,
                        color: '#3b82f6',
                        fillColor: '#3b82f6',
                        fillOpacity: 0.15,
                        weight: 1
                    }).addTo(map);

                    const marker = L.marker([lat, lng], {
                        icon: getComercioIcon(com.categoria)
                    }).addTo(map);

                    const imgHtml = com.imagen ? `<img src="${com.imagen}" style="width:100%; border-radius:6px; margin-top:6px;" alt="${com.nombre}">` : '';
                    marker.bindPopup(`
                        <div style="font-family:'Inter', sans-serif; font-size:13px;">
                            <b style="font-size:14px; color:#1e293b;">${com.nombre}</b><br>
                            <span style="color:#16a34a; font-weight:600;">${com.categoria_display || com.categoria}</span><br>
                            <span style="color:#64748b;">Radio: ${com.radio_tolerancia_metros}m</span>
                            ${imgHtml}
                        </div>
                    `);
                });
            }

            if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [50, 50] });
            } else {
                renderizarDemoMalagueno();
            }
        })
        .catch(() => {
            renderizarDemoMalagueno();
        });
});
