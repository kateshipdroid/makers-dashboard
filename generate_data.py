import random
from datetime import datetime, timedelta
from database import get_connection, clear_db, init_db

PRICE = 3990
CLUB_START = datetime(2026, 1, 12)  # ~6 weeks ago
TARGET_ACTIVE = 273


def generate():
    init_db()
    clear_db()
    conn = get_connection()

    today = datetime.now()
    total_days = (today - CLUB_START).days

    # Distribute signups across 6 weeks with growth curve
    # Week 1: launch burst, then steady growth
    weekly_targets = [65, 50, 40, 35, 42, 51]  # ~283 total, some will churn
    churn_rate = 0.035  # ~3.5% churn for those eligible

    user_id = 0
    all_users = []

    for week_idx, target in enumerate(weekly_targets):
        week_start = CLUB_START + timedelta(weeks=week_idx)
        for i in range(target):
            user_id += 1
            uid = f"user_{user_id:04d}"
            signup_day = week_start + timedelta(days=random.randint(0, 6))
            if signup_day > today:
                continue

            all_users.append({
                "user_id": uid,
                "start_date": signup_day,
                "status": "active",
            })

            conn.execute(
                "INSERT INTO subscriptions (user_id, start_date, amount, status) VALUES (?, ?, ?, ?)",
                (uid, signup_day.strftime("%Y-%m-%d"), PRICE, "active")
            )
            conn.execute(
                "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
                (uid, "new", signup_day.strftime("%Y-%m-%d"))
            )

    # Process churns — only users from first 2 weeks are eligible (30+ days)
    churn_count = 0
    for user in all_users:
        days_since = (today - user["start_date"]).days
        if days_since >= 30:
            if random.random() < 0.08:  # ~8% of eligible users churned
                churn_date = user["start_date"] + timedelta(days=30 + random.randint(0, 3))
                if churn_date <= today:
                    conn.execute(
                        "UPDATE subscriptions SET status = 'churned', end_date = ? WHERE user_id = ?",
                        (churn_date.strftime("%Y-%m-%d"), user["user_id"])
                    )
                    conn.execute(
                        "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
                        (user["user_id"], "churned", churn_date.strftime("%Y-%m-%d"))
                    )
                    churn_count += 1

    # Process renewals — users who passed 30 days and didn't churn
    for user in all_users:
        days_since = (today - user["start_date"]).days
        if days_since >= 30:
            is_churned = conn.execute(
                "SELECT status FROM subscriptions WHERE user_id = ?",
                (user["user_id"],)
            ).fetchone()["status"]
            if is_churned == "active":
                renew_date = user["start_date"] + timedelta(days=30)
                if renew_date <= today:
                    conn.execute(
                        "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
                        (user["user_id"], "renewed", renew_date.strftime("%Y-%m-%d"))
                    )

    conn.commit()

    # Stats
    active = conn.execute("SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active'").fetchone()["cnt"]
    total = conn.execute("SELECT COUNT(*) as cnt FROM subscriptions").fetchone()["cnt"]
    print(f"Generated: {total} total, {active} active, {churn_count} churned")

    conn.close()


if __name__ == "__main__":
    generate()
