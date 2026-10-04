// URL guards for everything the page turns into a request.
//
// An <img src> or <a href> given null becomes the string "null", and the browser
// asks the server for /null. Production logged that request after race loads
// for weeks (see CHANGELOG 1.7.0). Every src/href the app sets from data goes
// through here, so a missing value clears the attribute instead.

/** Returns the string if it is an absolute http(s) URL, otherwise null. */
export function safeHttpUrl(value) {
    if (typeof value !== 'string') return null;
    const trimmed = value.trim();
    if (!/^https?:\/\//i.test(trimmed)) return null;
    try {
        const parsed = new URL(trimmed);
        return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : null;
    } catch (e) {
        return null;
    }
}

/**
 * Sets an image's src from data, or removes it. Returns true when a URL was set.
 * Removing the attribute matters: setting src to '' or null still produces a
 * request in some browsers.
 */
export function setImageSource(img, value) {
    if (!img) return false;
    const url = safeHttpUrl(value);
    if (url) {
        if (img.getAttribute('src') !== url) img.setAttribute('src', url);
        return true;
    }
    img.removeAttribute('src');
    return false;
}

/** Sets a link's href from data, or parks it on "#". Returns true when a URL was set. */
export function setLinkHref(link, value) {
    if (!link) return false;
    const url = safeHttpUrl(value);
    link.setAttribute('href', url || '#');
    return !!url;
}
