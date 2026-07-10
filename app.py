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
