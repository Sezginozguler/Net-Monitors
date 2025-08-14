#!/usr/bin/env python3
"""
monitor.py — Ping ve Speedtest izleme (Windows servis uyumlu, emojisiz)

Özellikler:
- Sürekli ping (varsayılan her 3 sn)
- Belirli aralıklarla speedtest (varsayılan 6 saatte bir)
- Günlük özet rapor (paket kaybı vs.)
- Log dosyasına yazım (UTF-8), konsola güvenli çıktı
- Telegram bildirimleri OPSİYONEL (token/chat_id yoksa devre dışı)
- E-Posta bildirimleri OPSİYONEL (.env ile aç/kapat)

Gerekli ortam değişkenleri (.env):
# ---- Ping ----
TARGET=8.8.8.8
PING_INTERVAL_SECONDS=3
PING_TIMEOUT_SECONDS=1
TIMEOUT_ALERT_THRESHOLD=5
# ---- Speedtest ----
SPEEDTEST_EVERY_HOURS=6
# ---- Günlük Rapor ----
DAILY_REPORT_TIME=11:40           # HH:MM
# ---- Log ----
LOG_FILE=C:\PigMon\ping_speed_log.txt
# ---- Telegram (opsiyonel) ----
TG_BOT_TOKEN=
TG_CHAT_ID=
# ---- Mail (opsiyonel) ----
MAIL_ENABLED=True
MAIL_SMTP_SERVER=smtp.gmail.com
MAIL_SMTP_PORT=587
MAIL_USE_TLS=True                 # True: STARTTLS 587, False: SSL 465 (portu uygun verin)
MAIL_FROM=ornekmail@gmail.com
MAIL_TO=hedefmail@gmail.com
MAIL_USER=ornekmail@gmail.com
MAIL_PASS=uygulama_sifresi
"""

import os
import sys
import time
import asyncio
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from pythonping import ping
import speedtest

# -------- UTF-8 güvenli çıktı (PowerShell/cmd/servis) --------
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# -------- Yapılandırma --------
load_dotenv()

def _get_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

TARGET = os.getenv("TARGET", "google.com")

# Log yolu (varsayılan C:\PigMon\ping_speed_log.txt)
default_log = r"C:\PigMon\ping_speed_log.txt"
LOG_FILE = Path(os.path.expanduser(os.getenv("LOG_FILE", default_log)))

PING_INTERVAL_SECONDS   = int(os.getenv("PING_INTERVAL_SECONDS", "3") or 3)
PING_TIMEOUT_SECONDS    = int(os.getenv("PING_TIMEOUT_SECONDS", "1") or 1)
TIMEOUT_ALERT_THRESHOLD = int(os.getenv("TIMEOUT_ALERT_THRESHOLD", "5") or 5)

SPEEDTEST_EVERY_HOURS = int(os.getenv("SPEEDTEST_EVERY_HOURS", "6") or 6)
DAILY_REPORT_TIME     = os.getenv("DAILY_REPORT_TIME", "11:40")  # HH:MM

# Telegram opsiyonel
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "") or os.getenv("TELEGRAM_TOKEN", "")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID", "")   or os.getenv("CHAT_ID", "")

try:
    from telegram import Bot  # python-telegram-bot v20+
except Exception:
    Bot = None

bot = None
if TG_BOT_TOKEN and TG_CHAT_ID and Bot:
    try:
        bot = Bot(TG_BOT_TOKEN)
    except Exception:
        bot = None  # token hatalıysa telegram'ı kapat

# Mail opsiyonel
MAIL_ENABLED     = _get_bool("MAIL_ENABLED", False)
MAIL_SMTP_SERVER = os.getenv("MAIL_SMTP_SERVER", "smtp.gmail.com")
MAIL_SMTP_PORT   = int(os.getenv("MAIL_SMTP_PORT", "587") or 587)
MAIL_USE_TLS     = _get_bool("MAIL_USE_TLS", True)  # True: STARTTLS, False: SSL
MAIL_FROM        = os.getenv("MAIL_FROM", "")
MAIL_TO          = os.getenv("MAIL_TO", "")
MAIL_USER        = os.getenv("MAIL_USER", "")
MAIL_PASS        = os.getenv("MAIL_PASS", "")

