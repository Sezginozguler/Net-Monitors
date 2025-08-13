import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys

class PigMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PigMon"
    _svc_display_name_ = "PigMon Service (Ping + Speedtest + Alerts)"
    _svc_description_ = "Runs monitor.py as a Windows service under PigMon."

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
        servicemanager.LogInfoMsg("PigMon service started.")
        python = sys.executable
        script = os.path.join(os.path.dirname(__file__), "monitor.py")
        self.proc = subprocess.Popen([python, script], cwd=os.path.dirname(script))
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PigMonService)
