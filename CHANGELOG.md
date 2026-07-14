# Changelog

All notable changes to Merlin's Chronicle are documented here.

## [1.2.2] - 2026-07-14
### Fixed
- Morgan confidence showed "no confidence data" for OilTrader and GasTrader (they
  have not written a morgan_confidence.csv history yet). latest_morgan_confidence()
  now falls back to the persisted morgan_confidence.json, then the 50/MEDIUM
  baseline -- so all 6 systems report a confidence value (Oil/Gas show their 50
  baseline). Added the missing `import json`.

## [1.2.1] - 2026-07-14
### Fixed
- Guinevere Summary (Section 8) now reports real per-fetch sentiment readings and
  average score from guinevere_sentiment.csv (data_reader already computed these;
  the section was stale placeholder text) and now includes GoldTrader alongside
  Oil and Gas.

## [1.2.0] - 2026-07-13
### Added
- Custom lookback report (1-6 day rolling UTC window: 00:00 N days ago -> now), filling the gap below the 7-day weekly report.
- Dashboard "Custom Lookback Report" card: six buttons ("Last 1 day" ... "Last 6 days"). Clicking renders the Chronicle-view report (Format 1, same styling as weekly) inline in an iframe and reveals a "Copy Archie Report" button that copies the Archie plain-text version (Format 2) for the selected period to the clipboard.
- New route `/report/lookback?days=N` (1-6) -> Format 1 HTML.
- `/api/archie` now accepts optional `?days=N` (1-6) -> Format 2 text for that lookback. Default (no param) remains last 7 days, unchanged.
### Changed
- chronicle.VERSION aligned to the VERSION file (1.2.0); the "(last N days)" label in the Archie report is now parameterised.

## [1.1.1] - 2026-07-11
### Added
- Silent launcher (pythonw -- no console windows); output to logs/console.log with daily rotation (7 days kept)
- Launcher now starts the dashboard + watchdog silently (was cmd windows)

## [1.1.0] - 2026-07-11

### Added
- `GET /api/archie` endpoint: a structured, paste-able **plain-text** portfolio
  report (last 7 days) with header, portfolio overview, system performance
  table, Arthur performance, top phantom decisions, Morgan confidence, Guinevere
  sentiment, and an alerts/anomalies section. Guarded so it returns a readable
  error string rather than a 500.
- **[📋 Copy Archie Report]** button on the dashboard: fetches `/api/archie`,
  copies to the clipboard (`navigator.clipboard.writeText` with a
  `document.execCommand('copy')` textarea fallback for non-secure contexts), and
  shows a transient "Copied! Paste to Archie in Claude." confirmation.
- `data_reader.read_morgan_confidence` now reads persisted
  `logs/morgan_confidence.csv` (timestamp, confidence, level, reason) for all
  six systems, plus a `latest_morgan_confidence()` convenience helper.
- `data_reader.read_guinevere_sentiment` reads `logs/guinevere_sentiment.csv`
  (timestamp, sentiment, score, headlines, eia_window) for Oil & Gas.
- `aggregate_all_systems` now exposes, per system: latest Morgan confidence +
  level, a Morgan **confidence journey** (first→last confidence in the period),
  Guinevere **sentiment history** with an average score (None where no news
  module), all wrapped in try/except so a bad CSV never breaks aggregation.

### Notes
- Still READ-ONLY: the app only ever writes inside `reports/`.
- New readers return `[]` gracefully when their CSV is absent/unreadable.

## [1.0.0] - 2026-07-10

### Added
- Initial release of **Merlin's Chronicle** — a standalone, READ-ONLY Flask
  reporting app for the Albion Trading Desk (6 systems).
- `data_reader.py`: tolerant readers for all six systems' differing trade-CSV
  schemas (Gold/US/Oil/Gas USD-style, FTSE GBP-style, Crypto position-size
  style), uniform `phantom_trades.csv` reader, best-effort Morgan confidence
  reconstruction from logs, per-system balances, and `aggregate_all_systems`.
- `chronicle.py`: 10-section printable HTML report generator.
- `app.py`: Flask app on port 5011 with dashboard, daily/weekly/monthly/custom
  reports, saved-report viewer (path-traversal guarded), print view, `/generate`,
  and `/api/status`.
- `scheduler.py`: daily 21:00 UTC, weekly Sunday 20:00 UTC, monthly last-Friday
  20:00 UTC scheduled report saving.
- Deep Purple (#4B0082) theme with screen + A4 print stylesheets.

### Notes
- READ-ONLY: the app only ever writes inside `reports/`. It never modifies any
  trading system's files.
- All times are UTC. Paper Trading Mode.
- Data gaps at release: Oil/Gas/Crypto trade CSVs are header-only (0 trades);
  no persistent Morgan/Guinevere history files exist.
