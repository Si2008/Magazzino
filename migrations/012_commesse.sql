CREATE TABLE IF NOT EXISTS commesse (
 id SERIAL PRIMARY KEY, identita VARCHAR(64) NOT NULL UNIQUE,
 cognome VARCHAR(200) NOT NULL, cognome_chiave VARCHAR(200) NOT NULL,
 nome VARCHAR(250) NOT NULL, creata_il TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_commesse_cognome_chiave ON commesse (cognome_chiave);
CREATE TABLE IF NOT EXISTS righe_commessa (
 id SERIAL PRIMARY KEY, commessa_id INTEGER NOT NULL REFERENCES commesse(id),
 profilo VARCHAR(128) NOT NULL, colore VARCHAR(128) NOT NULL,
 lunghezza INTEGER NOT NULL, quantita INTEGER NOT NULL,
 riferimento TEXT NOT NULL DEFAULT '', barra_intera BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_righe_commessa_commessa_id ON righe_commessa (commessa_id);
CREATE TABLE IF NOT EXISTS assegnazioni_commessa (
 id SERIAL PRIMARY KEY, commessa_id INTEGER NOT NULL REFERENCES commesse(id),
 pezzo_id INTEGER NOT NULL UNIQUE REFERENCES pezzi(id)
);
CREATE INDEX IF NOT EXISTS ix_assegnazioni_commessa_commessa_id ON assegnazioni_commessa (commessa_id);
