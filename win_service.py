import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys
import threading
import time

class PingMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PingMon"
    _svc_display_name_ = "PingMon Service"
    _svc_description_ = "Ping & Speed Monitor Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None
        self.is_running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        if self.proc:
            self.proc.terminate()
        win32event.SetEvent(self.hWaitStop)

    def run_monitor(self):
        try:
            python = sys.executable
            script = os.path.join(os.path.dirname(__file__), "monitor.py")
            self.proc = subprocess.Popen([python, script], cwd=os.path.dirname(script))
            while self.is_running:
                time.sleep(1)
        except Exception as e:
            log_file = os.path.join(os.path.dirname(__file__), "service_error.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Error: {str(e)}\n")
            raise

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("PingMon Service starting...")
        # Servis başlatıldı bilgisini hemen gönder
        threading.Thread(target=self.run_monitor, daemon=True).start()
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        servicemanager.LogInfoMsg("PingMon Service stopped.")

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PingMonService)
