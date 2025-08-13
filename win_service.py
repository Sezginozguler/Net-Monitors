import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import threading
import sys
import os
import time

class NetMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NetMonitorService"
    _svc_display_name_ = "Net Monitor Service"
    _svc_description_ = "Network monitoring service for ping and speed tests."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Net Monitor Service starting (quick start mode)...")

        # Hızlı başlatma - asıl işi thread'de başlat
        t = threading.Thread(target=self.run_script)
        t.start()

        # Windows'a hemen "çalışıyor" sinyali ver
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        servicemanager.LogInfoMsg("Net Monitor Service stopped.")

    def run_script(self):
        time.sleep(5)  # sistem oturması için kısa gecikme
        script_path = os.path.join(os.path.dirname(__file__), "monitor.py")
        subprocess.Popen([sys.executable, script_path])

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(NetMonitorService)
