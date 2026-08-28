# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

