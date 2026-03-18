from __future__ import annotations

from src.core.config import settings


class VapidSettings:
    @property
    def vapid_public_key(self) -> str:
        return settings.vapid_public_key

    @property
    def vapid_private_key(self) -> str:
        return settings.vapid_private_key

    @property
    def vapid_subject(self) -> str:
        return settings.vapid_subject


vapid_settings = VapidSettings()
