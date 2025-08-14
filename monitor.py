#!/usr/bin/env python3
# monitor.py – NetWebo Ping & Speed + Telegram + 6h Speed + 3s Ping
import os, json, time, threading, asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pythonping import ping
import speedtest
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import concurrent.futures
# Telegram
from telegram import Bot

load_dotenv()
TARGET          = os.getenv("TARGET", "google.com")
LOG_FILE        = Path(os.path.expanduser(os.getenv("LOG_FILE", "~/ping_speed_log.txt")))

EMAIL_SENDER    = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER  = os.getenv("EMAIL_RECEIVER")
SMTP_SERVER     = os.getenv("SMTP_SERVER", "smtp.yandex.com.tr")
SMTP_PORT       = int(os.getenv("SMTP_PORT", 465))

TG_BOT_TOKEN    = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID      = int(os.getenv("TG_CHAT_ID", 0))
bot             = Bot(TG_BOT_TOKEN) if TG_BOT_TOKEN else None

ping_stats = {"günlük_gönderilen": 0, "günlük_ulaşan": 0, "gün": datetime.now().date()}

def log_write(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def send_html_email(subject, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"], msg["From"], msg["To"] = subject, EMAIL_SENDER, EMAIL_RECEIVER
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as s:
            s.login(EMAIL_SENDER, EMAIL_PASSWORD)
            s.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        log_write("HTML e-posta gönderildi")
    except Exception as e:
        log_write(f"E-posta hatası: {e}")

async def tg_send(text):
    if not bot:
        return
    try:
        await bot.send_message(chat_id=TG_CHAT_ID, text=text, parse_mode="HTML")
        log_write("Telegram mesajı gönderildi")
    except Exception as e:
        log_write(f"Telegram hatası: {e}")

def run_speedtest():
    def do():
        st = speedtest.Speedtest()
        st.get_best_server()
        down = st.download() / 1_000_000
        up = st.upload() / 1_000_000
        ping_ms = st.results.ping
        return round(down, 2), round(up, 2), round(ping_ms, 2)
    try:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            d, u, p = ex.submit(do).result(timeout=60)
    except Exception as e:
        log_write(f"Speedtest hatası: {e}")
        return
    msg = f"<b>Speed Test (6h)</b>\nDownload: {d} Mbps\nUpload: {u} Mbps\nPing: {p} ms\nZaman: {datetime.now():%d.%m.%Y %H:%M}"
    log_write(msg.replace("<b>","").replace("</b>",""))
    asyncio.run(tg_send(msg))
    html = f"""
    <html><body style='font-family:Arial;background:#f4f4f4;'>
      <div style='max-width:600px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;'>
        <h2 style='color:#004e92;'>6-Saatlik SpeedTest</h2>
        <table border='1' cellpadding='8'><tr><th>Ölçüm</th><th>Değer</th></tr>
        <tr><td>Download</td><td><b>{d} Mbps</b></td></tr>
        <tr><td>Upload</td><td><b>{u} Mbps</b></td></tr>
        <tr><td>Ping</td><td><b>{p} ms</b></td></tr>
        </table>
        <p style='font-size:12px;color:#555;'>{datetime.now():%d.%m.%Y %H:%M}</p>
      </div>
    </body></html>
    """
    send_html_email("6-Saatlik SpeedTest Raporu", html)

def send_daily_ping_report():
    g, u = ping_stats["günlük_gönderilen"], ping_stats["günlük_ulaşan"]
    t = g - u
    kayip = (t / g * 100) if g else 0
    msg = f"<b>Günlük Ping Özeti</b>\nToplam: {g}\nBaşarılı: {u}\nTimeout: {t}\nPaket Kaybı: %{kayip:.2f}"
    log_write(msg.replace("<b>","").replace("</b>",""))
    asyncio.run(tg_send(msg))
    html = f"""
    <html><body style='font-family:Arial;background:#f4f4f4;'>
      <div style='max-width:600px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;'>
        <h2 style='color:#004e92;'>Günlük Ping Özeti</h2>
        <table border='1' cellpadding='8'><tr><th>Metrik</th><th>Değer</th></tr>
        <tr><td>Toplam Ping</td><td><b>{g}</b></td></tr>
        <tr><td>Başarılı</td><td><b>{u}</b></td></tr>
        <tr><td>Timeout</td><td><b>{t}</b></td></tr>
        <tr><td>Paket Kaybı</td><td><b>%{kayip:.2f}</b></td></tr>
        </table>
        <p style='font-size:12px;color:#555;'>{datetime.now():%d.%m.%Y %H:%M}</p>
      </div>
    </body></html>
    """
    send_html_email("Günlük Ping Raporu", html)
    ping_stats.update({"günlük_gönderilen": 0, "günlük_ulaşan": 0, "gün": datetime.now().date()})

def continuous_ping():
    timeout_counter = 0
    while True:
        ping_stats["günlük_gönderilen"] += 1
        try:
            resp = ping(TARGET, count=1, timeout=1)
            if resp.success():
                ping_stats["günlük_ulaşan"] += 1
                timeout_counter = 0
                log_write(f"Reply from {TARGET}: {resp.rtt_avg_ms:.2f} ms")
            else:
                timeout_counter += 1
                log_write(f"Timeout ({timeout_counter}/5)")
                if timeout_counter == 5:
                    msg = f"<b>{TARGET}</b> 5 kez timeout!"
                    asyncio.run(tg_send(msg))
                    timeout_counter = 0
        except Exception as e:
            log_write(f"Ping hatası: {e}")
        time.sleep(3)

def scheduler_loop():
    schedule.every(6).hours.do(run_speedtest)        # 6 saatte bir
    schedule.every().day.at("11:40").do(send_daily_ping_report)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    log_write("Monitor + Telegram başlatıldı")
    threading.Thread(target=continuous_ping, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    while True:
        time.sleep(1)
