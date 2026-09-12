# Security Assessment Report

This report evaluates the security posture of the **Trail Mapper & Garmin POI Merger** codebase, highlighting implemented controls, potential vulnerability vectors, and recommended mitigations.

---

## 🛡️ Implemented Security Controls

### 1. SSRF Protection (Server-Side Request Forgery)
The backend endpoints `/api/parse-url` and `/api/download-gpx` fetch remote resources from user-supplied URLs (e.g. UTMB websites). To prevent attacks targeting localhost or internal network infrastructure (e.g., AWS Metadata endpoints at `169.254.169.254`), fetching is guarded in two layers:

* **Pre-check** — `is_safe_url(url)` resolves the hostname using the *original* `socket.getaddrinfo()` and rejects loopback, private, link-local, multicast, reserved and unspecified ranges, along with any non-`http(s)` scheme.
* **Pinned fetch** — `safe_urlopen()` re-resolves, re-validates, then performs the request inside a `pinned_dns()` context that forces the connection to the exact IP that was just checked. This closes the TOCTOU window between the check and the fetch (see *Resolved* below).
* **Coverage** — every fetch of a user-supplied URL goes through `safe_urlopen`: the GPX download, the LiveTrail `parcours.php` and `gmData` fetches, and the page scrape in `/api/parse-url`.

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

### 4. Payload Size Limits
* `/api/download-gpx` rejects a declared `Content-Length` over 5MB up front and aborts mid-transfer if the running total exceeds it, so a server lying about its length cannot stream unbounded data.
* `/api/merge` rejects uploads over 5MB (`MAX_FILE_SIZE`, `server.py`), covered by `test_merge_endpoint_size_limit`.

---

## ⚠️ Residual Risks

### 1. Slow-Read / Slowloris Socket Retention
> [!NOTE]
> **Risk Level: Low**
>
> Every proxy fetch passes an explicit `timeout=` (2s telemetry, 5s scrape and GPX, 10s LiveTrail and n8n), but `urllib`'s timeout applies to each individual socket operation, not to the transfer as a whole. A hostile server that drips bytes just inside the timeout can hold a worker for far longer than the nominal limit. `/api/download-gpx` bounds total *bytes* but not total *time*.

#### Recommendation
Enforce a wall-clock deadline across the whole read loop, not just a per-recv timeout.

---

### 2. Trusted-Domain Resolution Bypass
> [!WARNING]
> **Risk Level: Low**
>
> Both `is_safe_url` and `safe_urlopen` short-circuit for a trusted suffix list (`.utmb.world`, `google.com`, `github.com`), returning early **without resolving or pinning**. This exists so the container works in offline or DNS-restricted development environments, but it means those hosts get no SSRF protection at all. A subdomain takeover or DNS hijack under `utmb.world` would bypass the guard entirely.

#### Recommendation
Gate the bypass behind an explicit development flag rather than applying it in production, or keep the allow-list but still pin the resolved IP.

---

### 3. Upload Limit Applies After the Body Is Read
> [!NOTE]
> **Risk Level: Low**
>
> `/api/merge` checks the size *after* `await gpx_file.read()`, so an oversized upload is still fully received before being rejected. Starlette spools large uploads to a temporary file rather than holding them in RAM, which blunts the memory impact, but the limit caps what reaches the XML parser rather than what reaches the process.

#### Recommendation
Reject on `Content-Length` before reading, or read the stream in bounded chunks and abort once the cap is passed — the pattern `/api/download-gpx` already uses.

---

## ✅ Resolved

| Previously flagged | Status | Where |
| --- | --- | --- |
| DNS Rebinding / TOCTOU window (Medium) | **Mitigated** | `safe_urlopen` + `pinned_dns` in `utils/security.py`; the last unguarded call site, the page scrape in `/api/parse-url`, was migrated in 1.5.1 |
| No upload size limit on `/api/merge` (Low-Medium) | **Resolved** | `MAX_FILE_SIZE` in `server.py`, with `test_merge_endpoint_size_limit` — see residual risk 3 for the remaining nuance |

---

## 📝 Conclusion
The codebase follows solid security engineering practices: `defusedxml` for untrusted XML, a two-layer SSRF guard that both validates and pins the resolved address, and size caps on every payload path. The DNS rebinding window and the missing upload limit that earlier revisions of this report flagged as open have both been closed. What remains is a short tail of low-severity hardening: a wall-clock deadline on slow reads, the development-time trusted-domain bypass, and moving the merge size check ahead of the read.
