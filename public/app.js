import { state, saveStateToLocalStorage } from './state.js?v=1.0.5';
import { TRANSLATIONS, getSymbolLabel, SYMBOL_LABELS } from './translations.js?v=1.0.5';
import { 
    initMap, 
    drawRouteOnMap, 
    plotCheckpointsOnMap, 
    snapPOIsToTrack, 
    getMiniIconSvg,
    invalidateMapSize,
    getSymbolColor
} from './map-utils.js?v=1.0.5';
import { drawElevationProfile, initElevationChartListeners } from './elevation-chart.js?v=1.0.5';
import { shortenNameForGarmin, generateGarminName } from './utils.js?v=1.0.5';
import { VERSION } from './version.js?v=1.0.5';

// DOM Selectors
const raceUrlInput = document.getElementById('race-url');
const btnFetch = document.getElementById('btn-fetch');
const fetchLoader = document.getElementById('fetch-loader');
const fetchStatusText = document.getElementById('fetch-status');
const tableHtmlPaste = document.getElementById('table-html-paste');
const btnParseHtml = document.getElementById('btn-parse-html');

const settingCharLimit = document.getElementById('garmin-char-limit');
const settingSnapThreshold = document.getElementById('snap-threshold');
const settingShortenNames = document.getElementById('shorten-names');
const settingAddElevToName = document.getElementById('add-elev-to-name');

const statRaceName = document.getElementById('stat-race-name');
const statDistance = document.getElementById('stat-distance');
const statGain = document.getElementById('stat-gain');
const statGpxPoints = document.getElementById('stat-gpx-points');

const btnMergeDownload = document.getElementById('btn-merge-download');
const btnMergeDownloadTcx = document.getElementById('btn-merge-download-tcx');
const btnMergeDownloadSuunto = document.getElementById('btn-merge-download-suunto');
const btnMergeDownloadCoros = document.getElementById('btn-merge-download-coros');

const btnAbout = document.getElementById('btn-about');
const btnClearState = document.getElementById('btn-clear-state');
const fileInput = document.getElementById('gpx-file');
const dragDropZone = document.getElementById('drag-drop-zone');
const dragDropFileName = document.getElementById('drag-drop-file-name');

