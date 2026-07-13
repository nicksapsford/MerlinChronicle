"""
app.py -- Merlin's Chronicle Flask app (READ-ONLY reporting).

Port 5011. This app only ever WRITES inside reports/. It reads the six
trading systems' logs read-only via data_reader. It never modifies any
trading system's files.
"""

import os
import re
from datetime import datetime, timezone, timedelta
import calendar

from flask import (Flask, render_template, request, abort, send_from_directory,
                   jsonify, redirect, url_for, Response)

import chronicle
import data_reader
import scheduler

_HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(_HERE, "reports")

app = Flask(__name__, template_folder="templates", static_folder="static")

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.html$")
_VALID_TYPES = ("daily", "weekly", "monthly", "custom")


# ---------------------------------------------------------------------------
# period helpers (UTC)
# ---------------------------------------------------------------------------
def _now():
    return datetime.now(timezone.utc)


def _clamp_days(raw, default=7, lo=1, hi=6):
    """Parse a ?days= value -> int in [lo, hi], else `default`.
    Used by the custom lookback report (1-6) and /api/archie (default 7).
    'Last N days' is a rolling UTC window: 00:00 N days ago -> now."""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return n if lo <= n <= hi else default


def _period(report_type, frm=None, to=None):
    today = _now().date()
    if report_type == "daily":
        return today, today
    if report_type == "weekly":
        monday = today - timedelta(days=today.weekday())
        return monday, monday + timedelta(days=6)
    if report_type == "monthly":
        first = today.replace(day=1)
        last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        return first, last
    # custom
    return (frm or today.isoformat()), (to or today.isoformat())


