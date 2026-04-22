"""Workspace provisioning helpers for tenant-specific workspaces."""

from __future__ import annotations

import os
import shutil
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import yaml


class WorkspaceStore:
	"""Provision tenant workspaces from packaged templates or S3-backed copies."""

	def __init__(
		self,
		*,
		backend: str = "local",
		base_dir: str | Path | None = None,
		s3_bucket: str | None = None,
	):
		self.backend = backend
		self.base_dir = Path(base_dir or os.getenv("OPENAGNO_TENANT_WORKSPACES_DIR", "workspaces")).resolve()
		self.s3_bucket = s3_bucket or os.getenv("OPENAGNO_TENANT_S3_BUCKET")
		self.base_dir.mkdir(parents=True, exist_ok=True)

	def workspace_path(self, tenant_slug: str) -> Path:
		return self.base_dir / tenant_slug / "workspace"

	def provision(
		self,
		tenant_slug: str,
		*,
		template: str = "personal_assistant",
		workspace_config: dict[str, Any] | None = None,
		force: bool = False,
	) -> Path:
		if self.backend == "s3":
			return self._provision_from_s3(tenant_slug)

		target = self.workspace_path(tenant_slug)
		if target.exists() and any(target.iterdir()) and not force:
			if workspace_config:
				self.write_config(tenant_slug, workspace_config)
			return target

		if target.exists() and force:
			shutil.rmtree(target)

		template_resource = files("openagno.templates").joinpath(template)
		with as_file(template_resource) as template_path:
			shutil.copytree(template_path, target, dirs_exist_ok=True)

		if workspace_config:
			self.write_config(tenant_slug, workspace_config)
		return target

	def read_config(self, tenant_slug: str) -> dict[str, Any]:
		config_path = self.workspace_path(tenant_slug) / "config.yaml"
		if not config_path.exists():
			return {}
		return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

	def write_config(self, tenant_slug: str, updates: dict[str, Any]) -> dict[str, Any]:
		if self.backend == "s3":
			raise RuntimeError("write_config is not supported for the S3 workspace backend")

		workspace_dir = self.workspace_path(tenant_slug)
		workspace_dir.mkdir(parents=True, exist_ok=True)
		config_path = workspace_dir / "config.yaml"
		current = self.read_config(tenant_slug)
		current.update(updates)

		# Derrame a archivos que lee el loader del runtime. Estos campos
		# "meta" (instructions, self_knowledge, tools_yaml, mcp_yaml) viven
		# dentro del dict del Cloud por conveniencia pero el loader del OSS
		# espera archivos separados, no objetos dentro del config.yaml.
		instructions_value = current.get("instructions")
		if isinstance(instructions_value, str) and instructions_value.strip():
			(workspace_dir / "instructions.md").write_text(
				instructions_value, encoding="utf-8"
			)
		self_knowledge_value = current.get("self_knowledge")
		if isinstance(self_knowledge_value, str) and self_knowledge_value.strip():
			(workspace_dir / "self_knowledge.md").write_text(
				self_knowledge_value, encoding="utf-8"
			)

		# Nuevo (saneamiento 2026-04-22): el dict puede traer `tools_yaml`
		# y `mcp_yaml` con la estructura nativa de tools.yaml/mcp.yaml que
		# el loader espera. Los escribimos como archivos separados y los
		# quitamos del config.yaml para que no quede basura duplicada.
		tools_yaml_value = current.pop("tools_yaml", None)
		if isinstance(tools_yaml_value, dict) and tools_yaml_value:
			(workspace_dir / "tools.yaml").write_text(
				yaml.safe_dump(tools_yaml_value, allow_unicode=True, sort_keys=False),
				encoding="utf-8",
			)
		mcp_yaml_value = current.pop("mcp_yaml", None)
		if isinstance(mcp_yaml_value, dict) and mcp_yaml_value:
			(workspace_dir / "mcp.yaml").write_text(
				yaml.safe_dump(mcp_yaml_value, allow_unicode=True, sort_keys=False),
				encoding="utf-8",
			)

		config_path.write_text(
			yaml.safe_dump(current, allow_unicode=True, sort_keys=False),
			encoding="utf-8",
		)

		return current

	def _provision_from_s3(self, tenant_slug: str) -> Path:
		if not self.s3_bucket:
			raise RuntimeError("OPENAGNO_TENANT_S3_BUCKET is required for the S3 workspace backend")

		import boto3

		target = self.workspace_path(tenant_slug)
		target.mkdir(parents=True, exist_ok=True)
		client = boto3.client("s3")
		prefix = f"tenants/{tenant_slug}/workspace/"
		paginator = client.get_paginator("list_objects_v2")
		for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
			for obj in page.get("Contents", []):
				key = obj["Key"]
				relative = key.removeprefix(prefix)
				if not relative:
					continue
				destination = target / relative
				destination.parent.mkdir(parents=True, exist_ok=True)
				client.download_file(self.s3_bucket, key, str(destination))
		return target