// Language management
function setLanguage(lang) {
    state.locale = lang;
    try {
        localStorage.setItem('preferred-locale', lang);
    } catch (e) {}

    const selector = document.getElementById('locale-selector');
    if (selector) selector.value = lang;

    // Update translations in layout
    document.querySelector('.branding h1').innerHTML = `${TRANSLATIONS[lang].title} <span class="version-label"></span>`;
    document.querySelectorAll('.version-label').forEach(el => {
        el.textContent = `v${VERSION}`;
    });
    document.querySelectorAll('.version-badge').forEach(el => {
        el.textContent = `Version ${VERSION}`;
    });
    btnAbout.textContent = TRANSLATIONS[lang].about;
    btnClearState.textContent = TRANSLATIONS[lang].reset;
    
    const stepHeaders = document.querySelectorAll('.card-header h2');
    if (stepHeaders.length >= 4) {
        stepHeaders[0].textContent = TRANSLATIONS[lang].step1_title;
        stepHeaders[1].textContent = TRANSLATIONS[lang].step2_title;
        stepHeaders[2].innerHTML = `${TRANSLATIONS[lang].step3_title} (<span id="poi-count">${state.checkpoints.length}</span>)`;
        stepHeaders[3].textContent = TRANSLATIONS[lang].step4_title;
    }
    
    const tabBtns = document.querySelectorAll('.tab-btn');
    if (tabBtns.length >= 2) {
        tabBtns[0].textContent = TRANSLATIONS[lang].tab_fetch;
        tabBtns[1].textContent = TRANSLATIONS[lang].tab_upload;
    }
    
    document.querySelector('label[for="race-url"]').textContent = TRANSLATIONS[lang].race_url_label;
    btnFetch.textContent = TRANSLATIONS[lang].fetch;
    document.querySelector('.input-helper').textContent = TRANSLATIONS[lang].fetch_helper;
    document.querySelector('.drag-drop-zone p').innerHTML = `${TRANSLATIONS[lang].drag_drop} <span class="highlight">${TRANSLATIONS[lang].browse}</span>`;
    document.querySelector('label[for="table-html-paste"]').textContent = TRANSLATIONS[lang].paste_label;
    tableHtmlPaste.placeholder = TRANSLATIONS[lang].paste_placeholder;
    btnParseHtml.textContent = TRANSLATIONS[lang].parse_btn;
    
    document.querySelector('.glass-card:nth-of-type(2) .card-header h2').textContent = TRANSLATIONS[lang].step2_title;
    document.querySelector('label[for="char-limit"]').textContent = TRANSLATIONS[lang].char_limit_label;
    settingCharLimit.options[0].textContent = TRANSLATIONS[lang].char_limit_10;
    settingCharLimit.options[1].textContent = TRANSLATIONS[lang].char_limit_15;
    settingCharLimit.options[2].textContent = TRANSLATIONS[lang].char_limit_inf;
    document.querySelector('label[for="snap-threshold"]').textContent = TRANSLATIONS[lang].snap_threshold_label;
    document.querySelector('.settings-grid + .checkbox-group label').textContent = TRANSLATIONS[lang].shorten_names;
    document.querySelector('.settings-grid + .checkbox-group + .checkbox-group label').textContent = TRANSLATIONS[lang].add_elev;
    
    document.querySelectorAll('.stat-label')[0].textContent = TRANSLATIONS[lang].stat_race;
    document.querySelectorAll('.stat-label')[1].textContent = TRANSLATIONS[lang].stat_dist;
    document.querySelectorAll('.stat-label')[2].textContent = TRANSLATIONS[lang].stat_elev;
    document.querySelectorAll('.stat-label')[3].textContent = TRANSLATIONS[lang].stat_points;
    
    document.querySelector('.map-overlay h3').textContent = TRANSLATIONS[lang].map_title;
    document.querySelector('.map-overlay p').textContent = TRANSLATIONS[lang].map_helper;
    document.querySelector('.elevation-profile-card .card-header h2').textContent = TRANSLATIONS[lang].elev_profile;
    document.querySelector('.profile-helper').textContent = TRANSLATIONS[lang].hover_helper;
    
    document.getElementById('btn-add-poi').querySelector('span').textContent = TRANSLATIONS[lang].add_poi;
    
    const ths = document.querySelectorAll('.poi-table th');
    if (ths.length >= 7) {
        ths[0].textContent = TRANSLATIONS[lang].col_use;
        ths[1].textContent = TRANSLATIONS[lang].col_name;
        ths[2].textContent = state.unit === 'mi' ? 'Dist (mi)' : 'Dist (km)';
        ths[3].textContent = TRANSLATIONS[lang].col_elev;
        ths[4].textContent = TRANSLATIONS[lang].col_time;
        ths[5].textContent = TRANSLATIONS[lang].col_icon;
        ths[6].textContent = TRANSLATIONS[lang].col_del;
    }
    
    renderPOITable();
    
    // About Section
    document.querySelector('.modal-body h2').textContent = TRANSLATIONS[lang].about_title;
    const aboutParagraphs = document.querySelectorAll('.modal-body p');
    if (aboutParagraphs.length >= 3) {
        aboutParagraphs[0].innerHTML = TRANSLATIONS[lang].about_p1;
        aboutParagraphs[1].innerHTML = TRANSLATIONS[lang].about_p2;
        aboutParagraphs[2].innerHTML = TRANSLATIONS[lang].about_dev;
    }
    document.querySelector('.modal-body h3').textContent = TRANSLATIONS[lang].about_features_title;
    const aboutLis = document.querySelectorAll('.modal-body li');
    if (aboutLis.length >= 5) {
        aboutLis[0].innerHTML = TRANSLATIONS[lang].about_feat1;
        aboutLis[1].innerHTML = TRANSLATIONS[lang].about_feat2;
        aboutLis[2].innerHTML = TRANSLATIONS[lang].about_feat3;
        aboutLis[3].innerHTML = TRANSLATIONS[lang].about_feat4;
        aboutLis[4].innerHTML = TRANSLATIONS[lang].about_feat5;
    }
    document.querySelector('.modal-body .disclaimer').innerHTML = TRANSLATIONS[lang].about_disclaimer;
    
    // Success Modal
    document.getElementById('lbl-success-title').textContent = TRANSLATIONS[lang].modal_success_title;
    document.getElementById('lbl-success-dist').textContent = TRANSLATIONS[lang].modal_dist;
    document.getElementById('lbl-success-elev').textContent = TRANSLATIONS[lang].modal_elev;
    document.getElementById('lbl-success-start-loc').textContent = TRANSLATIONS[lang].modal_start_loc;
    document.getElementById('lbl-success-start-date').textContent = TRANSLATIONS[lang].modal_start_date;
    document.getElementById('btn-close-success-ok').textContent = TRANSLATIONS[lang].modal_got_it;
    
    // Watch Import Guide Card
    const lblGuideTitle = document.getElementById('lbl-guide-title');
    if (lblGuideTitle) {
        lblGuideTitle.textContent = TRANSLATIONS[lang].guide_title;
        document.getElementById('lbl-garmin-pc-title').querySelector('span').textContent = TRANSLATIONS[lang].garmin_pc_title;
        document.getElementById('lbl-garmin-pc-steps').innerHTML = TRANSLATIONS[lang].garmin_pc_steps;
        document.getElementById('lbl-garmin-mobile-title').querySelector('span').textContent = TRANSLATIONS[lang].garmin_mobile_title;
        document.getElementById('lbl-garmin-mobile-steps').innerHTML = TRANSLATIONS[lang].garmin_mobile_steps;
        
        document.getElementById('lbl-suunto-pc-title').querySelector('span').textContent = TRANSLATIONS[lang].suunto_pc_title;
        document.getElementById('lbl-suunto-pc-desc').textContent = TRANSLATIONS[lang].suunto_pc_desc;
        document.getElementById('lbl-suunto-mobile-title').querySelector('span').textContent = TRANSLATIONS[lang].suunto_mobile_title;
        document.getElementById('lbl-suunto-mobile-steps').innerHTML = TRANSLATIONS[lang].suunto_mobile_steps;
        
        document.getElementById('lbl-coros-pc-title').querySelector('span').textContent = TRANSLATIONS[lang].coros_pc_title;
        document.getElementById('lbl-coros-pc-steps').innerHTML = TRANSLATIONS[lang].coros_pc_steps;
        document.getElementById('lbl-coros-mobile-title').querySelector('span').textContent = TRANSLATIONS[lang].coros_mobile_title;
        document.getElementById('lbl-coros-mobile-steps').innerHTML = TRANSLATIONS[lang].coros_mobile_steps;
    }
}

