import win32serviceutil
import win32service
import win32event
import servicemanager
import os
import sys
import subprocess
import traceback

class PingMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PingMon"
    _svc_display_name_ = "PingMon Monitor"
    _svc_description_ = "Ping & Speed Monitor via PingMon – Windows Service"

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            if self.proc:
                self.proc.terminate()
        except Exception as e:
            servicemanager.LogErrorMsg(f"Error stopping process: {e}")
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("PingMon service started.")
        python_exe = sys.executable
        script_path = os.path.join(os.path.dirname(__file__), "monitor.py")
        try:
            self.proc = subprocess.Popen([python_exe, script_path], cwd=os.path.dirname(script_path))
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        except Exception as e:
            servicemanager.LogErrorMsg(f"PingMon service error: {e}\n{traceback.format_exc()}")
        servicemanager.LogInfoMsg("PingMon service stopped.")

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PingMonService)
