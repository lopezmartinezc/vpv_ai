-- Migration: add draft_telegram_chat_id to seasons
-- Date: 2026-05-22
-- Purpose: dedicated Telegram channel for live draft pick broadcasts.
--          Separate from seasons.telegram_chat_id so the draft can have its
--          own private channel (e.g. only the 16 participants).

ALTER TABLE seasons
    ADD COLUMN IF NOT EXISTS draft_telegram_chat_id VARCHAR(50);
