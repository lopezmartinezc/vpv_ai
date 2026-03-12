-- =============================================================================
-- Liga VPV Fantasy -- Seed Data
-- =============================================================================
-- File   : 01_seed_data.sql
-- Purpose: Inserts the fixed reference data required for the application to
--          function. This data is static across all seasons.
-- Source : modelo_datos_vpv.md
-- Date   : 2026-02-23
-- =============================================================================


-- ----------------------------------------------------------------------------
-- valid_formations -- Formaciones permitidas (datos fijos)
-- Always 1 goalkeeper + 10 outfield players.
-- ----------------------------------------------------------------------------

INSERT INTO valid_formations (formation, defenders, midfielders, forwards) VALUES
('1-3-4-3', 3, 4, 3),
('1-3-5-2', 3, 5, 2),
('1-4-4-2', 4, 4, 2),
('1-4-3-3', 4, 3, 3),
('1-5-4-1', 5, 4, 1),
('1-5-3-2', 5, 3, 2),
('1-4-5-1', 4, 5, 1);
