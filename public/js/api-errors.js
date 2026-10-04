// The error contract of /api/parse-url and /api/download-gpx, and what to tell
// the user about it. Pure functions: no DOM, so node:test covers them.
//
// The server answers a failure with
//   { "error": { "code", "source", "source_url", "upstream_status", "message" } }
// plus "detail" for older callers. `code` drives everything here:
//   UPSTREAM_NOT_FOUND, UPSTREAM_UNAVAILABLE, UPSTREAM_TIMEOUT,
//   UPSTREAM_FORMAT_CHANGED  -> the third party's problem, named as such
//   INVALID_URL              -> the user's input
//   INTERNAL_ERROR           -> ours

export const SOURCE_LABELS = {
    livetrail: 'LiveTrail',
    utmb: 'UTMB',
};

/**
 * Builds a normalised error from a failed fetch Response and its parsed body.
 * Anything that is not the contract (an HTML error page, a legacy {detail},
 * a network failure) becomes INTERNAL_ERROR with no source.
 */
export function parseApiError(status, body) {
    const err = body && typeof body === 'object' ? body.error : null;
    if (err && typeof err.code === 'string') {
        return {
            code: err.code,
            source: err.source || null,
            sourceUrl: typeof err.source_url === 'string' ? err.source_url : null,
            upstreamStatus: Number.isInteger(err.upstream_status) ? err.upstream_status : null,
            message: typeof err.message === 'string' ? err.message : '',
            status,
        };
    }
    const legacy = body && typeof body === 'object' && typeof body.detail === 'string' ? body.detail : '';
    return {
        code: status === 400 || status === 422 ? 'INVALID_URL' : 'INTERNAL_ERROR',
        source: null,
        sourceUrl: null,
        upstreamStatus: null,
        message: legacy,
        status,
    };
}

/** The user-facing name of a source id, falling back to the id or a generic word. */
export function sourceLabel(source, t) {
    if (!source) return t.err_source_generic;
    return SOURCE_LABELS[source] || source;
}

/**
 * Turns a normalised error into modal content: title, body, and which actions
 * make sense. `t` is the translation table of the current language.
 * `inputUrl` is what the user typed; it is the address to reopen on the source.
 */
export function describeError(error, t, inputUrl) {
    const code = error && error.code ? error.code : 'INTERNAL_ERROR';
    const label = sourceLabel(error && error.source, t);
    const fill = (s) => String(s || '').replace(/\{source\}/g, label);

    if (code.startsWith('UPSTREAM_')) {
        const bodies = {
            UPSTREAM_NOT_FOUND: t.err_body_upstream_not_found,
            UPSTREAM_UNAVAILABLE: t.err_body_upstream_unavailable,
            UPSTREAM_TIMEOUT: t.err_body_upstream_timeout,
            UPSTREAM_FORMAT_CHANGED: t.err_body_upstream_format,
        };
        return {
            code,
            title: fill(t.err_title_upstream),
            body: fill(bodies[code] || t.err_body_upstream_unavailable),
            hint: t.err_hint_upload,
            sourceUrl: inputUrl || (error && error.sourceUrl) || null,
            actions: ['open_source', 'try_another'],
            openLabel: fill(t.err_open_source),
        };
    }
    if (code === 'INVALID_URL') {
        return {
            code,
            title: t.err_title_invalid,
            body: (error && error.message) || t.err_body_invalid,
            hint: t.err_hint_invalid,
            sourceUrl: null,
            actions: ['try_another'],
        };
    }
    return {
        code: 'INTERNAL_ERROR',
        title: t.err_title_internal,
        body: t.err_body_internal,
        hint: t.err_hint_upload,
        sourceUrl: null,
        actions: ['retry', 'close'],
    };
}
