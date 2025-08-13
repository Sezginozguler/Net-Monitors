#!/usr/bin/env python3
# monitor.py – Ping & Speedtest + Email + Telegram (Windows friendly)

import os, time, threading, asyncio, concurrent.futures, smtplib
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pythonping import ping
import speedtest
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Telegram (optional)
try:
    from telegram import Bot  # python-telegram-bot v20+
except Exception:  # optional dependency
    Bot = None

load_dotenv()

# ---- Config from .env ----
TARGET = os.getenv("TARGET", "google.com")
LOG_FILE = Path(os.path.expanduser(os.getenv("LOG_FILE", "~/ping_speed_log.txt")))

EMAIL_SENDER   = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")
SMTP_SERVER    = os.getenv("SMTP_SERVER", "smtp.yandex.com.tr")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "465") or 465)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")
try:
    TG_CHAT_ID = int(TG_CHAT_ID) if TG_CHAT_ID else 0
except ValueError:
    TG_CHAT_ID = 0

DAILY_REPORT_TIME = os.getenv("DAILY_REPORT_TIME", "09:57")  # HH:MM
PING_INTERVAL_SECONDS = int(os.getenv("PING_INTERVAL_SECONDS", "3") or 3)
PING_TIMEOUT_SECONDS  = int(os.getenv("PING_TIMEOUT_SECONDS", "1") or 1)
TIMEOUT_ALERT_THRESHOLD = int(os.getenv("TIMEOUT_ALERT_THRESHOLD", "5") or 5)
SPEEDTEST_EVERY_HOURS = int(os.getenv("SPEEDTEST_EVERY_HOURS", "6") or 6)

bot = Bot(TG_BOT_TOKEN) if (Bot and TG_BOT_TOKEN) else None

# ---- State ----
ping_stats = {"sent": 0, "ok": 0, "day": datetime.now().date()}

def log_write(text: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def send_html_email(subject: str, html_body: str) -> None:
    if not (EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECEIVER):
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_SENDER, EMAIL_RECEIVER
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        log_write("Email sent")
    except Exception as e:
        log_write(f"Email error: {e}")

async def tg_send(text: str) -> None:
    if not (bot and TG_CHAT_ID):
        return
    try:
        await bot.send_message(chat_id=TG_CHAT_ID, text=text, parse_mode="HTML")
        log_write("Telegram message sent")
    except Exception as e:
        log_write(f"Telegram error: {e}")

def run_speedtest() -> None:
    def do():
        st = speedtest.Speedtest()
        st.get_best_server()
        down = st.download() / 1_000_000
        up = st.upload() / 1_000_000
        ping_ms = st.results.ping
        return round(down, 2), round(up, 2), round(ping_ms, 2)
    try:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            d, u, p = ex.submit(do).result(timeout=90)
    except Exception as e:
        log_write(f"Speedtest error: {e}")
        return
    msg = f"<b>Speed Test</b>\nDown: {d} Mbps\nUp: {u} Mbps\nPing: {p} ms\nTime: {datetime.now():%d.%m.%Y %H:%M}"
    log_write(msg.replace("<b>","").replace("</b>",""))
    try:
        asyncio.run(tg_send(msg))
    except RuntimeError:
        # if an event loop is already running
        asyncio.get_event_loop().create_task(tg_send(msg))

    html = f'''
    <html><body style="font-family:Arial;background:#f4f4f4;">
      <div style="max-width:600px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;">
        <h2>SpeedTest</h2>
        <table border="1" cellpadding="8"><tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Download</td><td><b>{d} Mbps</b></td></tr>
        <tr><td>Upload</td><td><b>{u} Mbps</b></td></tr>
        <tr><td>Ping</td><td><b>{p} ms</b></td></tr>
        </table>
        <p style="font-size:12px;color:#555;">{datetime.now():%d.%m.%Y %H:%M}</p>
      </div>
    </body></html>
    '''
    send_html_email("SpeedTest Report", html)

def send_daily_ping_report() -> None:
    g, u = ping_stats["sent"], ping_stats["ok"]
    t = g - u
    loss = (t / g * 100) if g else 0.0
    msg = f"<b>Daily Ping Summary</b>\nSent: {g}\nOK: {u}\nTimeout: {t}\nLoss: %{loss:.2f}"
    log_write(msg.replace("<b>","").replace("</b>",""))
    try:
        asyncio.run(tg_send(msg))
    except RuntimeError:
        asyncio.get_event_loop().create_task(tg_send(msg))

    html = f'''
    <html><body style="font-family:Arial;background:#f4f4f4;">
      <div style="max-width:600px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;">
        <h2>Daily Ping Summary</h2>
        <table border="1" cellpadding="8"><tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Ping</td><td><b>{g}</b></td></tr>
        <tr><td>Success</td><td><b>{u}</b></td></tr>
        <tr><td>Timeout</td><td><b>{t}</b></td></tr>
        <tr><td>Packet Loss</td><td><b>%{loss:.2f}</b></td></tr>
        </table>
        <p style="font-size:12px;color:#555;">{datetime.now():%d.%m.%Y %H:%M}</p>
      </div>
    </body></html>
    '''
    send_html_email("Daily Ping Report", html)
    # reset counters
    ping_stats["sent"] = 0
    ping_stats["ok"] = 0
    ping_stats["day"] = datetime.now().date()

def continuous_ping() -> None:
    timeout_counter = 0
    while True:
        ping_stats["sent"] += 1
        try:
            resp = ping(TARGET, count=1, timeout=PING_TIMEOUT_SECONDS)
            if resp.success():
                ping_stats["ok"] += 1
                timeout_counter = 0
                log_write(f"Reply from {TARGET}: {resp.rtt_avg_ms:.2f} ms")
            else:
                timeout_counter += 1
                log_write(f"Timeout ({timeout_counter}/{TIMEOUT_ALERT_THRESHOLD})")
                if timeout_counter >= TIMEOUT_ALERT_THRESHOLD:
                    msg = f"<b>{TARGET}</b> timeout x{TIMEOUT_ALERT_THRESHOLD}!"
                    try:
                        asyncio.run(tg_send(msg))
                    except RuntimeError:
                        asyncio.get_event_loop().create_task(tg_send(msg))
                    timeout_counter = 0
        except Exception as e:
            log_write(f"Ping error: {e}")
        time.sleep(PING_INTERVAL_SECONDS)

def scheduler_loop() -> None:
    last_speedtest = 0.0
    last_report_day = datetime.now().date()

    while True:
        # speedtest every N hours
        import time as _t
        if (_t.time() - last_speedtest) >= (SPEEDTEST_EVERY_HOURS * 3600):
            run_speedtest()
            last_speedtest = _t.time()

        # daily report at DAILY_REPORT_TIME
        now = datetime.now()
        hh, mm = map(int, DAILY_REPORT_TIME.split(":"))
        if now.date() != last_report_day and (now.hour > hh or (now.hour == hh and now.minute >= mm)):
            send_daily_ping_report()
            last_report_day = now.date()

        _t.sleep(1)

if __name__ == "__main__":
    log_write("Monitor started")
    threading.Thread(target=continuous_ping, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    while True:
        time.sleep(1)
