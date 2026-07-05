// 🏔️ Trail Mapper & GPX POI Merger - Core Logic

// State Management
let state = {
    gpxTrackPoints: [], // Array of { lat, lon, ele, dist }
    checkpoints: [],    // Array of { id, name, dist, ele, icon, use, lat, lon }
    raceName: 'Custom Trail Race',
    totalDistance: 0,   // km
    totalGain: 0,       // m D+
    originalGPXXml: null,
    gpxFileName: 'route.gpx'
};

// Map & Visualization Instances
let map = null;
let trackLayer = null;
let markerLayers = [];
let hoveredMapMarker = null;

// HTML Elements
const raceUrlInput = document.getElementById('race-url');
const btnFetch = document.getElementById('btn-fetch');
const fetchLoader = document.getElementById('fetch-loader');
const fetchStatusText = document.getElementById('fetch-status');
const gpxDropZone = document.getElementById('gpx-drop-zone');
const gpxFileInput = document.getElementById('gpx-file-input');
const gpxFileNameDisplay = document.getElementById('gpx-file-name');
const tableHtmlPaste = document.getElementById('table-html-paste');
const btnParseHtml = document.getElementById('btn-parse-html');
const poiTableBody = document.getElementById('poi-table-body');
const poiCountSpan = document.getElementById('poi-count');
const btnAddPoi = document.getElementById('btn-add-poi');
const btnMergeDownload = document.getElementById('btn-merge-download');
const btnMergeDownloadTcx = document.getElementById('btn-merge-download-tcx');
const btnMergeDownloadSuunto = document.getElementById('btn-merge-download-suunto');

// Stats Elements
const statRaceName = document.getElementById('stat-race-name');
const statDistance = document.getElementById('stat-distance');
const statGain = document.getElementById('stat-gain');
const statGpxPoints = document.getElementById('stat-gpx-points');

// Settings Elements
const settingCharLimit = document.getElementById('garmin-char-limit');
const settingSnapThreshold = document.getElementById('snap-threshold');
const settingShortenNames = document.getElementById('shorten-names');
const settingAddElevToName = document.getElementById('add-elev-to-name');

// Standard Garmin Symbols
const GARMIN_SYMBOLS = [
    { value: 'Food', label: 'Food / Aid Station' },
    { value: 'Water Source', label: 'Water Point' },
    { value: 'Summit', label: 'Summit / Peak' },
    { value: 'Danger', label: 'Danger / Hazard' },
    { value: 'Medical Facility', label: 'First Aid' },
    { value: 'Scenic Area', label: 'Scenic View' },
    { value: 'Flag, Red', label: 'Red Flag' },
    { value: 'Flag, Blue', label: 'Blue Flag' },
    { value: 'Residence', label: 'Generic Stop' }
];

// Initialize Leaflet Map
function initMap() {
    // Default to Chamonix coordinates
    map = L.map('map', {
        zoomControl: true,
        scrollWheelZoom: true
    }).setView([45.9233, 6.8689], 10);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
}

// Switch Tabs in Import Section
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Set active button
    event.currentTarget.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

// Haversine formula to compute distance in km between two lat/lon pairs
function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat/2) * Math.sin(dLat/2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
        Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Drag & Drop event listeners
gpxDropZone.addEventListener('click', () => gpxFileInput.click());
gpxDropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    gpxDropZone.classList.add('dragover');
});
gpxDropZone.addEventListener('dragleave', () => {
    gpxDropZone.classList.remove('dragover');
});
gpxDropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    gpxDropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
        handleGPXFile(e.dataTransfer.files[0]);
    }
});
gpxFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleGPXFile(e.target.files[0]);
    }
});

// Load GPX file contents
function handleGPXFile(file) {
    state.gpxFileName = file.name;
    gpxFileNameDisplay.textContent = file.name;
    
    // Save file object for uploading
    state.gpxFileObject = file;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        parseGPX(e.target.result);
    };
    reader.readAsText(file);
}

// Parse GPX XML content
function parseGPX(gpxText) {
    try {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(gpxText, 'text/xml');
        
        // Check for parsing errors
        const parserError = xmlDoc.querySelector('parsererror');
        if (parserError) {
            alert('Error parsing GPX file. Please verify it is a valid XML file.');
            return;
        }

        state.originalGPXXml = xmlDoc;
        const trackpoints = xmlDoc.querySelectorAll('trkpt');
        
        if (trackpoints.length === 0) {
            alert('No track points (<trkpt>) found in the GPX file.');
            return;
        }

        // Parse points
        let points = [];
        let cumDistance = 0;
        let cumGain = 0;
        
        for (let i = 0; i < trackpoints.length; i++) {
            const pt = trackpoints[i];
            const lat = parseFloat(pt.getAttribute('lat'));
            const lon = parseFloat(pt.getAttribute('lon'));
            const eleNode = pt.querySelector('ele');
            const ele = eleNode ? parseFloat(eleNode.textContent) : 0;
            
            if (i > 0) {
                const prevPt = points[i - 1];
                const d = haversine(prevPt.lat, prevPt.lon, lat, lon);
                cumDistance += d;
                
                // Gain calculation
                if (ele > prevPt.ele) {
                    cumGain += (ele - prevPt.ele);
                }
            }
            
            points.push({ lat, lon, ele, dist: cumDistance });
        }

        state.gpxTrackPoints = points;
        state.totalDistance = cumDistance;
        state.totalGain = Math.round(cumGain);
        
        // Attempt to find race name
        const trkName = xmlDoc.querySelector('trk > name');
        if (trkName) {
            state.raceName = trkName.textContent;
        }

        updateStats();
        drawRouteOnMap();
        hideMapOverlay();
        
        // Auto-trigger snapping of POIs if checkpoints already exist
        if (state.checkpoints.length > 0) {
            snapPOIsToTrack();
            renderPOITable();
        }

        // Enable merge button
        checkMergeAbility();
        
        // Draw elevation profile
        drawElevationProfile();
        
    } catch (err) {
        console.error(err);
        alert('An unexpected error occurred while parsing GPX: ' + err.message);
    }
}

