-- Consegna a un PC specifico e conferma dell'esito, mantenendo lo storico.
ALTER TABLE scansioni_telefono ADD COLUMN IF NOT EXISTS destinatario VARCHAR(64);
ALTER TABLE scansioni_telefono ADD COLUMN IF NOT EXISTS presa_il TIMESTAMPTZ;
ALTER TABLE scansioni_telefono ADD COLUMN IF NOT EXISTS esito VARCHAR(16);
ALTER TABLE scansioni_telefono ADD COLUMN IF NOT EXISTS dettaglio VARCHAR(512);
CREATE INDEX IF NOT EXISTS ix_scansioni_telefono_destinatario ON scansioni_telefono (destinatario, letta, id);
CREATE TABLE IF NOT EXISTS richieste_api (utente VARCHAR(64) NOT NULL, chiave VARCHAR(64) NOT NULL, impronta VARCHAR(64) NOT NULL, risposta JSON NOT NULL, creata_il TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (utente, chiave));
CREATE INDEX IF NOT EXISTS ix_richieste_api_creata_il ON richieste_api (creata_il);
