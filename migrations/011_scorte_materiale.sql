-- Scorte aggregate per materiale senza perdere l'identità dei singoli barcode.
CREATE INDEX IF NOT EXISTS pezzi_materiale_attivo ON pezzi (profilo_id, colore_id, lunghezza_mm) WHERE eliminato_il IS NULL;
