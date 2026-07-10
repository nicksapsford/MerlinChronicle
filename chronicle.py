"""
chronicle.py -- Merlin's Chronicle report generator.

generate_report(date_from, date_to, report_type='custom') -> HTML string.

The report contains all 10 sections in order. CSS is inlined so that a saved
report file is fully self-contained and printable when opened directly.
"""

import os
from datetime import datetime, timezone
from html import escape

import data_reader

_HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.0.0"
NEXT_SCHEDULED = "Daily 21:00 UTC / Weekly Sun 20:00 UTC / Monthly last-Fri 20:00 UTC"


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------
def _gbp(v):
    if v is None:
        return "-"
    sign = "-" if v < 0 else ""
    return f"{sign}£{abs(v):,.2f}"


def _pct(v):
    if v is None:
        return "-"
    return f"{v:.1f}%"


def _num(v, dp=2):
    if v is None:
        return "-"
    return f"{v:,.{dp}f}"


def _cls_pnl(v):
    return "win" if (v is not None and v >= 0) else "loss"


def _load_css():
    path = os.path.join(_HERE, "static", "chronicle.css")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# section builders
# ---------------------------------------------------------------------------
def _sec1_header(agg, report_type, generated):
    p = agg["period"]
    period = f"{p['from'] or 'ALL'} &rarr; {p['to'] or 'ALL'}"
    return f"""
<header class="chronicle-header section">
  <h1>MERLIN'S CHRONICLE</h1>
  <div class="subtitle">Albion Trading Desk &mdash; Reporting</div>
  <table class="meta">
    <tr><td>Period</td><td>{period} (UTC)</td></tr>
    <tr><td>Generated</td><td>{escape(generated)} UTC</td></tr>
    <tr><td>Report Type</td><td>{escape(report_type.upper())}</td></tr>
  </table>
</header>
"""


def _sec2_portfolio(agg):
    t = agg["totals"]
    bd = t["best_day"]
    wd = t["worst_day"]
    best = f"{bd['date']} ({_gbp(bd['pnl'])})" if bd else "n/a"
    worst = f"{wd['date']} ({_gbp(wd['pnl'])})" if wd else "n/a"
    return f"""
<section class="section">
  <h2>1. Portfolio Overview</h2>
  <table class="kv">
    <tr><td>Starting Balance</td><td>{_gbp(t['starting_balance'])}</td></tr>
    <tr><td>Closing Balance (sum of system balances)</td><td>{_gbp(t['closing_balance'])}</td></tr>
    <tr><td>Net P&amp;L</td><td class="{_cls_pnl(t['net_change'])}">{_gbp(t['net_change'])} ({_pct(t['net_change_pct'])})</td></tr>
    <tr><td>Total Trades (period)</td><td>{t['trades']}</td></tr>
    <tr><td>Overall Win Rate (period)</td><td>{_pct(t['win_rate'])}</td></tr>
    <tr><td>Best Day</td><td class="win">{escape(best)}</td></tr>
    <tr><td>Worst Day</td><td class="loss">{escape(worst)}</td></tr>
  </table>
  <p class="note">Note: closing balance is the all-time sum of each system's start balance + realised P&amp;L; period Net P&amp;L above reflects that closing figure vs the &pound;7,000 desk starting balance.</p>
</section>
"""


def _sec3_system_table(agg):
    rows = []
    for key in data_reader.SYSTEMS:
        s = agg["systems"][key]
        rows.append(f"""
    <tr>
      <td><span class="dot" style="background:{s['color']}"></span>{escape(s['display'])} <span class="muted">({escape(s['label'])})</span></td>
      <td>{s['n_trades']}</td>
      <td>{s['wins']}</td>
      <td>{s['losses']}</td>
      <td>{_pct(s['win_rate'])}</td>
      <td class="{_cls_pnl(s['pnl'])}">{_gbp(s['pnl'])}</td>
    </tr>""")
    t = agg["totals"]
    rows.append(f"""
    <tr class="total-row">
      <td>TOTAL</td>
      <td>{t['trades']}</td>
      <td>{t['wins']}</td>
      <td>{t['losses']}</td>
      <td>{_pct(t['win_rate'])}</td>
      <td class="{_cls_pnl(t['total_pnl'])}">{_gbp(t['total_pnl'])}</td>
    </tr>""")
    return f"""
<section class="section">
  <h2>2. System Performance</h2>
  <table class="grid">
    <thead><tr><th>System</th><th>Trades</th><th>Wins</th><th>Losses</th><th>Win Rate</th><th>P&amp;L</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
"""


