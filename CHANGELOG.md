# Changelog

All notable changes to Merlin's Chronicle are documented here.

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
