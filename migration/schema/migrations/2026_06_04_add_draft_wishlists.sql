-- Migration: add draft_wishlists + draft_wishlist_players
-- Date: 2026-06-04
-- Purpose: support the participant auto-pick wishlist. Each participant
--          can register a prioritized list of players in advance; when
--          their turn arrives in the draft, the system picks the first
--          available one from that list automatically.

CREATE TABLE IF NOT EXISTS draft_wishlists (
    id             SERIAL PRIMARY KEY,
    draft_id       INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    participant_id INTEGER NOT NULL REFERENCES season_participants(id) ON DELETE CASCADE,
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_wishlist_draft_participant UNIQUE (draft_id, participant_id)
);

CREATE TABLE IF NOT EXISTS draft_wishlist_players (
    id          SERIAL PRIMARY KEY,
    wishlist_id INTEGER NOT NULL REFERENCES draft_wishlists(id) ON DELETE CASCADE,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    priority    SMALLINT NOT NULL,
    CONSTRAINT uq_wishlist_player UNIQUE (wishlist_id, player_id),
    CONSTRAINT uq_wishlist_priority UNIQUE (wishlist_id, priority)
);

CREATE INDEX IF NOT EXISTS idx_wishlist_players_wishlist
    ON draft_wishlist_players(wishlist_id, priority);
