-- Migrazione 004: numero vassoio, stato, data ultimo cambio stato, eliminazione logica.
-- Solo colonne e indice nuovi. I record esistenti restano invariati (NULL = storico).
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS numero_vassoio VARCHAR(128);
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS stato VARCHAR(16);
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS data_ultimo_cambio_stato TIMESTAMP WITH TIME ZONE;
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS eliminato_il TIMESTAMP WITH TIME ZONE;
CREATE INDEX IF NOT EXISTS ix_pezzi_eliminato_il ON pezzi (eliminato_il);
