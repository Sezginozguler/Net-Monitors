import win32serviceutil, win32service, win32event, servicemanager
import os, sys, subprocess, traceback, time

class PingMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PingMon"
    _svc_display_name_ = "PingMon Service"
    _svc_description_ = "Ping & Speed Monitor"

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
            servicemanager.LogErrorMsg(f"Stop error: {e}")
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("PingMon service starting...")
        try:
            time.sleep(3)  # açılışta kısa gecikme
            python = sys.executable
            script = os.path.join(os.path.dirname(__file__), "monitor.py")
            self.proc = subprocess.Popen([python, script], cwd=os.path.dirname(script))
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        except Exception as e:
            servicemanager.LogErrorMsg(f"Run error: {e}\n{traceback.format_exc()}")
        finally:
            servicemanager.LogInfoMsg("PingMon service stopped.")

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PingMonService)
