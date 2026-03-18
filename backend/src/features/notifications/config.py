from __future__ import annotations

from pydantic_settings import BaseSettings


class VapidSettings(BaseSettings):
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@ligavpv.com"

    model_config = {"env_file": ".env", "extra": "ignore"}


vapid_settings = VapidSettings()
