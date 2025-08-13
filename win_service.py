import win32serviceutil
import win32service
import win32event
import servicemanager
import threading
import subprocess
import os
import sys
import signal

class PingMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PingMon"
    _svc_display_name_ = "PingMon Service"
    _svc_description_ = "Ping & Speed Monitor Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None
        self.thread = None
        self.stop_requested = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_requested = True
        try:
            if self.proc:
                self.proc.terminate()
        except Exception:
            pass
        win32event.SetEvent(self.hWaitStop)

    def run_monitor(self):
        python = sys.executable
        script = os.path.join("C:\\PingMon", "monitor.py")
        try:
            self.proc = subprocess.Popen([python, script], cwd="C:\\PingMon")
            self.proc.wait()
        except Exception as e:
            servicemanager.LogErrorMsg(f"PingMon run error: {e}")

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("PingMon service starting...")
        self.thread = threading.Thread(target=self.run_monitor)
        self.thread.start()
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        servicemanager.LogInfoMsg("PingMon service stopped.")

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(PingMonService)
