// The URL guards behind every src/href the app sets from data.
//
// Production logged GET /null after race loads for weeks (see CHANGELOG 1.7.0).
// The first test reproduces the mechanism: an <img src> given null asks the
// server for "/null". The others pin the guard that makes it impossible.
//
// Run: make test-js   (or: node --test tests/js/)

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { safeHttpUrl, setImageSource, setLinkHref } from '../../public/js/urls.js';

/** The part of an element the guards touch, with the browser's src coercion. */
function fakeElement() {
    const attrs = new Map();
    const el = {
        attrs,
        getAttribute: (k) => (attrs.has(k) ? attrs.get(k) : null),
        setAttribute: (k, v) => attrs.set(k, String(v)),
        removeAttribute: (k) => attrs.delete(k),
    };
    // HTMLImageElement.src is a reflected attribute: assigning null stores "null".
    Object.defineProperty(el, 'src', { set: (v) => attrs.set('src', String(v)), get: () => attrs.get('src') });
    return el;
}

test('the old assignment turned a null logo into a request to /null', () => {
    const img = fakeElement();
    img.src = null;                          // what updateRaceInfoCard did before 1.7.0
    assert.equal(img.getAttribute('src'), 'null');
    assert.equal(new URL('null', 'https://gpx.eole.me/').pathname, '/null');
});

test('safeHttpUrl keeps absolute http(s) URLs only', () => {
    assert.equal(safeHttpUrl('https://volvic.livetrail.net/'), 'https://volvic.livetrail.net/');
    assert.equal(safeHttpUrl('  http://example.org/a?b=1 '), 'http://example.org/a?b=1');
    for (const bad of [null, undefined, '', 'null', 'undefined', 'None', '#', 'javascript:alert(1)', 'ftp://x', 'www.example.org', 42, {}]) {
        assert.equal(safeHttpUrl(bad), null, `rejects ${JSON.stringify(bad)}`);
    }
});

test('setImageSource never writes a non-URL, and clears a stale src', () => {
    const img = fakeElement();
    assert.equal(setImageSource(img, 'https://res.cloudinary.com/x/logo.png'), true);
    assert.equal(img.getAttribute('src'), 'https://res.cloudinary.com/x/logo.png');
    for (const bad of [null, 'null', '', undefined]) {
        assert.equal(setImageSource(img, bad), false);
        assert.equal(img.getAttribute('src'), null, `no src left for ${JSON.stringify(bad)}`);
    }
});

test('setLinkHref parks a missing URL on "#"', () => {
    const a = fakeElement();
    assert.equal(setLinkHref(a, null), false);
    assert.equal(a.getAttribute('href'), '#');
    assert.equal(setLinkHref(a, 'https://montblanc.utmb.world/races/utmb'), true);
    assert.equal(a.getAttribute('href'), 'https://montblanc.utmb.world/races/utmb');
});
