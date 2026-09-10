from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AssistantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSISTANT_V2_", env_file=".env", extra="ignore")
    enabled: bool = True
    # A single reasoning call with an 8k output budget runs 30-60s: the model
    # thinks before it writes. The browser aborts at 190s and nginx's /api
    # read timeout is 300s, so the total stays under the former with margin.
    # See tests/test_timeouts.py.
    timeout_seconds: int = Field(default=150, ge=10, le=300)
    provider_timeout_seconds: int = Field(default=90, ge=5, le=180)
    # "¿A quién cojo en este pick?" legitimately chains eight or more tool
    # calls — board, picks, upcoming turns, rosters, fixtures, season form.
    # V1 shipped with eight rounds, production answered "me he quedado sin
    # vueltas consultando datos", and it was raised to twenty. V2 starts where
    # V1 ended rather than rediscovering the wall. See tests/test_budget.py.
    max_rounds: int = Field(default=20, ge=1, le=30)
    max_tool_calls: int = Field(default=30, ge=1, le=40)
    # Covers REASONING tokens as well as the visible answer on both providers.
    # A reasoning model spends the former before emitting the latter, so a
    # budget sized for prose alone comes back truncated with nothing in it —
    # which is exactly how V2 failed on its first real question with gpt-5.
    # See tests/test_output_budget.py.
    max_output_tokens: int = Field(default=8000, ge=256, le=32000)
    # Reasoning effort asked of OpenAI in "Rápido" mode. The first production
    # answer took 77 s at default effort — half a pick clock — on a question
    # the admin had marked quick. Detailed mode leaves it to the provider.
    # Empty disables the parameter (for a model that does not accept it).
    quick_effort: Literal["low", "medium", "high", ""] = "low"
    openai_models: list[str] = Field(default_factory=list)
    anthropic_models: list[str] = Field(default_factory=list)


config = AssistantSettings()