def log_write(text: str) -> None:
    """Hem ekrana (UTF-8) hem dosyaya güvenli yaz."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"

    # Ekran
    try:
        print(line)
    except Exception:
        try:
            sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
        except Exception:
            pass

    # Dosya
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ---- Telegram güvenli gönderim (opsiyonel) ----
async def _tg_send_async(msg: str) -> None:
    if not (bot and TG_CHAT_ID):
        return
    await bot.send_message(chat_id=TG_CHAT_ID, text=msg)

def tg_send(msg: str) -> None:
    """Event loop yoksa yeni loop ile, varsa mevcut loop'a iş planlayarak gönder."""
    if not (bot and TG_CHAT_ID):
        return
    try:
        asyncio.run(_tg_send_async(msg))
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_tg_send_async(msg))
        except Exception as e:
            log_write(f"Telegram gönderim hatası (loop): {e}")
    except Exception as e:
        log_write(f"Telegram gönderim hatası: {e}")

# ---- Mail gönderimi (opsiyonel) ----
def send_mail(subject: str, body_text: str = "", body_html: str | None = None) -> None:
    if not MAIL_ENABLED:
        return
    if not (MAIL_FROM and MAIL_TO and MAIL_USER and MAIL_PASS and MAIL_SMTP_SERVER and MAIL_SMTP_PORT):
        log_write("Mail ayarları eksik; gönderim atlandı.")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = MAIL_FROM
        msg["To"]      = MAIL_TO

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        if MAIL_USE_TLS:
            # STARTTLS (587)
            with smtplib.SMTP(MAIL_SMTP_SERVER, MAIL_SMTP_PORT, timeout=30) as s:
                s.ehlo()
                s.starttls()
                s.login(MAIL_USER, MAIL_PASS)
                s.sendmail(MAIL_FROM, [MAIL_TO], msg.as_string())
        else:
            # SSL (465)
            with smtplib.SMTP_SSL(MAIL_SMTP_SERVER, MAIL_SMTP_PORT, timeout=30) as s:
                s.login(MAIL_USER, MAIL_PASS)
                s.sendmail(MAIL_FROM, [MAIL_TO], msg.as_string())

        log_write("E-posta gönderildi")
    except Exception as e:
        log_write(f"E-posta gönderim hatası: {e}")

# ---- Durum sayaçları ----
ping_stats = {
    "day": datetime.now().date(),
    "sent": 0,
    "ok": 0,
}

# ---- Speedtest ----
def run_speedtest() -> None:
    def do_test():
        st = speedtest.Speedtest()
        st.get_best_server()
        down = st.download() / 1_000_000  # Mbps
        up   = st.upload()   / 1_000_000
        ping_ms = st.results.ping
        return round(down, 2), round(up, 2), round(ping_ms, 2)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            down, up, p = ex.submit(do_test).result(timeout=90)
    except Exception as e:
        log_write(f"Speedtest hatası: {e}")
        return

    text = (
        "Speed Test Sonucu\n"
        f"Download: {down} Mbps\n"
        f"Upload:   {up} Mbps\n"
        f"Ping:     {p} ms\n"
        f"Zaman:    {datetime.now():%d.%m.%Y %H:%M}"
    )
    log_write(text)
    tg_send(text)

    html = f"""
    <html><body style="font-family:Arial;background:#f4f4f4;">
      <div style="max-width:600px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;">
        <h2 style="color:#004e92;">SpeedTest</h2>
        <table border="1" cellpadding="8" cellspacing="0">
          <tr><th>Ölçüm</th><th>Değer</th></tr>
          <tr><td>Download</td><td><b>{down} Mbps</b></td></tr>
          <tr><td>Upload</td><td><b>{up} Mbps</b></td></tr>
          <tr><td>Ping</td><td><b>{p} ms</b></td></tr>
        </table>
        <p style="font-size:12px;color:#555;">{datetime.now():%d.%m.%Y %H:%M}</p>
      </div>
    </body></html>
    """
    send_mail("SpeedTest Raporu", body_text=text, body_html=html)

