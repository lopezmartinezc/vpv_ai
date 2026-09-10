"""Choosing the provider per question, from the chat.

Both keys live in the .env; which one answers is picked in the UI. That means
the provider name now arrives from the client, so it has to be validated like
any other untrusted input — and a provider whose key is missing must fail with
a clear message instead of a confusing auth error from the vendor.
"""

from __future__ import annotations

import pytest

from src.core.config import settings
from src.core.exceptions import BusinessRuleError
from src.features.draft_assistant.service import available_providers, build_provider


@pytest.fixture
def both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "openai_api_key", "sk-oai-test")
    monkeypatch.setattr(settings, "assistant_provider", "anthropic")


@pytest.fixture
def only_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "assistant_provider", "anthropic")


def test_explicit_choice_wins_over_the_default(both_keys: None) -> None:
    assert build_provider("openai").name == "openai"
    assert build_provider("anthropic").name == "anthropic"


def test_no_choice_falls_back_to_the_configured_default(both_keys: None) -> None:
    assert build_provider(None).name == "anthropic"


def test_choosing_a_provider_without_a_key_says_so(only_anthropic: None) -> None:
    """Better a clear 'missing key' than a 401 from the vendor mid-draft."""
    with pytest.raises(BusinessRuleError, match="OPENAI_API_KEY"):
        build_provider("openai")


def test_an_invented_provider_is_rejected(both_keys: None) -> None:
    """The name now comes from the client, so it is untrusted input."""
    with pytest.raises(BusinessRuleError):
        build_provider("gemini")


def test_available_lists_only_providers_with_a_key(only_anthropic: None) -> None:
    assert available_providers() == ["anthropic"]


def test_available_lists_both_when_both_are_configured(both_keys: None) -> None:
    assert sorted(available_providers()) == ["anthropic", "openai"]


def test_available_is_empty_when_nothing_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert available_providers() == []


# --------------------------------------------------------------------------
# Model choice
# --------------------------------------------------------------------------


def test_explicit_model_wins_over_the_configured_default(both_keys: None) -> None:
    assert build_provider("anthropic", "claude-sonnet-5").model == "claude-sonnet-5"


def test_no_model_uses_the_provider_default(
    both_keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "assistant_anthropic_model", "claude-opus-5")
    assert build_provider("anthropic", None).model == "claude-opus-5"


def test_the_model_default_is_per_provider(
    both_keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Switching provider must not carry the other one's model across."""
    monkeypatch.setattr(settings, "assistant_anthropic_model", "claude-opus-5")
    monkeypatch.setattr(settings, "assistant_openai_model", "gpt-5")
    assert build_provider("anthropic").model == "claude-opus-5"
    assert build_provider("openai").model == "gpt-5"


def test_a_model_id_with_junk_in_it_is_rejected(both_keys: None) -> None:
    """The model name comes from the client like everything else."""
    with pytest.raises(BusinessRuleError, match="Modelo no valido"):
        build_provider("anthropic", "claude-opus-5; rm -rf /")


def test_a_comment_suffix_on_the_model_setting_is_tolerated(
    both_keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """systemd EnvironmentFile again — see test_settings_parsing."""
    monkeypatch.setattr(settings, "assistant_anthropic_model", "claude-opus-5  # el bueno")
    assert build_provider("anthropic").model == "claude-opus-5"


# --------------------------------------------------------------------------
# Which provider the chat lands on
# --------------------------------------------------------------------------


def test_openai_is_offered_first(both_keys: None) -> None:
    """The panel falls back to the first available provider when the configured
    default has no key, so the order decides what people actually see."""
    assert available_providers()[0] == "openai"
