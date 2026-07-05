import { state } from './state.js?v=1.0.5';

export let map = null;
export let trackShadowLayer = null;
export let trackLayer = null;
export const markerLayers = [];
export let hoveredMapMarker = null;

export function initMap(elementId) {
    if (map) return map;
    
    map = L.map(elementId, {
        zoomControl: true,
        attributionControl: false
    }).setView([45.9227, 6.8685], 11); // Default to Chamonix
    
    // Add OpenTopoMap terrain tiles
    L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
        maxZoom: 17
    }).addTo(map);

    return map;
}

export function invalidateMapSize() {
    if (map) {
        map.invalidateSize();
    }
}

// Reusable color map matching the map markers and elevation profile dots
export function getSymbolColor(garminSym) {
    if (garminSym === 'Food') return '#f97316'; // Orange
    if (garminSym === 'Water Source') return '#0ea5e9'; // Blue
    if (garminSym === 'Summit') return '#a855f7'; // Purple
    if (garminSym === 'Medical Facility' || garminSym === 'First Aid') return '#ef4444'; // Red
    if (garminSym === 'Aid Station') return '#10b981'; // Green
    if (garminSym === 'Toilet') return '#8b5cf6'; // Indigo
    if (garminSym === 'Shower') return '#06b6d4'; // Cyan
    if (garminSym === 'Campsite') return '#84cc16'; // Lime
    if (garminSym === 'Shelter') return '#b45309'; // Amber/Brown
    if (garminSym === 'Rest Area') return '#475569'; // Slate
    if (garminSym === 'Transition') return '#ec4899'; // Pink
    if (garminSym === 'Danger') return '#f43f5e'; // Rose
    if (garminSym === 'Checkpoint') return '#eab308'; // Yellow
    return '#0284c7'; // Cyan / Generic Point
}

// Map helper icons with inline SVGs
export function getMarkerIcon(garminSym) {
    const color = getSymbolColor(garminSym);
    let svgHtml = '';
    
    if (garminSym === 'Food') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v14M12 16H9M18 2v14M18 16h-3M6 2v4a3 3 0 0 0 6 0V2"/></svg>`;
    } else if (garminSym === 'Water Source') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 C12 2 6 10 6 15a6 6 0 0 0 12 0 C18 10 12 2 12 2 Z"/></svg>`;
    } else if (garminSym === 'Summit') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 L22 22 H2 Z"/></svg>`;
    } else if (garminSym === 'Medical Facility' || garminSym === 'First Aid') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>`;
    } else if (garminSym === 'Aid Station') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>`;
    } else if (garminSym === 'Toilet') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9 22V12h6v10M12 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>`;
    } else if (garminSym === 'Shower') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16M12 4v8M8 16h8M6 20h12"/></svg>`;
    } else if (garminSym === 'Campsite') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 L22 20 H2 Z M12 2 v18"/></svg>`;
    } else if (garminSym === 'Shelter') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></svg>`;
    } else if (garminSym === 'Rest Area') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M17 8h1a4 4 0 1 1 0 8h-1M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"/></svg>`;
    } else if (garminSym === 'Transition') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3h5v5M21 3L14 10M8 21H3v-5M3 21l7-7"/></svg>`;
    } else if (garminSym === 'Danger') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v12M12 18h.01"/></svg>`;
    } else if (garminSym === 'Checkpoint') {
        svgHtml = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7"/></svg>`;
    } else {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>`;
    }
    
    return L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: ${color}; width: 22px; height: 22px; border: 2px solid #ffffff; border-radius: 50%; box-shadow: 0 2px 8px rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; transform: translate(0px, 0px);">${svgHtml}</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
    });
}

export function getMiniIconSvg(garminSym) {
    const color = getSymbolColor(garminSym);
    let svgHtml = '';
    
    if (garminSym === 'Food') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v14M12 16H9M18 2v14M18 16h-3M6 2v4a3 3 0 0 0 6 0V2"/></svg>`;
    } else if (garminSym === 'Water Source') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 C12 2 6 10 6 15a6 6 0 0 0 12 0 C18 10 12 2 12 2 Z"/></svg>`;
    } else if (garminSym === 'Summit') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 L22 22 H2 Z"/></svg>`;
    } else if (garminSym === 'Medical Facility' || garminSym === 'First Aid') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>`;
    } else if (garminSym === 'Aid Station') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>`;
    } else if (garminSym === 'Toilet') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M9 22V12h6v10M12 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>`;
    } else if (garminSym === 'Shower') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16M12 4v8M8 16h8M6 20h12"/></svg>`;
    } else if (garminSym === 'Campsite') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 L22 20 H2 Z M12 2 v18"/></svg>`;
    } else if (garminSym === 'Shelter') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></svg>`;
    } else if (garminSym === 'Rest Area') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M17 8h1a4 4 0 1 1 0 8h-1M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z"/></svg>`;
    } else if (garminSym === 'Transition') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3h5v5M21 3L14 10M8 21H3v-5M3 21l7-7"/></svg>`;
    } else if (garminSym === 'Danger') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v12M12 18h.01"/></svg>`;
    } else if (garminSym === 'Checkpoint') {
        svgHtml = `<svg viewBox="0 0 24 24" width="10" height="10" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7"/></svg>`;
    } else {
        svgHtml = `<svg viewBox="0 0 24 24" width="8" height="8" stroke="white" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/></svg>`;
    }
    
    return `<span style="display: inline-flex; align-items: center; justify-content: center; background-color: ${color}; width: 18px; height: 18px; border-radius: 50%; margin-right: 6px; vertical-align: middle;">${svgHtml}</span>`;
}

