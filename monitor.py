#!/usr/bin/env python3
# monitor.py – 6h + 1h speed test + <50 Mbps alarm
import os, time, threading, asyncio
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

ping_stats = {"gönderilen": 0, "ulaşan": 0, "gün": datetime.now().date()}

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
        log_write("✅ HTML e-posta gönderildi")
    except Exception as e:
        log_write(f"❌ E-posta hatası: {e}")

async def tg_send(text):
    if not bot:
        return
    try:
        await bot.send_message(chat_id=TG_CHAT_ID, text=text, parse_mode="HTML")
        log_write("📤 Telegram mesajı gönderildi")
    except Exception as e:
        log_write(f"❌ Telegram hatası: {e}")

def _do_speedtest():
    st = speedtest.Speedtest()
    st.get_best_server()
    down = st.download() / 1_000_000
    up = st.upload() / 1_000_000
    ping_ms = st.results.ping
    return round(down, 2), round(up, 2), round(ping_ms, 2)

def run_speedtest():
    """6 saatte bir – normal rapor"""
    try:
        d, u, p = _do_speedtest()
    except Exception as e:
        log_write(f"❌ Speedtest hatası: {e}")
        return
    log_write(f"📡 6h SpeedTest: ↓{d} Mbps  ↑{u} Mbps  {p} ms")
    msg = f"📡 <b>6-Saatlik SpeedTest</b>\n⬇️ {d} Mbps\n⬆️ {u} Mbps\n🏓 {p} ms"
    asyncio.run(tg_send(msg))

def hourly_speedtest():
    """Her saat – <50 Mbps alarmı"""
    try:
        d, u, p = _do_speedtest()
    except Exception as e:
        log_write(f"❌ Hourly speedtest hatası: {e}")
        return

    log_write(f"📊 Hourly SpeedTest: ↓{d} Mbps  ↑{u} Mbps  {p} ms")

    if d < 50:
        msg = f"⚠️ <b>Hız Düşüşü Alarmı</b>\n⬇️ {d} Mbps (< 50 Mbps)\n⬆️ {u} Mbps\n🏓 {p} ms"
        asyncio.run(tg_send(msg))
        html = f"""
        <html><body style='font-family:Arial;background:#fff3cd;'>
          <div style='max-width:600px;margin:30px auto;background:#fff;border:2px solid #ff6b00;padding:20px;border-radius:8px;'>
            <h2 style='color:#ff6b00;'>⚠️ Hız Düşüşü Alarmı</h2>
            <p><b>Download:</b> {d} Mbps (< 50 Mbps)</p>
            <p><b>Upload:</b> {u} Mbps</p>
            <p><b>Ping:</b> {p} ms</p>
          </div>
        </body></html>
        """
        send_html_email("Hız Düşüşü Alarmı", html)

def send_daily_ping_report():
    bugun = datetime.now().date()
    g, u = ping_stats["gönderilen"], ping_stats["ulaşan"]
    t = g - u
    kayip = (t / g * 100) if g else 0
    msg = f"📊 <b>Günlük Ping Özeti</b>\n📤 {g} ping\n✅ {u} başarılı\n❌ {t} timeout\n📉 %{kayip:.2f} kayıp"
    asyncio.run(tg_send(msg))
    ping_stats.update({"gönderilen": 0, "ulaşan": 0, "gün": datetime.now().date()})

def continuous_ping():
    timeout_counter = 0
    while True:
        ping_stats["gönderilen"] += 1
        try:
            resp = ping(TARGET, count=1, timeout=1)
            if resp.success():
                ping_stats["ulaşan"] += 1
                timeout_counter = 0
                log_write(f"✅ Reply from {TARGET}: {resp.rtt_avg_ms:.2f} ms")
            else:
                timeout_counter += 1
                log_write(f"❌ Timeout ({timeout_counter}/5)")
                if timeout_counter == 5:
                    msg = f"🚨 <b>{TARGET}</b> 5 kez timeout!"
                    asyncio.run(tg_send(msg))
                    timeout_counter = 0
        except Exception as e:
            log_write(f"❌ Ping hatası: {e}")
        time.sleep(3)

def scheduler_loop():
    schedule.every(6).hours.do(run_speedtest)
    schedule.every().hour.do(hourly_speedtest)
    schedule.every().day.at("23:59").do(send_daily_ping_report)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    log_write("🚀 Monitor + 6h + 1h + <50 Mbps alarm başlatıldı")
    threading.Thread(target=continuous_ping, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    while True:
        time.sleep(1)
