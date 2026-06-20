-- Marca cromo alias for Ben Doak. His full surname is "Gannon-Doak"
-- and Marca prints the compound form on the cromo, while
-- futbolfantasy stores him as just "Ben Doak". The matcher's hyphen
-- split would only see "doak" on the cromo side, so we add the
-- compound surname as an alias to bridge them.

UPDATE players SET aliases = 'Gannon-Doak' WHERE id = 6522 AND aliases IS NULL;
