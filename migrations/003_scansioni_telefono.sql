-- Migrazione 003 - coda delle scansioni inviate dal telefono al programma desktop.
CREATE TABLE IF NOT EXISTS scansioni_telefono (
    id SERIAL PRIMARY KEY,
    barcode VARCHAR(255) NOT NULL,
    utente VARCHAR(64) NOT NULL,
    creata_il TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    letta BOOLEAN NOT NULL DEFAULT FALSE
)
