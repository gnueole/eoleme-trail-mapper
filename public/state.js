export let state = {
    gpxTrackPoints: [], // Array of { lat, lon, ele, dist }
    checkpoints: [],    // Array of { id, name, dist, ele, icon, use, lat, lon }
    raceName: 'Custom Trail Race',
    totalDistance: 0,   // km
    totalGain: 0,       // m D+
    originalGPXXml: null,
    gpxFileName: 'route.gpx',
    locale: 'fr',       // Default to French interface
    raceCategory: null,
    raceRunningStones: null,
    raceLogoUrl: null,
    raceOfficialUrl: null,
    raceStartDate: null,
    raceDirectEntry: null,
    unit: 'km' // km or mi
};

export function saveStateToLocalStorage() {
    try {
        const raceUrlInput = document.getElementById('race-url');
        const settingCharLimit = document.getElementById('garmin-char-limit');
        const settingSnapThreshold = document.getElementById('snap-threshold');
        const settingShortenNames = document.getElementById('shorten-names');
        const settingAddElevToName = document.getElementById('add-elev-to-name');

        const dataToSave = {
            raceName: state.raceName,
            gpxFileName: state.gpxFileName,
            gpxTrackPoints: state.gpxTrackPoints,
            checkpoints: state.checkpoints,
            totalDistance: state.totalDistance,
            totalGain: state.totalGain,
            originalGPXXml: state.originalGPXXml ? new XMLSerializer().serializeToString(state.originalGPXXml) : null,
            raceUrl: raceUrlInput ? raceUrlInput.value : '',
            locale: state.locale || 'fr',
            raceCategory: state.raceCategory || null,
            raceRunningStones: state.raceRunningStones || null,
            raceLogoUrl: state.raceLogoUrl || null,
            raceOfficialUrl: state.raceOfficialUrl || null,
            raceStartDate: state.raceStartDate || null,
            raceDirectEntry: state.raceDirectEntry || null,
            unit: state.unit || 'km',
            settings: {
                charLimit: settingCharLimit ? settingCharLimit.value : '15',
                snapThreshold: settingSnapThreshold ? settingSnapThreshold.value : '150',
                shortenNames: settingShortenNames ? settingShortenNames.checked : true,
                addElev: settingAddElevToName ? settingAddElevToName.checked : false
            }
        };
        localStorage.setItem('trail_mapper_state', JSON.stringify(dataToSave));
    } catch (e) {
        console.error('Failed to save state to localStorage', e);
    }
}
