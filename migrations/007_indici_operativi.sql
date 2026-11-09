-- Indici additivi: nessuna modifica ai dati storici.
CREATE INDEX IF NOT EXISTS ix_pezzi_scadenza_attiva ON pezzi (data_ultimo_cambio_stato, id) WHERE eliminato_il IS NULL AND stato = 'Scaricato' AND quantita = 0;
CREATE INDEX IF NOT EXISTS ix_movimenti_data_ora ON movimenti (data_ora DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_movimenti_pezzo_data ON movimenti (pezzo_id, data_ora DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_scansioni_in_attesa ON scansioni_telefono (id) WHERE letta = FALSE;
CREATE INDEX IF NOT EXISTS ix_scansioni_creata ON scansioni_telefono (creata_il);
