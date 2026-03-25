"""
OpenAgno Service Manager — Gateway como servicio en segundo plano.
El agente puede solicitar reload sin matarse a si mismo.

Uso:
  python service_manager.py start
  python service_manager.py stop
  python service_manager.py restart
  python service_manager.py status
"""
import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.resolve()))
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
PID_FILE = OPENAGNO_ROOT / "openagno.pid"
LOG_FILE = OPENAGNO_ROOT / "gateway.log"
HEALTH_URL = f"http://127.0.0.1:{PORT}/admin/health"
HEALTH_INTERVAL = 30
RESTART_DELAY = 3


class GatewayDaemon:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self._stop_event = threading.Event()

    def start_gateway(self) -> None:
        if self.process and self.process.poll() is None:
            print(f"[daemon] Gateway ya corriendo (PID {self.process.pid})")
            return
        log_fd = open(LOG_FILE, "a")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "gateway:app",
             "--host", HOST, "--port", str(PORT), "--workers", "1",
             "--log-level", "info"],
            cwd=str(OPENAGNO_ROOT),
            stdout=log_fd, stderr=subprocess.STDOUT,
            env={**os.environ, "OPENAGNO_ROOT": str(OPENAGNO_ROOT)},
        )
        PID_FILE.write_text(str(self.process.pid))
        print(f"[daemon] Gateway arrancado (PID {self.process.pid})")

    def stop_gateway(self, timeout: int = 10) -> None:
        if not self.process or self.process.poll() is not None:
            return
        pid = self.process.pid
        self.process.send_signal(signal.SIGTERM)
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if PID_FILE.exists():
            PID_FILE.unlink()
        print(f"[daemon] Gateway detenido (PID {pid})")

    def restart_gateway(self) -> None:
        self.stop_gateway()
        time.sleep(RESTART_DELAY)
        self.start_gateway()

    def health_check(self) -> bool:
        try:
            import urllib.request
            return urllib.request.urlopen(HEALTH_URL, timeout=5).status == 200
        except Exception:
            return False

    def monitor_loop(self) -> None:
        """Monitorea health + senal de reload."""
        signal_file = OPENAGNO_ROOT / ".reload_requested"
        while not self._stop_event.is_set():
            # Gateway murio -> reiniciar
            if self.process and self.process.poll() is not None:
                print(f"[daemon] Gateway murio (exit={self.process.returncode}). Reiniciando...")
                time.sleep(RESTART_DELAY)
                self.start_gateway()
            # Senal de reload del agente
            if signal_file.exists():
                print("[daemon] Senal de reload detectada.")
                signal_file.unlink()
                self.restart_gateway()
            self._stop_event.wait(HEALTH_INTERVAL)

    def run(self) -> None:
        self.start_gateway()
        monitor = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor.start()

        def _shutdown(signum, frame):
            self._stop_event.set()
            self.stop_gateway()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(1)
        except KeyboardInterrupt:
            _shutdown(signal.SIGINT, None)


def main():
    if len(sys.argv) < 2:
        print("Uso: python service_manager.py [start|stop|restart|status]")
        sys.exit(1)

    daemon = GatewayDaemon()
    cmd = sys.argv[1]

    match cmd:
        case "start":
            daemon.run()
        case "stop":
            if PID_FILE.exists():
                os.kill(int(PID_FILE.read_text().strip()), signal.SIGTERM)
            else:
                print("[daemon] No hay PID file")
        case "restart":
            if PID_FILE.exists():
                os.kill(int(PID_FILE.read_text().strip()), signal.SIGTERM)
                time.sleep(RESTART_DELAY)
            daemon.run()
        case "status":
            pid = PID_FILE.read_text().strip() if PID_FILE.exists() else "N/A"
            print(f"PID: {pid} | Health: {'OK' if daemon.health_check() else 'FAIL'}")
        case _:
            print(f"Comando desconocido: {cmd}")
            sys.exit(1)


if __name__ == "__main__":
    main()