// Render dynamic POI aid stations table
function renderPOITable() {
    const tbody = document.getElementById('poi-table-body');
    const poiCountSpan = document.getElementById('poi-count');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    if (poiCountSpan) {
        poiCountSpan.textContent = state.checkpoints.length;
    }
    
    if (state.checkpoints.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="7" class="placeholder-row">${TRANSLATIONS[state.locale].placeholder_table}</td>`;
        tbody.appendChild(row);
        return;
    }
    
    state.checkpoints.forEach((poi) => {
        const tr = document.createElement('tr');
        if (!poi.use) tr.style.opacity = '0.5';
        
        // Active checkbox
        const tdUse = document.createElement('td');
        tdUse.style.textAlign = 'center';
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.checked = poi.use;
        chk.addEventListener('change', () => {
            poi.use = chk.checked;
            saveStateToLocalStorage();
            renderPOITable();
            plotCheckpointsOnMap();
            drawElevationProfile();
            checkMergeAbility();
        });
        tdUse.appendChild(chk);
        tr.appendChild(tdUse);
        
        // Name Field
        const tdName = document.createElement('td');
        const nameWrapper = document.createElement('div');
        nameWrapper.style.display = 'flex';
        nameWrapper.style.flexDirection = 'column';
        nameWrapper.style.gap = '0.25rem';
        
        const inputName = document.createElement('input');
        inputName.type = 'text';
        inputName.className = 'cell-input';
        inputName.value = poi.name;
        inputName.style.fontWeight = '600';
        inputName.addEventListener('change', () => {
            poi.name = inputName.value;
            saveStateToLocalStorage();
            updateGarminLabel();
        });
        
        const garminLabel = document.createElement('span');
        garminLabel.style.fontSize = '0.7rem';
        garminLabel.style.color = 'var(--accent-color)';
        garminLabel.style.fontWeight = '700';
        garminLabel.style.opacity = '0.85';
        
        const updateGarminLabel = () => {
            const garminName = generateGarminName(poi.name, poi.ele);
            garminLabel.textContent = `Garmin: ${garminName}`;
        };
        updateGarminLabel();
        
        nameWrapper.appendChild(inputName);
        nameWrapper.appendChild(garminLabel);
        tdName.appendChild(nameWrapper);
        tr.appendChild(tdName);
        
        // Distance
        const tdDist = document.createElement('td');
        const inputDist = document.createElement('input');
        inputDist.type = 'number';
        inputDist.step = '0.1';
        inputDist.className = 'cell-input';
        
        const displayDist = state.unit === 'mi' ? poi.dist * 0.621371 : poi.dist;
        inputDist.value = displayDist.toFixed(1);
        
        inputDist.addEventListener('change', () => {
            const parsedVal = parseFloat(inputDist.value) || 0;
            poi.dist = state.unit === 'mi' ? parsedVal / 0.621371 : parsedVal;
            snapPOIsToTrack();
            saveStateToLocalStorage();
            renderPOITable();
            drawElevationProfile();
        });
        tdDist.appendChild(inputDist);
        tr.appendChild(tdDist);
        
        // Elevation
        const tdEle = document.createElement('td');
        const inputEle = document.createElement('input');
        inputEle.type = 'number';
        inputEle.className = 'cell-input';
        inputEle.value = poi.ele || 0;
        inputEle.addEventListener('change', () => {
            poi.ele = parseInt(inputEle.value) || 0;
            saveStateToLocalStorage();
            updateGarminLabel();
            drawElevationProfile();
        });
        tdEle.appendChild(inputEle);
        tr.appendChild(tdEle);
        
        // Time / Cut off
        const tdTime = document.createElement('td');
        const inputTime = document.createElement('input');
        inputTime.type = 'text';
        inputTime.className = 'cell-input';
        inputTime.placeholder = 'ex: Sat 12:30 AM';
        inputTime.value = poi.time || '';
        inputTime.addEventListener('change', () => {
            poi.time = inputTime.value;
            saveStateToLocalStorage();
        });
        tdTime.appendChild(inputTime);
        tr.appendChild(tdTime);
        
        // Icon Select
        const tdIcon = document.createElement('td');
        const iconWrapper = document.createElement('div');
        iconWrapper.style.display = 'flex';
        iconWrapper.style.alignItems = 'center';
        iconWrapper.style.gap = '0.35rem';
        iconWrapper.style.width = '100%';
        iconWrapper.style.padding = '0 0.25rem';
        
        // Mini icon span
        const miniIconSpan = document.createElement('span');
        miniIconSpan.style.display = 'inline-flex';
        miniIconSpan.style.alignItems = 'center';
        miniIconSpan.style.justifyContent = 'center';
        miniIconSpan.style.flexShrink = '0';
        
        const selectIcon = document.createElement('select');
        selectIcon.className = 'cell-input';
        selectIcon.style.flexGrow = '1';
        selectIcon.style.borderWidth = '2px';
        selectIcon.style.borderStyle = 'solid';
        selectIcon.style.borderRadius = '6px';
        selectIcon.style.height = '32px';
        selectIcon.style.fontSize = '0.8rem';
        
        const symbols = [
            'Aid Station', 'Food', 'Water Source', 'Summit', 
            'Medical Facility', 'Toilet', 'Shower', 'Campsite', 
            'Shelter', 'Rest Area', 'Transition', 'Danger', 
            'Checkpoint', 'Residence'
        ];
        
        symbols.forEach(sym => {
            const opt = document.createElement('option');
            opt.value = sym;
            opt.textContent = getSymbolLabel(sym, state.locale);
            if (sym === poi.icon) opt.selected = true;
            selectIcon.appendChild(opt);
        });
        
        const updateSelectStyle = () => {
            const symColor = getSymbolColor(selectIcon.value);
            selectIcon.style.borderColor = symColor;
            miniIconSpan.innerHTML = getMiniIconSvg(selectIcon.value);
            const svgEl = miniIconSpan.querySelector('span');
            if (svgEl) svgEl.style.marginRight = '0';
        };
        
        selectIcon.addEventListener('change', () => {
            poi.icon = selectIcon.value;
            updateSelectStyle();
            saveStateToLocalStorage();
            plotCheckpointsOnMap();
            drawElevationProfile();
        });
        
        updateSelectStyle();
        
        iconWrapper.appendChild(miniIconSpan);
        iconWrapper.appendChild(selectIcon);
        tdIcon.appendChild(iconWrapper);
        tr.appendChild(tdIcon);
        
        // Delete button
        const tdDel = document.createElement('td');
        tdDel.style.textAlign = 'center';
        const btnDel = document.createElement('button');
        btnDel.type = 'button';
        btnDel.className = 'btn-icon btn-danger';
        btnDel.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
        btnDel.addEventListener('click', () => {
            state.checkpoints = state.checkpoints.filter(x => x.id !== poi.id);
            saveStateToLocalStorage();
            renderPOITable();
            plotCheckpointsOnMap();
            drawElevationProfile();
            checkMergeAbility();
        });
        tdDel.appendChild(btnDel);
        tr.appendChild(tdDel);
        
        tbody.appendChild(tr);
    });
}

function updateStats() {
    statRaceName.textContent = state.raceName;
    if (state.totalDistance) {
        const displayDist = state.unit === 'mi' ? state.totalDistance * 0.621371 : state.totalDistance;
        statDistance.textContent = `${displayDist.toFixed(1)} ${state.unit}`;
    } else {
        statDistance.textContent = `-- ${state.unit}`;
    }
    statGain.textContent = state.totalGain ? `${state.totalGain} m D+` : '-- m D+';
    statGpxPoints.textContent = state.gpxTrackPoints.length;
    updateDifficultyTheme();
    updateRaceInfoCard();
}

function updateDifficultyTheme() {
    const dist = state.totalDistance;
    const isTDS = state.raceName && state.raceName.toUpperCase().includes('TDS');
    const cat = state.raceCategory ? state.raceCategory.toUpperCase().replace('WS', '').replace('KM', 'K') : '';
    const kmEffort = dist + (state.totalGain / 100);
    
    document.body.classList.remove('difficulty-20k', 'difficulty-50k', 'difficulty-100k', 'difficulty-100m', 'difficulty-tds');
    
    let trackColor = '#7ddf65';
    
    if (isTDS) {
        document.body.classList.add('difficulty-tds');
        trackColor = '#00ade9';
    } else if (cat.includes('100M')) {
        document.body.classList.add('difficulty-100m');
        trackColor = '#ef4444';
    } else if (cat.includes('100K')) {
        document.body.classList.add('difficulty-100k');
        trackColor = '#7ddf65';
    } else if (cat.includes('50K')) {
        document.body.classList.add('difficulty-50k');
        trackColor = '#ff9600';
    } else if (cat.includes('20K')) {
        document.body.classList.add('difficulty-20k');
        trackColor = '#ffff00';
    } else if (dist > 0) {
        if (kmEffort < 35) {
            document.body.classList.add('difficulty-20k');
            trackColor = '#ffff00';
        } else if (kmEffort < 80) {
            document.body.classList.add('difficulty-50k');
            trackColor = '#ff9600';
        } else if (kmEffort < 140) {
            document.body.classList.add('difficulty-100k');
            trackColor = '#7ddf65';
        } else {
            document.body.classList.add('difficulty-100m');
            trackColor = '#ef4444';
        }
    } else {
        document.body.classList.add('difficulty-100k');
    }
    
    if (trackLayer && typeof trackLayer.setStyle === 'function') {
        trackLayer.setStyle({ color: trackColor });
    }
}

function updateRaceInfoCard() {
    const card = document.getElementById('race-info-card');
    const infoProfileRow = document.getElementById('info-profile-row');
    if (!card) return;
    
    const logoContainer = document.getElementById('info-logo-container');
    const logoImg = document.getElementById('info-race-logo');
    
    if (state.raceLogoUrl) {
        logoImg.src = state.raceLogoUrl;
        logoContainer.style.display = 'flex';
    } else {
        logoContainer.style.display = 'none';
    }
    
    const badgesContainer = document.getElementById('info-badges-container');
    if (badgesContainer) {
        badgesContainer.innerHTML = '';
        let hasBadges = false;
        
        if (state.raceCategory) {
            const cat = state.raceCategory.toUpperCase().replace('WS', '').replace('KM', 'K');
            const imgUrl = `https://res.cloudinary.com/utmb-world/image/upload/q_auto/f_auto/c_fill,g_auto/if_w_gt_1920/c_scale,w_1920/if_end/v1/Common/categories/${cat}_bg`;
            
            const badgeDiv = document.createElement('div');
            badgeDiv.style.display = 'flex';
            badgeDiv.style.alignItems = 'center';
            badgeDiv.innerHTML = `
                <img src="${imgUrl}" alt="Category ${cat}" style="height: 52px; object-fit: contain; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.25));">
            `;
            badgesContainer.appendChild(badgeDiv);
            hasBadges = true;
        }
        
        if (state.raceRunningStones !== null && state.raceRunningStones !== undefined) {
            const count = parseInt(state.raceRunningStones);
            if (count > 0) {
                const badgeDiv = document.createElement('div');
                badgeDiv.style.display = 'flex';
                badgeDiv.style.alignItems = 'center';
                badgeDiv.innerHTML = `
                    <div style="position: relative; width: 52px; height: 52px; border-radius: 50%; background: #000d44; border: 2px solid #00dbff; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 10px rgba(0, 219, 255, 0.25);">
                        <span style="color: #00dbff; font-family: var(--font-title); font-size: 1.6rem; font-weight: 900; line-height: 1; margin-top: -1px;">${count}</span>
                    </div>
                `;
                badgesContainer.appendChild(badgeDiv);
                hasBadges = true;
            }
        }
        
        if (state.raceDirectEntry) {
            const entryVal = state.raceDirectEntry;
            const imgUrl = `https://res.cloudinary.com/utmb-world/image/upload/v1/Common/categories/${entryVal}.png`;
            
            const badgeDiv = document.createElement('div');
            badgeDiv.style.display = 'flex';
            badgeDiv.style.alignItems = 'center';
            badgeDiv.innerHTML = `
                <img src="${imgUrl}" alt="Finals Access" style="height: 52px; object-fit: contain; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.25));">
            `;
            badgesContainer.appendChild(badgeDiv);
            hasBadges = true;
        }
        
        badgesContainer.style.display = hasBadges ? 'flex' : 'none';
        
        if (infoProfileRow) {
            if (hasBadges) {
                infoProfileRow.classList.remove('no-details');
            } else {
                infoProfileRow.classList.add('no-details');
            }
        }
    }
    
    const linkBtn = document.getElementById('btn-race-link');
    if (state.raceOfficialUrl) {
        linkBtn.href = state.raceOfficialUrl;
        linkBtn.style.display = 'flex';
    } else {
        linkBtn.style.display = 'none';
    }
    
    const lang = state.locale || 'fr';
    document.getElementById('lbl-race-link').textContent = lang === 'fr' ? 'Voir sur le site officiel' : 'View official site';
    document.getElementById('lbl-race-details-title').textContent = lang === 'fr' ? 'Détails de la Course' : 'Race Details';
    
    const hasDetails = !!(state.raceCategory || state.raceRunningStones || state.raceLogoUrl || state.raceOfficialUrl);
    card.style.display = hasDetails ? 'block' : 'none';
}

