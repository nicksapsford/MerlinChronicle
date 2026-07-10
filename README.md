# Merlin's Chronicle

**Version 1.0.0 · Port 5011 · Deep Purple #4B0082 · All times UTC · Paper Trading Mode**

Merlin's Chronicle is a standalone, **READ-ONLY** Flask reporting app for the
**Albion Trading Desk**. It reads the logs and trade CSVs of all six trading
systems and produces printable HTML reports.

> **It never writes to any trading system's files.** The only place Merlin's
> Chronicle ever writes is its own `reports/` directory.

## The six systems

| Key    | System        | Asset        | Colour   | Start   |
|--------|---------------|--------------|----------|---------|
| crypto | TideTraderAI  | BTC & ETH    | #00CED1  | £2,000  |
| ftse   | AlbionTraderAI| FTSE 100     | #4169E1  | £1,000  |
| gold   | GoldTraderAI  | Gold XAU     | #FFD700  | £1,000  |
| us     | USTraderAI    | S&P 500      | #FFFFFF  | £1,000  |
| oil    | OilTraderAI   | Brent Crude  | #FF6600  | £1,000  |
| gas    | GasTraderAI   | Natural Gas  | #228B22  | £1,000  |

**Total starting balance: £7,000.00**

## Running

```
pip install -r requirements.txt      # flask, schedule
python app.py                        # or double-click start_chronicle.bat
```

The app binds `0.0.0.0:5011` and starts the report scheduler in a daemon thread.

## Access URLs

- Local:     http://localhost:5011
- LAN:       http://<this-machine-ip>:5011
- Tailscale: http://100.76.0.42:5011

## Routes

| Route | Purpose |
|-------|---------|
| `GET /` | Dashboard: live portfolio, last 3 saved reports, quick buttons, custom picker, scheduled times |
| `GET /report/daily` | Today (00:00 UTC → now) |
| `GET /report/weekly` | This week (Mon–Sun) |
| `GET /report/monthly` | This month |
| `GET /report/custom?from=YYYY-MM-DD&to=YYYY-MM-DD` | Custom range |
| `GET /report/saved/<filename>` | View a saved report (path-traversal guarded) |
| `GET /print/<report_type>` | Print view with auto `window.print()` |
| `POST /generate` | Generate + save a report to `reports/`, returns filename |
| `GET /api/status` | JSON status |

## Scheduled reports (UTC)

- **Daily** — 21:00 UTC → `reports/daily_YYYY-MM-DD.html`
- **Weekly** — Sunday 20:00 UTC → `reports/weekly_YYYY-MM-DD.html`
- **Monthly** — last Friday of the month, 20:00 UTC → `reports/monthly_YYYY-MM-DD.html`

> The `schedule` library uses **local** time. This box runs on UTC, so local ==
> UTC and the times above are correct as-is.

## Printing

Open any report and click the **🖨️ Print** button (top-right, hidden when
printing), or open `/print/<type>` for an auto-print view. Print CSS targets A4
(`@page { size: A4; margin: 1.5cm }`), Arial 10pt, white background, black text,
bordered tables, page-breaks between sections, LOSS rows marked `(L)`, and an
"Albion Trading Desk" footer.

## Report sections

1. Header (title / period / generated UTC / type)
2. Portfolio overview
3. System performance table (+ TOTAL)
4. Lancelot performance (risk gate)
5. Arthur performance (stay-out judge)
6. Trade detail log
7. Phantom decision log (top 10 by |1hr move|)
8. Morgan intelligence (confidence)
9. Guinevere summary (news sentiment)
10. Footer

## Data sources (read-only)

Each system's `logs/` directory is read read-only:

- `*_trades.csv` — realised trades (schemas differ per system; the reader is tolerant)
- `phantom_trades.csv` — uniform stay-out / block decision log
- `*.log` — best-effort scan for Morgan confidence reconstruction

### Known data gaps (at v1.0.0)

- Oil, Gas and Crypto (BTC/ETH) trade CSVs are header-only (0 realised trades).
- No persistent `morgan_*.json` history — confidence is computed fresh each tick,
  so Morgan values default to the **MEDIUM (50)** baseline where no log evidence exists.
- No structured Guinevere sentiment/score history is persisted for Oil/Gas.
- All logged phantom decisions currently carry the generic `ARTHUR_STAY_OUT`
  reason (no distinct `LANCELOT_BLOCK` reasons), so block-reason breakdowns are
  reported as unavailable rather than invented.
