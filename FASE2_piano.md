# FASE 2 — Piano interventi prioritario

Data: 2026-10-18 · Ramo: `fase6-contrasti-animazioni` · HEAD: `2138f57`
Questa fase **non applica modifiche** a codice, database reale, `config.toml` né `.gitignore`.

## Stato verificato (evidenze di questa sessione)

| Voce | Esito |
|---|---|
| Git | 0 file modificati; 21 entry non tracciate; 1 stash (`wp2a-maschera-campi`) |
| Copia di sicurezza | `../magazzino_protezione_20261018_173922` — 20 file + `MANIFEST.sha256`, hash verificati OK (l'entry `nul`, artefatto di 102 byte, è escluso dal guard `is_file()`) |
| Target test | **BLOCCATO** — `MAGAZZINO_TEST_DB_URL` non definita; script `verifica_target_test.py` → `BLOCCATO: MAGAZZINO_TEST_DB_URL non definita` |
| Backup | `magazine_profili_20261017_191004.dump` (51 916 B, 2026-10-17 19:10) — `pg_restore --list` rc=0, 76 righe di catalogo; **limitazione**: `--list` certifica la leggibilità, non il restore |
| Suite | `200 passed, 5 skipped` (i 5 PG saltati per variabile assente); correzione d'ambiente: installato `qrcode` (dipendenza dichiarata in `requirements.txt` ma assente dal venv) |

## Vincoli trasversali

- **Test DB separato**: l'utente deve creare `magazine_profili_test` (nome con suffisso `_test`) e definire `MAGAZZINO_TEST_DB_URL`. `verifica_target_test.py` deve stampare `OK` prima di qualsiasi test PG.
- **Migrazioni**: il prossimo prefisso libero è **004** (001/002/003 già presenti in `migrations/`). Niente `;` dentro stringhe o funzioni (il runner `applica_migrazioni` taglia su `;` — vedi P-03). Solo `ADD COLUMN` con default NULL o valori, **mai DROP COLUMN / TRUNCATE / DELETE**.
- **Preservazione dati**: le colonne nuove nascono NULL; i dati esistenti non subiscono alcuna modifica.
- **Mai** avviare l'app in un ambiente di test: `main.py` crea tabelle e applica migrazioni usando `config.toml` reale (e avvia anche il server DB se assente).

## Tabella prioritaria (15 righe)

Formato: ID · Causa (verificata/ipotesi) · File:funzione · Modifica · Dipende da · Rischio · Test · Completamento

| ID | Causa (verificata/ipotesi) | File:funzione | Modifica | Dipende da | Rischio | Test | Completamento |
|---|---|---|---|---|---|---|---|
| P-01 Protezione dati | Verificata: `drop_all(engine)` senza guard nel target — `conftest.py:52`, `test_regressione_fase3.py:56,89` | `magazzino_profili/tests/conftest.py:fixture sessione` | Aggiungere `url_test_sicuro()`: valida scheme, dbname non vuoto, nome `_test`/`test_`, confronto con `leggi_config()` (mai stampato); non soddisfatto → `pytest.fail`; poi `drop_all` | Utente: DB test + `MAGAZZINO_TEST_DB_URL` | Basso (solo test) | 5 test PG; script `verifica_target_test.py` | Con variabile assente: BLOCCATO; con target `_test` valido: 5 test pass sul DB test |
| P-02 Protezione dati | Verificata: dump custom-format solo "leggibile"; nessun restore testato | `magazzino_profili/backup/backup_db.py` | `pg_restore --list` già ok; aggiungere restore di prova su DB test usa-e-getta (fase 8) | P-01 | Basso | nuovo test restore | Restore completo in DB test: dati identici al dump |
| P-03 Bug critico | Verificata: `applica_migrazioni` fa `sql.split(";")` → SQL con `;` dentro stringhe si spezza | `magazzino_profili/db/migrazioni.py:applica_migrazioni` | Sostituire lo split con parsing corretto (es. eseguire il file intero o uno splitter che ignori `;` in stringhe/commenti) | Nessuna | Basso (solo avvio) | unit test con migrazione contenente `;` in stringa | Migrazione con `;` in stringa esegue e viene registrata in `migrazioni` |
| P-04 DB/modello | Verificata: `Pezzo` senza `numero_vassoio`, `stato`, `data_ultimo_cambio_stato` | `magazzino_profili/domain/pezzo.py` + migrazione | `migrations/004_campi_vassoio.sql`: `ADD COLUMN numero_vassoio VARCHAR(128) NULL; ADD COLUMN stato VARCHAR(16) NULL CHECK (stato IN ('Caricato','Scaricato')); ADD COLUMN data_ultimo_cambio_stato TIMESTAMP NULL` — NULL, nessun DROP | P-03 | Medio (DDL sul reale, solo via app) | unit + PG | Colonne presenti; pezzi esistenti con `stato` NULL; nessun dato perso |
| P-05 Barcode/vassoio | Verificata: nessun servizio di aggiornamento barcode/vassoio/stato; `registra_movimento` solo in carica/scarica | `magazzino_profili/services/` (nuovo `barcode.py`) | `aggiorna_barcode(pezzo_id, codice)`, `imposta_numero_vassoio(...)`, `imposta_stato(...)` con `data_ultimo_cambio_stato`; ogni cambio loggato in `movimenti` | P-04 | Medio | unit + PG | UPDATE corretto, timestamp impostato, storico in `movimenti` |
| P-06 Stato/48h | Verificata: nessun campo `eliminato_il`, nessun servizio né azione UI di eliminazione | `domain/pezzo.py` + `services/` + `ui/tabella_pezzi.py` | Migrazione `005_eliminato_il.sql` (`ADD COLUMN eliminato_il TIMESTAMP NULL`); servizio `pezzi_da_cancellare_48h()`; voce contesto "Da cancellare" | P-04, P-05 | Alto (distruttivo) | unit + PG + GUI | A 48h il pezzo risulta "da cancellare"; eliminazione solo su conferma esplicita; log in `movimenti` |
| P-07 Telefono | Verificata: `preleva_scansioni` marca lette anche quelle stanche (barcode perso); `scarta_arretrate` elimina; niente `GET /api/pezzi/{barcode}`; pagina senza modalità "consulta" | `services/telefono.py:preleva_scansioni`, `web/routes_barcode.py`, `web/static/scansione.js` | Le stanche restano pending (no discard automatico); aggiungere route `GET` di consultazione senza consumare la scansione; pulsante "consulta" in pagina | P-04 | Medio | 5 test web esistenti + nuovi | Il telefono legge il pezzo senza consumare la scansione; nessuna eliminazione automatica di dati |
| P-08 CSV/ODS | Verificata: import CSV non atomico (le prime N righe restano salvate su errore); import ODS crea profili placeholder con peso 1,0 | `reports/export_csv.py:importa_peczi_csv`, `reports/importa_ods.py` | Import transazionale all-or-nothing con validazione pre-riga; ODS: importare solo profili/pezzi esistenti (niente placeholder) | Nessuna | Medio | unit con file campione valido e con riga guasta | Riga guasta → niente salvato; ODS usa i profili reali |
| P-09 Excel backup/restore | Verificata: `esporta_inventario_excel` è un report a foglio singolo (limite noto), non è un backup | `reports/` (nuovo `backup_excel.py`) | `.xlsx` multi-foglio (profili, colori, pezzi, impostazioni) + `importa_backup_excel` transazionale | P-04 | Alto | unit round-trip | Export → import in DB test pulito → tutti i dati identici |
| P-10 GUI | Verificata: `DialogoAccesso(QWidget)` non `QDialog`; colonne Vassoio/Stato assenti; nessuna azione di eliminazione | `ui/finestra_principale.py:71`, `ui/tabella_pezzi.py` (`_COLONNE` riga 61) | `DialogoAccesso(QDialog)` modale; aggiungere colonne "Vassoio" e "Stato" a `_COLONNE`; voce contesto "Da cancellare" | P-04, P-05, P-06 | Medio (UI) | `test_ui_fase4` + nuovi test GUI | Dialogo modale; colonne visibili; azione di eliminazione funzionante |
| P-11 Prestazione | Verificata: `riepilogo_inventario` carica tutti i pezzi in Python per calcolare `peso_kg` | `services/consultazione.py:232` | Calcolo con `SUM`/join SQL sul profilo | Nessuna | Basso | unit + PG esistenti | Stesso valore con una sola query |
| P-12 Background | Verificata: `PianificatoreBackup.avvia()` non idempotente (doppia chiamata → doppio timer); nessun worker di scadenze | `util/pianificatore.py:avvia`, `main.py` | Rendere `avvia()` idempotente; aggiungere `PianificatoreScadenze` (intervallo 30 s) che marca i pezzi "da cancellare" | P-06 | Medio | unit con orologio finto | Doppio `avvia()` → un solo timer; worker segna i pezzi scaduti |
| P-13 Aggiornamenti | BLOCCATO: nessun feed/autore di aggiornamenti; nessun client HTTP di update nel codice (verificato) | — | Fuori da questa fase (serve un publisher esterno) | Publisher esterno | — | — | n/a (BLOCCATO) |
| P-14 Sicurezza | Verificata: `main.py` hard-coda `Utente("simone", AMMINISTRATORE)` (login disattivato); web: `segrete_token` assente → token casuale a ogni avvio; niente rate-limit `/login` | `main.py`, `web/app.py:_stato` | Riattivare `DialogoAccesso`; token persistente; rate-limit sul login | P-10 | Medio | test web + manuale | Login richiesto; token stabile tra riavvii |
| P-15 Compatibilità/integrazione | Verificata: `db/server.py` usa `DETACHED_PROCESS` (Windows-only); `qrcode` dichiarata in `requirements.txt` ma mancante dal venv (corretto oggi); pytest raccoglie anche `fase6-file-modificati/` (duplicati) | `db/server.py:start`, `requirements.txt`, config pytest | Guard di `creationflags` per piattaforma; venv allineato a `requirements.txt`; `pytest.ini` con `norecursedirs = fase6-file-modificati` | Nessuna | Basso | suite completa + 5 PG | 205 test (200 + 5 PG) pass senza errori di raccolta |

## Note operative

1. Ordine di esecuzione consigliato: P-01 → P-02 → P-03 → P-04 → P-05 → (P-06 ∥ P-07 ∥ P-08) → P-09 → P-10 → P-11 → P-12 → P-14 → P-15 (P-13 resta BLOCCATO).
2. Ogni migrazione: un file `.sql` in `migrations/`, prefisso libero crescente (004, 005, …), senza `;` dentro stringhe, senza DDL distruttivo.
3. Prima di ogni blocco di modifiche: backup `pg_dump` + verifica `pg_restore --list`.
4. Nessuna modifica a `config.toml` né a `.gitignore` in questa fase.
