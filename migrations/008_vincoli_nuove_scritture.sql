-- NOT VALID preserva i dati preesistenti, applicando i controlli alle nuove scritture.
ALTER TABLE profili ADD CONSTRAINT ck_profili_codice_maiuscolo CHECK (codice = upper(codice) AND length(codice) > 0) NOT VALID;
ALTER TABLE profili ADD CONSTRAINT ck_profili_misure_positive CHECK (peso_kg_per_metro > 0 AND lunghezza_standard_mm > 0) NOT VALID;
ALTER TABLE pezzi ADD CONSTRAINT ck_pezzi_lunghezza_positiva CHECK (lunghezza_mm > 0) NOT VALID;
ALTER TABLE pezzi ADD CONSTRAINT ck_pezzi_scorta_non_negativa CHECK (scorta_minima IS NULL OR scorta_minima >= 0) NOT VALID;
ALTER TABLE colori ADD CONSTRAINT ck_colori_hex_valido CHECK (colore_hex IS NULL OR colore_hex ~ '^#[0-9A-Fa-f]{6}$') NOT VALID;
