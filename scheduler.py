"""
scheduler.py -- Merlin's Chronicle scheduled report generation.

Uses the `schedule` library + threading + time. `schedule` runs on LOCAL time;
this box runs on UTC, so local == UTC (assumption noted). The scheduler thread
is started as a daemon from app.py.

  * Daily      21:00 UTC  -> save 'daily'   (00:00 UTC -> now)
  * Sunday     20:00 UTC  -> save 'weekly'  (this week Mon-Sun)
  * Friday     20:00 UTC  -> maybe_save_monthly_report (only last Friday)

Reports are written ONLY inside reports/. This module never touches any
trading system's files.
"""

import os
import time
import threading
import calendar
from datetime import datetime, timezone, timedelta

import schedule

import chronicle

_HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(_HERE, "reports")

_last_report_iso = None


def get_last_report_iso():
    return _last_report_iso


# ---------------------------------------------------------------------------
# period helpers (all UTC)
# ---------------------------------------------------------------------------
def _today_utc():
    return datetime.now(timezone.utc).date()


def _period_for(report_type):
    today = _today_utc()
    if report_type == "daily":
        return today, today
    if report_type == "weekly":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday
    if report_type == "monthly":
        first = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        last = today.replace(day=last_day)
        return first, last
    # custom / fallback -> today
    return today, today


def is_last_friday(d=None):
    d = d or _today_utc()
    if d.weekday() != 4:  # 4 == Friday
        return False
    last_day = calendar.monthrange(d.year, d.month)[1]
    # last Friday: no Friday later in the month
    return (last_day - d.day) < 7


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------
def save_report(report_type):
    """Generate + save a report to reports/<type>_YYYY-MM-DD.html."""
    global _last_report_iso
    date_from, date_to = _period_for(report_type)
    try:
        html = chronicle.generate_report(date_from, date_to, report_type=report_type)
    except Exception as exc:  # never let a bad read kill the scheduler
        print(f"[scheduler] ERROR generating {report_type}: {exc}")
        return None

    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = _today_utc().isoformat()
    filename = f"{report_type}_{stamp}.html"
    path = os.path.join(REPORTS_DIR, filename)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
    except OSError as exc:
        print(f"[scheduler] ERROR writing {filename}: {exc}")
        return None

    _last_report_iso = datetime.now(timezone.utc).isoformat()
    print(f"[scheduler] Saved {report_type} report -> reports/{filename} "
          f"(period {date_from} -> {date_to}) at {_last_report_iso}")
    return filename


def maybe_save_monthly_report():
    if is_last_friday():
        print("[scheduler] Last Friday of month detected -> saving monthly report.")
        return save_report("monthly")
    print("[scheduler] Friday check: not the last Friday -> skipping monthly.")
    return None


# ---------------------------------------------------------------------------
# scheduler loop
# ---------------------------------------------------------------------------
def _run_loop():
    schedule.clear()
    schedule.every().day.at("21:00").do(save_report, "daily")
    schedule.every().sunday.at("20:00").do(save_report, "weekly")
    schedule.every().friday.at("20:00").do(maybe_save_monthly_report)
    print("[scheduler] Started. Daily 21:00 UTC, Weekly Sun 20:00 UTC, "
          "Monthly last-Fri 20:00 UTC. (schedule uses local time == UTC on this box.)")
    while True:
        try:
            schedule.run_pending()
        except Exception as exc:
            print(f"[scheduler] run_pending error: {exc}")
        time.sleep(60)


def start_scheduler():
    """Start the scheduler loop in a daemon thread."""
    t = threading.Thread(target=_run_loop, name="chronicle-scheduler", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    # manual test: generate one of each without saving to disk noise
    for rt in ("daily", "weekly", "monthly"):
        f, t = _period_for(rt)
        print(rt, "->", f, "to", t, "| last_friday?", is_last_friday())
