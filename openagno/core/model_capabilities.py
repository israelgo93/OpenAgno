"""Tabla de capacidades multimodales por modelo del catalogo.

Mirror en Python de `OpenAgnoCloud/src/lib/workspace/model-capabilities.ts`.
El gateway la usa para decidir si transcribe audio, si pasa imagen/video
directo al agente, o si devuelve un mensaje explicativo al usuario cuando
el modelo no soporta la capacidad requerida.

Mantener sincronizada con la version TS. El test
`tests/test_model_capabilities.py` verifica el shape y los defaults.
"""

from __future__ import annotations

from typing import TypedDict


class ModelCapabilities(TypedDict):
	audio: bool
	image: bool
	video: bool
	tools: bool


DEFAULT_MODEL_CAPABILITIES: ModelCapabilities = {
	"audio": False,
	"image": False,
	"video": False,
	"tools": True,
}


MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
	# OpenAI GPT-5 family + GPT-4.1 (texto + vision + tools, sin audio/video nativo)
	"gpt-5-mini": {"audio": False, "image": True, "video": False, "tools": True},
	"gpt-5": {"audio": False, "image": True, "video": False, "tools": True},
	"gpt-5-nano": {"audio": False, "image": True, "video": False, "tools": True},
	"gpt-4.1-mini": {"audio": False, "image": True, "video": False, "tools": True},
	# Anthropic Claude 4.x / 4.5
	"claude-sonnet-4-5-20250929": {"audio": False, "image": True, "video": False, "tools": True},
	"claude-opus-4-5-20251101": {"audio": False, "image": True, "video": False, "tools": True},
	"claude-opus-4-1-20250805": {"audio": False, "image": True, "video": False, "tools": True},
	"claude-sonnet-4-20250514": {"audio": False, "image": True, "video": False, "tools": True},
	"claude-3-5-haiku-20241022": {"audio": False, "image": True, "video": False, "tools": True},
	# Google Gemini 2.5 y 3 (multimodal completo)
	"gemini-2.5-flash": {"audio": True, "image": True, "video": True, "tools": True},
	"gemini-2.5-pro": {"audio": True, "image": True, "video": True, "tools": True},
	"gemini-3-pro-preview": {"audio": True, "image": True, "video": True, "tools": True},
	"gemini-3-flash-preview": {"audio": True, "image": True, "video": True, "tools": True},
	"gemini-2.0-flash": {"audio": True, "image": True, "video": True, "tools": True},
	# AWS Bedrock Claude (vision + tools)
	"global.anthropic.claude-sonnet-4-5-20250929-v1:0": {"audio": False, "image": True, "video": False, "tools": True},
	"us.anthropic.claude-sonnet-4-5-20250929-v1:0": {"audio": False, "image": True, "video": False, "tools": True},
	"us.anthropic.claude-opus-4-6-v1": {"audio": False, "image": True, "video": False, "tools": True},
	"anthropic.claude-sonnet-4-20250514-v1:0": {"audio": False, "image": True, "video": False, "tools": True},
	"anthropic.claude-3-5-haiku-20241022-v2:0": {"audio": False, "image": True, "video": False, "tools": True},
	# Amazon Nova (Nova Pro tiene video, Nova Lite no)
	"amazon.nova-pro-v1:0": {"audio": False, "image": True, "video": True, "tools": True},
	"amazon.nova-lite-v1:0": {"audio": False, "image": True, "video": False, "tools": True},
	# Mistral on Bedrock (solo texto)
	"mistral.mistral-large-2402-v1:0": {"audio": False, "image": False, "video": False, "tools": True},
}


def get_model_capabilities(model_id: str | None) -> ModelCapabilities:
	"""Devuelve las capacidades declaradas para `model_id`.

	Cuando el modelo no esta en el catalogo se cae al default conservador
	(sin audio/image/video, con tools). El caller debe tratar el resultado
	como de solo lectura.
	"""
	if not model_id:
		return dict(DEFAULT_MODEL_CAPABILITIES)  # copia defensiva
	return dict(MODEL_CAPABILITIES.get(model_id, DEFAULT_MODEL_CAPABILITIES))


def model_supports(model_id: str | None, capability: str) -> bool:
	"""Helper boolean para lecturas puntuales."""
	caps = get_model_capabilities(model_id)
	return bool(caps.get(capability, False))