function loadStateFromLocalStorage() {
    try {
        const saved = localStorage.getItem('trail_mapper_state');
        if (!saved) return;
        
        const data = JSON.parse(saved);
        state.raceName = data.raceName || 'Custom Trail Race';
        state.gpxFileName = data.gpxFileName || 'route.gpx';
        state.gpxTrackPoints = data.gpxTrackPoints || [];
        state.checkpoints = data.checkpoints || [];
        state.totalDistance = data.totalDistance || 0;
        state.totalGain = data.totalGain || 0;
        state.locale = data.locale || 'fr';
        state.raceCategory = data.raceCategory || null;
        state.raceRunningStones = data.raceRunningStones || null;
        state.raceLogoUrl = data.raceLogoUrl || null;
        state.raceOfficialUrl = data.raceUrl || null;
        state.raceStartDate = data.raceStartDate || null;
        state.raceDirectEntry = data.raceDirectEntry || null;
        state.unit = data.unit || localStorage.getItem('preferred-unit') || 'km';
        
        if (data.originalGPXXml) {
            const parser = new DOMParser();
            state.originalGPXXml = parser.parseFromString(data.originalGPXXml, 'application/xml');
        }
        
        if (data.settings) {
            if (settingCharLimit) settingCharLimit.value = data.settings.charLimit || '15';
            if (settingSnapThreshold) settingSnapThreshold.value = data.settings.snapThreshold || '150';
            if (settingShortenNames) settingShortenNames.checked = data.settings.shortenNames !== false;
            if (settingAddElevToName) settingAddElevToName.checked = !!data.settings.addElev;
        }
        
        if (state.gpxFileName && dragDropFileName) {
            dragDropFileName.textContent = state.gpxFileName;
            dragDropFileName.style.display = 'inline-block';
        }
        
        if (state.locale) {
            setLanguage(state.locale);
        }
        
        if (state.gpxTrackPoints.length > 0) {
            document.getElementById('map-overlay').classList.add('hidden');
            drawRouteOnMap();
        }
        
        renderPOITable();
        updateStats();
        drawElevationProfile();
        checkMergeAbility();
        
    } catch (e) {
        console.error('Failed to load state from localStorage', e);
    }
}

