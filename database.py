import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "makers.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            amount REAL NOT NULL DEFAULT 3990,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            date TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def clear_db():
    conn = get_connection()
    conn.execute("DELETE FROM subscriptions")
    conn.execute("DELETE FROM events")
    conn.commit()
    conn.close()


def get_metrics():
    conn = get_connection()
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)

    active = conn.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active'"
    ).fetchone()["cnt"]

    mrr = active * 3990

    new_this_week = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE event_type = 'new' AND date >= ?",
        (week_ago.isoformat(),)
    ).fetchone()["cnt"]

    churned = conn.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'churned'"
    ).fetchone()["cnt"]

    total_ever = conn.execute(
        "SELECT COUNT(DISTINCT user_id) as cnt FROM subscriptions"
    ).fetchone()["cnt"]

    renewed = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE event_type = 'renewed'"
    ).fetchone()["cnt"]

    first_renewal_eligible = conn.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE start_date <= ? AND start_date > ? AND status = 'active'",
        ((today - timedelta(days=25)).isoformat(), (today - timedelta(days=35)).isoformat())
    ).fetchone()["cnt"]

    retention_m1 = round(renewed / max(churned + renewed, 1) * 100, 1)

    conn.close()

    return {
        "active": active,
        "mrr": mrr,
        "new_this_week": new_this_week,
        "churned": churned,
        "total_ever": total_ever,
        "retention_m1": retention_m1,
        "first_renewal_upcoming": first_renewal_eligible,
    }


def get_chart_data():
    conn = get_connection()

    # MRR by week
    mrr_rows = conn.execute("""
        SELECT
            strftime('%Y-%W', date) as week,
            date as raw_date,
            event_type
        FROM events
        ORDER BY date
    """).fetchall()

    # Group events by week to calculate running totals
    weeks = {}
    running_active = 0
    for row in mrr_rows:
        week = row["week"]
        if week not in weeks:
            weeks[week] = {"new": 0, "churned": 0, "raw_date": row["raw_date"]}
        if row["event_type"] == "new":
            weeks[week]["new"] += 1
        elif row["event_type"] == "churned":
            weeks[week]["churned"] += 1

    mrr_data = []
    new_by_week = []
    active_by_week = []
    labels = []

    for week_key in sorted(weeks.keys()):
        w = weeks[week_key]
        running_active += w["new"] - w["churned"]
        date_label = w["raw_date"][:10]
        labels.append(date_label)
        mrr_data.append(running_active * 3990)
        new_by_week.append(w["new"])
        active_by_week.append(running_active)

    # Segments
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    segments = {}

    new_seg = conn.execute(
        "SELECT COUNT(*) as cnt FROM events WHERE event_type = 'new' AND date >= ?",
        (week_ago.isoformat(),)
    ).fetchone()["cnt"]
    segments["new"] = new_seg

    first_renewal = conn.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE start_date <= ? AND start_date > ? AND status = 'active'",
        ((today - timedelta(days=25)).isoformat(), (today - timedelta(days=35)).isoformat())
    ).fetchone()["cnt"]
    segments["first_renewal"] = first_renewal

    active_seg = conn.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active'"
    ).fetchone()["cnt"]
    segments["active"] = active_seg - new_seg - first_renewal

    churned_seg = conn.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'churned'"
    ).fetchone()["cnt"]
    segments["churned"] = churned_seg

    conn.close()

    return {
        "labels": labels,
        "mrr": mrr_data,
        "new_by_week": new_by_week,
        "active_by_week": active_by_week,
        "segments": segments,
    }


init_db()
