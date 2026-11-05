-- Nessuna divisione automatica dei record storici: conserva ID e movimenti.
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS unitario BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE pezzi DROP CONSTRAINT IF EXISTS uq_pezzi_combinazione;
ALTER TABLE pezzi DROP CONSTRAINT IF EXISTS combinazione;
CREATE UNIQUE INDEX IF NOT EXISTS combinazione_legacy ON pezzi (profilo_id, colore_id, lunghezza_mm) WHERE NOT unitario;
ALTER TABLE pezzi DROP CONSTRAINT IF EXISTS ck_pezzi_pezzo_unitario_quantita;
ALTER TABLE pezzi ADD CONSTRAINT ck_pezzi_pezzo_unitario_quantita CHECK (NOT unitario OR quantita IN (0,1)) NOT VALID;
