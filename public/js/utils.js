export function shortenNameForGarmin(name) {
    const settingShortenNames = document.getElementById('shorten-names');
    if (!settingShortenNames || !settingShortenNames.checked) return name;
    
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

export function generateGarminName(name, ele, unit = 'km') {
    let clean = shortenNameForGarmin(name).trim();
    const settingAddElevToName = document.getElementById('add-elev-to-name');
    const settingCharLimit = document.getElementById('char-limit');
    
    if (settingAddElevToName && settingAddElevToName.checked && ele) {
        if (unit === 'mi') {
            const eleFt = Math.round(ele * 3.28084);
            clean = `${clean} ${eleFt}ft`;
        } else {
            clean = `${clean} ${ele}m`;
        }
    }
    
    // Apply character truncation
    const limit = settingCharLimit ? parseInt(settingCharLimit.value) : 15;
    if (clean.length > limit) {
        clean = clean.substring(0, limit);
    }
    
    return clean;
}
