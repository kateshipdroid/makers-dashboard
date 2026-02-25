import io
import csv
from datetime import datetime
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from database import init_db, get_metrics, get_chart_data, get_connection, clear_db
from generate_data import generate
from ai_digest import generate_digest

app = FastAPI(title="Makers Club Dashboard")
templates = Jinja2Templates(directory="templates")

init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/metrics")
async def api_metrics():
    return get_metrics()


@app.get("/api/charts")
async def api_charts():
    return get_chart_data()


@app.post("/api/demo-data")
async def demo_data():
    generate()
    return {"status": "ok", "message": "Demo data generated"}


@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    conn = get_connection()
    clear_db()

    count = 0
    for row in reader:
        user_id = row.get("user_id", "").strip()
        event_type = row.get("event_type", "").strip()
        date = row.get("date", "").strip()
        amount = float(row.get("amount", 3990))

        if not user_id or not event_type or not date:
            continue

        conn.execute(
            "INSERT INTO events (user_id, event_type, date) VALUES (?, ?, ?)",
            (user_id, event_type, date)
        )

        if event_type == "new":
            conn.execute(
                "INSERT INTO subscriptions (user_id, start_date, amount, status) VALUES (?, ?, ?, ?)",
                (user_id, date, amount, "active")
            )
        elif event_type == "churned":
            conn.execute(
                "UPDATE subscriptions SET status = 'churned', end_date = ? WHERE user_id = ?",
                (date, user_id)
            )
        elif event_type == "renewed":
            pass  # just log the event

        count += 1

    conn.commit()
    conn.close()

    return {"status": "ok", "events_loaded": count}


@app.get("/api/digest")
async def api_digest():
    metrics = get_metrics()
    chart_data = get_chart_data()
    digest = generate_digest(metrics, chart_data)
    return {"digest": digest}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