export function drawRouteOnMap() {
    if (!map) return;
    
    // Clear old layers
    if (trackShadowLayer) {
        map.removeLayer(trackShadowLayer);
        trackShadowLayer = null;
    }
    if (trackLayer) {
        map.removeLayer(trackLayer);
        trackLayer = null;
    }
    
    const latLons = state.gpxTrackPoints.map(p => [p.lat, p.lon]);
    if (latLons.length === 0) return;
    
    // Resolve dynamic track color based on kilometer-effort or state.raceCategory
    const dist = state.totalDistance;
    const isTDS = state.raceName && state.raceName.toUpperCase().includes('TDS');
    const cat = state.raceCategory ? state.raceCategory.toUpperCase().replace('WS', '').replace('KM', 'K') : '';
    const kmEffort = dist + (state.totalGain / 100);
    
    let trackColor = '#7ddf65';
    if (isTDS) {
        trackColor = '#00ade9';
    } else if (cat.includes('100M')) {
        trackColor = '#ef4444';
    } else if (cat.includes('100K')) {
        trackColor = '#7ddf65';
    } else if (cat.includes('50K')) {
        trackColor = '#ff9600';
    } else if (cat.includes('20K')) {
        trackColor = '#ffff00';
    } else {
        if (kmEffort < 35) trackColor = '#ffff00';
        else if (kmEffort < 80) trackColor = '#ff9600';
        else if (kmEffort < 140) trackColor = '#7ddf65';
        else trackColor = '#ef4444';
    }
    
    // Create dark shadow layer (wider) for background legibility
    trackShadowLayer = L.polyline(latLons, {
        color: '#000000',
        weight: 7,
        opacity: 0.5,
        interactive: false
    }).addTo(map);
    
    trackLayer = L.polyline(latLons, {
        color: trackColor,
        weight: 4,
        opacity: 0.95
    }).addTo(map);
    
    trackLayer.addTo(map);
    map.fitBounds(trackLayer.getBounds());
}

