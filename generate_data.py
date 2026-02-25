import random
from datetime import datetime, timedelta
from database import get_connection, clear_db, init_db

PRICE = 3990
CLUB_START = datetime(2026, 1, 12)  # ~6 weeks ago


def generate():
    random.seed(42)
    init_db()
    clear_db()
    conn = get_connection()

    today = datetime.now()

    # 273 total signups, 2 churn = 271 active
    weekly_targets = [60, 48, 38, 35, 45, 47]  # = 273
    churn_target = 2

    user_id = 0
    all_users = []

    for week_idx, target in enumerate(weekly_targets):
        week_start = CLUB_START + timedelta(weeks=week_idx)
        # Spread signups evenly across the week
        for i in range(target):
            user_id += 1
            uid = f"user_{user_id:04d}"
            day_offset = (i * 7) // target  # evenly distribute across 7 days
            signup_day = week_start + timedelta(days=day_offset)
            if signup_day > today:
                continue

            all_users.append({
                "user_id": uid,
                "start_date": signup_day,
            })

            conn.execute(
                "INSERT INTO subscriptions (user_id, start_date, amount, status) VALUES (?, ?, ?, ?)",
                (uid, signup_day.strftime("%Y-%m-%d"), PRICE, "active")
            )
            conn.execute(
                "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
                (uid, "new", signup_day.strftime("%Y-%m-%d"))
            )

    # Churn exactly 2 users from the first week
    eligible = [u for u in all_users if (today - u["start_date"]).days >= 30]
    churned_users = eligible[:churn_target]
    for user in churned_users:
        churn_date = user["start_date"] + timedelta(days=31)
        conn.execute(
            "UPDATE subscriptions SET status = 'churned', end_date = ? WHERE user_id = ?",
            (churn_date.strftime("%Y-%m-%d"), user["user_id"])
        )
        conn.execute(
            "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
            (user["user_id"], "churned", churn_date.strftime("%Y-%m-%d"))
        )

    # Renewals — users who passed 30 days and didn't churn
    churned_ids = {u["user_id"] for u in churned_users}
    for user in all_users:
        if user["user_id"] in churned_ids:
            continue
        days_since = (today - user["start_date"]).days
        if days_since >= 30:
            renew_date = user["start_date"] + timedelta(days=30)
            conn.execute(
                "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
                (user["user_id"], "renewed", renew_date.strftime("%Y-%m-%d"))
            )

    conn.commit()

    active = conn.execute("SELECT COUNT(*) as cnt FROM subscriptions WHERE status = 'active'").fetchone()["cnt"]
    total = conn.execute("SELECT COUNT(*) as cnt FROM subscriptions").fetchone()["cnt"]
    print(f"Generated: {total} total, {active} active, {total - active} churned")

    conn.close()


if __name__ == "__main__":
    generate()
