-- Migrazione 005: ammette solo Caricato e Scaricato (NULL consentito per i record storici).
-- Il nome coincide con quello generato dal modello (convenzione ck_<tabella>_<nome>).
ALTER TABLE pezzi DROP CONSTRAINT IF EXISTS ck_pezzi_stato_valido;
ALTER TABLE pezzi ADD CONSTRAINT ck_pezzi_stato_valido CHECK (stato IS NULL OR stato IN ('Caricato', 'Scaricato'));
