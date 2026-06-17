-- Marca alias for Emiliano Martínez. The cromo prints him as
-- "'Dibu' Martinez" (the famous nickname), but Argentina has THREE
-- "Martínez" players in the roster (Emiliano, Lisandro, Lautaro).
-- The matcher already has tiebreakers but they can't recover this
-- one because "Dibu" doesn't appear anywhere in the display_name.
-- The alias lets the token-set matcher pick him directly.

UPDATE players SET aliases = 'Dibu' WHERE id = 6701 AND aliases IS NULL;
