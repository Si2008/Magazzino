-- Migrazione 002 - impostazioni globali dell'applicazione (chiave e valore).
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave VARCHAR(64) PRIMARY KEY,
    valore VARCHAR(255) NOT NULL
)
