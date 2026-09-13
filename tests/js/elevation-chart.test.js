// Frontend tests run on node:test — no runner, no devDependencies. The repo has
// deliberately shipped zero JS tooling (package.json only echoes a message), and
// that is exactly why a ReferenceError in the chart's hover path survived
// unnoticed: nothing has ever executed this code outside a browser.
//
// Run: make test-js   (or: node --test tests/js/)

import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

/** Records every call and property set, so a draw can be asserted on. */
function makeContext() {
    const text = [];
    const noop = () => {};
    return {
        text,
        clearRect: noop, beginPath: noop, moveTo: noop, lineTo: noop,
        closePath: noop, stroke: noop, fill: noop, arc: noop, scale: noop,
        setLineDash: noop,
        fillText: (value) => text.push(String(value)),
        createLinearGradient: () => ({ addColorStop: noop }),
        strokeStyle: '', fillStyle: '', font: '',
        lineWidth: 0, textAlign: '', textBaseline: ''
    };
}

/**
 * A non-zero rect matters: drawElevationProfile derives chartWidth/chartHeight
 * from it, and a 0x0 canvas would sail past the interesting code and let a
 * broken test pass for the wrong reason.
 */
function installDom(ctx, { lightTheme = false } = {}) {
    const canvas = {
        width: 0,
        height: 0,
        getContext: () => ctx,
        getBoundingClientRect: () => ({ width: 640, height: 220 }),
        addEventListener: () => {}
    };
    globalThis.window = { devicePixelRatio: 1, addEventListener: () => {} };
    globalThis.document = {
        body: { classList: { contains: (c) => lightTheme && c === 'light-theme' } },
        getElementById: (id) => (id === 'elevation-canvas' ? canvas : { style: {} })
    };
    return canvas;
}

// window must exist before the module is evaluated: it registers a resize
// listener at import time.
installDom(makeContext());
const { drawElevationProfile } = await import('../../public/js/elevation-chart.js');
const { state } = await import('../../public/js/state.js');

const TRACK = [
    { lat: 45.92, lon: 6.86, ele: 1035, dist: 0 },
    { lat: 45.88, lon: 6.79, ele: 1400, dist: 9.14 },
    { lat: 45.89, lon: 6.71, ele: 809, dist: 22.89 }
];

beforeEach(() => {
    state.gpxTrackPoints = TRACK;
    state.checkpoints = [
        { name: 'Les Houches', dist: 9.14, ele: 1400, icon: 'Water Source', use: true }
    ];
    state.hoveredPoint = null;
    state.unit = 'km';
    state.raceName = 'UTMB';
    state.totalDistance = 22.89;
    state.totalGain = 900;
});

test('renders a track without a hover', () => {
    const ctx = makeContext();
    installDom(ctx);
    assert.doesNotThrow(() => drawElevationProfile());
    // Axis labels prove it drew rather than bailing out early
    assert.ok(ctx.text.some((t) => t.endsWith('m')), 'expected elevation axis labels');
});

test('renders the hover readout', () => {
    const ctx = makeContext();
    installDom(ctx);
    state.hoveredPoint = TRACK[1];

    assert.doesNotThrow(
        () => drawElevationProfile(),
        'the hover path must not throw — a ReferenceError here aborts the render mid-frame'
    );

    // The whole point of the hover: the distance/elevation readout beside the
    // cursor. It is drawn last, so an exception earlier silently removes it.
    assert.ok(
        ctx.text.some((t) => t.includes('9.1km') && t.includes('1400m')),
        `expected a "9.1km | 1400m" readout, got: ${JSON.stringify(ctx.text)}`
    );
});

test('renders the hover readout in light theme', () => {
    const ctx = makeContext();
    installDom(ctx, { lightTheme: true });
    state.hoveredPoint = TRACK[1];

    assert.doesNotThrow(() => drawElevationProfile());
    assert.ok(ctx.text.some((t) => t.includes('9.1km')), 'expected the readout in light theme too');
});

test('handles an empty track without drawing', () => {
    const ctx = makeContext();
    installDom(ctx);
    state.gpxTrackPoints = [];
    assert.doesNotThrow(() => drawElevationProfile());
    assert.equal(ctx.text.length, 0, 'nothing should be drawn for an empty track');
});
