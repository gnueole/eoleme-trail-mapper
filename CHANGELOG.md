# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.1] - 2026-09-12

### Added

- **CI actually runs the tests now.** The README badge had always pointed at
  `.github/workflows/ci.yml`, which did not exist — the only workflow was the
  image build, and it runs no test. Nothing but a developer's laptop had ever
  verified the suite. `ci.yml` runs pytest on Python 3.11 (matching the
  Dockerfile) on pushes to `main` and on pull requests.

### Fixed

- **The scrape fetch bypassed the SSRF guard.** `/api/parse-url` fetched the
  user-supplied URL with a bare `urllib.request.urlopen` while its three
  siblings all used `safe_urlopen`, which is what pins the connection to the
  validated IP and closes the TOCTOU window between the check and the fetch.
- **A UTC offset on the start date was truncated rather than converted**, so
  `…T08:00:00+02:00` produced course points at `08:00Z` instead of `06:00Z`.
  UTMB supplies no offset, so nothing changes for a scraped race today; this
  unblocks the datetime picker on the roadmap.
- **Keyword matching fired mid-word.** `guess_waypoint_symbol` tested plain
  substrings, so "eau" inside *Plateau* and *Château* made them water points —
  *Plateau de la Justice* on the Nice 100K was one — "cade" inside *Cascade*
  made it food, and "mont" inside *Clermont* made it a summit. Keywords are
  stems, not whole words (`ravit` must still catch *ravitaillement*), so they
  are now anchored at the start of a word only, never the end.
- Removed a duplicated `stations`/`rows` block in `/api/parse-url` that ran the
  same `<tr>` regex over the whole page twice.

### Notes

- `TODO.md` claimed all three security items were open; every one had already
  been implemented. Reconciled, with the remaining bare `urlopen` calls
  documented as deliberate — they post to operator-configured endpoints, and
  the telemetry one targets `vector:8080`, which `safe_urlopen` is meant to
  reject.
- The race timezone stays unresolved and is now recorded as blocked rather than
  pending: UTMB publishes none, so course points carry local wall time under a
  `Z` suffix. It is a uniform shift, so the spacing between cutoffs is right and
  only the absolute times are wrong.

---

## [1.5.0] - 2026-09-12

### Fixed

- **Realigned the UTMB scraper with the current race pages.** Event sites
  (`montblanc.utmb.world`, `nice.utmb.world`, …) still ship a `__NEXT_DATA__`
  blob, but its contents moved underneath us:

  - `supplies` gained a `hotFood` level and dropped `complete`. Unrecognised
    levels fell through to name guessing, so every warm-meal aid station —
    Les Chapieux, Courmayeur, Champex-Lac, the Chamonix finish — lost its
    food icon.
  - `hasMedical` is now set on *every* staffed aid station, and it was tested
    first. The whole course came back stamped with red crosses and the
    food/water distinction was gone. Supplies now win; medical labels only the
    points that hand out nothing.
  - `raceLogo` is null on World Series races, which carry their logo on
    `event.siteLogo` / `siteLogoDark`. Those races had no logo at all.
  - The `__NEXT_DATA__` regex demanded an exact attribute order and single
    spaces. Any reshuffle would have silently downgraded a race page to the
    generic table scraper.

- **`live.utmb.world` now fails loudly.** It has moved to the Next.js App
  Router and renders its courses from `utmblive-api.utmb.world`, so its HTML
  contains no aid stations. Fetching one returned `200` with zero stations and
  "UTMB Live" as the race name; it now returns `422` pointing at the event race
  page, which is where the GPX and the aid stations actually live.

- `/api/parse-url` no longer rewraps its own `HTTPException`s into opaque
  `500`s.

### Added

- **Course points are now timed against the real race start.** UTMB's GPX files
  carry no `<time>` element at all, and the frontend never sent `start_date`, so
  `garmin_course_injector.py` always fell back to a hardcoded Friday
  (`2026-07-03 06:00`). Every cutoff was then placed relative to the wrong
  weekday: on Nice — a Saturday start — the first cutoff landed 26 hours late,
  and the whole course carried that error through to the finish.

  `pageHeader.startDateIso` is now surfaced as `metadata.start_date_iso`, kept
  in `state.raceStartDateIso`, and posted with the merge request, which
  `/api/merge` already accepted. `start_date` stays human-readable for the race
  card. A hand-uploaded GPX sends nothing and keeps its own timestamps.

  The per-point `cutoffDatetime` UTMB added alongside it is deliberately *not*
  used: on several World Series races it still carries last edition's year
  (`Sat 02:15 PM` → `2025-09-27T14:15:00` on a 2026 race), whereas the display
  strings are self-consistent and `resolve_cutoff_time` already parses them.

---

## [1.4.3] - 2026-08-28

### Fixed

- **Telemetry never left the container, and now does.** `server.py` read
  `N8N_TRAIL_MAPPER_TELEMETRY_WEBHOOK_URL`, which exists in Doppler but never
  reached this service: `docker-compose.prod.yml` declared no `environment`
  block at all, so every event returned
  `{"status":"skipped","reason":"webhook_not_configured"}` and always had.

  The service now has an environment block, and telemetry posts to
  `http://vector:8080` — Vector ships to the Axiom `eole-telemetry` dataset —
  tagged `application: "trail-mapper"`.

  The old receiving workflow carried the same `$json.body` defect as its two
  siblings and is quarantined.

---

## [1.4.2] - 2026-08-27

### Known

- **Telemetry has never reached n8n.** `server.py:434` reads
  `N8N_TRAIL_MAPPER_TELEMETRY_WEBHOOK_URL`, which exists in Doppler but never
  reaches the container: `docker/docker-compose.prod.yml` declares neither
  `environment:` nor `env_file:`. The code returns
  `{"status":"skipped","reason":"webhook_not_configured"}` and always has.

- **The receiving workflow would fail anyway.** An end-to-end probe showed
  `Trail Mapper - Telemetry to Notion` dying at the Notion node —
  `Event.title[0].text.content should be defined` — because the mapping reads
  `$json.body.*` while its input is the data-table node's output. Nothing was
  written; the workflow fails before that.

### Changed

- **n8n export refreshed** from the live instance, and the stale duplicate
  `n8n/trail-mapper-telemetry.json` superseded by
  `n8n/trail-mapper-telemetry-to-notion.json`.

---

