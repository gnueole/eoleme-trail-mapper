import { state } from './state.js?v=1.0.5';
import { getSymbolColor, updateHoverMarker, clearHoverMarker } from './map-utils.js?v=1.0.5';

export function drawElevationProfile() {
    const canvas = document.getElementById('elevation-canvas');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const points = state.gpxTrackPoints;
    const profileCard = document.getElementById('elevation-profile-card');
    const infoProfileRow = document.getElementById('info-profile-row');
    
    if (points.length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (profileCard) profileCard.style.display = 'none';
        if (infoProfileRow && (!state.raceCategory && !state.raceRunningStones && !state.raceLogoUrl && !state.raceOfficialUrl)) {
            infoProfileRow.style.display = 'none';
        }
        return;
    }
    
    if (profileCard) profileCard.style.display = 'block';
    if (infoProfileRow) infoProfileRow.style.display = 'grid';
    
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
    
    const paddingLeft = 45;
    const paddingRight = 15;
    const paddingTop = 15;
    const paddingBottom = 20;
    
    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;
    
    const maxDist = points[points.length - 1].dist;
    
    const getX = (dist) => paddingLeft + (dist / maxDist) * chartWidth;
    const getY = (ele) => paddingTop + chartHeight - ((ele - minElev) / (elevRange || 1)) * chartHeight;
    
    const isLightTheme = document.body.classList.contains('light-theme');
    ctx.strokeStyle = isLightTheme ? 'rgba(15, 23, 42, 0.08)' : 'rgba(255, 255, 255, 0.05)';
    ctx.fillStyle = isLightTheme ? 'rgba(15, 23, 42, 0.5)' : 'rgba(255, 255, 255, 0.4)';
    ctx.font = '9px Outfit';
    ctx.lineWidth = 1;
    
    for (let i = 0; i <= 4; i++) {
        const d = (i / 4) * maxDist;
        const x = getX(d);
        ctx.beginPath();
        ctx.moveTo(x, paddingTop);
        ctx.lineTo(x, paddingTop + chartHeight);
        ctx.stroke();
        
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const displayD = state.unit === 'mi' ? d * 0.621371 : d;
        const unitSuffix = state.unit === 'mi' ? 'mi' : 'k';
        ctx.fillText(`${displayD.toFixed(0)}${unitSuffix}`, x, paddingTop + chartHeight + 4);
        
        const e = minElev + (i / 4) * elevRange;
        const y = getY(e);
        ctx.beginPath();
        ctx.moveTo(paddingLeft, y);
        ctx.lineTo(paddingLeft + chartWidth, y);
        ctx.stroke();
        
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(`${Math.round(e)}m`, paddingLeft - 6, y);
    }
    
    // Draw elevation fill
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(points[0].ele));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(getX(points[i].dist), getY(points[i].ele));
    }
    ctx.lineTo(getX(maxDist), getY(points[points.length - 1].ele));
    ctx.lineTo(getX(maxDist), paddingTop + chartHeight);
    ctx.lineTo(getX(0), paddingTop + chartHeight);
    ctx.closePath();
    
    const dist = state.totalDistance;
    const isTDS = state.raceName && state.raceName.toUpperCase().includes('TDS');
    const cat = state.raceCategory ? state.raceCategory.toUpperCase().replace('WS', '').replace('KM', 'K') : '';
    const kmEffort = dist + (state.totalGain / 100);
    
    let rgb = '125, 223, 101'; // default 100K
    let hexColor = '#7ddf65';
    
    if (isTDS) {
        rgb = '0, 173, 233';
        hexColor = '#00ade9';
    } else if (cat.includes('100M')) {
        rgb = '239, 68, 68';
        hexColor = '#ef4444';
    } else if (cat.includes('100K')) {
        rgb = '125, 223, 101';
        hexColor = '#7ddf65';
    } else if (cat.includes('50K')) {
        rgb = '255, 150, 0';
        hexColor = '#ff9600';
    } else if (cat.includes('20K')) {
        rgb = '255, 255, 0';
        hexColor = '#ffff00';
    } else if (dist > 0) {
        if (kmEffort < 35) {
            rgb = '255, 255, 0';
            hexColor = '#ffff00';
        } else if (kmEffort < 80) {
            rgb = '255, 150, 0';
            hexColor = '#ff9600';
        } else if (kmEffort < 140) {
            rgb = '125, 223, 101';
            hexColor = '#7ddf65';
        } else {
            rgb = '239, 68, 68';
            hexColor = '#ef4444';
        }
    }
    
    const fillGradient = ctx.createLinearGradient(0, paddingTop, 0, paddingTop + chartHeight);
    fillGradient.addColorStop(0, `rgba(${rgb}, 0.3)`);
    fillGradient.addColorStop(1, `rgba(${rgb}, 0.01)`);
    ctx.fillStyle = fillGradient;
    ctx.fill();
    
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(points[0].ele));
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(getX(points[i].dist), getY(points[i].ele));
    }
    ctx.strokeStyle = hexColor;
    ctx.lineWidth = 2;
    ctx.stroke();
    
    state.checkpoints.forEach(poi => {
        if (!poi.use) return;
        const x = getX(poi.dist);
        const y = getY(poi.ele || 0);
        const color = getSymbolColor(poi.icon);
        
        ctx.strokeStyle = color + '55';
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, paddingTop + chartHeight);
        ctx.stroke();
        ctx.setLineDash([]);
        
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.stroke();
    });
    
    if (state.hoveredPoint) {
        const hX = getX(state.hoveredPoint.dist);
        const hY = getY(state.hoveredPoint.ele);
        
        ctx.strokeStyle = isLightTheme ? 'rgba(15, 23, 42, 0.3)' : 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(hX, paddingTop);
        ctx.lineTo(hX, paddingTop + chartHeight);
        ctx.stroke();
        
        ctx.beginPath();
        ctx.arc(hX, hY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.strokeStyle = hexColor;
        ctx.lineWidth = 1.5;
        ctx.stroke();
        
        ctx.fillStyle = isLightTheme ? '#0f172a' : '#ffffff';
        ctx.font = '10px Outfit';
        const displayH = state.unit === 'mi' ? state.hoveredPoint.dist * 0.621371 : state.hoveredPoint.dist;
        ctx.fillText(`${displayH.toFixed(1)}${state.unit} | ${Math.round(state.hoveredPoint.ele)}m`, hX + 8, hY - 5);
    }
}

// Window resize listener
window.addEventListener('resize', drawElevationProfile);

// Setup hover listeners on canvas
export function initElevationChartListeners() {
    const canvas = document.getElementById('elevation-canvas');
    if (!canvas) return;
    
    canvas.addEventListener('mousemove', (e) => {
        const points = state.gpxTrackPoints;
        if (points.length === 0) return;
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        
        const paddingLeft = 45;
        const paddingRight = 15;
        const chartWidth = rect.width - paddingLeft - paddingRight;
        const maxDist = points[points.length - 1].dist;
        
        const hoveredDist = ((mouseX - paddingLeft) / chartWidth) * maxDist;
        
        let bestPt = points[0];
        let minDist = Math.abs(bestPt.dist - hoveredDist);
        for (let i = 1; i < points.length; i++) {
            const diff = Math.abs(points[i].dist - hoveredDist);
            if (diff < minDist) {
                minDist = diff;
                bestPt = points[i];
            }
        }
        
        state.hoveredPoint = bestPt;
        updateHoverMarker(bestPt.lat, bestPt.lon);
        drawElevationProfile();
    });
    
    canvas.addEventListener('mouseleave', () => {
        state.hoveredPoint = null;
        clearHoverMarker();
        drawElevationProfile();
    });
}