// Update stats on UI
function updateStats() {
    statRaceName.textContent = state.raceName;
    statDistance.textContent = state.totalDistance ? `${state.totalDistance.toFixed(1)} km` : '-- km';
    statGain.textContent = state.totalGain ? `${state.totalGain} m D+` : '-- m D+';
    statGpxPoints.textContent = state.gpxTrackPoints.length;
}

// Draw GPX route line on Leaflet map
function drawRouteOnMap() {
    if (!map) return;
    
    // Clear old layers
    if (trackLayer) {
        map.removeLayer(trackLayer);
    }
    
    const latLons = state.gpxTrackPoints.map(p => [p.lat, p.lon]);
    
    trackLayer = L.polyline(latLons, {
        color: '#10b981', // Neon green
        weight: 4,
        opacity: 0.85
    }).addTo(map);
    
    map.fitBounds(trackLayer.getBounds());
}

function hideMapOverlay() {
    document.getElementById('map-overlay').classList.add('hidden');
}

// Map helper icons
function getMarkerIcon(garminSym) {
    let color = '#38bdf8'; // Cyan
    if (garminSym === 'Food') color = '#f97316'; // Orange
    if (garminSym === 'Water Source') color = '#0ea5e9'; // Blue
    if (garminSym === 'Summit') color = '#a855f7'; // Purple
    if (garminSym === 'Danger') color = '#ef4444'; // Red
    
    return L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: ${color}; width: 14px; height: 14px; border: 2px solid #ffffff; border-radius: 50%; box-shadow: 0 0 8px rgba(0,0,0,0.5);"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7]
    });
}

// Plot checkpoints on map
function plotCheckpointsOnMap() {
    // Clear old markers
    markerLayers.forEach(m => map.removeLayer(m));
    markerLayers = [];

    state.checkpoints.forEach(poi => {
        if (!poi.use || poi.lat === undefined || poi.lon === undefined) return;
        
        const marker = L.marker([poi.lat, poi.lon], {
            icon: getMarkerIcon(poi.icon)
        });
        
        const popupContent = `
            <div class="map-popup-title">${poi.name}</div>
            <div class="map-popup-text">Distance: <b>${poi.dist.toFixed(1)} km</b></div>
            <div class="map-popup-text">Elevation: <b>${poi.ele} m</b></div>
            <div class="map-popup-text">Icon: <b>${poi.icon}</b></div>
        `;
        
        marker.bindPopup(popupContent);
        marker.addTo(map);
        markerLayers.push(marker);
    });
}

// Snapping algorithm: Projects checkpoints on nearest GPX track point
function snapPOIsToTrack() {
    if (state.gpxTrackPoints.length === 0) return;
    
    const thresholdMeters = parseFloat(settingSnapThreshold.value);
    const thresholdKm = thresholdMeters / 1000;
    
    state.checkpoints = state.checkpoints.map(poi => {
        let bestPoint = null;
        let minDiff = Infinity;
        
        // Find track point closest in distance
        for (let i = 0; i < state.gpxTrackPoints.length; i++) {
            const pt = state.gpxTrackPoints[i];
            const diff = Math.abs(pt.dist - poi.dist);
            if (diff < minDiff) {
                minDiff = diff;
                bestPoint = pt;
            }
        }
        
        // Check if matching point is within snapping threshold
        if (bestPoint && minDiff <= thresholdKm) {
            return {
                ...poi,
                lat: bestPoint.lat,
                lon: bestPoint.lon,
                ele: poi.ele || Math.round(bestPoint.ele) // Fallback to GPX elevation if missing
            };
        } else {
            // Keep original coords if available, otherwise mark unsnapped
            return {
                ...poi,
                lat: poi.lat || undefined,
                lon: poi.lon || undefined
            };
        }
    });

    plotCheckpointsOnMap();
}

