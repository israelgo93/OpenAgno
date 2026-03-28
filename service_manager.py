"""
OpenAgno local supervisor helper.

Este modulo se invoca desde `openagno start`, `openagno stop`,
`openagno restart` y `openagno status` para manejar el gateway en background.
"""
import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path
from dotenv import load_dotenv

from openagno.core.process_utils import (
	IS_WINDOWS,
	is_pid_running,
	read_pid_file,
	terminate_pid,
)

load_dotenv()

OPENAGNO_ROOT = Path(os.getenv("OPENAGNO_ROOT", Path(__file__).parent.resolve()))
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
PID_FILE = OPENAGNO_ROOT / "openagno.pid"
LOG_FILE = OPENAGNO_ROOT / "gateway.log"
HEALTH_URL = f"http://127.0.0.1:{PORT}/admin/health"
HEALTH_INTERVAL = 15
RESTART_DELAY = 3
MAX_START_WAIT = 30


class GatewayDaemon:
	def __init__(self) -> None:
		self.process: subprocess.Popen | None = None
		self._stop_event = threading.Event()
		self._log_fd = None

	def _open_log(self):
		if self._log_fd and not self._log_fd.closed:
			self._log_fd.close()
		self._log_fd = open(LOG_FILE, "a", buffering=1)
		return self._log_fd

	def start_gateway(self) -> None:
		if self.process and self.process.poll() is None:
			print(f"[daemon] Gateway ya corriendo (PID {self.process.pid})")
			return

		log_fd = self._open_log()

		env = {**os.environ, "OPENAGNO_ROOT": str(OPENAGNO_ROOT)}
		env["PYTHONUNBUFFERED"] = "1"

		self.process = subprocess.Popen(
			[sys.executable, "-u", "gateway.py"],
			cwd=str(OPENAGNO_ROOT),
			stdout=log_fd,
			stderr=subprocess.STDOUT,
			env=env,
		)
		PID_FILE.write_text(str(self.process.pid))
		print(f"[daemon] Gateway arrancado (PID {self.process.pid})")

		# Esperar a que el health check responda
		started = time.time()
		while time.time() - started < MAX_START_WAIT:
			if self.process.poll() is not None:
				print(f"[daemon] Gateway fallo al arrancar (exit={self.process.returncode})")
				print(f"[daemon] Revisa el log: {LOG_FILE}")
				return
			if self.health_check():
				elapsed = time.time() - started
				print(f"[daemon] Gateway listo en {elapsed:.1f}s -> http://{HOST}:{PORT}")
				return
			time.sleep(1)

		print(f"[daemon] Gateway arrancado pero health check no responde tras {MAX_START_WAIT}s")

	def stop_gateway(self, timeout: int = 10) -> None:
		if not self.process or self.process.poll() is not None:
			if PID_FILE.exists():
				PID_FILE.unlink()
			return
		pid = self.process.pid
		if IS_WINDOWS:
			self.process.terminate()
		else:
			self.process.send_signal(signal.SIGTERM)
		try:
			self.process.wait(timeout=timeout)
		except subprocess.TimeoutExpired:
			self.process.kill()
			self.process.wait()
		if PID_FILE.exists():
			PID_FILE.unlink()
		if self._log_fd and not self._log_fd.closed:
			self._log_fd.close()
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
		health_fails = 0
		while not self._stop_event.is_set():
			# Gateway murio -> reiniciar
			if self.process and self.process.poll() is not None:
				print(f"[daemon] Gateway murio (exit={self.process.returncode}). Reiniciando...")
				time.sleep(RESTART_DELAY)
				self.start_gateway()
				health_fails = 0
			# Senal de reload del agente
			elif signal_file.exists():
				print("[daemon] Senal de reload detectada.")
				signal_file.unlink()
				self.restart_gateway()
				health_fails = 0
			# Health check periodico
			elif self.process and self.process.poll() is None:
				if not self.health_check():
					health_fails += 1
					if health_fails >= 3:
						print(f"[daemon] Health check fallo {health_fails} veces. Reiniciando...")
						self.restart_gateway()
						health_fails = 0
				else:
					health_fails = 0
			self._stop_event.wait(HEALTH_INTERVAL)

	def run(self) -> None:
		self.start_gateway()
		monitor = threading.Thread(target=self.monitor_loop, daemon=True)
		monitor.start()

		def _shutdown(signum, frame):
			print("\n[daemon] Apagando...")
			self._stop_event.set()
			self.stop_gateway()
			sys.exit(0)

		if hasattr(signal, "SIGTERM"):
			signal.signal(signal.SIGTERM, _shutdown)
		signal.signal(signal.SIGINT, _shutdown)
		try:
			while not self._stop_event.is_set():
				self._stop_event.wait(1)
		except KeyboardInterrupt:
			_shutdown(signal.SIGINT, None)


def _kill_existing() -> bool:
	"""Detiene el proceso existente si hay PID file."""
	pid = read_pid_file(PID_FILE)
	if pid is None:
		return False
	if not is_pid_running(pid):
		PID_FILE.unlink(missing_ok=True)
		return False
	stopped = terminate_pid(pid)
	PID_FILE.unlink(missing_ok=True)
	if stopped:
		print(f"[daemon] Proceso anterior detenido (PID {pid})")
	return stopped


def main() -> None:
	if len(sys.argv) < 2:
		print("Usa: openagno start | openagno stop | openagno restart | openagno status")
		sys.exit(1)

	cmd = sys.argv[1]

	match cmd:
		case "start":
			_kill_existing()
			GatewayDaemon().run()
		case "stop":
			if not _kill_existing():
				print("[daemon] No hay proceso corriendo")
		case "restart":
			_kill_existing()
			time.sleep(RESTART_DELAY)
			GatewayDaemon().run()
		case "status":
			daemon = GatewayDaemon()
			pid = read_pid_file(PID_FILE)
			pid_display = str(pid) if pid is not None else "N/A"
			healthy = daemon.health_check()
			running = is_pid_running(pid) if pid is not None else False
			print(f"PID: {pid_display} | Proceso: {'ACTIVO' if running else 'INACTIVO'} | Health: {'OK' if healthy else 'FAIL'}")
			if healthy:
				try:
					import urllib.request
					import json
					resp = urllib.request.urlopen(HEALTH_URL, timeout=5)
					data = json.loads(resp.read())
					print(f"Agentes: {data.get('agents', [])}")
					print(f"Canales: {data.get('channels', [])}")
					print(f"Modelo: {data.get('model', {}).get('provider', '?')}/{data.get('model', {}).get('id', '?')}")
				except Exception:
					pass
		case _:
			print(f"Comando desconocido: {cmd}")
			sys.exit(1)


if __name__ == "__main__":
	main()
