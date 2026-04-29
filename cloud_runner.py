from __future__ import annotations

import html
import json
import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

from jobfit.classify import classify_job_type, short_job_type, source_label
from main import scan_once


STATE_PATH = Path("cloud_state.json")
DOCS_PATH = Path("docs/index.html")

FAST_INTERVAL_SECONDS = 12 * 60 * 60
SLOW_INTERVAL_SECONDS = 36 * 60 * 60
SLOW_INITIAL_DELAY_SECONDS = 6 * 60 * 60


def now_ts() -> float:
    return time.time()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load_state() -> dict:
    current = now_ts()
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "created_at": current,
        "last_fast_scan": 0,
        "last_slow_scan": current - SLOW_INTERVAL_SECONDS + SLOW_INITIAL_DELAY_SECONDS,
        "sent_urls": [],
    }


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_config() -> dict:
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def threshold() -> int:
    config = load_config()
    return int(config.get("score_threshold", 80))


def esc(x) -> str:
    return html.escape(str(x or ""))


def get_rows(min_score: int = 0, limit: int = 200):
    db_path = os.getenv("DATABASE_PATH", "jobs.db")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT *
        FROM jobs
        WHERE score >= ?
        ORDER BY score DESC, first_seen_at DESC
        LIMIT ?
        """,
        (min_score, limit),
    ).fetchall()
    con.close()
    return rows


def get_dashboard_rows(min_score: int):
    rows = list(get_rows(min_score=min_score, limit=200))
    seen = {r["url"] for r in rows}

    # Add one best representative role per region if not already visible.
    db_path = os.getenv("DATABASE_PATH", "jobs.db")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    region_filters = {
        "Hong Kong": "location LIKE '%Hong%' OR url LIKE '%hk.jobsdb.com%'",
        "Singapore": "location LIKE '%Singapore%' OR url LIKE '%sg.jobstreet.com%'",
        "Korea": "location LIKE '%Korea%' OR location LIKE '%Seoul%' OR url LIKE '%South%20Korea%' OR url LIKE '%Seoul%'",
        "Japan": "location LIKE '%Japan%' OR location LIKE '%Tokyo%' OR url LIKE '%Tokyo%2C%20Japan%'",
    }

    for region, where in region_filters.items():
        already = False
        for r in rows:
            loc = str(r["location"] or "").lower()
            url = str(r["url"] or "").lower()
            if region == "Hong Kong" and ("hong" in loc or "hk.jobsdb.com" in url):
                already = True
            elif region == "Singapore" and ("singapore" in loc or "sg.jobstreet.com" in url):
                already = True
            elif region == "Korea" and ("korea" in loc or "seoul" in loc or "south%20korea" in url):
                already = True
            elif region == "Japan" and ("japan" in loc or "tokyo" in loc or "tokyo%2c%20japan" in url):
                already = True

        if already:
            continue

        top = con.execute(
            f"""
            SELECT *
            FROM jobs
            WHERE ({where})
            ORDER BY score DESC, first_seen_at DESC
            LIMIT 1
            """
        ).fetchone()

        if top and top["url"] not in seen:
            rows.append(top)
            seen.add(top["url"])

    con.close()
    rows.sort(key=lambda r: int(r["score"] or 0), reverse=True)
    return rows


def write_public_dashboard(rows):
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)

    sections = {
        "Full-time / Graduate": [],
        "Internship / Temporary": [],
        "Official Portal": [],
        "Other / Review": [],
    }

    for r in rows:
        sections.setdefault(classify_job_type(r), []).append(r)

    nav = []
    body = []
    idx = 1

    for section, items in sections.items():
        if not items:
            continue

        anchor = section.lower().replace(" / ", "-").replace(" ", "-")
        nav.append(f'<a href="#{anchor}">{esc(section)} ({len(items)})</a>')
        body.append(f'<h2 id="{anchor}">{esc(section)} <span>{len(items)} role(s)</span></h2>')

        for r in items:
            title = esc(r["title"])
            company = esc(r["company"])
            location = esc(r["location"])
            score = esc(r["score"])
            url = esc(r["url"])
            src = esc(source_label(r))
            typ = esc(classify_job_type(r))

            body.append(f"""
            <article class="card">
              <div class="meta">
                <span>#{idx}</span>
                <span class="pill score">{score}/100</span>
                <span class="pill">{src}</span>
                <span class="pill">{typ}</span>
              </div>
              <h3>{title}</h3>
              <p>{company} · {location}</p>
              <a class="button" href="{url}" target="_blank" rel="noopener">Open application link</a>
            </article>
            """)
            idx += 1

    generated = now_text()
    total = len(rows)

    html_doc = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Job Fit Radar Shortlist</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7fb;
      color: #152033;
    }}
    .wrap {{
      max-width: 1050px;
      margin: 0 auto;
      padding: 36px 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 34px;
      letter-spacing: -0.03em;
    }}
    .sub {{
      color: #667085;
      margin-bottom: 22px;
    }}
    .nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 20px 0 30px;
    }}
    .nav a {{
      text-decoration: none;
      color: #172033;
      background: white;
      border: 1px solid #e7eaf0;
      border-radius: 999px;
      padding: 9px 13px;
      font-weight: 700;
    }}
    h2 {{
      margin-top: 34px;
      font-size: 24px;
    }}
    h2 span {{
      color: #7a8497;
      font-size: 16px;
      font-weight: 500;
    }}
    .card {{
      background: white;
      border: 1px solid #e4e8f0;
      border-radius: 18px;
      padding: 22px;
      margin: 14px 0;
      box-shadow: 0 10px 28px rgba(16, 24, 40, 0.07);
    }}
    .meta {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      color: #667085;
      font-weight: 700;
      font-size: 14px;
    }}
    .pill {{
      background: #eef2ff;
      color: #3446a1;
      border-radius: 999px;
      padding: 5px 10px;
    }}
    .score {{
      background: #dcfce7;
      color: #166534;
    }}
    h3 {{
      font-size: 21px;
      margin: 14px 0 6px;
    }}
    p {{
      color: #667085;
    }}
    .button {{
      display: inline-block;
      margin-top: 10px;
      background: #111827;
      color: white;
      text-decoration: none;
      padding: 11px 14px;
      border-radius: 11px;
      font-weight: 800;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Job Fit Radar Shortlist</h1>
    <p class="sub">Generated at {generated}. Showing {total} role(s). Public-safe version: no CV or profile details included.</p>
    <nav class="nav">{''.join(nav)}</nav>
    {''.join(body)}
  </main>
</body>
</html>
"""
    DOCS_PATH.write_text(html_doc, encoding="utf-8")


