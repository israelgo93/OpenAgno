"""
SchedulerTools — Gestion de crons via API REST nativa de AgentOS.
Docs: https://docs.agno.com/agent-os/scheduler/overview

El scheduler de AgentOS expone:
  POST   /schedules                 — crear
  GET    /schedules                 — listar
  PATCH  /schedules/{id}            — actualizar
  DELETE /schedules/{id}            — eliminar
  POST   /schedules/{id}/enable     — habilitar
  POST   /schedules/{id}/disable    — deshabilitar
  POST   /schedules/{id}/trigger    — ejecutar ahora
  GET    /schedules/{id}/runs       — historial
"""
import os
import json
import urllib.request
import urllib.error

from agno.tools import Toolkit
from agno.utils.log import logger

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000")


class SchedulerTools(Toolkit):
    """Gestiona crons y recordatorios via la API REST nativa del scheduler."""

    def __init__(self, base_url: str = GATEWAY_URL):
        super().__init__(name="scheduler_tools")
        self.base_url = base_url.rstrip("/")
        self.register(self.list_schedules)
        self.register(self.create_schedule)
        self.register(self.delete_schedule)
        self.register(self.trigger_schedule)

    def _api_call(self, method: str, path: str, data: dict | None = None) -> dict:
        """Llamada a la API REST del scheduler."""
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            url, data=body, method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    def list_schedules(self) -> str:
        """Lista todos los schedules/recordatorios activos."""
        result = self._api_call("GET", "/schedules")
        if "error" in result:
            return f"Error: {result['error']}"
        schedules = result if isinstance(result, list) else result.get("schedules", [])
        if not schedules:
            return "No hay schedules configurados."
        lines = []
        for s in schedules:
            status = "✅" if s.get("enabled", True) else "⏸️"
            lines.append(
                f"- {status} {s.get('name', '?')} | {s.get('cron_expr', '?')} | "
                f"→ {s.get('endpoint', '?')} | ID: {s.get('id', '?')}"
            )
        return "\n".join(lines)

    def create_schedule(
        self,
        name: str,
        cron_expr: str,
        message: str,
        agent_id: str = "agnobot-main",
        timezone: str = "America/Guayaquil",
    ) -> str:
        """Crea un recordatorio/schedule.

        Args:
            name: Nombre descriptivo (ej: "Resumen matutino")
            cron_expr: Expresion cron (ej: "0 9 * * 1-5" = L-V 9am)
            message: Mensaje que el agente procesara
            agent_id: ID del agente que ejecutara la tarea
            timezone: Zona horaria IANA
        """
        data = {
            "name": name,
            "cron_expr": cron_expr,
            "endpoint": f"/agents/{agent_id}/runs",
            "method": "POST",
            "payload": {"message": message},
            "timezone": timezone,
            "max_retries": 2,
            "retry_delay_seconds": 30,
        }
        result = self._api_call("POST", "/schedules", data)
        if "error" in result:
            return f"Error creando schedule: {result['error']}"
        return f"Schedule '{name}' creado ({cron_expr}, tz={timezone}). ID: {result.get('id', '?')}"

    def delete_schedule(self, schedule_id: str) -> str:
        """Elimina un schedule por ID."""
        result = self._api_call("DELETE", f"/schedules/{schedule_id}")
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Schedule {schedule_id} eliminado."

    def trigger_schedule(self, schedule_id: str) -> str:
        """Ejecuta un schedule manualmente ahora."""
        result = self._api_call("POST", f"/schedules/{schedule_id}/trigger")
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Schedule {schedule_id} ejecutado manualmente."