// GPX file parser logic
function handleGpxFile(file) {
    if (!file) return;
    
    state.gpxFileName = file.name;
    if (dragDropFileName) {
        dragDropFileName.textContent = file.name;
        dragDropFileName.style.display = 'inline-block';
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(text, 'application/xml');
        
        // Check for XML parsing errors
        const parseError = xmlDoc.getElementsByTagName('parsererror');
        if (parseError.length > 0) {
            alert('Format XML invalide. Veuillez téléverser un fichier GPX valide.');
            return;
        }
        
        state.originalGPXXml = xmlDoc;
        
        // Extract track points and compute distances
        const trkpts = xmlDoc.getElementsByTagName('trkpt');
        if (trkpts.length === 0) {
            alert('Aucun tracé (trkpt) trouvé dans le fichier GPX.');
            return;
        }
        
        const points = [];
        let cumDist = 0;
        let cumGain = 0;
        
        // Haversine formula
        const getDistance = (lat1, lon1, lat2, lon2) => {
            const R = 6371; // Earth radius in km
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                      Math.sin(dLon / 2) * Math.sin(dLon / 2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            return R * c;
        };
        
        for (let i = 0; i < trkpts.length; i++) {
            const pt = trkpts[i];
            const lat = parseFloat(pt.getAttribute('lat'));
            const lon = parseFloat(pt.getAttribute('lon'));
            const eleEl = pt.getElementsByTagName('ele')[0];
            const ele = eleEl ? parseFloat(eleEl.textContent) : 0;
            
            if (i > 0) {
                const prev = points[i - 1];
                cumDist += getDistance(prev.lat, prev.lon, lat, lon);
                if (ele > prev.ele) {
                    cumGain += (ele - prev.ele);
                }
            }
            
            points.push({ lat, lon, ele, dist: cumDist });
        }
        
        state.gpxTrackPoints = points;
        state.totalDistance = cumDist;
        state.totalGain = Math.round(cumGain);
        
        // Try to read race name from metadata
        const nameEl = xmlDoc.getElementsByTagName('name')[0];
        if (nameEl && nameEl.textContent) {
            state.raceName = nameEl.textContent.trim();
        } else {
            state.raceName = file.name.replace(/\.[^/.]+$/, "");
        }
        
        // Hide map instructions overlay
        document.getElementById('map-overlay').classList.add('hidden');
        
        // Redraw
        drawRouteOnMap();
        
        // Snap POIs if already loaded
        if (state.checkpoints.length > 0) {
            snapPOIsToTrack();
            renderPOITable();
        }
        
        updateStats();
        drawElevationProfile();
        checkMergeAbility();
        saveStateToLocalStorage();
    };
    reader.readAsText(file);
}

// Scrape HTML table parser
function parseUTMBTableHTML(htmlString) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, 'text/html');
    const rows = doc.querySelectorAll('tr');
    if (rows.length === 0) return [];
    
    let checkpoints = [];
    let headers = [];
    const headerRow = doc.querySelector('thead tr') || rows[0];
    if (headerRow) {
        const ths = headerRow.querySelectorAll('th, td');
        ths.forEach((th, idx) => {
            headers.push({ text: th.textContent.toLowerCase().trim(), index: idx });
        });
    }
    
    let distCol = -1;
    let eleCol = -1;
    let nameCol = -1;
    let cutoffCol = -1;
    
    headers.forEach(h => {
        if (h.text.match(/km|dist/)) distCol = h.index;
        if (h.text.match(/alt|elev|d\+|deni/)) eleCol = h.index;
        if (h.text.match(/checkpoint|post|lieu|stat|ravit|nom/)) nameCol = h.index;
        if (h.text.match(/cut\s*off|barriere|cutoff|limite/i)) cutoffCol = h.index;
    });
    
    if (distCol === -1) distCol = 1;
    if (eleCol === -1) eleCol = 2;
    if (nameCol === -1) nameCol = 0;
    
    rows.forEach((row, idx) => {
        if (idx === 0 && headerRow) return;
        const tds = row.querySelectorAll('td');
        if (tds.length < 2) return;
        
        const nameVal = tds[nameCol] ? tds[nameCol].textContent.trim() : '';
        const distVal = tds[distCol] ? tds[distCol].textContent.trim() : '';
        const eleVal = tds[eleCol] ? tds[eleCol].textContent.trim() : '';
        const timeVal = cutoffCol !== -1 && tds[cutoffCol] ? tds[cutoffCol].textContent.trim() : '';
        
        const distMatch = distVal.replace(',', '.').match(/[\d\.]+/);
        const distance = distMatch ? parseFloat(distMatch[0]) : null;
        
        const eleMatch = eleVal.match(/\d+/);
        const elevation = eleMatch ? parseInt(eleMatch[0]) : null;
        
        if (nameVal && distance !== null) {
            let icon = 'Checkpoint';
            const nameLower = nameVal.toLowerCase();
            const ICON_MAP = [
                { pattern: /ravit|food|repas|restau/i, icon: 'Food' },
                { pattern: /eau|water|sourc/i, icon: 'Water Source' },
                { pattern: /sommet|peak|col|summit|mont/i, icon: 'Summit' },
                { pattern: /secour|medical|aid|croix/i, icon: 'Medical Facility' },
                { pattern: /danger|warning|diffic/i, icon: 'Danger' },
                { pattern: /refuge|chalet|gîte|gite|shelter|cabane/i, icon: 'Shelter' },
                { pattern: /camp|bivouac/i, icon: 'Campsite' },
                { pattern: /toilet|wc|sanit/i, icon: 'Toilet' },
                { pattern: /douche|shower/i, icon: 'Shower' }
            ];
            for (const item of ICON_MAP) {
                if (nameLower.match(item.pattern)) {
                    icon = item.icon;
                    break;
                }
            }
            
            checkpoints.push({
                id: 'scraped_' + idx + '_' + Date.now(),
                name: nameVal,
                dist: distance,
                ele: elevation || 0,
                icon: icon,
                use: true,
                time: timeVal
            });
        }
    });
    
    return checkpoints;
}

