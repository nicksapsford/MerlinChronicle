"""
data_reader.py -- Merlin's Chronicle

READ-ONLY access to the six Albion Trading Desk systems' logs/CSVs.
This module NEVER writes to any trading system's files. It only ever opens
files that live inside one of the six systems' `logs/` directories, and it
only opens them for reading. All parsing is wrapped in try/except so that a
missing, empty, header-only, or locked file yields empty results rather than
a crash.

All times are treated as UTC.
"""

import os
import csv
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
# This file lives in  <Desktop>/MerlinChronicle/data_reader.py
# The trading systems live in  <Desktop>/<SystemDir>/logs/
_HERE = os.path.dirname(os.path.abspath(__file__))
_DESKTOP = os.path.dirname(_HERE)


# ---------------------------------------------------------------------------
# SYSTEMS registry -- EXACTLY as specified
# ---------------------------------------------------------------------------
# Order matters (used for table rendering).
SYSTEMS = {
    "crypto": {
        "dir": "TideTraderAI",
        "color": "#00CED1",
        "label": "BTC & ETH",
        "asset": "BTC & ETH",
        "start_balance": 2000.00,
        "trade_files": ["trades.csv", "eth_trades.csv"],
        "display": "CryptoTrader",
    },
    "ftse": {
        "dir": "AlbionTraderAI",
        "color": "#4169E1",
        "label": "FTSE 100",
        "asset": "FTSE 100",
        "start_balance": 1000.00,
        "trade_files": ["ftse_trades.csv"],
        "display": "FTSETrader",
    },
    "gold": {
        "dir": "GoldTraderAI",
        "color": "#FFD700",
        "label": "Gold XAU",
        "asset": "Gold XAU",
        "start_balance": 1000.00,
        "trade_files": ["gold_trades.csv"],
        "display": "GoldTrader",
    },
    "us": {
        "dir": "USTraderAI",
        "color": "#FFFFFF",
        "label": "S&P 500",
        "asset": "S&P 500",
        "start_balance": 1000.00,
        "trade_files": ["us_trades.csv"],
        "display": "USTrader",
    },
    "oil": {
        "dir": "OilTraderAI",
        "color": "#FF6600",
        "label": "Brent Crude",
        "asset": "Brent Crude",
        "start_balance": 1000.00,
        "trade_files": ["oil_trades.csv"],
        "display": "OilTrader",
    },
    "gas": {
        "dir": "GasTraderAI",
        "color": "#228B22",
        "label": "Natural Gas",
        "asset": "Natural Gas",
        "start_balance": 1000.00,
        "trade_files": ["gas_trades.csv"],
        "display": "GasTrader",
    },
}

TOTAL_STARTING_BALANCE = 7000.00


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _logs_dir(system_key):
    sys = SYSTEMS[system_key]
    return os.path.join(_DESKTOP, sys["dir"], "logs")


def _safe_path(system_key, filename):
    """Return an absolute path INSIDE the system's logs dir, or None if the
    resolved path would escape that directory (path-traversal guard)."""
    base = os.path.abspath(_logs_dir(system_key))
    target = os.path.abspath(os.path.join(base, filename))
    if os.path.commonpath([base, target]) != base:
        return None
    return target