// Automatic text shortener mapping for Garmin (often 10/15 chars max)
function shortenNameForGarmin(name) {
    if (!settingShortenNames.checked) return name;
    
    let res = name;
    // Common french contractions for trails
    res = res.replace(/ravitaillement/gi, 'RAV');
    res = res.replace(/point d'eau/gi, 'EAU');
    res = res.replace(/point d eau/gi, 'EAU');
    res = res.replace(/départ/gi, 'DEP');
    res = res.replace(/depart/gi, 'DEP');
    res = res.replace(/arrivée/gi, 'ARR');
    res = res.replace(/arrivee/gi, 'ARR');
    res = res.replace(/sommet/gi, 'SMT');
    res = res.replace(/refuge/gi, 'REF');
    res = res.replace(/col de la/gi, 'COL');
    res = res.replace(/col du/gi, 'COL');
    res = res.replace(/col de/gi, 'COL');
    res = res.replace(/chalet de la/gi, 'CHAL');
    res = res.replace(/chalet du/gi, 'CHAL');
    res = res.replace(/chalet de/gi, 'CHAL');
    
    // English replacements
    res = res.replace(/aid station/gi, 'AID');
    res = res.replace(/water point/gi, 'WTR');
    res = res.replace(/checkpoint/gi, 'CP');
    res = res.replace(/start/gi, 'STR');
    res = res.replace(/finish/gi, 'FNS');
    
    return res;
}

// Generate the output Garmin name checking settings
function generateGarminName(name, ele) {
    let clean = shortenNameForGarmin(name).trim();
    
    if (settingAddElevToName.checked && ele) {
        clean = `${clean} ${ele}m`;
    }
    
    // Apply character truncation
    const limit = parseInt(settingCharLimit.value);
    if (clean.length > limit) {
        clean = clean.substring(0, limit);
    }
    
    return clean;
}

// Render POI Checkpoints Table
function renderPOITable() {
    poiCountSpan.textContent = state.checkpoints.length;
    
    if (state.checkpoints.length === 0) {
        poiTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="placeholder-row">No checkpoints loaded. Use the controls above to fetch a race or upload data.</td>
            </tr>
        `;
        return;
    }
    
    poiTableBody.innerHTML = '';
    
    state.checkpoints.forEach((poi, index) => {
        const tr = document.createElement('tr');
        
        // Use Checkbox
        const tdUse = document.createElement('td');
        tdUse.style.textAlign = 'center';
        const chkUse = document.createElement('input');
        chkUse.type = 'checkbox';
        chkUse.checked = poi.use;
        chkUse.addEventListener('change', (e) => {
            state.checkpoints[index].use = e.target.checked;
            plotCheckpointsOnMap();
            checkMergeAbility();
        });
        tdUse.appendChild(chkUse);
        
        // Name input
        const tdName = document.createElement('td');
        const inputName = document.createElement('input');
        inputName.type = 'text';
        inputName.value = poi.name;
        inputName.className = 'cell-input';
        inputName.addEventListener('change', (e) => {
            state.checkpoints[index].name = e.target.value;
            plotCheckpointsOnMap();
        });
        tdName.appendChild(inputName);
        
        // Distance input
        const tdDist = document.createElement('td');
        const inputDist = document.createElement('input');
        inputDist.type = 'number';
        inputDist.step = '0.1';
        inputDist.value = poi.dist.toFixed(1);
        inputDist.className = 'cell-input';
        inputDist.addEventListener('change', (e) => {
            state.checkpoints[index].dist = parseFloat(e.target.value) || 0;
            snapPOIsToTrack();
            renderPOITable();
            drawElevationProfile();
        });
        tdDist.appendChild(inputDist);
        
        // Elevation input
        const tdEle = document.createElement('td');
        const inputEle = document.createElement('input');
        inputEle.type = 'number';
        inputEle.value = poi.ele || '';
        inputEle.placeholder = '--';
        inputEle.className = 'cell-input';
        inputEle.addEventListener('change', (e) => {
            state.checkpoints[index].ele = parseInt(e.target.value) || 0;
        });
        tdEle.appendChild(inputEle);
        
        // Icon / Symbol select
        const tdIcon = document.createElement('td');
        const selectIcon = document.createElement('select');
        selectIcon.className = 'cell-input';
        GARMIN_SYMBOLS.forEach(sym => {
            const opt = document.createElement('option');
            opt.value = sym.value;
            opt.textContent = sym.label;
            if (sym.value === poi.icon) opt.selected = true;
            selectIcon.appendChild(opt);
        });
        selectIcon.addEventListener('change', (e) => {
            state.checkpoints[index].icon = e.target.value;
            plotCheckpointsOnMap();
        });
        tdIcon.appendChild(selectIcon);
        
        // Delete button
        const tdDel = document.createElement('td');
        tdDel.style.textAlign = 'center';
        const btnDel = document.createElement('button');
        btnDel.type = 'button';
        btnDel.className = 'btn-icon';
        btnDel.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
        btnDel.addEventListener('click', () => {
            state.checkpoints.splice(index, 1);
            snapPOIsToTrack();
            renderPOITable();
            drawElevationProfile();
            checkMergeAbility();
        });
        tdDel.appendChild(btnDel);
        
        tr.appendChild(tdUse);
        tr.appendChild(tdName);
        tr.appendChild(tdDist);
        tr.appendChild(tdEle);
        tr.appendChild(tdIcon);
        tr.appendChild(tdDel);
        
        poiTableBody.appendChild(tr);
    });
}

// Add empty POI
btnAddPoi.addEventListener('click', () => {
    const newPoi = {
        id: 'manual_' + Date.now(),
        name: 'New Station',
        dist: state.totalDistance / 2,
        ele: 0,
        icon: 'Food',
        use: true
    };
    state.checkpoints.push(newPoi);
    state.checkpoints.sort((a, b) => a.dist - b.dist);
    snapPOIsToTrack();
    renderPOITable();
    drawElevationProfile();
    checkMergeAbility();
});

// Enable/Disable download buttons
function checkMergeAbility() {
    const hasGPX = state.gpxTrackPoints.length > 0;
    const hasActiveStops = state.checkpoints.some(c => c.use);
    const disabled = !(hasGPX && hasActiveStops);
    
    btnMergeDownload.disabled = disabled;
    if (btnMergeDownloadTcx) btnMergeDownloadTcx.disabled = disabled;
    if (btnMergeDownloadSuunto) btnMergeDownloadSuunto.disabled = disabled;
}

// Hook Settings Redraws
settingCharLimit.addEventListener('change', renderPOITable);
settingShortenNames.addEventListener('change', renderPOITable);
settingAddElevToName.addEventListener('change', renderPOITable);
settingSnapThreshold.addEventListener('change', () => {
    snapPOIsToTrack();
    renderPOITable();
});

// Canvas-based Elevation Profile Drawing
function drawElevationProfile() {
    const canvas = document.getElementById('elevation-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const points = state.gpxTrackPoints;
    if (points.length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }
    
    // Resize canvas properly for retina displays
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    
    const width = rect.width;
    const height = rect.height;
    
    ctx.clearRect(0, 0, width, height);
    
    // Find min and max values
    const elevs = points.map(p => p.ele);
    const maxElev = Math.max(...elevs);
    const minElev = Math.min(...elevs);
    const elevRange = maxElev - minElev;
    const padding = 15;
    
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;
    
    const maxDist = points[points.length - 1].dist;
    
    // Coordinate mapping functions
    const getX = (dist) => padding + (dist / maxDist) * chartWidth;
    const getY = (ele) => padding + chartHeight - ((ele - minElev) / (elevRange || 1)) * chartHeight;
    
    // Draw background grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        // Vertical lines
        const d = (i / 4) * maxDist;
        const x = getX(d);
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, padding + chartHeight);
        ctx.stroke();
        
        // Horizontal lines
        const e = minElev + (i / 4) * elevRange;
        const y = getY(e);
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(padding + chartWidth, y);
        ctx.stroke();
    }
    
    // Draw elevation fill
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(points[0].ele));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(getX(points[i].dist), getY(points[i].ele));
    }
    ctx.lineTo(getX(maxDist), getY(points[points.length - 1].ele));
    ctx.lineTo(getX(maxDist), padding + chartHeight);
    ctx.lineTo(getX(0), padding + chartHeight);
    ctx.closePath();
    
    const fillGradient = ctx.createLinearGradient(0, padding, 0, padding + chartHeight);
    fillGradient.addColorStop(0, 'rgba(16, 185, 129, 0.3)');
    fillGradient.addColorStop(1, 'rgba(16, 185, 129, 0.01)');
    ctx.fillStyle = fillGradient;
    ctx.fill();
    
    // Draw elevation path line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(points[0].ele));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(getX(points[i].dist), getY(points[i].ele));
    }
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Plot checkpoints on elevation profile
    state.checkpoints.forEach(poi => {
        if (!poi.use) return;
        const x = getX(poi.dist);
        const y = getY(poi.ele || 0);
        
        // Draw vertical dotted line
        ctx.strokeStyle = 'rgba(249, 115, 22, 0.35)'; // Dotted Orange
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, padding + chartHeight);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Draw checkpoint dot
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fillStyle = '#f97316'; // Orange
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.stroke();
    });
    
    // Mouse hover listener on canvas to sync tracker on map
    canvas.addEventListener('mousemove', (e) => {
        const mouseX = e.offsetX;
        if (mouseX < padding || mouseX > padding + chartWidth) return;
        
        const hoverDist = ((mouseX - padding) / chartWidth) * maxDist;
        
        // Find nearest point
        let nearestPt = points[0];
        let minDiff = Infinity;
        for (let i = 0; i < points.length; i++) {
            const diff = Math.abs(points[i].dist - hoverDist);
            if (diff < minDiff) {
                minDiff = diff;
                nearestPt = points[i];
            }
        }
        
        // Re-draw chart + hover elements
        drawElevationProfile();
        
        // Draw hover vertical line
        const hX = getX(nearestPt.dist);
        const hY = getY(nearestPt.ele);
        
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(hX, padding);
        ctx.lineTo(hX, padding + chartHeight);
        ctx.stroke();
        
        // Hover dot
        ctx.beginPath();
        ctx.arc(hX, hY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        
        // Hover label text
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px Outfit';
        ctx.fillText(`${nearestPt.dist.toFixed(1)}km | ${Math.round(nearestPt.ele)}m`, hX + 8, hY - 5);
        
        // Set / Move temporary tracker marker on map
        if (map) {
            if (hoveredMapMarker) {
                hoveredMapMarker.setLatLng([nearestPt.lat, nearestPt.lon]);
            } else {
                hoveredMapMarker = L.marker([nearestPt.lat, nearestPt.lon], {
                    icon: L.divIcon({
                        className: 'hover-tracker-icon',
                        html: `<div style="background-color: #ffffff; width: 12px; height: 12px; border: 3px solid #10b981; border-radius: 50%; box-shadow: 0 0 10px #10b981;"></div>`,
                        iconSize: [12, 12],
                        iconAnchor: [6, 6]
                    })
                }).addTo(map);
            }
        }
    });
    
    canvas.addEventListener('mouseleave', () => {
        // Clear tracker
        if (map && hoveredMapMarker) {
            map.removeLayer(hoveredMapMarker);
            hoveredMapMarker = null;
        }
        drawElevationProfile(); // Redraw without vertical line
    });
}

// Trigger chart redraw on window resize
window.addEventListener('resize', drawElevationProfile);

// HTML parsing algorithm for UTMB checkpoints tables
// HTML parsing algorithm for UTMB checkpoints tables
function parseUTMBTableHTML(htmlString) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, 'text/html');
    
    // Look for all table rows
    const rows = doc.querySelectorAll('tr');
    if (rows.length === 0) {
        return [];
    }
    
    let checkpoints = [];
    let headers = [];
    
    // Parse headers if available
    const headerRow = doc.querySelector('thead tr') || rows[0];
    if (headerRow) {
        const ths = headerRow.querySelectorAll('th, td');
        ths.forEach((th, idx) => {
            headers.push({ text: th.textContent.toLowerCase().trim(), index: idx });
        });
    }
    
    // Auto-detect columns
    let distCol = -1;
    let eleCol = -1;
    let nameCol = -1;
    
    headers.forEach(h => {
        if (h.text.match(/km|dist/)) distCol = h.index;
        if (h.text.match(/alt|elev|d\+|deni/)) eleCol = h.index;
        if (h.text.match(/checkpoint|post|lieu|stat|ravit|nom/)) nameCol = h.index;
    });
    
    // Fallbacks if header matching fails
    if (distCol === -1) distCol = 1; // commonly second column
    if (eleCol === -1) eleCol = 2;  // commonly third column
    if (nameCol === -1) nameCol = 0; // commonly first column
    
    rows.forEach((row, idx) => {
        // Skip header row
        if (idx === 0 && headerRow) return;
        
        const tds = row.querySelectorAll('td');
        if (tds.length < 2) return; // Need at least name and distance
        
        const nameVal = tds[nameCol] ? tds[nameCol].textContent.trim() : '';
        const distVal = tds[distCol] ? tds[distCol].textContent.trim() : '';
        const eleVal = tds[eleCol] ? tds[eleCol].textContent.trim() : '';
        
        // Clean distance: extract first decimal or float
        const distMatch = distVal.replace(',', '.').match(/[\d\.]+/);
        const distance = distMatch ? parseFloat(distMatch[0]) : null;
        
        // Clean elevation: extract first digits
        const eleMatch = eleVal.match(/\d+/);
        const elevation = eleMatch ? parseInt(eleMatch[0]) : null;
        
        if (nameVal && distance !== null) {
            // Determine type / icon
            let icon = 'Residence';
            const nameLower = nameVal.toLowerCase();
            if (nameLower.match(/ravit|food|repas|restau/)) icon = 'Food';
            else if (nameLower.match(/eau|water|sourc/)) icon = 'Water Source';
            else if (nameLower.match(/sommet|peak|col|summit|mont/)) icon = 'Summit';
            else if (nameLower.match(/secour|medical|aid|croix/)) icon = 'Medical Facility';
            else if (nameLower.match(/danger|warning|diffic/)) icon = 'Danger';
            
            checkpoints.push({
                id: 'scraped_' + idx + '_' + Date.now(),
                name: nameVal,
                dist: distance,
                ele: elevation || 0,
                icon: icon,
                use: true
            });
        }
    });
    
    return checkpoints;
}

// Copy-pasted plain text parser for UTMB non-table schedule layout
function parseUTMBCopyPastedText(rawText) {
    const lines = rawText.split('\n')
                         .map(l => l.trim())
                         .filter(l => l.length > 0);
    
    let startIdx = 0;
    // Skip header labels if present at the top
    while (startIdx < lines.length) {
        const line = lines[startIdx].toLowerCase();
        if (line.match(/point|altitude|dist|gain|loss|fastest|slowest|cut\s*off|services|inter/)) {
            startIdx++;
        } else {
            break;
        }
    }
    
    const parsedLines = lines.slice(startIdx);
    const checkpoints = [];
    let i = 0;
    
    // Time matching regex: e.g. "Fri 06:00 AM" or "Sat 10:30 AM"
    const timeRegex = /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/i;
    
    while (i < parsedLines.length) {
        if (i + 7 >= parsedLines.length) break;
        
        const name = parsedLines[i++];
        const altStr = parsedLines[i++];
        const distStr = parsedLines[i++];
        const distInterStr = parsedLines[i++];
        const gainStr = parsedLines[i++];
        const lossStr = parsedLines[i++];
        
        const altitude = parseFloat(altStr.replace(',', '.'));
        const distance = parseFloat(distStr.replace(',', '.'));
        const distInter = parseFloat(distInterStr.replace(',', '.'));
        const gain = parseFloat(gainStr.replace(',', '.'));
        const loss = parseFloat(lossStr.replace(',', '.'));
        
        // Self-healing recovery: if we hit non-numeric fields, we skipped/misparsed a label
        if (isNaN(distance) || isNaN(altitude)) {
            console.warn(`Recovering line mismatch: invalid numbers for checkpoint [${name}]. Alt: ${altStr}, Dist: ${distStr}`);
            // Advance by 1 line from where we read the name, to re-try
            i = i - 5;
            continue;
        }
        
        const fastest = parsedLines[i++];
        const slowest = parsedLines[i++];
        
        let cutoff = '';
        let services = '';
        
        // Parse optional fields
        if (i < parsedLines.length) {
            const nextLine = parsedLines[i];
            if (timeRegex.test(nextLine)) {
                cutoff = parsedLines[i++];
                if (i < parsedLines.length && (parsedLines[i].startsWith('+') || parsedLines[i].match(/^\d+$/))) {
                    services = parsedLines[i++];
                }
            } else if (nextLine.startsWith('+') || nextLine.match(/^\d+$/)) {
                services = parsedLines[i++];
            }
        }
        
        // Icon mapping based on names
        let icon = 'Residence';
        const nameLower = name.toLowerCase();
        if (nameLower.match(/ravit|food|repas|restau|beret|salardu|beaufort|canejan|vielha|arties|honeria/)) icon = 'Food';
        else if (nameLower.match(/eau|water|sourc/)) icon = 'Water Source';
        else if (nameLower.match(/sommet|peak|col|summit|mont|tuc|còth/)) icon = 'Summit';
        else if (nameLower.match(/secour|medical|aid|croix/)) icon = 'Medical Facility';
        else if (nameLower.match(/danger|warning|diffic/)) icon = 'Danger';
        
        // If services count is high, mark it as Food
        if (services && parseInt(services.replace('+', '')) > 2) {
            icon = 'Food';
        }
        
        checkpoints.push({
            id: 'text_' + checkpoints.length + '_' + Date.now(),
            name: name,
            dist: distance,
            ele: altitude,
            icon: icon,
            use: true
        });
    }
    
    return checkpoints;
}

// Parse pasted HTML or raw text trigger button
btnParseHtml.addEventListener('click', () => {
    const rawInput = tableHtmlPaste.value.trim();
    if (!rawInput) {
        alert('Please paste some HTML or raw copied UTMB schedule text first.');
        return;
    }
    
    let parsed = [];
    let method = '';
    
    // Attempt HTML parsing first
    if (rawInput.includes('<tr') || rawInput.includes('<table')) {
        parsed = parseUTMBTableHTML(rawInput);
        method = 'HTML table';
    }
    
    // Fallback to plain text parser
    if (parsed.length === 0) {
        parsed = parseUTMBCopyPastedText(rawInput);
        method = 'raw text';
    }
    
    if (parsed.length > 0) {
        // Sort by distance
        parsed.sort((a, b) => a.dist - b.dist);
        state.checkpoints = parsed;
        
        snapPOIsToTrack();
        renderPOITable();
        drawElevationProfile();
        checkMergeAbility();
        
        alert(`Successfully parsed ${parsed.length} checkpoints from ${method}!`);
    } else {
        alert('Could not extract any valid checkpoints. Please verify that your pasted text matches either the UTMB HTML structure or the plain text copied schedule layout.');
    }
});

// Fetch UTMB Race Data via backend proxy
btnFetch.addEventListener('click', async () => {
    const url = raceUrlInput.value.trim();
    if (!url) {
        alert('Please enter a UTMB race URL.');
        return;
    }
    
    fetchLoader.classList.add('active');
    fetchStatusText.textContent = 'Requesting page content via server...';
    
    try {
        const response = await fetch('/trail-mapper/api/parse-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to parse URL on server');
        }
        
        const data = await response.json();
        const scrapedStations = data.stations || [];
        const gpxUrl = data.gpx_link;
        
        if (scrapedStations.length > 0) {
            state.checkpoints = scrapedStations.map((s, idx) => ({
                id: s.id || ('scraped_' + idx + '_' + Date.now()),
                name: s.name,
                dist: s.dist,
                ele: s.ele || 0,
                icon: s.icon,
                use: s.use !== undefined ? s.use : true
            }));
            renderPOITable();
        }
        
        if (gpxUrl) {
            fetchStatusText.textContent = 'Downloading GPX track via server...';
            const gpxResponse = await fetch('/trail-mapper/api/download-gpx', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: gpxUrl })
            });
            
            if (!gpxResponse.ok) {
                const errData = await gpxResponse.json();
                throw new Error(errData.detail || 'Failed to download GPX via server');
            }
            
            const gpxText = await gpxResponse.text();
            parseGPX(gpxText);
            
            alert(`Successfully fetched GPX track and ${scrapedStations.length} aid stations!`);
        } else {
            alert(`Parsed ${scrapedStations.length} aid stations, but could not find a GPX link in the page. Please upload the GPX file manually.`);
            switchTab('upload-tab');
        }
        
    } catch (err) {
        console.error(err);
        alert('Failed to retrieve race data: ' + err.message + '\n\nFallback to "Upload Files" tab to load GPX and paste HTML manually.');
        switchTab('upload-tab');
    } finally {
        fetchLoader.classList.remove('active');
    }
});

// Generic merge and export trigger
async function triggerMergeDownload(format) {
    if (state.gpxTrackPoints.length === 0 || !state.originalGPXXml) {
        alert('No GPX route loaded.');
        return;
    }
    
    // Prepare GPX blob
    let gpxBlob;
    if (state.gpxFileObject) {
        gpxBlob = state.gpxFileObject;
    } else {
        const serializer = new XMLSerializer();
        const gpxString = serializer.serializeToString(state.originalGPXXml);
        gpxBlob = new Blob([gpxString], { type: 'application/gpx+xml' });
    }
    
    // Map icons to backend expected symbols
    const mappedStations = state.checkpoints.map(c => ({
        name: c.name,
        dist: c.dist,
        icon: c.icon,
        use: c.use
    }));
    
    const formData = new FormData();
    formData.append('gpx_file', gpxBlob, state.gpxFileName || 'route.gpx');
    formData.append('stations_json', JSON.stringify(mappedStations));
    
    // Check settings
    const noScale = document.getElementById('no-scale')?.checked || false;
    formData.append('no-scale', noScale);
    
    // Total distance limit/setting
    formData.append('official_dist', state.totalDistance);
    
    try {
        btnMergeDownload.disabled = true;
        if (btnMergeDownloadTcx) btnMergeDownloadTcx.disabled = true;
        if (btnMergeDownloadSuunto) btnMergeDownloadSuunto.disabled = true;
        
        const response = await fetch('/trail-mapper/api/merge', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Merge failed on server');
        }
        
        const data = await response.json();
        
        let downloadString = "";
        let fileNameSuffix = "";
        let contentType = "";
        
        if (format === 'garmin_gpx') {
            downloadString = data.garmin_gpx;
            fileNameSuffix = "_garmin.gpx";
            contentType = "application/gpx+xml";
        } else if (format === 'garmin_tcx') {
            downloadString = data.garmin_tcx;
            fileNameSuffix = "_garmin.tcx";
            contentType = "application/xml";
        } else if (format === 'suunto_gpx') {
            downloadString = data.suunto_gpx;
            fileNameSuffix = "_suunto.gpx";
            contentType = "application/gpx+xml";
        }
        
        if (!downloadString) {
            alert("No data generated for " + format);
            return;
        }
        
        const blob = new Blob([downloadString], { type: contentType + ';charset=utf-8' });
        const downloadUrl = URL.createObjectURL(blob);
        const downloadLink = document.createElement('a');
        
        const baseName = state.gpxFileName.replace(/\.gpx$/i, '');
        downloadLink.href = downloadUrl;
        downloadLink.download = `${baseName}${fileNameSuffix}`;
        
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(downloadUrl);
        
    } catch (err) {
        console.error(err);
        alert('Merge error: ' + err.message);
    } finally {
        checkMergeAbility();
    }
}

// Bind merge download listeners
btnMergeDownload.addEventListener('click', () => triggerMergeDownload('garmin_gpx'));
if (btnMergeDownloadTcx) {
    btnMergeDownloadTcx.addEventListener('click', () => triggerMergeDownload('garmin_tcx'));
}
if (btnMergeDownloadSuunto) {
    btnMergeDownloadSuunto.addEventListener('click', () => triggerMergeDownload('suunto_gpx'));
}

// Mock TDS Race Data for Startup Demo
const DEFAULT_RACE_NODES = [
    { lat: 45.7915, lon: 6.9650, ele: 1220, dist: 0.0, name: "Courmayeur (Start)", icon: "Flag, Red" },
    { lat: 45.7831, lon: 6.9242, ele: 1956, dist: 6.8, name: "Maison Vieille", icon: "Food" },
    { lat: 45.7725, lon: 6.8624, ele: 1968, dist: 15.0, name: "Lac Combal", icon: "Water Source" },
    { lat: 45.7512, lon: 6.8210, ele: 2596, dist: 19.8, name: "Col Chavannes", icon: "Summit" },
    { lat: 45.6980, lon: 6.7820, ele: 2270, dist: 30.2, name: "Alpetta", icon: "Residence" },
    { lat: 45.6179, lon: 6.7692, ele: 810, dist: 51.3, name: "Bourg St-Maurice", icon: "Food" },
    { lat: 45.6912, lon: 6.7121, ele: 1970, dist: 67.2, name: "Cormet de Roselend", icon: "Food" },
    { lat: 45.7120, lon: 6.6450, ele: 1660, dist: 75.8, name: "La Gittaz", icon: "Residence" },
    { lat: 45.7050, lon: 6.6110, ele: 2030, dist: 83.1, name: "Entre deux Nants", icon: "Water Source" },
    { lat: 45.7176, lon: 6.5721, ele: 740, dist: 94.5, name: "Beaufort", icon: "Food" },
    { lat: 45.7480, lon: 6.5850, ele: 1150, dist: 100.8, name: "Hauteluce", icon: "Water Source" },
    { lat: 45.7954, lon: 6.6710, ele: 1989, dist: 115.4, name: "Col du Joly", icon: "Food" },
    { lat: 45.8233, lon: 6.7265, ele: 1160, dist: 125.1, name: "Les Contamines", icon: "Food" },
    { lat: 45.8390, lon: 6.7450, ele: 1590, dist: 129.2, name: "Chalets du Truc", icon: "Residence" },
    { lat: 45.8643, lon: 6.7845, ele: 1650, dist: 138.5, name: "Col de Voza", icon: "Water Source" },
    { lat: 45.8900, lon: 6.7980, ele: 1010, dist: 144.1, name: "Les Houches", icon: "Residence" },
    { lat: 45.9233, lon: 6.8689, ele: 1035, dist: 153.2, name: "Chamonix (Finish)", icon: "Flag, Blue" }
];

function loadDefaultDemoRace() {
    state.raceName = "UTMB TDS - Courmayeur to Chamonix (Demo)";
    state.gpxFileName = "tds_2025_route.gpx";
    
    let syntheticPoints = [];
    let amplitude = 0.005;
    let computedDist = 0;
    
    // Calibration loop to find the exact switchback amplitude required for a total length of 153.2 km
    for (let iter = 0; iter < 10; iter++) {
        syntheticPoints = [];
        
        for (let i = 0; i < DEFAULT_RACE_NODES.length - 1; i++) {
            const n1 = DEFAULT_RACE_NODES[i];
            const n2 = DEFAULT_RACE_NODES[i+1];
            
            const segmentDist = n2.dist - n1.dist;
            // Generate denser points for segments to support winding
            const steps = Math.max(25, Math.ceil(segmentDist * 6));
            
            for (let s = 0; s < steps; s++) {
                const t = s / steps;
                
                // Add switchback oscillations
                const freq = Math.max(6, Math.ceil(segmentDist * 2));
                const windingLat = Math.sin(t * Math.PI * freq) * amplitude;
                const windingLon = Math.cos(t * Math.PI * freq) * amplitude;
                
                const lat = n1.lat + (n2.lat - n1.lat) * t + windingLat;
                const lon = n1.lon + (n2.lon - n1.lon) * t + windingLon;
                
                // Generate elevation peaks and valleys
                const hillProfile = Math.sin(t * Math.PI) * (180 * Math.sin(i * 2.8));
                const ele = Math.round(n1.ele + (n2.ele - n1.ele) * t + hillProfile);
                
                syntheticPoints.push({ lat, lon, ele });
            }
        }
        
        // Add final finish point
        const lastNode = DEFAULT_RACE_NODES[DEFAULT_RACE_NODES.length - 1];
        syntheticPoints.push({ lat: lastNode.lat, lon: lastNode.lon, ele: lastNode.ele });
        
        // Compute total distance with current amplitude
        computedDist = 0;
        for (let i = 1; i < syntheticPoints.length; i++) {
            computedDist += haversine(syntheticPoints[i-1].lat, syntheticPoints[i-1].lon, syntheticPoints[i].lat, syntheticPoints[i].lon);
        }
        
        // Target is 153.2 km
        const ratio = 153.2 / computedDist;
        if (Math.abs(ratio - 1) < 0.005) {
            break; // Converged
        }
        amplitude = amplitude * Math.sqrt(ratio); // Adjust amplitude for next iteration
    }
    
    // Construct standard GPX XML from calibrated points
    let gpxXml = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="UTMB Trail Mapper &amp; POI Merger" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${state.raceName}</name>
  </metadata>
  <trk>
    <name>${state.raceName}</name>
    <trkseg>`;
    
    syntheticPoints.forEach(p => {
        gpxXml += `
      <trkpt lat="${p.lat.toFixed(6)}" lon="${p.lon.toFixed(6)}">
        <ele>${p.ele}</ele>
      </trkpt>`;
    });
    
    gpxXml += `
    </trkseg>
  </trk>
</gpx>`;
    
    // Initialize checkpoints list from Default Race Nodes
    state.checkpoints = DEFAULT_RACE_NODES.map((n, idx) => ({
        id: 'default_' + idx + '_' + Date.now(),
        name: n.name,
        dist: n.dist,
        ele: n.ele,
        icon: n.icon,
        use: true
    }));

    
    // Parse the generated XML to establish the full GPX state
    parseGPX(gpxXml);
}

async function loadValDAranCDHRace() {
    try {
        fetchLoader.classList.add('active');
        fetchStatusText.textContent = 'Loading Val d\'Aran CDH GPX...';
        
        // Fetch local GPX track (bypassing CORS)
        const gpxResponse = await fetch('valdaran-cdh.gpx?v=1.0.1');
        if (!gpxResponse.ok) throw new Error('Failed to load local GPX file');
        const gpxText = await gpxResponse.text();
        
        fetchStatusText.textContent = 'Loading Val d\'Aran CDH schedule...';
        
        // Fetch local plain text schedule (bypassing CORS)
        const txtResponse = await fetch('valdaran-cdh-schedule.txt?v=1.0.1');
        if (!txtResponse.ok) throw new Error('Failed to load local schedule file');
        const txtText = await txtResponse.text();
        
        state.raceName = "HOKA Val d'Aran by UTMB - CDH 110K";
        state.gpxFileName = "valdaran_cdh_route.gpx";
        
        // Parse GPX first (sets state.gpxTrackPoints, distance, etc.)
        parseGPX(gpxText);
        
        // Parse checkpoints from copy-paste text format
        const parsed = parseUTMBCopyPastedText(txtText);
        if (parsed.length > 0) {
            parsed.sort((a, b) => a.dist - b.dist);
            state.checkpoints = parsed;
            
            // Project aid stations onto the real GPX track coordinates
            snapPOIsToTrack();
            renderPOITable();
            drawElevationProfile();
            checkMergeAbility();
        }
        
        hideMapOverlay();
        
    } catch (err) {
        console.error(err);
        alert('Failed to load Val d\'Aran CDH demo data: ' + err.message);
    } finally {
        fetchLoader.classList.remove('active');
    }
}

// Bind Quick Demo buttons
document.getElementById('btn-load-tds-demo').addEventListener('click', loadDefaultDemoRace);
document.getElementById('btn-load-cdh-demo').addEventListener('click', loadValDAranCDHRace);

// Run Initialization
initMap();
loadDefaultDemoRace();
checkMergeAbility();