function parseUTMBCopyPastedText(rawText) {
    const lines = rawText.split('\n')
                         .map(l => l.trim())
                         .filter(l => l.length > 0);
    
    let startIdx = 0;
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
        
        if (isNaN(distance) || isNaN(altitude)) {
            i = i - 5;
            continue;
        }
        
        const fastest = parsedLines[i++];
        const slowest = parsedLines[i++];
        
        let cutoff = '';
        let services = '';
        
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
        
        let icon = 'Residence';
        const nameLower = name.toLowerCase();
        if (nameLower.match(/ravit|food|repas|restau|beret|salardu|beaufort|canejan|vielha|arties|honeria/)) icon = 'Food';
        else if (nameLower.match(/eau|water|sourc/)) icon = 'Water Source';
        else if (nameLower.match(/sommet|peak|col|summit|mont|tuc|còth/)) icon = 'Summit';
        else if (nameLower.match(/secour|medical|aid|croix/)) icon = 'Medical Facility';
        else if (nameLower.match(/danger|warning|diffic/)) icon = 'Danger';
        
        if (services && parseInt(services.replace('+', '')) > 2) {
            icon = 'Food';
        }
        
        checkpoints.push({
            id: 'text_' + checkpoints.length + '_' + Date.now(),
            name: name,
            dist: distance,
            ele: altitude,
            icon: icon,
            use: true,
            time: cutoff || slowest || fastest || ''
        });
    }
    
    return checkpoints;
}

function checkMergeAbility() {
    const hasGPX = state.gpxTrackPoints.length > 0;
    const hasActiveStops = state.checkpoints.some(c => c.use);
    const disabled = !(hasGPX && hasActiveStops);
    
    btnMergeDownload.disabled = disabled;
    if (btnMergeDownloadTcx) btnMergeDownloadTcx.disabled = disabled;
    if (btnMergeDownloadSuunto) btnMergeDownloadSuunto.disabled = disabled;
    if (btnMergeDownloadCoros) btnMergeDownloadCoros.disabled = disabled;
}

async function triggerMergeDownload(format) {
    if (state.gpxTrackPoints.length === 0 || !state.originalGPXXml) {
        alert('No GPX route loaded.');
        return;
    }
    
    let gpxBlob;
    const serializer = new XMLSerializer();
    const gpxString = serializer.serializeToString(state.originalGPXXml);
    gpxBlob = new Blob([gpxString], { type: 'application/gpx+xml' });
    
    const mappedStations = state.checkpoints.map(c => ({
        name: c.name,
        dist: c.dist,
        icon: c.icon,
        use: c.use,
        time: c.time || ''
    }));
    
    const formData = new FormData();
    formData.append('gpx_file', gpxBlob, state.gpxFileName || 'route.gpx');
    formData.append('stations_json', JSON.stringify(mappedStations));
    
    const limit = settingCharLimit ? parseInt(settingCharLimit.value) : 15;
    const addElev = settingAddElevToName ? settingAddElevToName.checked : false;
    const shortenVal = settingShortenNames ? settingShortenNames.checked : true;
    
    formData.append('char_limit', limit);
    formData.append('add_elevation', addElev);
    formData.append('shorten_names', shortenVal);
    formData.append('format', format);
    
    try {
        const response = await fetch('/trail-mapper/api/merge', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Merge request failed on backend');
        }
        
        // Download the file
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        
        const ext = format === 'tcx' ? 'tcx' : 'gpx';
        const cleanName = state.raceName.toLowerCase().replace(/[^a-z0-9]/g, '_');
        a.download = `${cleanName}_with_checkpoints.${ext}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        
    } catch (err) {
        console.error(err);
        alert('Error during merge process: ' + err.message);
    }
}

// Event Listeners setup
btnParseHtml.addEventListener('click', () => {
    const rawInput = tableHtmlPaste.value.trim();
    if (!rawInput) {
        alert(TRANSLATIONS[state.locale].alert_parse_fail);
        return;
    }
    
    let parsed = [];
    let method = '';
    
    if (rawInput.includes('<tr') || rawInput.includes('<table')) {
        parsed = parseUTMBTableHTML(rawInput);
        method = 'HTML table';
    }
    
    if (parsed.length === 0) {
        parsed = parseUTMBCopyPastedText(rawInput);
        method = 'raw text';
    }
    
    if (parsed.length > 0) {
        parsed.sort((a, b) => a.dist - b.dist);
        state.checkpoints = parsed;
        
        snapPOIsToTrack();
        renderPOITable();
        drawElevationProfile();
        checkMergeAbility();
        
        const lang = state.locale || 'fr';
        const methodLabel = method === 'HTML table' 
            ? (lang === 'fr' ? 'tableau HTML' : 'HTML table') 
            : (lang === 'fr' ? 'texte brut' : 'raw text');
        const successMsg = lang === 'fr' 
            ? `Analyse réussie de ${parsed.length} points de passage depuis le ${methodLabel} !`
            : `Successfully parsed ${parsed.length} checkpoints from ${methodLabel}!`;
            
        showSuccessModal(
            state.raceName,
            successMsg,
            {
                dist: state.totalDistance ? state.totalDistance.toFixed(1) + " km" : (parsed[parsed.length - 1].dist.toFixed(1) + " km"),
                elev: state.totalGain ? state.totalGain + " m D+" : "--",
                startLoc: "--",
                startDate: "--"
            }
        );
        saveStateToLocalStorage();
    } else {
        alert(TRANSLATIONS[state.locale].alert_parse_fail);
    }
});

btnFetch.addEventListener('click', async () => {
    const url = raceUrlInput.value.trim();
    if (!url) {
        alert('Please enter a UTMB race URL.');
        return;
    }
    
    fetchLoader.classList.add('active');
    fetchStatusText.textContent = TRANSLATIONS[state.locale].status_connecting;
    
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
        const metadata = data.metadata || {};
        
        state.raceCategory = metadata.category || null;
        state.raceRunningStones = metadata.running_stones || null;
        state.raceLogoUrl = metadata.logo_url || null;
        state.raceOfficialUrl = url;
        state.raceStartDate = metadata.start_date || null;
        state.raceDirectEntry = metadata.direct_entry || null;
        
        if (scrapedStations.length > 0) {
            state.checkpoints = scrapedStations.map((s, idx) => ({
                id: s.id || ('scraped_' + idx + '_' + Date.now()),
                name: s.name,
                dist: s.dist,
                ele: s.ele || 0,
                icon: s.icon,
                use: s.use !== undefined ? s.use : true,
                time: s.time || ''
            }));
            if (metadata.course_name) {
                state.raceName = metadata.course_name;
            }
            renderPOITable();
        }
        
        updateRaceInfoCard();
        saveStateToLocalStorage();
        
        if (gpxUrl) {
            fetchStatusText.textContent = TRANSLATIONS[state.locale].status_downloading;
            const downloadResponse = await fetch('/trail-mapper/api/download-gpx', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: gpxUrl })
            });
            
            if (!downloadResponse.ok) {
                throw new Error('Failed to download GPX file from target URL');
            }
            
            const gpxBlob = await downloadResponse.blob();
            const mockFile = new File([gpxBlob], `${state.raceName.toLowerCase().replace(/[^a-z0-9]/g, '_')}.gpx`, { type: 'application/gpx+xml' });
            
            handleGpxFile(mockFile);
            
            showSuccessModal(
                state.raceName,
                TRANSLATIONS[state.locale].alert_fetch_success,
                {
                    dist: metadata.distance || "--",
                    elev: metadata.elevation || "--",
                    startLoc: metadata.start_location || "--",
                    startDate: metadata.start_date || "--"
                }
            );
        } else {
            showSuccessModal(
                metadata.course_name || state.raceName,
                TRANSLATIONS[state.locale].alert_fetch_no_gpx,
                {
                    dist: metadata.distance || "--",
                    elev: metadata.elevation || "--",
                    startLoc: metadata.start_location || "--",
                    startDate: metadata.start_date || "--"
                }
            );
            switchTab('upload-tab');
        }
        
    } catch (err) {
        console.error(err);
        const lang = state.locale || 'fr';
        const failMsg = lang === 'fr'
            ? `Impossible de récupérer les données de la course : ${err.message}\n\nRetour à l'onglet "Téléverser Fichiers" pour charger manuellement.`
            : `Failed to retrieve race data: ${err.message}\n\nFallback to "Upload Files" tab to load GPX and paste HTML manually.`;
        alert(failMsg);
        switchTab('upload-tab');
    } finally {
        fetchLoader.classList.remove('active');
    }
});

