-- Migration: add telegram_thread_id to seasons
-- Date: 2026-05-28
-- Purpose: like draft_telegram_thread_id but for the *general* season chat
--          (lineup images, season messages, alerts). Lets lineups and the
--          draft live in the same supergroup but in distinct topics.
--          Null = post to the chat's default thread (or to the chat directly
--          when topics are disabled).

ALTER TABLE seasons
    ADD COLUMN IF NOT EXISTS telegram_thread_id INTEGER;
