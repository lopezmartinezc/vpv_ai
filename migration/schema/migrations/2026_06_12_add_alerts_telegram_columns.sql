-- Dedicated alerts channel/topic per season.
-- Falls back to telegram_chat_id in TelegramService.send_alert when NULL.
-- Idempotent: safe to re-run.
ALTER TABLE seasons ADD COLUMN IF NOT EXISTS alerts_telegram_chat_id VARCHAR(50);
ALTER TABLE seasons ADD COLUMN IF NOT EXISTS alerts_telegram_thread_id INTEGER;
