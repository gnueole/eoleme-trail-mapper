# 🏔️ Trail Mapper - Development Roadmap & TODOs

**Author: Julien (Éole) Avarre**
**Last Update: 2026-07-06**

This document maintains the active task list, security mitigations, and feature enhancements planned for **Trail Mapper & Garmin POI Merger**.

---

## 🔒 Security Enhancements
Tasks identified during the **Security Assessment**
- [ ] **Mitigate DNS Rebinding (SSRF)**:
  - Modify `server.py` to bind HTTP requests in `urlopen` directly to the resolved IP address validated in `is_safe_url()`. Pass the original domain name in the `Host` header to prevent TOCTOU exploitation.
- [ ] **Enforce Upload Limits on Merge Endpoint**:
  - Add an explicit file size check (e.g. 5MB) on the `UploadFile` stream in `/api/merge` to prevent memory exhaustion from massive file uploads.
- [ ] **HTTP Requests Timeout**:
  - Enforce strict socket-level read timeouts on all proxy fetches to prevent backend resource leaks from slow HTTP responses.

---

## 🚀 Upcoming Features & Enhancements

### 1. Strava Integration
- [ ] Add support for importing routes directly from Strava routes/activities via the Strava API.

### 2. Timezone and Race Start Calibration
- [ ] Add a UI datetime picker to allow custom start date/time adjustments for the race track.
- [ ] Automatically extract the race start timezone from the UTMB scrape properties and apply it during GPX timestamp interpolation.

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
