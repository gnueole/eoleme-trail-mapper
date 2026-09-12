# 🏔️ Trail Mapper - Development Roadmap & TODOs

**Author: Julien (Éole) Avarre**
**Last Update: 2026-07-06**

This document maintains the active task list, security mitigations, and feature enhancements planned for **Trail Mapper & Garmin POI Merger**.

---

## 🔒 Security Enhancements
Tasks identified during the **Security Assessment**
- [x] **Mitigate DNS Rebinding (SSRF)**:
  - `utils/security.py::safe_urlopen` resolves the host, rejects private/reserved
    addresses and pins the connection to the validated IP. Every fetch of a
    *user-supplied* URL now goes through it — the scrape fetch in
    `/api/parse-url` was the last holdout.
  - The two remaining bare `urlopen` calls (the n8n parser webhook and the
    telemetry post) target operator-configured endpoints, and the telemetry one
    is the internal `vector:8080`, which `safe_urlopen` is *supposed* to reject.
    They stay raw on purpose.
- [x] **Enforce Upload Limits on Merge Endpoint**:
  - `/api/merge` rejects payloads over 5MB; covered by
    `test_merge_endpoint_size_limit`.
- [x] **HTTP Requests Timeout**:
  - Every proxy fetch passes an explicit `timeout=` (2s telemetry, 5s scrape and
    GPX, 10s LiveTrail and n8n).

---

## 🚀 Upcoming Features & Enhancements

### 1. Strava Integration
- [ ] Add support for importing routes directly from Strava routes/activities via the Strava API.

### 2. Timezone and Race Start Calibration
- [x] Anchor the course points to the real race start. `pageHeader.startDateIso`
  now reaches `/api/merge`; before this the injector fell back to a hardcoded
  Friday and every cutoff on a non-Friday race landed a day out.
- [x] Honour a UTC offset when the start date carries one — it used to be
  truncated, so `…T08:00:00+02:00` was written as `08:00Z`.
- [ ] Add a UI datetime picker to allow custom start date/time adjustments for the race track.
- [ ] **Blocked — UTMB publishes no timezone.** Every ISO string in
  `__NEXT_DATA__` is naive local wall time; the props carry only
  `event.region` ("Europe") and `event.lat`/`event.lng`. Course points are
  therefore written with local wall time under a `Z` suffix, a *uniform* shift
  (2h for Chamonix and Nice in summer) that leaves the spacing between cutoffs
  correct but the absolute times wrong. Closing this needs either a
  coordinates→IANA-zone dependency such as `timezonefinder` (~50MB of polygon
  data in the image, for a display-only error) or the datetime picker above
  supplying the offset by hand. Worth deciding which before either is built.

### 3. Checkpoints Table Improvements
- [ ] Add multi-select checkboxes for batch actions (e.g., toggle active state, delete multiple).
- [ ] Allow importing checkpoints from custom CSV templates (in addition to pasted HTML and text).

### 4. Interactive Mapping & Charting
- [ ] Add a "Zoom to Fit" button overlay to the Leaflet map card to quickly center the route track.
- [ ] Add elevation gradient colors to the polyline track based on slope percentage.

---

## 📂 Reference Links
* To understand the system layout, refer to the **[Architecture Overview](architecture.md)**.
* To set up the development environment, see the **[README.md](README.md#💻-local-development)**.
