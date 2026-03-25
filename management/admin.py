"""
Admin - Gestion programatica via AgentOSClient.

Uso como CLI:
	python -m management.admin status
	python -m management.admin sessions --user +593991234567
	python -m management.admin memories --user +593991234567
	python -m management.admin run --agent agnobot-main --message "Hola"
	python -m management.admin knowledge-search --query "documento"

Uso como modulo:
	from management.admin import AdminClient
	admin = AdminClient("http://localhost:8000")
	await admin.status()
"""
import asyncio
import argparse
import sys
from typing import Optional

from agno.client import AgentOSClient
from agno.run.agent import RunContentEvent, RunCompletedEvent


class AdminClient:
	"""Wrapper de AgentOSClient con operaciones de administracion."""

	def __init__(self, base_url: str = "http://localhost:8000"):
		self.client = AgentOSClient(base_url=base_url)

	async def status(self) -> dict[str, list[str]]:
		"""Obtiene configuracion y estado del AgentOS."""
		config = await self.client.aget_config()
		return {
			"name": config.name or config.os_id,
			"agents": [a.id for a in (config.agents or [])],
			"teams": [t.id for t in (config.teams or [])],
			"workflows": [w.id for w in (config.workflows or [])],
		}

	async def list_sessions(self, user_id: str) -> list[dict[str, str]]:
		"""Lista sesiones de un usuario."""
		sessions = await self.client.get_sessions(user_id=user_id)
		return [
			{
				"session_id": s.session_id,
				"name": s.session_name or "Sin nombre",
			}
			for s in sessions.data
		]

	async def get_session_detail(self, session_id: str) -> list[dict[str, Optional[str]]]:
		"""Obtiene los runs de una sesion."""
		runs = await self.client.get_session_runs(session_id=session_id)
		return [
			{
				"run_id": r.run_id,
				"content": (str(r.content)[:100] + "...") if r.content and len(str(r.content)) > 100 else str(r.content),
			}
			for r in runs
		]

	async def delete_session(self, session_id: str) -> None:
		"""Elimina una sesion."""
		await self.client.delete_session(session_id)

	async def list_memories(self, user_id: str) -> list[dict[str, object]]:
		"""Lista memorias de un usuario."""
		memories = await self.client.list_memories(user_id=user_id)
		return [
			{
				"memory_id": m.memory_id,
				"memory": m.memory,
				"topics": getattr(m, "topics", []),
			}
			for m in memories.data
		]

	async def create_memory(
		self,
		user_id: str,
		memory: str,
		topics: Optional[list[str]] = None,
	) -> dict[str, str]:
		"""Crea una memoria para un usuario."""
		result = await self.client.create_memory(
			memory=memory,
			user_id=user_id,
			topics=topics or [],
		)
		return {
			"memory_id": result.memory_id,
			"memory": result.memory,
		}

	async def delete_memory(self, memory_id: str, user_id: str) -> None:
		"""Elimina una memoria."""
		await self.client.delete_memory(memory_id, user_id=user_id)

	async def run_agent(
		self,
		agent_id: str,
		message: str,
		user_id: str = "admin",
		session_id: Optional[str] = None,
	) -> str:
		"""Ejecuta el agente y retorna la respuesta completa."""
		result = await self.client.run_agent(
			agent_id=agent_id,
			message=message,
			user_id=user_id,
			session_id=session_id,
		)
		return result.content or ""

	async def run_agent_stream(
		self,
		agent_id: str,
		message: str,
		user_id: str = "admin",
		session_id: Optional[str] = None,
	) -> str:
		"""Ejecuta el agente con streaming."""
		full_response: list[str] = []
		async for event in self.client.run_agent_stream(
			agent_id=agent_id,
			message=message,
			user_id=user_id,
			session_id=session_id,
		):
			if isinstance(event, RunContentEvent):
				print(event.content, end="", flush=True)
				full_response.append(event.content)
			elif isinstance(event, RunCompletedEvent):
				print()
		return "".join(full_response)

	async def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, object]]:
		"""Busca en la Knowledge Base via AgentOS API."""
		results = await self.client.search_knowledge(query=query, limit=limit)
		return [
			{
				"content": str(r.content)[:200] if hasattr(r, "content") else str(r)[:200],
				"score": getattr(r, "score", None),
			}
			for r in results.data
		]


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="admin",
		description="OpenAgno - Herramienta de administracion",
	)
	parser.add_argument(
		"--url",
		default="http://localhost:8000",
		help="URL del AgentOS (default: http://localhost:8000)",
	)
	sub = parser.add_subparsers(dest="command", required=True)

	sub.add_parser("status", help="Estado del AgentOS")

	p_sessions = sub.add_parser("sessions", help="Listar sesiones")
	p_sessions.add_argument("--user", required=True, help="User ID")

	p_detail = sub.add_parser("session-detail", help="Detalle de una sesion")
	p_detail.add_argument("--session-id", required=True)

	p_del_sess = sub.add_parser("delete-session", help="Eliminar sesion")
	p_del_sess.add_argument("--session-id", required=True)

	p_mem = sub.add_parser("memories", help="Listar memorias")
	p_mem.add_argument("--user", required=True)

	p_cmem = sub.add_parser("create-memory", help="Crear memoria")
	p_cmem.add_argument("--user", required=True)
	p_cmem.add_argument("--memory", required=True)
	p_cmem.add_argument("--topics", nargs="*", default=[])

	p_dmem = sub.add_parser("delete-memory", help="Eliminar memoria")
	p_dmem.add_argument("--memory-id", required=True)
	p_dmem.add_argument("--user", required=True)

	p_run = sub.add_parser("run", help="Ejecutar agente")
	p_run.add_argument("--agent", default="agnobot-main")
	p_run.add_argument("--message", required=True)
	p_run.add_argument("--user", default="admin")
	p_run.add_argument("--stream", action="store_true")

	p_ks = sub.add_parser("knowledge-search", help="Buscar en Knowledge Base")
	p_ks.add_argument("--query", required=True)
	p_ks.add_argument("--limit", type=int, default=5)

	return parser


