import sys
import types

import pytest

import config
import llm_provider


class TestSecrets:
    def test_missing_key_stops_startup_with_a_clear_message(self, monkeypatch):
        monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
        with pytest.raises(config.ConfigError, match="EMERGENT_LLM_KEY"):
            config.validate_settings()

    def test_blank_key_counts_as_missing(self, monkeypatch):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "   ")
        with pytest.raises(config.ConfigError):
            config.validate_settings()

    def test_key_is_masked_in_logs(self, monkeypatch, caplog):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-emergent-ABCDEFGH1234")
        with caplog.at_level("INFO"):
            config.validate_settings()
        assert "sk-emergent-ABCDEFGH1234" not in caplog.text
        assert "sk-e...34" in caplog.text

    @pytest.mark.parametrize("secret,expected", [("", "(not set)"), ("short", "***"), ("sk-emergent-ABCDEFGH1234", "sk-e...34")])
    def test_mask_secret(self, secret, expected):
        assert config.mask_secret(secret) == expected

    def test_wildcard_cors_warns(self, monkeypatch, caplog):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "k" * 12)
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        with caplog.at_level("WARNING"):
            config.validate_settings()
        assert "CORS_ORIGINS" in caplog.text

    def test_cors_origins_are_split_and_trimmed(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example ,")
        assert config.get_cors_origins() == ["https://a.example", "https://b.example"]


class TestProviderSelection:
    @pytest.fixture
    def fake_library(self, monkeypatch):
        """Stand-in for emergentintegrations so the adapter can be tested without it"""
        created = []

        class UserMessage:
            def __init__(self, text):
                self.text = text

        class LlmChat:
            def __init__(self, api_key, session_id, system_message):
                self.session_id = session_id
                self.model = None
                created.append(self)

            def with_model(self, vendor, model):
                self.model = (vendor, model)
                return self

            async def send_message(self, message):
                return f"echo:{message.text}"

        for name in ("emergentintegrations", "emergentintegrations.llm", "emergentintegrations.llm.chat"):
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        sys.modules["emergentintegrations.llm.chat"].LlmChat = LlmChat
        sys.modules["emergentintegrations.llm.chat"].UserMessage = UserMessage
        return created

    def test_default_is_emergent_with_gpt4o(self, monkeypatch, fake_library):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        provider = llm_provider.get_llm_provider()
        assert provider.name == "emergent" and provider._model == "gpt-4o"

    def test_unknown_provider_is_rejected(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "mystery")
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            llm_provider.get_llm_provider()

    def test_empty_key_is_rejected(self, monkeypatch, fake_library):
        monkeypatch.setenv("EMERGENT_LLM_KEY", "")
        with pytest.raises(ValueError, match="EMERGENT_LLM_KEY"):
            llm_provider.get_llm_provider()

    async def test_each_call_gets_its_own_chat_session(self, fake_library):
        provider = llm_provider.EmergentProvider(api_key="k")
        await provider.complete("one", "sys", "scan-1")
        await provider.complete("two", "sys", "scan-2")
        await provider.complete("three", "sys", "scan-1")
        sessions = [chat.session_id for chat in fake_library]
        assert len(fake_library) == 3  # no shared chat object, so no shared history
        assert sessions[0] == sessions[2] == "resume-scan-scan-1"
        assert sessions[1] == "resume-scan-scan-2"
        assert "resume-scanner" not in sessions
