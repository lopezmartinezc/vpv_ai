-- Migration: add draft_telegram_thread_id to seasons
-- Date: 2026-05-28
-- Purpose: support Telegram supergroups with topics/forums enabled. The
--          draft broadcast can target a specific topic by passing
--          `message_thread_id` to the Bot API; this column stores it.
--          Null = send to the general topic (or to the main chat if the
--          group has no topics).

ALTER TABLE seasons
    ADD COLUMN IF NOT EXISTS draft_telegram_thread_id INTEGER;
