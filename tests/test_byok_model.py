"""Tests for BYOK credentials flowing from workspace config into the Agno model.

This guards against a regression where we lose the per-tenant api_key/aws_*
and silently fall back to the operator's server .env.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_fake_agno_models(monkeypatch):
	"""Stub agno.models.<provider> to avoid touching external SDKs during tests.

	Only the leaf modules imported inside loader._build_single_model are replaced;
	the real `agno` and `agno.models` packages stay intact so the rest of the
	loader (Agent, MemoryManager, etc.) keeps working.
	"""
	# openai
	agno_openai = types.ModuleType("agno.models.openai")

	class FakeOpenAIChat:
		def __init__(self, id: str, api_key: Any | None = None, **rest: Any):
			self.id = id
			self.api_key = api_key
			self.rest = rest

	agno_openai.OpenAIChat = FakeOpenAIChat
	monkeypatch.setitem(sys.modules, "agno.models.openai", agno_openai)

	# anthropic
	agno_anthropic = types.ModuleType("agno.models.anthropic")

	class FakeAnthropicClaude:
		def __init__(self, id: str, api_key: Any | None = None, **rest: Any):
			self.id = id
			self.api_key = api_key
			self.rest = rest

	agno_anthropic.Claude = FakeAnthropicClaude
	monkeypatch.setitem(sys.modules, "agno.models.anthropic", agno_anthropic)

	# google
	agno_google = types.ModuleType("agno.models.google")

	class FakeGemini:
		def __init__(self, id: str, api_key: Any | None = None, **rest: Any):
			self.id = id
			self.api_key = api_key
			self.rest = rest

	agno_google.Gemini = FakeGemini
	monkeypatch.setitem(sys.modules, "agno.models.google", agno_google)

	# aws: both AwsBedrock and Claude (Bedrock Claude)
	agno_aws = types.ModuleType("agno.models.aws")

	class FakeAwsBedrock:
		def __init__(
			self,
			id: str,
			aws_region: str | None = None,
			aws_access_key_id: Any | None = None,
			aws_secret_access_key: Any | None = None,
			**rest: Any,
		):
			self.id = id
			self.aws_region = aws_region
			self.aws_access_key_id = aws_access_key_id
			self.aws_secret_access_key = aws_secret_access_key
			self.rest = rest

	class FakeBedrockClaude:
		def __init__(
			self,
			id: str,
			aws_region: str | None = None,
			aws_access_key: Any | None = None,
			aws_secret_key: Any | None = None,
			**rest: Any,
		):
			self.id = id
			self.aws_region = aws_region
			self.aws_access_key = aws_access_key
			self.aws_secret_key = aws_secret_key
			self.rest = rest

	agno_aws.AwsBedrock = FakeAwsBedrock
	agno_aws.Claude = FakeBedrockClaude
	monkeypatch.setitem(sys.modules, "agno.models.aws", agno_aws)

	return {
		"openai": FakeOpenAIChat,
		"anthropic": FakeAnthropicClaude,
		"google": FakeGemini,
		"aws_bedrock": FakeAwsBedrock,
		"aws_bedrock_claude": FakeBedrockClaude,
	}


@pytest.fixture
def fake_models(monkeypatch):
	return _install_fake_agno_models(monkeypatch)


def test_build_model_openai_forwards_tenant_api_key(fake_models, monkeypatch):
	# Force the env var to something we can detect, then assert the tenant key
	# overrides it via direct kwarg forwarding.
	monkeypatch.setenv("OPENAI_API_KEY", "env-fallback")
	from loader import build_model

	model = build_model({
		"provider": "openai",
		"id": "gpt-5-mini",
		"api_key": "tenant-openai-key",
	})

	assert isinstance(model, fake_models["openai"])
	assert model.id == "gpt-5-mini"
	assert model.api_key == "tenant-openai-key"


def test_build_model_openai_without_api_key_leaves_env_fallback(fake_models, monkeypatch):
	# When the tenant does NOT provide a key (operator scenario), we do not pass
	# api_key at all so Agno can read os.environ internally.
	monkeypatch.setenv("OPENAI_API_KEY", "env-fallback")
	from loader import build_model

	model = build_model({"provider": "openai", "id": "gpt-5-mini"})

	assert model.api_key is None  # kwarg not forwarded -> default None -> Agno reads env


def test_build_model_anthropic_forwards_api_key(fake_models):
	from loader import build_model

	model = build_model({
		"provider": "anthropic",
		"id": "claude-sonnet-4-5-20250929",
		"api_key": "tenant-anthropic-key",
	})

	assert isinstance(model, fake_models["anthropic"])
	assert model.api_key == "tenant-anthropic-key"


def test_build_model_google_forwards_api_key(fake_models):
	from loader import build_model

	model = build_model({
		"provider": "google",
		"id": "gemini-2.5-flash",
		"api_key": "tenant-google-key",
	})

	assert isinstance(model, fake_models["google"])
	assert model.api_key == "tenant-google-key"


def test_build_model_aws_bedrock_non_claude_uses_access_key_id(fake_models):
	from loader import build_model

	model = build_model({
		"provider": "aws_bedrock",
		"id": "amazon.nova-pro-v1:0",
		"aws_access_key_id": "AKIATENANT",
		"aws_secret_access_key": "secret-value",
		"aws_region": "us-east-1",
	})

	assert isinstance(model, fake_models["aws_bedrock"])
	assert model.aws_access_key_id == "AKIATENANT"
	assert model.aws_secret_access_key == "secret-value"
	assert model.aws_region == "us-east-1"


def test_build_model_aws_bedrock_claude_uses_access_key_without_id_suffix(fake_models):
	"""agno.models.aws.Claude uses aws_access_key (no `_id` suffix). The loader
	must translate aws_access_key_id from config to the correct kwarg name."""
	from loader import build_model

	model = build_model({
		"provider": "aws_bedrock_claude",
		"id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
		"aws_access_key_id": "AKIATENANT",
		"aws_secret_access_key": "secret-value",
		"aws_region": "us-east-1",
	})

	assert isinstance(model, fake_models["aws_bedrock_claude"])
	assert model.aws_access_key == "AKIATENANT"
	assert model.aws_secret_key == "secret-value"
	assert model.aws_region == "us-east-1"