def _to_date(value):
    """Coerce a str / date / datetime / None into a date (or None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Handle 'YYYY-MM-DD', ISO timestamps, 'YYYY-MM-DD HH:MM:SS'
    s = s.replace("T", " ")
    s = s.split("+")[0].split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[: len(fmt) + 8] if False else s, fmt).date()
        except ValueError:
            continue
    # last resort: first 10 chars
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _in_range(d, date_from, date_to):
    """Inclusive UTC date-range check. date_from/date_to may be None."""
    if d is None:
        return False
    lo = _to_date(date_from)
    hi = _to_date(date_to)
    if lo is not None and d < lo:
        return False
    if hi is not None and d > hi:
        return False
    return True


def _fnum(row, *keys, default=None):
    """Fetch the first present, non-empty numeric field from row by keys."""
    for k in keys:
        if k in row and row[k] not in (None, ""):
            v = str(row[k]).strip().replace("+", "")
            if v in ("", "-", "nan", "None"):
                continue
            try:
                return float(v)
            except ValueError:
                continue
    return default


def _fstr(row, *keys, default=""):
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return str(row[k]).strip()
    return default


# ---------------------------------------------------------------------------
# read_trades
# ---------------------------------------------------------------------------
def read_trades(system_key, date_from=None, date_to=None):
    """Read all trades for a system, tolerant of the differing CSV schemas.

    Returns a list of normalised trade dicts sorted by (date, time). A missing
    / empty / header-only file yields no rows for that file (graceful).
    """
    if system_key not in SYSTEMS:
        return []

    sys = SYSTEMS[system_key]
    trades = []

    for fname in sys["trade_files"]:
        path = _safe_path(system_key, fname)
        if not path or not os.path.exists(path):
            continue
        # crypto has two files; tag the sub-market by filename
        sub_market = None
        if system_key == "crypto":
            sub_market = "ETH" if "eth" in fname.lower() else "BTC"

        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if not row:
                        continue
                    d = _to_date(row.get("date") or row.get("entry_time"))
                    if not _in_range(d, date_from, date_to):
                        continue

                    pnl_gbp = _fnum(row, "pnl_gbp", default=0.0)
                    entry = _fnum(row, "entry_price", "entry_price_usd")
                    exit_p = _fnum(row, "exit_price", "exit_price_usd")
                    capital = _fnum(row, "capital_after", "capital_after_gbp")
                    points = _fnum(row, "points_gained")  # None for crypto

                    market = sub_market if sub_market else sys["label"]

                    trades.append({
                        "system": system_key,
                        "system_display": sys["display"],
                        "market": market,
                        "date": row.get("date", "").strip() if row.get("date") else (
                            d.isoformat() if d else ""),
                        "time": _fstr(row, "time"),
                        "direction": _fstr(row, "direction"),
                        "entry": entry,
                        "exit": exit_p,
                        "points": points,
                        "pnl_gbp": pnl_gbp,
                        "capital_after": capital,
                        "exit_reason": _fstr(row, "exit_reason"),
                        "entry_time": _fstr(row, "entry_time"),
                        "exit_time": _fstr(row, "exit_time"),
                        "result": "WIN" if pnl_gbp >= 0 else "LOSS",
                        "_date": d,
                    })
        except (OSError, csv.Error, UnicodeDecodeError):
            # missing / locked / malformed -> skip gracefully
            continue

    trades.sort(key=lambda t: (t.get("date", ""), t.get("time", "")))
    return trades


# ---------------------------------------------------------------------------
# read_phantom_decisions
# ---------------------------------------------------------------------------
def read_phantom_decisions(system_key, date_from=None, date_to=None):
    """Read phantom_trades.csv (uniform schema across all six systems)."""
    if system_key not in SYSTEMS:
        return []

    path = _safe_path(system_key, "phantom_trades.csv")
    if not path or not os.path.exists(path):
        return []

    out = []
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not row:
                    continue
                ts = _fstr(row, "timestamp")
                d = _to_date(ts)
                if not _in_range(d, date_from, date_to):
                    continue
                out.append({
                    "system": system_key,
                    "timestamp": ts,
                    "market": _fstr(row, "market"),
                    "direction_blocked": _fstr(row, "direction_blocked"),
                    "price_at_decision": _fnum(row, "price_at_decision"),
                    "confidence": _fstr(row, "confidence"),
                    "reason": _fstr(row, "reason_for_stay_out"),
                    "price_30min": _fnum(row, "price_30min"),
                    "pnl_30min": _fnum(row, "pnl_30min"),
                    "price_1hr": _fnum(row, "price_1hr"),
                    "pnl_1hr": _fnum(row, "pnl_1hr"),
                    "price_2hr": _fnum(row, "price_2hr"),
                    "pnl_2hr": _fnum(row, "pnl_2hr"),
                    "verdict": _fstr(row, "verdict").upper(),
                    "_date": d,
                })
    except (OSError, csv.Error, UnicodeDecodeError):
        return []
    return out


# ---------------------------------------------------------------------------
# _level_for_confidence
# ---------------------------------------------------------------------------
def _level_for_confidence(conf):
    """Bucket a numeric confidence (0-100) into a level word, used only when
    the CSV row itself does not carry an explicit level."""
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return "MEDIUM"
    if c >= 65:
        return "HIGH"
    if c < 40:
        return "LOW"
    return "MEDIUM"


# ---------------------------------------------------------------------------
# read_morgan_confidence
# ---------------------------------------------------------------------------
def read_morgan_confidence(system_key, date_from=None, date_to=None):
    """Read a system's logs/morgan_confidence.csv.

    Expected columns: timestamp, confidence, level, reason.

    Returns a list of dicts (in chronological order, filtered to the date
    range) shaped as:
        {timestamp, confidence(float), level, value(int), reason}
    (``value`` is retained for backward compatibility with the report
    generator, which renders "<level> (<value>)".)

    A missing / empty / header-only / locked / malformed file yields ``[]`` --
    this reader NEVER raises.
    """
    if system_key not in SYSTEMS:
        return []

    path = _safe_path(system_key, "morgan_confidence.csv")
    if not path or not os.path.exists(path):
        return []

    out = []
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not row:
                    continue
                ts = _fstr(row, "timestamp")
                d = _to_date(ts)
                if (date_from is not None or date_to is not None) and \
                        not _in_range(d, date_from, date_to):
                    continue
                conf = _fnum(row, "confidence")
                if conf is None:
                    continue
                level = _fstr(row, "level").upper() or _level_for_confidence(conf)
                out.append({
                    "system": system_key,
                    "timestamp": ts,
                    "confidence": conf,
                    "value": int(round(conf)),
                    "level": level,
                    "reason": _fstr(row, "reason"),
                    "_date": d,
                })
    except (OSError, csv.Error, UnicodeDecodeError, ValueError):
        return []

    out.sort(key=lambda e: e.get("timestamp", ""))
    return out


def latest_morgan_confidence(system_key):
    """Convenience: the most recent Morgan reading (all-time) as a
    ``(confidence, level)`` tuple, or ``(None, None)`` if none exists."""
    events = read_morgan_confidence(system_key)
    if not events:
        return (None, None)
    last = events[-1]
    return (last.get("confidence"), last.get("level"))


# ---------------------------------------------------------------------------
# read_guinevere_sentiment
# ---------------------------------------------------------------------------
def read_guinevere_sentiment(system_key, date_from=None, date_to=None):
    """Read a system's logs/guinevere_sentiment.csv (only Oil & Gas run the
    Guinevere news module).

    Expected columns: timestamp, sentiment, score, headline_1..3, eia_window.

    Returns a list of dicts (chronological, date-filtered):
        {timestamp, sentiment, score(int or None)}
    Empty list if absent / unreadable -- NEVER raises.
    """
    if system_key not in SYSTEMS:
        return []

    path = _safe_path(system_key, "guinevere_sentiment.csv")
    if not path or not os.path.exists(path):
        return []

    out = []
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not row:
                    continue
                ts = _fstr(row, "timestamp")
                d = _to_date(ts)
                if (date_from is not None or date_to is not None) and \
                        not _in_range(d, date_from, date_to):
                    continue
                sc = _fnum(row, "score")
                out.append({
                    "system": system_key,
                    "timestamp": ts,
                    "sentiment": _fstr(row, "sentiment"),
                    "score": int(round(sc)) if sc is not None else None,
                    "_date": d,
                })
    except (OSError, csv.Error, UnicodeDecodeError, ValueError):
        return []

    out.sort(key=lambda e: e.get("timestamp", ""))
    return out


# ---------------------------------------------------------------------------
# get_system_balance
# ---------------------------------------------------------------------------
def get_system_balance(system_key):
    """Start balance + sum of pnl_gbp over ALL trades (no date filter)."""
    if system_key not in SYSTEMS:
        return 0.0
    start = SYSTEMS[system_key]["start_balance"]
    trades = read_trades(system_key)  # all-time
    return start + sum(t["pnl_gbp"] for t in trades)


# ---------------------------------------------------------------------------
# aggregate_all_systems
# ---------------------------------------------------------------------------
def aggregate_all_systems(date_from=None, date_to=None):
    """Return the full nested aggregation used by chronicle.generate_report."""
    result = {
        "period": {
            "from": _to_date(date_from).isoformat() if _to_date(date_from) else None,
            "to": _to_date(date_to).isoformat() if _to_date(date_to) else None,
        },
        "systems": {},
        "all_trades": [],
        "all_phantoms": [],
        "totals": {},
    }

    tot_trades = tot_wins = tot_losses = 0
    tot_pnl = 0.0
    tot_phantom = 0
    tot_arthur = 0
    tot_lancelot = 0
    tot_correct = tot_wrong = tot_neutral = tot_pending = 0
    net_saved = 0.0   # magnitude of loss avoided (CORRECT stay-outs)
    net_missed = 0.0  # magnitude of profit missed (WRONG stay-outs)

    # daily pnl accumulator (for best/worst day across all systems)
    daily_pnl = {}

    for key in SYSTEMS:
        trades = read_trades(key, date_from, date_to)
        phantoms = read_phantom_decisions(key, date_from, date_to)

        # New persistence readers -- wrapped so a bad CSV never breaks aggregation.
        try:
            morgan = read_morgan_confidence(key, date_from, date_to)
        except Exception:
            morgan = []
        try:
            guinevere = read_guinevere_sentiment(key, date_from, date_to)
        except Exception:
            guinevere = []
        try:
            latest_conf, latest_level = latest_morgan_confidence(key)
        except Exception:
            latest_conf, latest_level = (None, None)

        # Confidence journey: first -> last confidence within the period.
        if morgan:
            morgan_journey = {
                "first": morgan[0]["confidence"],
                "first_level": morgan[0]["level"],
                "last": morgan[-1]["confidence"],
                "last_level": morgan[-1]["level"],
            }
        else:
            morgan_journey = None

        # Average Guinevere sentiment score (None if no news module / no data).
        _g_scores = [g["score"] for g in guinevere if g.get("score") is not None]
        guin_avg = (sum(_g_scores) / len(_g_scores)) if _g_scores else None

        wins = sum(1 for t in trades if t["result"] == "WIN")
        losses = sum(1 for t in trades if t["result"] == "LOSS")
        pnl = sum(t["pnl_gbp"] for t in trades)
        n = len(trades)
        wr = (wins / n * 100.0) if n else 0.0

        arthur = sum(1 for p in phantoms if p["reason"] == "ARTHUR_STAY_OUT")
        lancelot = sum(1 for p in phantoms if p["reason"] == "LANCELOT_BLOCK")
        correct = sum(1 for p in phantoms if p["verdict"] == "CORRECT")
        wrong = sum(1 for p in phantoms if p["verdict"] == "WRONG")
        neutral = sum(1 for p in phantoms if p["verdict"] == "NEUTRAL")
        pending = sum(1 for p in phantoms if p["verdict"] == "PENDING")

        sys_saved = sum(abs(p["pnl_1hr"]) for p in phantoms
                        if p["verdict"] == "CORRECT" and p["pnl_1hr"] is not None)
        sys_missed = sum(abs(p["pnl_1hr"]) for p in phantoms
                         if p["verdict"] == "WRONG" and p["pnl_1hr"] is not None)

        for t in trades:
            daily_pnl[t.get("date", "")] = daily_pnl.get(t.get("date", ""), 0.0) + t["pnl_gbp"]

        result["systems"][key] = {
            "key": key,
            "dir": SYSTEMS[key]["dir"],
            "display": SYSTEMS[key]["display"],
            "label": SYSTEMS[key]["label"],
            "color": SYSTEMS[key]["color"],
            "start_balance": SYSTEMS[key]["start_balance"],
            "current_balance": get_system_balance(key),
            "trades": trades,
            "phantoms": phantoms,
            "morgan": morgan,
            "guinevere": guinevere,
            "morgan_latest_confidence": latest_conf,
            "morgan_latest_level": latest_level,
            "morgan_confidence_journey": morgan_journey,
            "guinevere_avg_score": guin_avg,
            "guinevere_days": len(guinevere),
            "n_trades": n,
            "wins": wins,
            "losses": losses,
            "win_rate": wr,
            "pnl": pnl,
            "phantom_decisions": len(phantoms),
            "arthur_decisions": arthur,
            "lancelot_blocks": lancelot,
            "correct": correct,
            "wrong": wrong,
            "neutral": neutral,
            "pending": pending,
            "net_saved": sys_saved,
            "net_missed": sys_missed,
        }

        result["all_trades"].extend(trades)
        result["all_phantoms"].extend(phantoms)

        tot_trades += n
        tot_wins += wins
        tot_losses += losses
        tot_pnl += pnl
        tot_phantom += len(phantoms)
        tot_arthur += arthur
        tot_lancelot += lancelot
        tot_correct += correct
        tot_wrong += wrong
        tot_neutral += neutral
        tot_pending += pending
        net_saved += sys_saved
        net_missed += sys_missed

    result["all_trades"].sort(key=lambda t: (t.get("date", ""), t.get("time", "")))

    best_day = worst_day = None
    if daily_pnl:
        best_k = max(daily_pnl, key=lambda k: daily_pnl[k])
        worst_k = min(daily_pnl, key=lambda k: daily_pnl[k])
        best_day = {"date": best_k, "pnl": daily_pnl[best_k]}
        worst_day = {"date": worst_k, "pnl": daily_pnl[worst_k]}

    closing = sum(s["current_balance"] for s in result["systems"].values())

    result["totals"] = {
        "trades": tot_trades,
        "wins": tot_wins,
        "losses": tot_losses,
        "win_rate": (tot_wins / tot_trades * 100.0) if tot_trades else 0.0,
        "total_pnl": tot_pnl,
        "phantom_decisions": tot_phantom,
        "arthur_decisions": tot_arthur,
        "lancelot_blocks": tot_lancelot,
        "correct_stay_outs": tot_correct,
        "wrong_stay_outs": tot_wrong,
        "neutral_stay_outs": tot_neutral,
        "pending_stay_outs": tot_pending,
        "net_saved": net_saved,
        "net_missed": net_missed,
        "net_benefit": net_saved - net_missed,
        "starting_balance": TOTAL_STARTING_BALANCE,
        "closing_balance": closing,
        "net_change": closing - TOTAL_STARTING_BALANCE,
        "net_change_pct": ((closing - TOTAL_STARTING_BALANCE) / TOTAL_STARTING_BALANCE * 100.0)
                          if TOTAL_STARTING_BALANCE else 0.0,
        "best_day": best_day,
        "worst_day": worst_day,
    }
    return result
