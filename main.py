import os

files = {
    "app.py": """
from flask import Flask, render_template, send_file, redirect, url_for
from scraper import run_scraper
from database import export_csv, get_last_run, get_total_records
import os

app = Flask(__name__)

@app.route('/')
def dashboard():
    last_run = get_last_run()
    total = get_total_records()
    return render_template('dashboard.html', last_run=last_run, total=total)

@app.route('/scrape')
def scrape():
    run_scraper()
    return redirect(url_for('dashboard'))

@app.route('/download')
def download():
    filename = export_csv()
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
""",

    "scraper.py": """
import asyncio
import random
from playwright.async_api import async_playwright
from database import save_profile, profile_exists, update_last_run

BASE_URL = "https://www.fgirl.ch/filles/"

async def scrape_profiles():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        links = await page.locator("a.girl-card").evaluate_all("els => els.map(e => e.href)")

        new_count = 0
        for link in links:
            if profile_exists(link):
                continue
            await page.goto(link)
            await asyncio.sleep(random.uniform(2, 5))
            profile = await parse_profile(page, link)
            save_profile(profile)
            new_count += 1

        await browser.close()
        update_last_run()
        return new_count

async def parse_profile(page, url):
    name = await page.locator("h1").inner_text()
    phone = await page.locator("a[href^='tel:']").inner_text() if await page.locator("a[href^='tel:']").count() > 0 else ""
    about = await page.locator(".about").inner_text() if await page.locator(".about").count() > 0 else ""
    return {"url": url, "name": name, "phone": phone, "about": about}

def run_scraper():
    asyncio.run(scrape_profiles())
""",

    "database.py": """
import sqlite3
import csv
import os
from datetime import datetime

DB_FILE = os.environ.get("DB_FILE", "scraper.db")

def connect():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS profiles(url TEXT PRIMARY KEY, name TEXT, phone TEXT, about TEXT, scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cur.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

def profile_exists(url):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT url FROM profiles WHERE url=?", (url,))
    res = cur.fetchone()
    conn.close()
    return res is not None

def save_profile(profile):
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO profiles(url,name,phone,about) VALUES(?,?,?,?)",
                (profile["url"], profile["name"], profile["phone"], profile["about"]))
    conn.commit()
    conn.close()

def export_csv():
    filename = "output.csv"
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT url,name,phone,about,scraped_at FROM profiles")
    rows = cur.fetchall()
    with open(filename, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["URL","Name","Phone","About","Scraped_At"])
        writer.writerows(rows)
    conn.close()
    return filename

def update_last_run():
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('last_run',?)", (datetime.utcnow().isoformat(),))
    conn.commit()
    conn.close()

def get_last_run():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM metadata WHERE key='last_run'")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "Never"

def get_total_records():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM profiles")
    row = cur.fetchone()
    conn.close()
    return row[0]
""",

    "templates/dashboard.html": """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FGirl Scraper Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="p-4">
    <div class="container">
        <h1>FGirl Scraper</h1>
        <p>Last Run: {{ last_run }}</p>
        <p>Total Records: {{ total }}</p>
        <a class="btn btn-primary" href="/scrape">Run Scraper</a>
        <a class="btn btn-success" href="/download">Download CSV</a>
    </div>
</body>
</html>
""",

    "Dockerfile": """
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl unzip nodejs npm && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install playwright && playwright install chromium

COPY . .
CMD ["python", "app.py"]
""",

    "requirements.txt": """
Flask==2.3.3
playwright==1.39.0
""",

    "render.yaml": """
services:
  - type: web
    name: fgirl-scraper
    env: docker
    plan: free
    branch: main
    autoDeploy: true
""",

    "README.md": """
# FGirl Scraper

Click below to deploy to Render:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Once deployed, you will get your own public URL.
"""
}

os.makedirs("templates", exist_ok=True)
for path, content in files.items():
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("Project files created successfully.")
