// The error contract of /api/parse-url as the frontend reads it, and the modal
// content each class of failure produces, in both languages.
//
// Run: make test-js   (or: node --test tests/js/)

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseApiError, describeError, sourceLabel } from '../../public/js/api-errors.js';
import { TRANSLATIONS } from '../../public/js/translations.js';

const upstream404 = {
    detail: 'The source has no data at this address.',
    error: { code: 'UPSTREAM_NOT_FOUND', source: 'livetrail', source_url: 'https://volvic.livetrail.net/', upstream_status: 404, message: 'The source has no data at this address.' },
};

test('parseApiError reads the contract', () => {
    const e = parseApiError(404, upstream404);
    assert.deepEqual(e, { code: 'UPSTREAM_NOT_FOUND', source: 'livetrail', sourceUrl: 'https://volvic.livetrail.net/', upstreamStatus: 404, message: 'The source has no data at this address.', status: 404 });
});

test('parseApiError falls back for legacy and non-JSON answers', () => {
    assert.equal(parseApiError(400, { detail: 'URL is unsafe (SSRF Protection).' }).code, 'INVALID_URL');
    assert.equal(parseApiError(400, { detail: 'x' }).message, 'x');
    assert.equal(parseApiError(502, null).code, 'INTERNAL_ERROR');
    assert.equal(parseApiError(500, '<html>Bad Gateway</html>').code, 'INTERNAL_ERROR');
    assert.equal(parseApiError(0, null).code, 'INTERNAL_ERROR');
});

for (const lang of ['en', 'fr']) {
    const t = TRANSLATIONS[lang];

    test(`[${lang}] an upstream failure names the source and offers to open it`, () => {
        const view = describeError(parseApiError(404, upstream404), t, 'https://volvic.livetrail.net/');
        assert.equal(view.code, 'UPSTREAM_NOT_FOUND');
        assert.match(view.title, /LiveTrail/);
        assert.match(view.body, /LiveTrail/);
        assert.doesNotMatch(view.body, /\{source\}/, 'placeholder filled');
        assert.ok(!/Trail Mapper[^.]*(bug|fault)/i.test(view.body));
        assert.equal(view.sourceUrl, 'https://volvic.livetrail.net/');
        assert.deepEqual(view.actions, ['open_source', 'try_another']);
        assert.match(view.openLabel, /LiveTrail/);
    });

    test(`[${lang}] every upstream code has its own wording`, () => {
        const bodies = new Set(['UPSTREAM_NOT_FOUND', 'UPSTREAM_UNAVAILABLE', 'UPSTREAM_TIMEOUT', 'UPSTREAM_FORMAT_CHANGED']
            .map(code => describeError({ code, source: 'utmb' }, t, null).body));
        assert.equal(bodies.size, 4);
        for (const body of bodies) assert.match(body, /UTMB/);
    });

    test(`[${lang}] INVALID_URL helps with the input and shows the server's hint when there is one`, () => {
        const generic = describeError({ code: 'INVALID_URL', message: '' }, t, null);
        assert.deepEqual(generic.actions, ['try_another']);
        assert.match(generic.body, /utmb\.world/);
        const specific = describeError({ code: 'INVALID_URL', message: 'Use the race page on the event site instead.' }, t, null);
        assert.equal(specific.body, 'Use the race page on the event site instead.');
    });

    test(`[${lang}] INTERNAL_ERROR owns up and offers a retry`, () => {
        const view = describeError({ code: 'INTERNAL_ERROR' }, t, 'https://x.org/');
        assert.deepEqual(view.actions, ['retry', 'close']);
        assert.equal(view.sourceUrl, null, 'no "open on source" for our own failure');
        assert.ok(view.body.length > 20);
    });

    test(`[${lang}] an unknown source still gets a label`, () => {
        assert.equal(sourceLabel('example.org', t), 'example.org');
        assert.ok(sourceLabel(null, t).length > 0);
    });
}
