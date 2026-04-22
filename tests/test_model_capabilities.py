# ruff: noqa: E402
"""Tests para openagno/core/model_capabilities.py."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openagno.core.model_capabilities import (
    DEFAULT_MODEL_CAPABILITIES,
    MODEL_CAPABILITIES,
    get_model_capabilities,
    model_supports,
)


class TestDefaults:
    def test_default_es_conservador(self):
        # Sin audio/image/video pero con tools habilitado.
        assert DEFAULT_MODEL_CAPABILITIES["audio"] is False
        assert DEFAULT_MODEL_CAPABILITIES["image"] is False
        assert DEFAULT_MODEL_CAPABILITIES["video"] is False
        assert DEFAULT_MODEL_CAPABILITIES["tools"] is True

    def test_modelo_desconocido_cae_al_default(self):
        caps = get_model_capabilities("openai-mystery-model-4000")
        assert caps == DEFAULT_MODEL_CAPABILITIES

    def test_modelo_vacio_o_none(self):
        assert get_model_capabilities(None) == DEFAULT_MODEL_CAPABILITIES
        assert get_model_capabilities("") == DEFAULT_MODEL_CAPABILITIES

    def test_get_devuelve_copia(self):
        caps = get_model_capabilities("gpt-5-mini")
        caps["audio"] = True
        # La tabla original no debe haber cambiado.
        assert MODEL_CAPABILITIES["gpt-5-mini"]["audio"] is False


class TestGemini:
    def test_gemini_2_5_flash_es_multimodal_completo(self):
        caps = get_model_capabilities("gemini-2.5-flash")
        assert caps == {"audio": True, "image": True, "video": True, "tools": True}

    def test_gemini_3_pro_preview_es_multimodal_completo(self):
        caps = get_model_capabilities("gemini-3-pro-preview")
        assert caps["audio"] and caps["image"] and caps["video"] and caps["tools"]


class TestOpenAI:
    def test_gpt_5_mini_soporta_vision_pero_no_audio(self):
        caps = get_model_capabilities("gpt-5-mini")
        assert caps["image"] is True
        assert caps["audio"] is False
        assert caps["video"] is False
        assert caps["tools"] is True


class TestAnthropic:
    def test_claude_sonnet_4_5_soporta_vision_no_audio(self):
        caps = get_model_capabilities("claude-sonnet-4-5-20250929")
        assert caps["image"] is True
        assert caps["audio"] is False


class TestBedrock:
    def test_claude_opus_bedrock_soporta_vision(self):
        caps = get_model_capabilities("us.anthropic.claude-opus-4-6-v1")
        assert caps["image"] is True
        assert caps["video"] is False

    def test_nova_pro_soporta_video(self):
        caps = get_model_capabilities("amazon.nova-pro-v1:0")
        assert caps["video"] is True
        assert caps["image"] is True

    def test_mistral_solo_texto(self):
        caps = get_model_capabilities("mistral.mistral-large-2402-v1:0")
        assert caps == {"audio": False, "image": False, "video": False, "tools": True}


class TestModelSupports:
    def test_model_supports_helper(self):
        assert model_supports("gemini-2.5-flash", "audio") is True
        assert model_supports("gpt-5-mini", "audio") is False
        assert model_supports("gpt-5-mini", "image") is True
        assert model_supports(None, "image") is False

    def test_capability_desconocida_es_false(self):
        assert model_supports("gpt-5-mini", "telepathy") is False
