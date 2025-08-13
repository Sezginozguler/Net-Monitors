# win_service_PigMon.py
import win32serviceutil
import win32service
import win32event
import servicemanager
import os
import sys
import subprocess
import logging

# Servis tanımı
class PigMonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PigMon"
    _svc_display_name_ = "PigMon Monitor"
    _svc_description_ = "Ping & Speed Monitor via PigMon – Windows Service"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        # Log servis başlatıldı
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            ("PigMon service started",)
        )

        # Python çalıştırıcısı ve script yolu
        python_exe = sys.executable
        script_path = os.path.join(os.path.dirname(__file__), "monitor.py")

        # monitor.py’yi çalıştır
        try:
            proc = subprocess.Popen([python_exe, script_path], cwd=os.path.dirname(script_path))
            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
            proc.terminate()
            proc.wait()
        except Exception as e:
            servicemanager.LogErrorMsg(f"PigMon service error: {e}")

        # Log servis durdu
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            ("PigMon service stopped",)
        )

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(PigMonService)