def _sec4_lancelot(agg):
    t = agg["totals"]
    total = t["phantom_decisions"]
    blocks = t["lancelot_blocks"]
    passed = t["arthur_decisions"]
    bpct = (blocks / total * 100.0) if total else 0.0
    ppct = (passed / total * 100.0) if total else 0.0
    reason_note = ("All phantom decisions in the current data carry the generic "
                   "reason <code>ARTHUR_STAY_OUT</code>; no distinct "
                   "<code>LANCELOT_BLOCK</code> reasons were logged, so a "
                   "block-reason breakdown is not available for this period.")
    return f"""
<section class="section">
  <h2>3. Lancelot Performance (Risk Gate)</h2>
  <table class="kv">
    <tr><td>Total Phantom Decisions</td><td>{total}</td></tr>
    <tr><td>LANCELOT_BLOCK</td><td>{blocks} ({_pct(bpct)})</td></tr>
    <tr><td>Passed to Arthur (ARTHUR_STAY_OUT)</td><td>{passed} ({_pct(ppct)})</td></tr>
  </table>
  <p class="note">{reason_note}</p>
</section>
"""


def _sec5_arthur(agg):
    t = agg["totals"]
    total = t["phantom_decisions"]
    stay = t["arthur_decisions"]
    c, w, n, pend = (t["correct_stay_outs"], t["wrong_stay_outs"],
                     t["neutral_stay_outs"], t["pending_stay_outs"])

    def pc(x):
        return _pct((x / total * 100.0) if total else 0.0)

    saved = t["net_saved"]
    missed = t["net_missed"]
    benefit = t["net_benefit"]
    return f"""
<section class="section">
  <h2>4. Arthur Performance (Stay-Out Judge)</h2>
  <table class="kv">
    <tr><td>Total Decisions</td><td>{total}</td></tr>
    <tr><td>STAY_OUT Calls</td><td>{stay}</td></tr>
    <tr><td>Quality &mdash; CORRECT</td><td class="win">{c} ({pc(c)})</td></tr>
    <tr><td>Quality &mdash; WRONG</td><td class="loss">{w} ({pc(w)})</td></tr>
    <tr><td>Quality &mdash; NEUTRAL</td><td>{n} ({pc(n)})</td></tr>
    <tr><td>Quality &mdash; PENDING</td><td>{pend} ({pc(pend)})</td></tr>
    <tr><td>Net Saved (loss avoided on CORRECT stay-outs)</td><td class="win">+{_gbp(saved).lstrip('-')}</td></tr>
    <tr><td>Net Missed (profit forgone on WRONG stay-outs)</td><td class="loss">-{_gbp(missed).lstrip('-')}</td></tr>
    <tr><td>Net Arthur Benefit (saved &minus; missed)</td><td class="{_cls_pnl(benefit)}">{_gbp(benefit)}</td></tr>
  </table>
  <p class="note">Net figures use the phantom <code>pnl_1hr</code> horizon, expressed in the price units of each blocked market.</p>
</section>
"""


def _sec6_trade_log(agg):
    rows = []
    for tr in agg["all_trades"]:
        rows.append(f"""
    <tr>
      <td>{escape(tr['date'])}</td>
      <td>{escape(tr['time'])}</td>
      <td>{escape(tr['system_display'])}</td>
      <td>{escape(tr['direction'])}</td>
      <td>{_num(tr['entry'])}</td>
      <td>{_num(tr['exit'])}</td>
      <td>{_num(tr['points'], 1)}</td>
      <td class="{_cls_pnl(tr['pnl_gbp'])}">{_gbp(tr['pnl_gbp'])}</td>
      <td class="{_cls_pnl(tr['pnl_gbp'])} result">{tr['result']}</td>
    </tr>""")
    body = "".join(rows) if rows else (
        '<tr><td colspan="9" class="muted">No trades in this period.</td></tr>')
    return f"""
<section class="section">
  <h2>5. Trade Detail Log</h2>
  <table class="grid">
    <thead><tr><th>Date</th><th>Time</th><th>System</th><th>Dir</th><th>Entry</th><th>Exit</th><th>Pts</th><th>P&amp;L</th><th>Result</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>
"""


