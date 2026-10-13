# Registro modifiche — Fase 3 (correzione dei bug verificati)

Patch: `fase3-correzioni.patch` (generata con `git diff --ignore-cr-at-eol HEAD`,
applicabile con `git apply --ignore-whitespace` su un worktree che ha le
modifiche di fine riga già presenti).

Base: commit `a2bb74f` (branch `main`). Il lavoro è stato svolto su una copia
di analisi; il repository dell'utente non è stato modificato.

> Applicazione nel repository locale: branch `fase3-correzioni` creato da
> `a2bb74f`; patch applicata con `git apply --ignore-whitespace` il
> 2026-10-13; suite verificata su Windows (Python locale, PostgreSQL 16
> locale, DB di test `magazzino_profili_test`, DB reale non toccato).

## 1. Esiti dei test

| Esecuzione | Superati | Falliti | Saltati | Note |
|---|---|---|---|---|
| Baseline Fase 1 (prima delle modifiche) | 125 | 0 | 3 | I 3 saltati richiedono `MAGAZZINO_TEST_DB_URL` |
| Regressioni Fase 3 prima delle correzioni | 2 | **22** | 0 | 22 falliscono per il bug atteso (vedi §3) |
| Dopo le correzioni, senza PostgreSQL | 147 | 0 | 5 | 5 saltati: 3 integrazione + 2 concorrenza |
| Dopo le correzioni, con PostgreSQL 16 locale | **152** | 0 | 0 | Suite completa |
| Patch su copia pulita del commit base, con PostgreSQL | **152** | 0 | 0 | Verifica di applicazione |

Ambiente: Linux (Ubuntu 24.04), Python 3.12, PostgreSQL 16 locale su database
di test `magazzino_profili_test`. **Non eseguiti:** test su Windows (percorsi
`%LOCALAPPDATA%`, `DETACHED_PROCESS`, eseguibile PyInstaller), test con il
database reale, test con file ODS reali, test del telefono con HTTPS reale.

Due test sono già verdi prima della correzione (non sono regressioni):
`test_validatore_rifiuta_lettere` e `test_ods_vassoio_numerico_diventa_ubicazione`.
Sono mantenuti come guardie di comportamento.

## 2. Bug corretti