// Drag and drop setup
if (dragDropZone) {
    dragDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragDropZone.classList.add('dragover');
    });
    
    dragDropZone.addEventListener('dragleave', () => {
        dragDropZone.classList.remove('dragover');
    });
    
    dragDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dragDropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleGpxFile(e.dataTransfer.files[0]);
        }
    });
    
    dragDropZone.addEventListener('click', () => {
        fileInput.click();
    });
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleGpxFile(e.target.files[0]);
        }
    });
}

// Merge & export trigger registrations
if (btnMergeDownload) btnMergeDownload.addEventListener('click', () => triggerMergeDownload('gpx_garmin'));
if (btnMergeDownloadTcx) btnMergeDownloadTcx.addEventListener('click', () => triggerMergeDownload('tcx'));
if (btnMergeDownloadSuunto) btnMergeDownloadSuunto.addEventListener('click', () => triggerMergeDownload('gpx_suunto'));
if (btnMergeDownloadCoros) btnMergeDownloadCoros.addEventListener('click', () => triggerMergeDownload('gpx_coros'));

// Settings triggers
settingCharLimit.addEventListener('change', () => {
    renderPOITable();
    saveStateToLocalStorage();
});
settingShortenNames.addEventListener('change', () => {
    renderPOITable();
    saveStateToLocalStorage();
});
settingAddElevToName.addEventListener('change', () => {
    renderPOITable();
    saveStateToLocalStorage();
});
settingSnapThreshold.addEventListener('change', () => {
    snapPOIsToTrack();
    renderPOITable();
    saveStateToLocalStorage();
});

// Reset logic
btnClearState.addEventListener('click', () => {
    localStorage.removeItem('trail_mapper_state');
    
    state.gpxTrackPoints = [];
    state.checkpoints = [];
    state.raceName = 'Custom Trail Race';
    state.totalDistance = 0;
    state.totalGain = 0;
    state.originalGPXXml = null;
    state.gpxFileName = 'route.gpx';
    state.raceCategory = null;
    state.raceRunningStones = null;
    state.raceLogoUrl = null;
    state.raceOfficialUrl = null;
    state.raceStartDate = null;
    state.raceDirectEntry = null;
    
    if (dragDropFileName) {
        dragDropFileName.style.display = 'none';
        dragDropFileName.textContent = '';
    }
    
    document.getElementById('map-overlay').classList.remove('hidden');
    
    // Clear layers
    if (map) {
        initMap('map');
    }
    
    renderPOITable();
    updateStats();
    drawElevationProfile();
    checkMergeAbility();
    
    alert(TRANSLATIONS[state.locale].alert_reset);
});

// Tab Switcher logic
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.id === `${tabId}-btn` || btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    document.querySelectorAll('.tab-content').forEach(content => {
        if (content.id === tabId) {
            content.classList.add('active');
        } else {
            content.classList.remove('active');
        }
    });
}

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.id.replace('-btn', '');
        switchTab(tabId);
    });
});

// Language Switcher handler
const localeSelector = document.getElementById('locale-selector');
if (localeSelector) {
    localeSelector.addEventListener('change', (e) => {
        setLanguage(e.target.value);
    });
}