# ---- Günlük özet ----
def send_daily_ping_report() -> None:
    total = ping_stats["sent"]
    ok    = ping_stats["ok"]
    timeouts = total - ok
    loss = (timeouts / total * 100) if total else 0.0

    text = (
        "Günlük Ping Özeti\n"
        f"Toplam:   {total}\n"
        f"Başarılı: {ok}\n"
        f"Timeout:  {timeouts}\n"
        f"Paket Kaybı: %{loss:.2f}\n"
        f"Zaman:    {datetime.now():%d.%m.%Y %H:%M}"
    )
    log_write(text)
    tg_send(text)

    html = f"""
    <html><body style="font-family:Arial;background:#f4f4f4;">
      <div style="max-width:600px;margin:30px auto;background:#fff;padding:20px;border-radius:8px;">
        <h2 style="color:#004e92;">Günlük Ping Özeti</h2>
        <table border="1" cellpadding="8" cellspacing="0">
          <tr><th>Metrik</th><th>Değer</th></tr>
          <tr><td>Toplam Ping</td><td><b>{total}</b></td></tr>
          <tr><td>Başarılı</td><td><b>{ok}</b></td></tr>
          <tr><td>Timeout</td><td><b>{timeouts}</b></td></tr>
          <tr><td>Paket Kaybı</td><td><b>%{loss:.2f}</b></td></tr>
        </table>
        <p style="font-size:12px;color:#555;">{datetime.now():%d.%m.%Y %H:%M}</p>
      </div>
    </body></html>
    """
    send_mail("Günlük Ping Raporu", body_text=text, body_html=html)

    # sayaçları sıfırla
    ping_stats["day"]  = datetime.now().date()
    ping_stats["sent"] = 0
    ping_stats["ok"]   = 0

# ---- Sürekli ping döngüsü ----
def continuous_ping() -> None:
    timeout_counter = 0
    while True:
        # gün değiştiyse otomatik günlük rapor ve reset
        if datetime.now().date() != ping_stats["day"]:
            send_daily_ping_report()

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
                    alert_text = f"{TARGET} için ardışık {TIMEOUT_ALERT_THRESHOLD} timeout."
                    tg_send(alert_text)
                    # basit düz metin e-posta (HTML’siz)
                    send_mail("Timeout Uyarısı", body_text=alert_text, body_html=None)
                    timeout_counter = 0
        except Exception as e:
            log_write(f"Ping hatası: {e}")

        time.sleep(PING_INTERVAL_SECONDS)

# ---- Zamanlayıcı döngüsü (speedtest + günlük saatli rapor) ----
def scheduler_loop() -> None:
    last_speedtest = 0.0
    last_daily_sent_date = None

    # günlük rapor zamanı parse et
    try:
        daily_hh, daily_mm = map(int, DAILY_REPORT_TIME.split(":"))
    except Exception:
        daily_hh, daily_mm = 11, 40  # varsayılan

    while True:
        now = datetime.now()

        # periyodik speedtest
        if last_speedtest == 0.0 or (time.time() - last_speedtest) >= (SPEEDTEST_EVERY_HOURS * 3600):
            run_speedtest()
            last_speedtest = time.time()

        # günlük rapor (belirlenen saati geçtiyse ve o güne daha önce gönderilmediyse)
        if (now.hour > daily_hh or (now.hour == daily_hh and now.minute >= daily_mm)):
            if last_daily_sent_date != now.date():
                send_daily_ping_report()
                last_daily_sent_date = now.date()

        time.sleep(1)

# ---- Ana ----
if __name__ == "__main__":
    log_write("Monitor başlatıldı")
    log_write(f"Ping hedefi: {TARGET}")
    log_write(f"Telegram: {'aktif' if (bot and TG_CHAT_ID) else 'kapalı'}")
    log_write(f"Mail: {'aktif' if MAIL_ENABLED else 'kapalı'}")

    # Ping ve zamanlayıcı paralel
    threading.Thread(target=continuous_ping, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    # ana thread uyur (servis için gerekir)
    while True:
        time.sleep(1)