export function plotCheckpointsOnMap() {
    if (!map) return;
    
    // Clear old markers
    markerLayers.forEach(m => map.removeLayer(m));
    markerLayers.length = 0;

    // Filter active checkpoints that have valid coordinates
    const activeCheckpoints = state.checkpoints.filter(poi => poi.use && poi.lat !== undefined && poi.lon !== undefined);

    activeCheckpoints.forEach((poi, idx) => {
        const marker = L.marker([poi.lat, poi.lon], {
            icon: getMarkerIcon(poi.icon)
        });
        
        let fromLastHtml = '';
        let toNextHtml = '';
        
        const lang = state.locale || 'fr';
        const distLabel = lang === 'fr' ? 'Distance' : 'Distance';
        const elevLabel = lang === 'fr' ? 'Altitude' : 'Elevation';
        const denivLabel = lang === 'fr' ? 'Dénivelé' : 'Elevation Change';
        const unit = state.unit || 'km';

        if (idx > 0) {
            const prev = activeCheckpoints[idx - 1];
            const dDist = poi.dist - prev.dist;
            const dEle = poi.ele - prev.ele;
            const sign = dEle >= 0 ? '+' : '';
            const displayDDist = unit === 'mi' ? dDist * 0.621371 : dDist;
            const headerText = lang === 'fr' ? 'Depuis le point précédent :' : 'From last checkpoint:';
            fromLastHtml = `
                <div style="border-top: 1px dashed rgba(255,255,255,0.15); margin: 0.5rem 0;"></div>
                <div style="font-family: var(--font-title); font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">${headerText}</div>
                <div style="font-size: 0.8rem; color: var(--text-color); margin-bottom: 0.15rem;">${distLabel}: <strong>${displayDDist.toFixed(1)} ${unit}</strong></div>
                <div style="font-size: 0.8rem; color: var(--text-color);">${denivLabel}: <strong>${sign}${dEle} m</strong></div>
            `;
        }
        
        if (idx < activeCheckpoints.length - 1) {
            const next = activeCheckpoints[idx + 1];
            const dDist = next.dist - poi.dist;
            const dEle = next.ele - poi.ele;
            const sign = dEle >= 0 ? '+' : '';
            const displayDDist = unit === 'mi' ? dDist * 0.621371 : dDist;
            const headerText = lang === 'fr' ? 'Vers le point suivant :' : 'To next checkpoint:';
            toNextHtml = `
                <div style="border-top: 1px dashed rgba(255,255,255,0.15); margin: 0.5rem 0;"></div>
                <div style="font-family: var(--font-title); font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.25rem;">${headerText}</div>
                <div style="font-size: 0.8rem; color: var(--text-color); margin-bottom: 0.15rem;">${distLabel}: <strong>${displayDDist.toFixed(1)} ${unit}</strong></div>
                <div style="font-size: 0.8rem; color: var(--text-color);">${denivLabel}: <strong>${sign}${dEle} m</strong></div>
            `;
        }

        const iconHtml = getMiniIconSvg(poi.icon);
        const displayPoiDist = unit === 'mi' ? poi.dist * 0.621371 : poi.dist;

        const popupContent = `
            <div style="font-family: var(--font-title); font-size: 0.95rem; font-weight: 700; color: var(--accent-color); margin-bottom: 0.4rem;">${poi.name}</div>
            <div style="display: flex; align-items: center; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.4rem;">
                ${iconHtml} <span style="font-weight: 600;">${poi.icon}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-color); margin-bottom: 0.15rem;">${distLabel}: <strong>${displayPoiDist.toFixed(1)} ${unit}</strong></div>
            <div style="font-size: 0.8rem; color: var(--text-color);">${elevLabel}: <strong>${poi.ele} m</strong></div>
            ${fromLastHtml}
            ${toNextHtml}
        `;
        
        marker.bindPopup(popupContent);
        marker.addTo(map);
        markerLayers.push(marker);
    });
}

export function snapPOIsToTrack() {
    if (state.gpxTrackPoints.length === 0) return;
    
    const settingSnapThreshold = document.getElementById('snap-threshold');
    const thresholdMeters = settingSnapThreshold ? parseFloat(settingSnapThreshold.value) : 150;
    const thresholdKm = thresholdMeters / 1000;
    
    state.checkpoints = state.checkpoints.map(poi => {
        let bestPoint = null;
        let minDiff = Infinity;
        
        for (let i = 0; i < state.gpxTrackPoints.length; i++) {
            const pt = state.gpxTrackPoints[i];
            const diff = Math.abs(pt.dist - poi.dist);
            if (diff < minDiff) {
                minDiff = diff;
                bestPoint = pt;
            }
        }
        
        if (bestPoint && minDiff <= thresholdKm) {
            return {
                ...poi,
                lat: bestPoint.lat,
                lon: bestPoint.lon,
                ele: Math.round(bestPoint.ele)
            };
        } else {
            return {
                ...poi,
                lat: poi.lat || undefined,
                lon: poi.lon || undefined
            };
        }
    });

    plotCheckpointsOnMap();
}

export function updateHoverMarker(lat, lon) {
    if (!map) return;
    
    if (hoveredMapMarker) {
        map.removeLayer(hoveredMapMarker);
    }
    
    hoveredMapMarker = L.circleMarker([lat, lon], {
        radius: 6,
        color: '#ffffff',
        fillColor: '#ef4444',
        fillOpacity: 1,
        weight: 2
    }).addTo(map);
}

export function clearHoverMarker() {
    if (map && hoveredMapMarker) {
        map.removeLayer(hoveredMapMarker);
        hoveredMapMarker = null;
    }
}
