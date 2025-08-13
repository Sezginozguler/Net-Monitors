import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys
import traceback

class PingMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PingMon"
    _svc_display_name_ = "PingMon Service"
    _svc_description_ = "Ping & Speed Monitor via PingMon"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_file = os.path.join(self.base_dir, "service_error.log")

    def log_error(self, msg):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except:
            pass

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            if self.proc:
                self.proc.terminate()
        except Exception as e:
            self.log_error(f"SVCSTOP ERROR: {e}")
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        try:
            servicemanager.LogInfoMsg("PingMon service started.")
            python = os.path.join(self.base_dir, "venv", "Scripts", "python.exe")
            script = os.path.join(self.base_dir, "monitor.py")

            if not os.path.exists(python):
                raise FileNotFoundError(f"Python bulunamadı: {python}")
            if not os.path.exists(script):
                raise FileNotFoundError(f"monitor.py bulunamadı: {script}")

            self.proc = subprocess.Popen(
                [python, script],
                cwd=self.base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

        except Exception as e:
            err = f"Service crashed: {e}\n{traceback.format_exc()}"
            self.log_error(err)
            servicemanager.LogErrorMsg(err)

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PingMonService)
