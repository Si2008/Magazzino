-- Migrazione 006 (Fase 8): esagono #RRGGBB del colore reale associato al codice.
-- NULL = l'interfaccia usa il colore neutro (mai un colore casuale da hash).
ALTER TABLE colori ADD COLUMN IF NOT EXISTS colore_hex VARCHAR(7);
