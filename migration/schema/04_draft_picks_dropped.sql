-- Add dropped_player_id to draft_picks for winter draft swaps
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'draft_picks' AND column_name = 'dropped_player_id'
    ) THEN
        ALTER TABLE draft_picks ADD COLUMN dropped_player_id INT REFERENCES players(id);
    END IF;
END $$;
