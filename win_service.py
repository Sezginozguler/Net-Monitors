import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys

class PingMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PingMonitorService"
    _svc_display_name_ = "Ping Monitor Service"
    _svc_description_ = "PingMon scriptini arkaplanda çalıştırır (ping ve speedtest raporları)."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            if self.proc:
                self.proc.terminate()
        except Exception:
            pass
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("PingMon servisi başlatılıyor...")
        python = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
        script = os.path.join(os.path.dirname(__file__), "monitor.py")

        # Sanal ortam + monitor.py başlat
        self.proc = subprocess.Popen([python, script], cwd=os.path.dirname(__file__))
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PingMonitorService)
