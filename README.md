# Net Monitor (Ping + Speedtest + Email + Telegram)

A simple, Windows-friendly monitoring script that pings a target every few seconds, sends a daily ping report via email, runs scheduled speedtests, and optionally alerts to Telegram on repeated timeouts.

No secrets are committed. Configure everything via `.env` (see `.env.example`).

## Features
- Continuous ping with rolling stats
- Daily email report (HTML)
- Speedtest every N hours
- Telegram notifications for repeated timeouts
- Minimal dependencies, works on Windows

## Quick Start

```bash
# 1) Clone your repo, then:
copy .env.example .env   # or manually create .env from the example
# 2) Install deps
pip install -r requirements.txt
# 3) Run
python monitor.py
```

### Windows with multiple Python versions
```bash
py -m pip install -r requirements.txt
py monitor.py
```

## Configuration (`.env`)
See `.env.example` for all keys. Key items:

- `TARGET` — host to ping (default: `google.com`)
- `LOG_FILE` — path to append logs (default: `~/ping_speed_log.txt`)
- Email (optional): `EMAIL_SENDER`, `EMAIL_PASSWORD`, `EMAIL_RECEIVER`, `SMTP_SERVER`, `SMTP_PORT`
- Telegram (optional): `TG_BOT_TOKEN`, `TG_CHAT_ID`
- Schedules & tuning: `DAILY_REPORT_TIME`, `PING_INTERVAL_SECONDS`, `PING_TIMEOUT_SECONDS`, `TIMEOUT_ALERT_THRESHOLD`, `SPEEDTEST_EVERY_HOURS`

Leaving any email or Telegram variables empty will disable that channel.

## Run as a Windows Service (optional)

This repo includes `win_service.py` based on `pywin32`.

Install requirements (with admin shell):
```bash
py -m pip install -r requirements.txt
```

Install service:
```bash
# In an elevated (Administrator) PowerShell or CMD
py win_service.py install
py win_service.py start
```

Stop / remove:
```bash
py win_service.py stop
py win_service.py remove
```

The service launches the same `monitor.py` in this folder using your current Python interpreter.

## Logs
- Console output is also appended to `LOG_FILE` (default: `ping_speed_log.txt`).
- Rotate the file using your OS tools if needed.

## License
MIT
