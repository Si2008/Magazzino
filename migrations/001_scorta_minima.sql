-- Migrazione 001: scorta minima per gli avvisi di scorte basse.
-- Aggiunge la colonna alla tabella esistente senza modificarla.
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS scorta_minima INTEGER;