def _sec7_phantom_log(agg):
    ph = [p for p in agg["all_phantoms"] if p["pnl_1hr"] is not None]
    ph.sort(key=lambda p: abs(p["pnl_1hr"]), reverse=True)
    top = ph[:10]
    rows = []
    for p in top:
        rows.append(f"""
    <tr>
      <td>{escape(p['timestamp'][:19].replace('T',' '))}</td>
      <td>{escape(p['market'])}</td>
      <td>{escape(p['direction_blocked'])}</td>
      <td>{_num(p['price_at_decision'])}</td>
      <td class="{_cls_pnl(p['pnl_1hr'])}">{_num(p['pnl_1hr'])}</td>
      <td class="v-{p['verdict'].lower()}">{escape(p['verdict'])}</td>
    </tr>""")
    body = "".join(rows) if rows else (
        '<tr><td colspan="6" class="muted">No phantom decisions with a 1hr outcome yet.</td></tr>')
    return f"""
<section class="section">
  <h2>6. Phantom Decision Log (Top 10 by |1hr move|)</h2>
  <table class="grid">
    <thead><tr><th>Timestamp (UTC)</th><th>Market</th><th>Blocked Dir</th><th>Price</th><th>P&amp;L 1hr</th><th>Verdict</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
  <p class="note">Biggest misses (WRONG) and biggest saves (CORRECT) surface here by absolute 1-hour move.</p>
</section>
"""


def _sec8_morgan(agg):
    rows = []
    for key in data_reader.SYSTEMS:
        s = agg["systems"][key]
        events = s["morgan"]
        if events:
            start = f"{events[0]['level']} ({events[0]['value']})"
            end = f"{events[-1]['level']} ({events[-1]['value']})"
            src = f"{len(events)} log mentions"
        else:
            start = end = "MEDIUM (50)"
            src = "baseline (no history)"
        note = ""
        if key == "crypto":
            note = "-5 penalty SUSPENDED 10 Jul"
        rows.append(f"""
    <tr>
      <td>{escape(s['display'])}</td>
      <td>{escape(start)}</td>
      <td>{escape(end)}</td>
      <td class="muted">{escape(src)}</td>
      <td class="muted">{escape(note)}</td>
    </tr>""")
    return f"""
<section class="section">
  <h2>7. Morgan Intelligence (Confidence)</h2>
  <table class="grid">
    <thead><tr><th>System</th><th>Start</th><th>End</th><th>Source</th><th>Note</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="note">No persistent morgan_*.json history exists; confidence is computed fresh each tick.
  Values shown are reconstructed best-effort from the main log, defaulting to the MEDIUM (50) baseline where no history is present.</p>
</section>
"""


def _sec9_guinevere(agg):
    # Best-effort: no structured sentiment/score history is logged for Oil/Gas.
    def summarise(key):
        s = agg["systems"][key]
        # We do not have a structured sentiment reader; report the data gap.
        return f"<tr><td>{escape(s['display'])}</td><td class='muted'>no sentiment history logged</td><td class='muted'>-</td></tr>"

    return f"""
<section class="section">
  <h2>8. Guinevere Summary (News Sentiment)</h2>
  <table class="grid">
    <thead><tr><th>System</th><th>Sentiment Days</th><th>Avg Score</th></tr></thead>
    <tbody>
      {summarise('oil')}
      {summarise('gas')}
    </tbody>
  </table>
  <p class="note">No structured Guinevere sentiment/score history is persisted for Oil or Gas
  (news_sentiment / news_score trade columns are empty and no sentiment scores are logged). Reported as a data gap rather than inventing numbers.</p>
</section>
"""


def _sec10_footer(generated):
    return f"""
<footer class="section chronicle-footer">
  <hr/>
  <p>Merlin's Chronicle v{VERSION} &mdash; <strong>Paper Trading Mode</strong> &mdash; All times UTC.</p>
  <p>Next scheduled report: {escape(NEXT_SCHEDULED)}.</p>
  <p class="desk">Albion Trading Desk</p>
</footer>
"""


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def generate_report(date_from, date_to, report_type="custom", inline_css=True,
                    auto_print=False):
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    agg = data_reader.aggregate_all_systems(date_from, date_to)

    css = _load_css() if inline_css else ""
    head_css = f"<style>{css}</style>" if inline_css else \
        '<link rel="stylesheet" href="/static/chronicle.css">'

    print_btn = ('<button class="print-btn no-print" onclick="window.print()">'
                 '&#128424;&#65039; Print</button>')

    autoprint_js = ("<script>window.addEventListener('load',function(){"
                    "setTimeout(function(){window.print();},400);});</script>") \
        if auto_print else ""

    body = "".join([
        _sec1_header(agg, report_type, generated),
        _sec2_portfolio(agg),
        _sec3_system_table(agg),
        _sec4_lancelot(agg),
        _sec5_arthur(agg),
        _sec6_trade_log(agg),
        _sec7_phantom_log(agg),
        _sec8_morgan(agg),
        _sec9_guinevere(agg),
        _sec10_footer(generated),
    ])

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Merlin's Chronicle &mdash; {escape(report_type.title())} Report</title>
{head_css}
</head>
<body class="report-page">
<div class="report-container">
{print_btn}
{body}
</div>
{autoprint_js}
</body>
</html>"""
    return html