| ID | Bug | Correzione | File | Test di regressione |
|---|---|---|---|---|
| P2 | Campi lunghezza e quantità accettano una cifra (`setInputMask("#")`) | `QIntValidator(1, 99_999_999)` | `ui/scheda_carico.py`, `ui/scheda_scarico.py` | `test_input_numerici.py` (5 test) |
| P2-b | Scansione di `AB12-NERO-6000` creava un pezzo da 6 mm | Conseguenza di P2, risolta da P2 | — | `test_scansione_barcode_esistente_non_crea_pezzi_nuovi` |
| P1 | Perdita di unità con carichi concorrenti (299 su 600) | `SELECT ... FOR UPDATE` con `populate_existing`; creazione di colore e pezzo protetta da savepoint e riuso in caso di conflitto | `services/carico.py`, `services/scarico.py` | `test_concorrenza_nessuna_unita_persa`, `test_concorrenza_creazione_pezzo_senza_errori` (PostgreSQL) |
| P7 | Parser del barcode divide per `-` e assegna campi sbagliati | Ricerca del pezzo nel database; altrimenti scomposizione solo se unica tra i profili in anagrafica; se ambigua, i campi restano vuoti | `ui/scheda_carico.py`, `services/consultazione.py` (`candidati_da_barcode`) | `test_parser_barcode_*` (3 test) |
| S6 | Causali con HTML interpretato nei movimenti | `html.escape` su codice, colore, data, utente e causale | `ui/scheda_carico.py` | `test_causale_html_mostrata_come_testo` |
| P8 | Scarico con barcode minuscolo rifiutato dal desktop e dal telefono | Barcode normalizzato in maiuscolo in `scarica` e nelle route | `services/scarico.py`, `web/routes_barcode.py` | `test_scarico_accetta_barcode_minuscolo` |
| W1 | Carico dal telefono con barcode minuscolo: 404 | Come P8 | `web/routes_barcode.py` | verificato con `r_web.py` (200) |
| W5 | Carico dal telefono poteva creare un pezzo se il pezzo era cancellato nel frattempo | Parametro `crea_se_mancante=False` nel carico remoto; `PezzoNonTrovatoError` → 404 | `services/carico.py`, `web/routes_barcode.py` | `test_carico_senza_creazione_non_crea_pezzi` |
| W3 | Token con ruolo declassato ancora valido per un'ora | Utente e ruolo riletti dal database a ogni richiesta | `web/auth.py`, `web/routes_barcode.py` | verificato con `r_web.py` (403) |
| W4 | Token di utente cancellato ancora accettato | Utente inesistente → 401 | `web/auth.py` | verificato con `r_web.py` (401) |
| S-ricerca | `%` e `_` nella ricerca agiscono da jolly | Escape di `\`, `%`, `_` e `ESCAPE` nei LIKE | `services/consultazione.py` | `test_ricerca_jolly_non_sono_wildcard` |
| P5 | Import CSV parziale con errore di profilo | Lettura e validazione di tutte le righe prima di scrivere; messaggio con numero di riga | `reports/export_csv.py` | `test_csv_profilo_mancante_non_importa_nulla`, `test_csv_riga_non_valida_indica_il_numero_di_riga` |
| P6 | Ubicazione persa nel round-trip CSV | Lettura della colonna `Ubicazione` | `reports/export_csv.py` | `test_csv_ubicazione_sopravvive_al_round_trip` |
| P4 | Ubicazione ODS `Vassoio Vassoio 4`; vassoio ignorato su pezzi esistenti | `_ubicazione_da_vassoio`: numero → `Vassoio N`, testo invariato; pezzo esistente senza ubicazione la riceve | `reports/importa_ods.py` | `test_ods_vassoio_gia_con_prefisso_non_duplicato`, `test_ods_pezzo_esistente_senza_ubicazione_la_riceve` |
| B1 | Un errore imprevisto ferma la pianificazione del backup | `finally` riprogramma sempre; errori registrati con traceback nel log | `backup/backup_db.py` | `test_backup_errore_imprevisto_non_ferma_la_pianificazione` |
| S7 | Cartella di backup non scrivibile: crash all'avvio | Errore gestito e registrato nel piano; `avvia()` non solleva | `backup/backup_db.py` | `test_backup_avvio_con_cartella_non_scrivibile_non_solleva` |
| S8 | `setup_database` riscrive `[web]` (host `localhost`, porta `5432`) | Modifica limitata alla sezione `[database]`; `pg_dump` inserito in `[backup]` e non sovrascritto | `setup_database.py` | `test_setup_non_altera_la_sezione_web` |
| — | Messaggi di errore in inglese e con dettaglio mancante in `main` | Messaggi in italiano con `Dettaglio: <errore>` | `main.py` | verifica manuale |
| — | Nessun log su file | `app.log` in `%LOCALAPPDATA%\magazzino_profili` (fallback su stderr) | `main.py`, `backup/backup_db.py` | verifica manuale |

## 3. Correzioni dei test (non del comportamento)

Tre test di `test_input_numerici.py` digitavano su un campo che parte già con
il valore `1`, ottenendo `112` invece di `12`. Ho aggiunto `clear()` prima della
digitazione. Il comportamento del programma non è cambiato.

## 4. Cambiamenti di comportamento da conoscere

- **Import CSV:** se una riga è non valida o un profilo manca in anagrafica, nessuna riga viene importata. Prima le righe valide precedenti venivano salvate.
- **Carico dal telefono:** non crea mai pezzi, nemmeno in caso di concorrenza.
- **Token del telefono:** il ruolo è quello attuale nel database. Utenti cancellati o declassati vengono rifiutati alla richiesta successiva.
- **Scansione nel desktop:** un barcode che corrisponde a un pezzo esistente compila i campi da quel pezzo. Un barcode di pezzo nuovo compila i campi solo se la scomposizione è unica.
- **Backup:** gli errori compaiono nel log invece di essere ignorati in silenzio.

## 5. Problemi noti non corretti (serve una decisione o un lavoro separato)

| ID | Problema | Motivo del mancato intervento |
|---|---|---|
| P3 | Import ODS ripetuto raddoppia le giacenze | Richiede una tabella `importazioni` (migrazione 002) e la scelta di come trattare la reimportazione |
| P7-b | Due combinazioni diverse possono generare lo stesso barcode (`AB-12`+`X` e `AB`+`12-X`) | Richiede di cambiare il formato del barcode o di vietare il trattino nei codici (decisione 8). Verificare prima i dati reali |
| W2 | Nessun limite ai tentativi di login dal telefono (60 errori senza blocco) | Funzione di sicurezza nuova, da progettare (tabella dei tentativi o rate limit per IP) |
| S1 | Login desktop disattivato: l'app entra sempre come amministratore `simone` | Scelta di prodotto (decisione 7) |
| S4 | Password del database in `config.toml`, incluso nell'eseguibile e nello zip | Richiede spostare la configurazione in `%LOCALAPPDATA%` e cambiare la password: operazione dell'utente |
| S5 | Dump di backup dentro lo zip caricato | Operazione di distribuzione, non di codice |
| B2 | Retention per numero di file (7), non per tempo; riavvii ravvicinati accorciano la storia | Politica di conservazione da decidere |
| B3 | Cartella di backup relativa alla working directory | Da risolvere con percorso assoluto, dopo decisione sulla posizione |
| R1 | Riepilogo e lista pezzi ricaricano tutto a ogni operazione (0,32 s su 12.000 pezzi, SQLite) | Ottimizzazione, misurare su PostgreSQL prima |
| R2 | Primo backup e avvio di PostgreSQL bloccano la finestra | Ottimizzazione (WP11) |
| — | Scansione con digitazione manuale: un barcode parziale seguito da Invio può salvare un pezzo sbagliato | Comportamento di UI da decidere (es. Invio salva solo se il barcode corrisponde a un pezzo esistente) |
| — | `session.delete(pezzo)` fallisce per `movimenti.pezzo_id` NOT NULL | Nel codice non esiste alcuna cancellazione di pezzi; latente |
| — | Stati Caricato/Scaricato, cancellazione dopo 48 ore, modifica dei barcode, backup Excel multi-foglio, ripristino | Non esistono nel codice: serve la specifica (decisioni 1, 2, 4, 5) |
| — | Mockup e implementazione divergono (accoppiamento via QR nel mockup, login nel codice; barcode `MP-…` contro `CODICE-COLORE-LUNGHEZZA`) | Decisione 6 |
| — | Errore imprevisto del database durante un import CSV lascia le righe precedenti salvate (il messaggio lo indica) | Un import completamente atomico richiede di far partecipare `carica` a una transazione esterna; rinviato |

## 6. Note tecniche

- `carica` e `scarica` usano `with_for_update()`: su SQLite la clausola è ignorata. La protezione reale è verificata solo su PostgreSQL.
- La patch è stata generata con `--ignore-cr-at-eol`. I file che nel worktree dell'utente hanno fine riga CRLF (`export_csv.py`, `backup_db.py`, `main.py`, `setup_database.py`) sono stati riscritti mantenendo CRLF; nel commit base sono LF, quindi la patch contiene righe CRLF in quei file. `git apply --ignore-whitespace` le accetta.
- Nessun file di configurazione, nessuno spec PyInstaller e nessuna migrazione è stato modificato.