def send_ntfy(rows, scan_label: str, total_high: int):
    if not rows:
        return

    server = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    topic = os.getenv("NTFY_TOPIC", "").strip()
    dashboard_url = os.getenv("DASHBOARD_URL", "").strip()

    if not topic:
        print("[WARN] NTFY_TOPIC missing; notification skipped.")
        return

    shown = rows[:10]
    lines = [
        f"Job Fit Radar — {scan_label}",
        f"{total_high} new high-match role(s). Showing top {len(shown)}.",
    ]

    if dashboard_url:
        lines.append(f"Dashboard: {dashboard_url}")

    for i, r in enumerate(shown, start=1):
        lines.append("")
        lines.append(f"{i}. [{source_label(r)} | {short_job_type(r)}] {r['title']}")
        lines.append(f"Score: {r['score']}/100")
        lines.append(f"Apply: {r['url']}")

    text = "\n".join(lines)

    resp = requests.post(
        f"{server}/{topic}",
        data=text.encode("utf-8"),
        headers={
            "Title": "Job Fit Radar",
            "Priority": "default",
            "Tags": "briefcase",
        },
        timeout=30,
    )
    resp.raise_for_status()
    print(f"Notification sent: {len(shown)} role(s).")


def run_one_scan(label: str, source_file: str, state: dict):
    print(f"[{now_text()}] Running {label} scan with {source_file}")

    if not Path(source_file).exists():
        print(f"[WARN] Missing {source_file}; skipped.")
        return False

    shutil.copyfile(source_file, "sources.yaml")

    db_path = Path(os.getenv("DATABASE_PATH", "jobs.db"))
    if db_path.exists():
        db_path.unlink()

    # Use existing app logic, but cloud_runner handles notification and public dashboard.
    scan_once(send=False)

    min_score = threshold()
    rows = get_rows(min_score=min_score, limit=200)

    sent_urls = set(state.get("sent_urls", []))
    new_high = [r for r in rows if r["url"] and r["url"] not in sent_urls]

    dashboard_rows = get_dashboard_rows(min_score=min_score)
    write_public_dashboard(dashboard_rows)

    if new_high:
        send_ntfy(new_high, scan_label=label, total_high=len(new_high))
        for r in new_high:
            sent_urls.add(r["url"])

    state["sent_urls"] = sorted(sent_urls)
    state[f"last_{label.lower()}_scan"] = now_ts()

    print(f"[{now_text()}] {label} scan done. New high-match roles: {len(new_high)}")
    return True


def main():
    state = load_state()
    current = now_ts()

    due_fast = current - float(state.get("last_fast_scan", 0)) >= FAST_INTERVAL_SECONDS
    due_slow = current - float(state.get("last_slow_scan", 0)) >= SLOW_INTERVAL_SECONDS

    ran_any = False

    # If both are somehow due, run slow first, then fast.
    if due_slow:
        ran_any = run_one_scan("SLOW", "sources_slow.yaml", state) or ran_any

    if due_fast:
        ran_any = run_one_scan("FAST", "sources_fast.yaml", state) or ran_any

    if not ran_any:
        print("No scan due. Refreshing dashboard from existing data if available.")
        if Path(os.getenv("DATABASE_PATH", "jobs.db")).exists():
            write_public_dashboard(get_dashboard_rows(min_score=threshold()))

    save_state(state)


if __name__ == "__main__":
    main()