// Add Custom POI Row manually
document.getElementById('btn-add-poi').addEventListener('click', () => {
    const newPoi = {
        id: 'manual_' + Date.now(),
        name: state.locale === 'fr' ? 'Nouveau POI' : 'New POI',
        dist: 0,
        ele: 0,
        icon: 'Checkpoint',
        use: true,
        time: ''
    };
    state.checkpoints.push(newPoi);
    saveStateToLocalStorage();
    renderPOITable();
    snapPOIsToTrack();
    drawElevationProfile();
    checkMergeAbility();
});

// Modal triggers
const aboutModal = document.getElementById('about-modal');
if (btnAbout && aboutModal) {
    btnAbout.addEventListener('click', () => {
        aboutModal.style.display = 'flex';
    });
}

const btnCloseModal = document.querySelector('.btn-close');
if (btnCloseModal && aboutModal) {
    btnCloseModal.addEventListener('click', () => {
        aboutModal.style.display = 'none';
    });
}

if (aboutModal) {
    aboutModal.addEventListener('click', (e) => {
        if (e.target === aboutModal) {
            aboutModal.style.display = 'none';
        }
    });
}

// Theme switch triggers
const themeBtns = document.querySelectorAll('.theme-btn');

function applyTheme(theme) {
    themeBtns.forEach(btn => {
        if (btn.getAttribute('data-theme') === theme) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    if (theme === 'light') {
        document.body.classList.add('light-theme');
        document.body.classList.remove('dark-theme');
    } else if (theme === 'dark') {
        document.body.classList.add('dark-theme');
        document.body.classList.remove('light-theme');
    } else {
        document.body.classList.remove('light-theme');
        document.body.classList.remove('dark-theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (systemPrefersDark) {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.add('light-theme');
        }
    }
    
    try {
        localStorage.setItem('preferred-theme', theme);
    } catch (e) {}
    
    drawElevationProfile();
}

themeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const theme = btn.getAttribute('data-theme');
        applyTheme(theme);
    });
});

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const savedTheme = localStorage.getItem('preferred-theme') || 'system';
    if (savedTheme === 'system') {
        applyTheme('system');
    }
});

// Unit switcher logic
export function applyUnit(unit) {
    state.unit = unit;
    
    const btnUnitToggle = document.getElementById('btn-unit-toggle');
    if (btnUnitToggle) {
        btnUnitToggle.textContent = unit.toUpperCase();
        if (unit === 'mi') {
            btnUnitToggle.classList.add('btn-primary');
            btnUnitToggle.classList.remove('btn-secondary');
        } else {
            btnUnitToggle.classList.add('btn-secondary');
            btnUnitToggle.classList.remove('btn-primary');
        }
    }
    
    try {
        localStorage.setItem('preferred-unit', unit);
    } catch (e) {}
    
    // Refresh UI elements
    setLanguage(state.locale);
    updateStats();
    renderPOITable();
    drawElevationProfile();
    plotCheckpointsOnMap();
}

// Watch Import Guide Tab Switcher
const guideTabBtns = document.querySelectorAll('.guide-tab-container .tab-btn');
const guideContents = document.querySelectorAll('.guide-content');

function switchGuideTab(brand) {
    guideTabBtns.forEach(btn => {
        if (btn.getAttribute('data-guide-tab') === brand) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    guideContents.forEach(content => {
        if (content.id === `guide-${brand}`) {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    });
}

guideTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const brand = btn.getAttribute('data-guide-tab');
        switchGuideTab(brand);
    });
});

// Success Modal closing
const btnCloseSuccess = document.getElementById('btn-close-success');
if (btnCloseSuccess) btnCloseSuccess.addEventListener('click', () => {
    document.getElementById('success-modal').style.display = 'none';
});

const btnCloseSuccessOk = document.getElementById('btn-close-success-ok');
if (btnCloseSuccessOk) btnCloseSuccessOk.addEventListener('click', () => {
    document.getElementById('success-modal').style.display = 'none';
});

const successModal = document.getElementById('success-modal');
if (successModal) {
    successModal.addEventListener('click', (e) => {
        if (e.target === successModal) {
            document.getElementById('success-modal').style.display = 'none';
        }
    });
}

function showSuccessModal(title, msg, stats) {
    const modal = document.getElementById('success-modal');
    if (!modal) return;
    
    document.getElementById('success-course-name').textContent = title || 'Custom Trail Race';
    document.getElementById('success-message').textContent = msg || 'Successfully loaded checkpoints and GPX data!';
    
    document.getElementById('success-meta-dist').textContent = stats.dist || '--';
    document.getElementById('success-meta-elev').textContent = stats.elev || '--';
    document.getElementById('success-meta-start-loc').textContent = stats.startLoc || '--';
    document.getElementById('success-meta-start-date').textContent = stats.startDate || '--';
    
    modal.style.display = 'flex';
}

// DOM Content Loaded orchestrations
document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Map
    initMap('map');
    
    // 2. Initialize active theme
    try {
        const activeTheme = localStorage.getItem('preferred-theme') || 'system';
        applyTheme(activeTheme);
    } catch (e) {
        applyTheme('system');
    }
    
    // 3. Load active state / local persistence
    loadStateFromLocalStorage();
    
    // Set active unit switcher state
    applyUnit(state.unit || 'km');
    
    // Setup unit toggle button click handler
    const btnUnitToggle = document.getElementById('btn-unit-toggle');
    if (btnUnitToggle) {
        btnUnitToggle.addEventListener('click', () => {
            const nextUnit = state.unit === 'mi' ? 'km' : 'mi';
            applyUnit(nextUnit);
        });
    }
    
    // 4. Register elevation chart hover triggers
    initElevationChartListeners();
    
    // 5. Setup map fullscreen button click handler
    const btnMapFullscreen = document.getElementById('btn-map-fullscreen');
    if (btnMapFullscreen) {
        btnMapFullscreen.addEventListener('click', () => {
            const mapCard = document.querySelector('.map-card');
            if (!mapCard) return;
            const isFullscreen = mapCard.classList.toggle('fullscreen-active');
            if (isFullscreen) {
                btnMapFullscreen.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M10 14l-7 7"/></svg>`;
            } else {
                btnMapFullscreen.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>`;
            }
            setTimeout(() => {
                invalidateMapSize();
            }, 300);
        });
    }
});