def _list_saved():
    try:
        files = [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")]
    except OSError:
        files = []
    files.sort(key=lambda f: os.path.getmtime(os.path.join(REPORTS_DIR, f)),
               reverse=True)
    return files


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    agg = data_reader.aggregate_all_systems()  # all-time live summary
    saved = _list_saved()[:3]
    scheduled = [
        "Daily report: 21:00 UTC",
        "Weekly report: Sunday 20:00 UTC",
        "Monthly report: last Friday 20:00 UTC",
    ]
    return render_template(
        "dashboard.html",
        agg=agg,
        systems=data_reader.SYSTEMS,
        saved=saved,
        scheduled=scheduled,
        last_report=scheduler.get_last_report_iso(),
        now=_now().strftime("%Y-%m-%d %H:%M:%S"),
        version=chronicle.VERSION,
    )


def _render_report(report_type, frm=None, to=None, auto_print=False):
    date_from, date_to = _period(report_type, frm, to)
    html = chronicle.generate_report(date_from, date_to,
                                     report_type=report_type,
                                     auto_print=auto_print)
    return Response(html, mimetype="text/html")


@app.route("/report/daily")
def report_daily():
    return _render_report("daily")


@app.route("/report/weekly")
def report_weekly():
    return _render_report("weekly")


@app.route("/report/monthly")
def report_monthly():
    return _render_report("monthly")


@app.route("/report/custom")
def report_custom():
    frm = request.args.get("from")
    to = request.args.get("to")
    return _render_report("custom", frm, to)


@app.route("/report/lookback")
def report_lookback():
    """Custom rolling-window report (Format 1 -- same styling as the weekly
    report) for a 1-6 day lookback. Window is UTC: 00:00 N days ago -> now,
    mirroring /api/archie?days=N so both formats cover the identical period."""
    days = _clamp_days(request.args.get("days"), default=6)
    now = _now()
    date_from = (now - timedelta(days=days)).date()
    date_to = now.date()
    label = "Last {} day{}".format(days, "" if days == 1 else "s")
    html = chronicle.generate_report(date_from, date_to, report_type=label,
                                     auto_print=(request.args.get("print") == "1"))
    return Response(html, mimetype="text/html")


@app.route("/print/<report_type>")
def print_report(report_type):
    if report_type not in _VALID_TYPES:
        abort(404)
    frm = request.args.get("from")
    to = request.args.get("to")
    return _render_report(report_type, frm, to, auto_print=True)


@app.route("/report/saved/<path:filename>")
def report_saved(filename):
    # path-traversal guard: only a bare safe filename, only from reports/
    if not _SAFE_NAME.match(filename):
        abort(404)
    full = os.path.abspath(os.path.join(REPORTS_DIR, filename))
    if os.path.commonpath([os.path.abspath(REPORTS_DIR), full]) != os.path.abspath(REPORTS_DIR):
        abort(404)
    if not os.path.exists(full):
        abort(404)
    return send_from_directory(REPORTS_DIR, filename)


@app.route("/generate", methods=["POST"])
def generate():
    report_type = request.values.get("type", "custom")
    frm = request.values.get("from")
    to = request.values.get("to")
    if report_type not in _VALID_TYPES:
        report_type = "custom"
    date_from, date_to = _period(report_type, frm, to)
    html = chronicle.generate_report(date_from, date_to, report_type=report_type)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = _now().date().isoformat()
    filename = f"{report_type}_{stamp}.html"
    with open(os.path.join(REPORTS_DIR, filename), "w", encoding="utf-8") as fh:
        fh.write(html)
    return jsonify({"status": "ok", "filename": filename,
                    "url": url_for("report_saved", filename=filename)})


# ---------------------------------------------------------------------------
# Archie report (plain-text, paste-able into Claude)
# ---------------------------------------------------------------------------
def _money(v):
    try:
        return "{:,.2f}".format(float(v))
    except (TypeError, ValueError):
        return "0.00"


def _signed(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = 0.0
    return ("-" if f < 0 else "+") + "{:,.2f}".format(abs(f))


def _build_archie_report(agg, now, date_from, date_to, days=7):
    """Build the structured plain-text Archie report from the aggregate.

    Every value is mapped to what aggregate_all_systems() actually returns;
    derived values (net Arthur benefit, closing balance, etc.) are taken from
    the ``totals`` block, which already computes them.
    """
    t = agg.get("totals", {})
    systems = agg.get("systems", {})
    order = list(data_reader.SYSTEMS.keys())

    out = []
    w = out.append

    # --- header -------------------------------------------------------------
    w("=" * 64)
    w("MERLIN'S CHRONICLE  --  ARCHIE REPORT")
    w("Albion Trading Desk (6 systems)  --  Paper Trading Mode")
    w("Generated: {} UTC".format(now.strftime("%Y-%m-%d %H:%M:%S")))
    w("Period:    {}  ->  {}   (last {} day{})".format(
        date_from.isoformat(), date_to.isoformat(), days, "" if days == 1 else "s"))
    w("=" * 64)
    w("")

    # --- portfolio overview -------------------------------------------------
    w("PORTFOLIO OVERVIEW")
    w("-" * 64)
    w("Starting balance : GBP {}".format(_money(t.get("starting_balance", 0))))
    w("Current balance  : GBP {}".format(_money(t.get("closing_balance", 0))))
    w("Net P&L          : GBP {} ({:.1f}%)".format(
        _signed(t.get("net_change", 0)), t.get("net_change_pct", 0.0)))
    w("Trades (period)  : {}  (wins {} / losses {})".format(
        t.get("trades", 0), t.get("wins", 0), t.get("losses", 0)))
    w("Win rate         : {:.1f}%".format(t.get("win_rate", 0.0)))
    bd, wd = t.get("best_day"), t.get("worst_day")
    w("Best day         : {}".format(
        "{}  GBP {}".format(bd["date"], _signed(bd["pnl"])) if bd else "n/a"))
    w("Worst day        : {}".format(
        "{}  GBP {}".format(wd["date"], _signed(wd["pnl"])) if wd else "n/a"))
    w("")

    # --- system performance -------------------------------------------------
    w("SYSTEM PERFORMANCE")
    w("-" * 64)
    w("{:<13}{:>7}{:>6}{:>8}{:>14}".format(
        "System", "Trades", "Wins", "WR%", "P&L(GBP)"))
    for key in order:
        s = systems.get(key, {})
        w("{:<13}{:>7}{:>6}{:>7.1f}%{:>14}".format(
            s.get("display", key), s.get("n_trades", 0), s.get("wins", 0),
            s.get("win_rate", 0.0), _signed(s.get("pnl", 0.0))))
    w("")

    # --- Arthur performance -------------------------------------------------
    w("ARTHUR PERFORMANCE (stay-out judge)")
    w("-" * 64)
    w("Phantom decisions : {}".format(t.get("phantom_decisions", 0)))
    w("  CORRECT (loss avoided)  : {}".format(t.get("correct_stay_outs", 0)))
    w("  WRONG   (profit missed) : {}".format(t.get("wrong_stay_outs", 0)))
    w("  NEUTRAL                 : {}".format(t.get("neutral_stay_outs", 0)))
    w("  PENDING                 : {}".format(t.get("pending_stay_outs", 0)))
    w("Net saved  (loss avoided)   : GBP {}".format(_money(t.get("net_saved", 0))))
    w("Net missed (profit missed)  : GBP {}".format(_money(t.get("net_missed", 0))))
    # net Arthur benefit = net_saved - net_missed (totals already provides it)
    net_benefit = t.get("net_benefit",
                        t.get("net_saved", 0.0) - t.get("net_missed", 0.0))
    w("Net Arthur benefit          : GBP {}".format(_signed(net_benefit)))
    w("")

    # --- top phantom decisions ---------------------------------------------
    w("TOP PHANTOM DECISIONS (top 5 by |1hr move|)")
    w("-" * 64)
    phantoms = [p for p in agg.get("all_phantoms", [])
                if p.get("pnl_1hr") is not None]
    phantoms.sort(key=lambda p: abs(p["pnl_1hr"]), reverse=True)
    if phantoms:
        for p in phantoms[:5]:
            disp = systems.get(p.get("system"), {}).get("display", p.get("system", ""))
            w("  {:<12} {:<6} {:<5} 1hr GBP {:>9}  [{}]  {}".format(
                disp, p.get("market", ""), p.get("direction_blocked", ""),
                _signed(p["pnl_1hr"]), p.get("verdict", ""),
                (p.get("timestamp", "") or "")[:16]))
    else:
        w("  (no phantom decisions with a 1hr outcome in this period)")
    w("")

    # --- Morgan confidence --------------------------------------------------
    w("MORGAN CONFIDENCE (latest per system)")
    w("-" * 64)
    for key in order:
        s = systems.get(key, {})
        c = s.get("morgan_latest_confidence")
        if c is None:
            w("  {:<13} no confidence data".format(s.get("display", key)))
        else:
            lvl = s.get("morgan_latest_level") or "-"
            j = s.get("morgan_confidence_journey")
            jtxt = "  journey {:.0f}->{:.0f}".format(j["first"], j["last"]) if j else ""
            w("  {:<13} {:.0f} ({}){}".format(s.get("display", key), c, lvl, jtxt))
    w("")

    # --- Guinevere sentiment ------------------------------------------------
    w("GUINEVERE SENTIMENT (avg score, this period)")
    w("-" * 64)
    for key in order:
        s = systems.get(key, {})
        avg = s.get("guinevere_avg_score")
        if avg is None:
            w("  {:<13} no news module".format(s.get("display", key)))
        else:
            w("  {:<13} avg {:.1f}  ({} readings)".format(
                s.get("display", key), avg, s.get("guinevere_days", 0)))
    w("")

    # --- alerts & anomalies -------------------------------------------------
    w("ALERTS & ANOMALIES")
    w("-" * 64)
    alerts = []
    for key in order:
        s = systems.get(key, {})
        if s.get("n_trades", 0) > 0 and s.get("win_rate", 0.0) == 0.0:
            alerts.append("[!] {}: 0% win rate over {} trade(s)".format(
                s.get("display", key), s.get("n_trades", 0)))
    if net_benefit < -100:
        alerts.append("[!] Net Arthur benefit GBP {} (< -100): Arthur is "
                      "costing more than it saves".format(_signed(net_benefit)))
    for key in order:
        s = systems.get(key, {})
        c = s.get("morgan_latest_confidence")
        if c is not None and c < 40:
            alerts.append("[!] {}: Morgan confidence {:.0f} (<40) -- "
                          "Morgan-spiral risk".format(s.get("display", key), c))
    if alerts:
        for a in alerts:
            w(a)
    else:
        w("[OK] No alerts")
    w("")
    w("=" * 64)
    w("End of Archie report  --  paste this into Claude for Archie.")

    return "\n".join(out) + "\n"


@app.route("/api/archie")
def api_archie():
    try:
        now = _now()
        # Optional ?days=N (1-6) for a custom lookback; default 7 (unchanged).
        days = _clamp_days(request.args.get("days"), default=7)
        date_from = (now - timedelta(days=days)).date()
        date_to = now.date()
        agg = data_reader.aggregate_all_systems(date_from=date_from, date_to=date_to)
        text = _build_archie_report(agg, now, date_from, date_to, days=days)
        return Response(text, content_type="text/plain; charset=utf-8")
    except Exception as exc:  # never 500 -- return a readable error string
        import traceback
        body = ("Archie report generation failed.\n"
                "Error: {!r}\n\n{}".format(exc, traceback.format_exc()))
        return Response(body, content_type="text/plain; charset=utf-8")


@app.route("/api/status")
def api_status():
    try:
        count = len([f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")])
    except OSError:
        count = 0
    return jsonify({
        "status": "ok",
        "name": "Merlin's Chronicle",
        "port": 5011,
        "last_report": scheduler.get_last_report_iso(),
        "reports_generated": count,
    })


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(REPORTS_DIR, exist_ok=True)
    scheduler.start_scheduler()
    print("Merlin's Chronicle running on http://0.0.0.0:5011 (READ-ONLY reporting)")
    app.run(host="0.0.0.0", port=5011, debug=False, use_reloader=False)
