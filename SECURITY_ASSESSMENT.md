# Security Assessment Report

This report evaluates the security posture of the **Trail Mapper & Garmin POI Merger** codebase, highlighting implemented controls, potential vulnerability vectors, and recommended mitigations.

---

## 🛡️ Implemented Security Controls

### 1. SSRF Protection (Server-Side Request Forgery)
The backend endpoints `/api/parse-url` and `/api/download-gpx` fetch remote resources from user-supplied URLs (e.g. UTMB websites). To prevent attacks targeting localhost or internal network infrastructure (e.g., AWS Metadata endpoints at `169.254.169.254`), fetching is guarded in two layers:

* **Pre-check** — `is_safe_url(url)` resolves the hostname using the *original* `socket.getaddrinfo()` and rejects loopback, private, link-local, multicast, reserved and unspecified ranges, along with any non-`http(s)` scheme.
* **Pinned fetch** — `safe_urlopen()` re-resolves, re-validates, then performs the request inside a `pinned_dns()` context that forces the connection to the exact IP that was just checked. This closes the TOCTOU window between the check and the fetch (see *Resolved* below).
* **Coverage** — every fetch of a user-supplied URL goes through `safe_urlopen`: the GPX download, the LiveTrail `parcours.php` and `gmData` fetches, and the page scrape in `/api/parse-url`.
* **Allow-list is a fallback, not a bypass** — `TRUSTED_DOMAINS` (`utmb.world`, `google.com`, `github.com`) applies *only* when name resolution itself fails, which is what an offline or DNS-restricted development container looks like. A trusted name that resolves is still resolved, IP-checked and pinned like any other, so it cannot be used to skip validation. Matching is by domain or subdomain via `is_trusted_domain`, never a bare string suffix.

> [!NOTE]
> Two bare `urllib.request.urlopen` calls remain on purpose: the n8n parser webhook and the telemetry post. Both target operator-configured endpoints rather than user input, and the telemetry endpoint is the internal `vector:8080`, which `safe_urlopen` is *designed* to reject.

### 2. XML External Entity (XXE) & DoS Protection
GPX and TCX files are XML-based formats, making them targets for XXE injection and XML entity expansion (Billion Laughs / XML Bomb) DoS attacks.
* **Backend**: The server parses and validates GPX payloads using `defusedxml.ElementTree` (`defusedxml.ElementTree.fromstring`), which disables entity resolution and DTD loading entirely.
* **Frontend**: The browser's native `DOMParser` parses GPX files. Modern web browsers disable external entity parsing by default.

### 3. XSS (Cross-Site Scripting) Prevention
The application handles race names, checkpoint names, and distances:
* **Backend**: Text fields scraped from HTML are sanitized of HTML tags using `re.sub(r'<[^>]*>', '', text)`.
* **Frontend**: Dynamic UI tables and forms populate inputs using `input.value = poi.name` or `element.textContent`, which automatically escapes HTML and prevents DOM-based XSS.

### 4. Payload and Transfer Limits
* `/api/download-gpx` rejects a declared `Content-Length` over 5MB up front and aborts mid-transfer if the running total exceeds it, so a server lying about its length cannot stream unbounded data.
* `/api/merge` reads the upload in 1MB chunks and aborts as soon as the 5MB cap is passed, so the limit bounds what the process accepts rather than only what reaches the XML parser. Covered by `test_merge_endpoint_size_limit`.
* **Wall-clock transfer ceiling** — `urllib`'s `timeout=` applies to each socket operation, not the transfer as a whole, so a server dripping bytes just inside it could hold a worker indefinitely. `MAX_TRANSFER_SECONDS` bounds the entire `/api/download-gpx` read loop and returns `504` when exceeded.

---

## ⚠️ Residual Risks

### 1. No Request-Level Body Cap Ahead of the Application
> [!NOTE]
> **Risk Level: Low**
>
> `/api/merge` now reads the upload in 1MB chunks and aborts once the 5MB cap is
> passed, so an oversized body is no longer buffered in full before rejection.
> The bytes still traverse Traefik and the ASGI server before the handler sees
> them, though — there is no proxy-level `maxRequestBodyBytes` in front.

#### Recommendation
Set a body limit on the Traefik router if upload abuse ever becomes a concern.

---

## ✅ Resolved

| Previously flagged | Status | Where |
| --- | --- | --- |
| DNS Rebinding / TOCTOU window (Medium) | **Mitigated** | `safe_urlopen` + `pinned_dns` in `utils/security.py`; the last unguarded call site, the page scrape in `/api/parse-url`, was migrated in 1.5.1 |
| No upload size limit on `/api/merge` (Low-Medium) | **Resolved** | `MAX_FILE_SIZE` in `server.py`, enforced during a chunked read so the cap bounds what the process accepts, not just what the parser sees |
| Slow-read / slowloris socket retention (Low) | **Mitigated** | `MAX_TRANSFER_SECONDS` puts a wall-clock ceiling on the whole `/api/download-gpx` transfer, on top of the per-read socket timeout |
| Trusted-domain resolution bypass (Low) | **Mitigated** | The allow-list no longer short-circuits validation. Every host is resolved and IP-checked; `TRUSTED_DOMAINS` applies only when resolution itself fails |
| Allow-list matched bare string suffixes (Medium) | **Fixed** | `is_trusted_domain` matches a domain or subdomain, so `evilgoogle.com` no longer satisfies `endswith("google.com")` |

---

## 📝 Conclusion
The codebase follows solid security engineering practices: `defusedxml` for untrusted XML, a two-layer SSRF guard that both validates and pins the resolved address, and size and time caps on every payload path.

Every risk earlier revisions of this report flagged as open has now been closed, along with two the report never named: the allow-list matched bare string suffixes, so `evilgoogle.com` satisfied `endswith("google.com")` and inherited full trust; and that trust skipped resolution entirely, meaning the application's own primary traffic — `*.utmb.world` — had no SSRF protection at all. Both are fixed, and the allow-list is now reachable only when DNS is unavailable.

What remains is one low-severity item: there is no proxy-level body cap in front of the application, so oversized uploads still traverse Traefik and the ASGI server before the handler rejects them.
