from __future__ import annotations

from pydantic import BaseModel, Field


class WishlistPlayerItem(BaseModel):
    player_id: int
    display_name: str
    position: str | None = None
    team_name: str | None = None
    photo_path: str | None = None
    is_already_picked: bool
    priority: int


class WishlistResponse(BaseModel):
    draft_id: int
    participant_id: int
    enabled: bool
    players: list[WishlistPlayerItem]


class WishlistUpsertRequest(BaseModel):
    enabled: bool = True
    player_ids: list[int] = Field(default_factory=list, max_length=50)


class WishlistToggleRequest(BaseModel):
    enabled: bool


class AdminWishlistResponse(BaseModel):
    """Audit view — exposes ONLY metadata, never the player list.

    The wishlist contents are private to each participant; the admin
    learns that someone has configured one and how many entries it
    holds, but not which players. This keeps the admin from inferring
    rival draft strategy through `/drafts/gestionar`.
    """

    participant_id: int
    display_name: str
    enabled: bool
    total: int
