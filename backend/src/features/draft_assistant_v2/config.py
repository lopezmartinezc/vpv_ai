from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AssistantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSISTANT_V2_", env_file=".env", extra="ignore")
    enabled: bool = True
    timeout_seconds: int = Field(default=75, ge=10, le=180)
    provider_timeout_seconds: int = Field(default=25, ge=5, le=60)
    # "¿A quién cojo en este pick?" legitimately chains eight or more tool
    # calls — board, picks, upcoming turns, rosters, fixtures, season form.
    # V1 shipped with eight rounds, production answered "me he quedado sin
    # vueltas consultando datos", and it was raised to twenty. V2 starts where
    # V1 ended rather than rediscovering the wall. See tests/test_budget.py.
    max_rounds: int = Field(default=20, ge=1, le=30)
    max_tool_calls: int = Field(default=30, ge=1, le=40)
    max_output_tokens: int = Field(default=2000, ge=256, le=4000)
    openai_models: list[str] = Field(default_factory=list)
    anthropic_models: list[str] = Field(default_factory=list)


config = AssistantSettings()
