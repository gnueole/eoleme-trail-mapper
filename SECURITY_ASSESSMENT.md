# Security Assessment Report

This report evaluates the security posture of the **Trail Mapper & Garmin POI Merger** codebase, highlighting implemented controls, potential vulnerability vectors, and recommended mitigations.

---

## 🛡️ Implemented Security Controls

### 1. SSRF Protection (Server-Side Request Forgery)
The backend endpoint `/api/parse-url` and `/api/download-gpx` fetch remote resources from user-supplied URLs (e.g. UTMB websites). To prevent attacks targeting localhost or internal network infrastructure (e.g., AWS Metadata endpoints at `169.254.169.254`), the server implements an IP resolution check:
* **Mechanism**: `is_safe_url(url)` resolves the hostname using `socket.getaddrinfo()` and checks if the resulting IP falls within loopback, private, link-local, multicast, or reserved ranges.
* **Effectiveness**: Highly effective at blocking standard SSRF vectors.

### 2. XML External Entity (XXE) & DoS Protection
GPX and TCX files are XML-based formats, making them targets for XXE injection and XML entity expansion (Billion Laughs / XML Bomb) DoS attacks.
* **Backend**: The server parses and validates GPX payloads using `defusedxml.ElementTree` (`defusedxml.ElementTree.fromstring`), which disables entity resolution and DTD loading entirely.
* **Frontend**: The browser's native `DOMParser` parses GPX files. Modern web browsers disable external entity parsing by default.

### 3. XSS (Cross-Site Scripting) Prevention
The application handles race names, checkpoint names, and distances:
* **Backend**: Text fields scraped from HTML are sanitized of HTML tags using `re.sub(r'<[^>]*>', '', text)`.
* **Frontend**: Dynamic UI tables and forms populate inputs using `input.value = poi.name` or `element.textContent`, which automatically escapes HTML and prevents DOM-based XSS.

---

## ⚠️ Identified Risks & Recommendations

### 1. DNS Rebinding / TOCTOU (Time of Check to Time of Use) Window
> [!WARNING]
> **Risk Level: Medium**
> 
> In `server.py`, the `is_safe_url()` helper resolves the hostname IP address to check if it is safe. If the check passes, `urllib.request.urlopen(url)` is called.
> 
> Because DNS resolution happens twice (once during `is_safe_url` and once when `urlopen` fetches the URL), a malicious DNS server can perform a **DNS Rebinding attack**: returning a safe public IP on the first resolution, and a private IP (e.g., `127.0.0.1`) on the second.

#### Recommendation
Bind the request to the checked IP directly. Instead of letting `urllib` re-resolve the hostname, override the connection pool or make the request directly to the resolved IP, passing the original domain name in the `Host` header:
```python
# Pin the request directly to the checked IP address
req = urllib.request.Request(
    f"https://{resolved_ip}{parsed_url.path}",
    headers={'Host': parsed_url.hostname}
)
```

---

### 2. Lack of File Upload Size Limits in Upload Route
> [!IMPORTANT]
> **Risk Level: Low-Medium**
> 
> While `download_gpx()` limits downloads to 5MB, the `/api/merge` endpoint accepts raw GPX file uploads via `UploadFile` without an explicit size check before loading the file into memory. A very large file upload could exhaust server RAM (Denial of Service).

#### Recommendation
Add an explicit size limit check on the uploaded file stream:
```python
MAX_FILE_SIZE = 5 * 1024 * 1024 # 5MB
gpx_bytes = await gpx_file.read()
if len(gpx_bytes) > MAX_FILE_SIZE:
    raise HTTPException(status_code=400, detail="File size exceeds the 5MB limit.")
```

---

### 3. HTTP Timeout Limitations
> [!NOTE]
> **Risk Level: Low**
> 
> Remote page fetches currently use a `timeout=5` or `timeout=10` limit. If the targeted website acts as a slowloris or delays response chunks, the socket can be kept open. Ensuring explicit chunk size reads and timeouts is recommended to prevent resource starvation.

---

## 📝 Conclusion
The codebase follows solid security engineering practices by adopting `defusedxml` and protecting against SSRF. Addressing the DNS Rebinding window in URL-fetching functions and enforcing upload size boundaries on `/api/merge` will elevate the security posture to production-grade quality.