async def _run_cli(args: argparse.Namespace) -> None:
	admin = AdminClient(base_url=args.url)

	match args.command:
		case "status":
			info = await admin.status()
			print(f"\n{info['name']}")
			print(f"   Agentes: {', '.join(info['agents']) or 'ninguno'}")
			print(f"   Teams:   {', '.join(info['teams']) or 'ninguno'}")

		case "sessions":
			sessions = await admin.list_sessions(args.user)
			print(f"\nSesiones de {args.user} ({len(sessions)}):")
			for s in sessions:
				print(f"  - {s['session_id']}: {s['name']}")

		case "session-detail":
			runs = await admin.get_session_detail(args.session_id)
			print(f"\nRuns en sesion ({len(runs)}):")
			for r in runs:
				print(f"  - {r['run_id']}: {r['content']}")

		case "delete-session":
			await admin.delete_session(args.session_id)
			print(f"Sesion {args.session_id} eliminada")

		case "memories":
			memories = await admin.list_memories(args.user)
			print(f"\nMemorias de {args.user} ({len(memories)}):")
			for m in memories:
				topics = ", ".join(m["topics"]) if m["topics"] else "sin topics"
				print(f"  - [{topics}] {m['memory']}")

		case "create-memory":
			result = await admin.create_memory(args.user, args.memory, args.topics)
			print(f"Memoria creada: {result['memory_id']}")

		case "delete-memory":
			await admin.delete_memory(args.memory_id, args.user)
			print(f"Memoria {args.memory_id} eliminada")

		case "run":
			print(f"\nEjecutando {args.agent}...\n")
			if args.stream:
				await admin.run_agent_stream(args.agent, args.message, args.user)
			else:
				response = await admin.run_agent(args.agent, args.message, args.user)
				print(response)

		case "knowledge-search":
			results = await admin.search_knowledge(args.query, args.limit)
			print(f"\nResultados para '{args.query}' ({len(results)}):")
			for i, r in enumerate(results, 1):
				score = f" (score: {r['score']:.3f})" if r["score"] else ""
				print(f"  {i}.{score} {r['content']}")

		case _:
			print(f"Comando desconocido: {args.command}")


def main() -> None:
	parser = _build_parser()
	args = parser.parse_args()
	try:
		asyncio.run(_run_cli(args))
	except Exception as e:
		print(f"\nError: {e}")
		sys.exit(1)


if __name__ == "__main__":
	main()
