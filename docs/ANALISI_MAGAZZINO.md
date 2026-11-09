# Analisi tecnica di Magazzino Profili

Data: **4 novembre 2026**, fuso di riferimento Europe/Rome. Oggetto: cartella `C:/Users/Simone/Desktop/magazzino`, codice effettivamente presente, comprese modifiche non committate. HEAD rilevato: `8b82b066176bb33c6c8037fc477a400712515acb` (evidenza `E/rilievi_statici.txt:610`).

Convenzioni delle evidenze:

- I percorsi del progetto sono relativi alla radice indicata sopra; `file:123` indica una riga, non una stima.
- **E** indica la cartella esterna delle prove: `C:/Users/Simone/.codex/visualizations/2026/11/04/01a1a805-2281-70a3-b843-3ab704fdf9a3/copia_temporanea_analisi`. Quindi, per esempio, `E/misure.py:1` è un percorso abbreviato ma risolvibile. Log, XML dei test, script di misura e screenshot rimangono lì, fuori dal repository.
- **VERIFICATO**: letto nel codice oppure riprodotto nelle prove indicate. Non significa automaticamente verificato su PostgreSQL di produzione o sul telefono.
- **IPOTESI**: conseguenza plausibile del codice, con prova di conferma proposta. **NON VERIFICABILE**: mancano dispositivo, materiale originale, ambiente o autorizzazione a usare dati reali.
- Gli interventi della sezione 9 sono proposte, non modifiche applicate. I giudizi di gravità sono valutazioni tecniche basate sulle evidenze associate.

## 1. Sintesi esecutiva

1. **VERIFICATO:** architettura recuperabile con interventi incrementali; esistono servizi, transazioni, test e protezioni web, ma l'integrazione delle funzioni è incompleta (`magazzino_profili/services/carico.py:170`, `magazzino_profili/web/sicurezza_web.py:152`).
2. **Problema 1 — critico:** un barcode attivo Scaricato può essere ricaricato senza cambiare stato e poi sparire dall'inventario con quantità positiva; riprodotto con 5 pezzi (`magazzino_profili/services/carico.py:108`, `magazzino_profili/services/stati.py:99`; `E/misure.json:14`).
3. **Problema 2 — alto:** il ruolo Sola lettura può modificare lo stato dalla scheda Inventario; modifica persistita nella prova (`magazzino_profili/ui/tabella_pezzi.py:765`; `E/prove_aggiuntive.json:2`).
4. **Problema 3 — alto:** il telefono non ha URL da mostrare nel QR; il certificato copre solo localhost/127.0.0.1 e il server va avviato separatamente (`config.toml:28`, `magazzino_profili/main.py:81`; `E/ambiente.txt:8`).
5. **Problema 4 — alto:** il backup iniziale blocca l'avvio; backup su file con nomi al secondo, senza coordinamento fra processi e con configurazione fragile nell'exe (`magazzino_profili/backup/backup_db.py:99`, `magazzino_profili/backup/backup_db.py:226`).
6. **Problema 5 — alto:** import ODS storico parziale e additivo, distinto dai formati V2; il backup XLSX completo non è collegato al menu (`magazzino_profili/reports/importa_ods.py:227`, `magazzino_profili/ui/finestra_principale.py:717`).
7. **VERIFICATO:** 528 test superati, 6 falliti, 49 saltati, 69 bloccati, 1 errore di setup e 1 escluso nell'esecuzione controllata; nessuna attestazione di funzionamento completo (`E/riepilogo_test.json:2`).
8. **VERIFICATO:** a 12.000 righe sintetiche: lettura 0,117 s, ricostruzione tabella 4,063 s; la paginazione manca (`E/misure.json:70`; `E/misure.json:78`; `magazzino_profili/ui/tabella_pezzi.py:926`).
9. **NON VERIFICABILE:** catalogo dei 211 PNG, indice aggiornato e mockup HTML originale assenti dalla cartella esaminata (`E/rilievi_statici.txt:267`).
10. **Rischio principale:** giacenza reale e giacenza visibile possono divergere senza una cancellazione fisica; prima di nuove funzioni occorrono backup ripristinabili e regole coerenti per stato/quantità (`magazzino_profili/services/stati.py:105`, `magazzino_profili/services/consultazione.py:40`).

## 2. Mappa del progetto (Fase A)

### 2.1 Metodo, perimetro e limiti della sola lettura

**VERIFICATO:** esplorazione ricorsiva di nomi e dimensioni anche nelle cartelle ignorate, lettura dei sorgenti applicativi, SQL, documentazione, configurazioni, script di manutenzione, metadati dell'ambiente Python e artefatti di build. Il censimento completo dei file applicativi e delle risorse è in `E/rilievi_statici.txt:1`; i metadati di build sono in `build/MagazzinoProfili/Analysis-00.toc:1`. I dump sono stati censiti soltanto per nome/dimensione: non sono stati aperti con PostgreSQL, ripristinati o modificati. Nessun server originale è stato avviato e nessun database reale è stato interrogato.

**VERIFICATO:** test e benchmark eseguiti sulla copia esterna E, con SQLite sintetico, Qt offscreen, URL PostgreSQL di test rimossi dall'ambiente e directory utente dei processi di prova indirizzate a E. Non sono state installate dipendenze. Copia senza `config.toml` reale, backup reali ed eseguibili reali; la chiave privata di firma non è stata letta dalle analisi. Gli script di prova e l'orchestrazione sono verificabili in `E/esegui_isolato.py:1`, `E/misure.py:1`, `E/prove_aggiuntive.py:1`, `E/recupera_test.py:1`. La copia iniziale di `firme/` aveva incluso il file privato: non è stato usato né riportato nel report e la sola copia temporanea è stata rimossa; l’originale è rimasto al suo posto (`E/rilievi_statici.txt:12`, `firme/README.md:17`).

**Scostamento operativo dichiarato:** durante il censimento un comando ha creato accidentalmente il solo file nuovo `distribuzione.txt` nella radice; il file è stato immediatamente trasferito in E. Nessun file preesistente è stato modificato da questa operazione. Alla consegna l'unico nuovo file lasciato nel progetto è questo report. Il contenuto di quel rilievo è in `E/distribuzione.txt:1`; il confronto conclusivo dello stato Git è riportato nel registro di verifica esterno.

**NON VERIFICABILE:** correttezza dello schema del database attualmente installato, validità dei dump originali, comportamento dell'exe installato, stampante/lettore fisico, telefono, Wi-Fi e firewall effettivo. Gli exe sono stati confrontati per hash, senza eseguirli o decompilarli (`E/distribuzione.txt:1`). I risultati dei sorgenti non dimostrano che l'exe incorpori le modifiche locali.

### 2.2 Albero funzionale

**VERIFICATO:** struttura dal censimento `E/rilievi_statici.txt:2`; ruolo dei moduli dai rispettivi docstring/import, elencati anche nell'appendice 2.7.

```text
magazzino/
├── MagazzinoApp.py                 ingresso PyInstaller → main.main
├── setup_database.py               provisioning PostgreSQL e primo amministratore
├── importa_ods.py                  CLI dell'importatore ODS storico
├── requirements.txt                dipendenze, intervalli di versione
├── MagazzinoProfili.spec            specifica PyInstaller locale, ignorata da Git
├── version_info.txt, icona.ico      metadati Windows e icona
├── config.example.toml             modello di configurazione
├── config.toml                     configurazione locale con segreti, ignorata
├── conftest.py                     Qt offscreen e catalogo immagini isolato nei test
├── magazzino_profili/
│   ├── __init__.py                 versione del programma
│   ├── main.py, launch_app.py       avvio desktop e launcher alternativo
│   ├── crea_utente.py              CLI gestione iniziale utenti
│   ├── db/                         config, engine/sessioni, normalizzazione,
│   │                               migrazioni SQL, avvio server PostgreSQL locale
│   ├── domain/                     modelli SQLAlchemy: profili, colori, pezzi,
│   │                               movimenti, spezzoni, impostazioni e scansioni
│   ├── sicurezza/                  utenti, bcrypt, ruoli e permessi
│   ├── services/                   carico/scarico, anagrafiche, consultazione,
│   │                               barcode/vassoio, stati/scadenze, telefono,
│   │                               immagini, colori, aggiornamenti
│   ├── ui/                         Qt Widgets: finestra, Inventario, Carico,
│   │                               Scarico, Profili, Avvisi, telefono, temi,
│   │                               componenti, animazioni e gestione colori
│   ├── barcode/                    generazione Code128, PDF etichette, input scanner
│   ├── reports/                    CSV storico e V2, ODS storico e V2,
│   │                               report Excel/PDF, backup XLSX con restore
│   ├── backup/                     pg_dump, verifica pg_restore, rotazione e timer
│   ├── web/                        FastAPI/uvicorn HTTPS, auth, barcode e aggiornamenti
│   │   ├── templates/scansione.html pagina mobile reale, non mockup desktop
│   │   └── static/                 scansione.js, html5-qrcode.min.js e licenza
│   └── tests/                      62 moduli test_*.py, conftest e prove JS
├── migrations/                     SQL 001..006, applicazione incrementale
├── catalogo_immagini/              soltanto .gitkeep: nessun PNG
├── immagini_sezioni/               tre PNG dimostrativi
├── Profili_cataloghi/              Riepilogo.csv e una sola immagine sorgente _atl...
├── backup/                        sette dump locali + .gitkeep
├── firme/                         strumenti firma, README e chiave privata locale
├── release/                       manifest firmato ed exe 1.0.0
├── dist/                          exe, config locale e sette dump separati
├── build/MagazzinoProfili/         TOC, archivi, warning, xref HTML e bytecode build
├── fase5/                         40 screenshot storici
├── fase6-file-modificati/          copia di consegna di sei moduli UI e test animazioni
├── scan_work/                     tre JSON di ricerca cataloghi e log pypdf
├── CHANGELOG-fase3/4/6.md          resoconti storici, da non confondere con test odierni
├── FASE2_piano.md                  piano precedente
├── _prompt_fase5.md                specifica testuale del mockup e codice di esempio
├── Prompt Pi Agent - ...md         istruzioni/piano di sviluppo precedente
├── screenshot_ui.py,
│   screenshot_fase5.py             generatori screenshot con dati predisposti
├── screenshot_*.png                screenshot radice
├── _audit_ods.py                   ricognizione ODS con percorso personale esterno
├── _crea_consegna.py, _fix_six.py   script estrazione/consegna PNG, con scritture
├── tmp_terminal_pg.ps1             apertura terminale PostgreSQL, non launcher app
├── nul                            artefatto anomalo locale di 90 byte
├── .venv/                         ambiente Python locale (~836 MB)
├── .git/                          repository e cronologia
├── .pytest_cache/, __pycache__/    risultati/cache storici, non prove dell'audit
└── docs/ANALISI_MAGAZZINO.md        questo report
```

Evidenze funzionali dei file radice: `MagazzinoApp.py:5`, `setup_database.py:203`, `importa_ods.py:27`, `MagazzinoProfili.spec:12`, `conftest.py:26`, `_audit_ods.py:2`, `_crea_consegna.py:6`, `_fix_six.py:5`, `tmp_terminal_pg.ps1:9`. Per le risorse: `E/rilievi_statici.txt:19` e seguenti. `nul` non è stato eseguito; funzione **NON VERIFICABILE**, non necessario all'avvio secondo gli import statici.

### 2.3 Linguaggi, librerie e versioni

**VERIFICATO:** Python per applicazione/strumenti, SQL PostgreSQL per migrazioni, HTML/CSS/JavaScript per telefono, TOML per configurazione, PowerShell per lo script terminale, Markdown per documentazione (`requirements.txt:1`, `migrations/004_campi_giacenza.sql:3`, `magazzino_profili/web/templates/scansione.html:1`, `tmp_terminal_pg.ps1:1`). Non sono presenti `pyproject.toml`, lockfile o progetto Node con build frontend nel censimento (`E/rilievi_statici.txt:19`).

| Componente | Dichiarato | Installato nell'ambiente letto | Evidenza |
|---|---|---|---|
| Python | nessun vincolo formale; uso tomllib richiede almeno 3.11 | 3.14.7, Windows AMD64 | `.venv/pyvenv.cfg:3`; `magazzino_profili/db/config.py:23`; `E/versioni.txt:1` |
| PySide6 / Qt Widgets / QtSvg | >=6.7 | 6.12.0 | `requirements.txt:15`; `magazzino_profili/ui/icone.py:12`; `E/versioni.txt:2` |
| SQLAlchemy | >=2,<3 | 2.1.6 | `requirements.txt:1`; `E/versioni.txt:3` |
| psycopg binary | >=3.1,<4 | 3.3.6 | `requirements.txt:2`; `E/versioni.txt:4` |
| openpyxl | >=3.1 | 3.1.5 | `requirements.txt:4`; `E/versioni.txt:5` |
| odfpy | >=1.4.1,<2 | 1.4.1 | `requirements.txt:12`; `E/versioni.txt:6` |
| FastAPI / uvicorn | >=0.110 / >=0.29 con standard | 0.162.0 / 0.54.0 | `requirements.txt:23`; `requirements.txt:24`; `E/versioni.txt:7` |
| ReportLab | >=4 | 5.1.0 | `requirements.txt:3`; `E/versioni.txt:17` |
| Pillow / pypdf | >=13.0.0 / >=6.21.1 | 13.0.0 / 6.21.4 | `requirements.txt:7`; `E/versioni.txt:11` |
| bcrypt / cryptography | >=4 / >=42 | 5.0.0 / 50.0.2 | `requirements.txt:8`; `requirements.txt:17`; `E/versioni.txt:13` |
| python-barcode / qrcode | >=0.16 / >=7.4 | 0.16.1 / 8.2 | `requirements.txt:10`; `requirements.txt:14`; `E/versioni.txt:15` |
| pytest / pytest-qt | >=8 / >=4.4 | 9.2.0 / 4.5.0 | `requirements.txt:18`; `requirements.txt:19`; `E/versioni.txt:9` |
| CSV, ZIP, XML, threading, TOML | libreria standard | quella di Python 3.14.7 | `magazzino_profili/reports/export_csv.py:14`; `magazzino_profili/reports/importa_ods.py:27` |
| html5-qrcode | file JS locale vendorizzato, non package lock | versione operativa non dedotta dal nome | `magazzino_profili/web/templates/scansione.html:93`; `magazzino_profili/tests/test_sicurezza_fase14.py:241` |
| PostgreSQL | nessun major richiesto/pinnato | server reale **NON VERIFICATO** | `magazzino_profili/db/config.py:52`; `setup_database.py:63` |
| PyInstaller / postgresql_binaries | usati ma non dichiarati in requirements | riproducibilità della build/setup **parziale** | `MagazzinoProfili.spec:2`; `setup_database.py:63` |

Gli intervalli ampi non garantiscono la riproducibilità dell'ambiente, e i commenti su un audit vulnerabilità precedente non equivalgono a un audit odierno (`requirements.txt:5`). Nessun controllo vulnerabilità online delle dipendenze è stato eseguito.

### 2.4 Avvio e punti d'ingresso

**VERIFICATO:** `MagazzinoApp.py:5` e `magazzino_profili/launch_app.py:10` chiamano `magazzino_profili/main.py:31`. L'avvio configura i log, legge il DB, tenta l'avvio del PostgreSQL locale, crea le tabelle mancanti e applica le migrazioni; prepara il factory; esegue il primo backup; richiede almeno un utente e il login; interroga il feed aggiornamenti; costruisce tutte le schede consentite e mostra la finestra massimizzata (`magazzino_profili/main.py:32`, `:50`, `:53`, `:78`, `:86`, `:100`, `:111`, `:116`).

**VERIFICATO:** il backup iniziale avviene **prima di QApplication/login** ed è sincrono; il commento sul timer non cambia questo comportamento (`magazzino_profili/backup/backup_db.py:226`, `:235`). Il server telefono si avvia con un comando distinto, `python -m magazzino_profili.web.app`; non viene lanciato dal desktop (`magazzino_profili/web/app.py:290`, `magazzino_profili/main.py:81`). Il server web non applica automaticamente le migrazioni né esegue `crea_tabelle`: presuppone un database predisposto (`magazzino_profili/web/app.py:339`).

Altri ingressi **VERIFICATI**: setup iniziale (`setup_database.py:203`), creazione utente (`magazzino_profili/crea_utente.py:1`), import ODS CLI (`importa_ods.py:27`), generazione chiavi e firma manifest (`firme/genera_chiave.py:1`, `firme/firma_manifest.py:1`). Gli script `_fix_six.py` e `_crea_consegna.py` scrivono file: non sono stati eseguiti.

### 2.5 Dipendenze interne e cicli

**VERIFICATO:** flusso prevalente `main → db + backup + ui`; `ui → services → domain + db.normalizzazione`; `web.routes_barcode → services + web.auth`; `reports → services/domain`; `sicurezza → domain.base`. Elenco completo degli import applicativi con righe e distinzione fra import a livello modulo, ritardati e TYPE_CHECKING: `E/rilievi_statici.txt:355` e appendice A. Esempi concreti: `magazzino_profili/main.py:24`, `magazzino_profili/ui/tabella_pezzi.py:49`, `magazzino_profili/services/carico.py:19`, `magazzino_profili/web/routes_barcode.py:36`, `magazzino_profili/reports/export_csv.py:23`.

**VERIFICATO:** il grafo statico rileva una componente ciclica nel pacchetto UI tramite i re-export di `ui/__init__.py`, `finestra_principale`, schede e `componenti`; non è una prova di crash all'import, poiché gli import concreti delle prove sono riusciti (`E/rilievi_statici.txt:603`; `magazzino_profili/ui/__init__.py:1`; `magazzino_profili/ui/componenti.py:39`). Anche `domain/pezzo.py:9 → db.normalizzazione` crea una dipendenza del dominio verso il pacchetto DB. Gli import effettuati per soli suggerimenti di tipo non vengono trattati come cicli runtime (`magazzino_profili/domain/pezzo.py:12`).

**IPOTESI:** import selettivi con ordine diverso possono risentire dell'inizializzazione dei pacchetti. Conferma: provare in processi puliti gli import di `domain`, `db`, `ui`, `services` in permutazioni significative. Correzione incrementale: ridurre i re-export e rendere la normalizzazione un modulo condiviso indipendente solo se un test dimostra il problema; non serve riscrivere l'applicazione.

### 2.6 Codice morto, duplicati, risorse non referenziate

| Riscontro | Classificazione | Evidenza e limite |
|---|---|---|
| `fase6-file-modificati/` è una seconda copia di moduli UI, non l'app caricata dagli ingressi | VERIFICATO | `MagazzinoApp.py:5`; `E/rilievi_statici.txt:281`. `animazioni.py` e `test_animazioni.py` sono byte per byte identici; gli altri snapshot divergono e non vanno sostituiti al codice attuale |
| Sei coppie di screenshot dopo7a/fase6 sono identiche SHA256 | VERIFICATO | `E/rilievi_statici.txt:275` |
| Import e nomi esportati di `ensure_running/is_ready/start` duplicati in db.__init__ | VERIFICATO, basso | `magazzino_profili/db/__init__.py:6`, `:7`, `:22` |
| `ControlloScadenze` precedente non è più avviato in produzione, ma resta testato | VERIFICATO nel grafo; candidato a dismissione | `magazzino_profili/services/controllo_scadenze.py:19`; `magazzino_profili/services/scadenze.py:92`; `magazzino_profili/tests/test_stati_scadenze.py:17`; `E/rilievi_statici.txt:606` |
| Segnale `scadenze_eliminate` e slot desktop senza produttore collegato al worker web | VERIFICATO nel percorso corrente | `magazzino_profili/ui/finestra_principale.py:273`, `:566`; `magazzino_profili/web/app.py:346`. Aggiornamento UI immediato dopo scadenza non implementato fra processi |
| `nome_file_sezione`, `qss_badge`, `qss_card`, `colore_sbiadito` | IPOTESI: helper di compatibilità non usati dalla produzione attuale | definizioni `magazzino_profili/domain/pezzo.py:92`, `magazzino_profili/ui/tema.py:233`, `:496`, `:506`; verificare riferimenti dinamici/utenze esterne prima di eliminare |
| Servizi CSV/ODS V2 e backup XLSX non raggiunti dal menu principale | VERIFICATO, funzioni di libreria non equivalgono a codice inutile | `magazzino_profili/reports/__init__.py:7`; `magazzino_profili/ui/finestra_principale.py:357`, `:717` |
| Script screenshot, estrazione PNG, JSON scan_work, screenshot storici, CSV riepilogo | VERIFICATO: strumenti/artefatti esterni al flusso di avvio | `screenshot_ui.py:1`, `_crea_consegna.py:1`, `E/rilievi_statici.txt:19`. L'assenza di import non dimostra che l'utente non li usi manualmente |
| Tre PNG in immagini_sezioni | NON VERIFICABILE se realmente referenziati nel DB | `E/rilievi_statici.txt:274`; riferimento è una stringa persistita, non un import |

### 2.7 Cronologia rilevante

**VERIFICATO:** `d8e4245`, 13/10/2026, modifica 24 file, +1.636/-228 righe. Introduce/corregge blocchi di riga e retry sulle creazioni concorrenti, gestione errori backup con ripianificazione, normalizzazione/validazioni import, autenticazione web e revisione UI con nuovi test. Sono stati letti stat e diff, non soltanto il messaggio (`E/git_d8e4245.diff:1`; `E/rilievi_statici.txt:646`; `CHANGELOG-fase3.md:1`, `CHANGELOG-fase4.md:1`).

I successori si raggruppano così; i messaggi sono evidenza della storia dichiarata, non certificazione che oggi ogni funzione funzioni (`E/rilievi_statici.txt:612`):

| Commit/gruppo | Cambiamento rilevante |
|---|---|
| `e1c885e`..`76f5ca5` | icone SVG, tema grande, componenti, Inventario, Carico/Scarico, Profili/Avvisi |
| `5140ef0` | contrasti e transizioni |
| `c2e1909`..`36d7cf5` | impostazioni e soglia globale avvisi |
| `b2d5cff` | elimina ricorsione cambiato→aggiorna nell'Inventario |
| `958a5e6`..`2138f57` | coda scansioni, ping, QR e collegamento alle schede desktop |
| `9d937d0`, `7e1adea`, `c9c6c59` | rifiuto bool nelle quantità, StrictInt web, gestione errori DB UI |
| `a3f3c20`, `0a3f86e` | aggregazione KPI unica e ottimizzazione costruzione tabella |
| `aaf8993`, `b10c630` | vassoio/barcode/stati, soft delete, controllo scadenze |
| `907e598` | timeout client telefono, consulta e gestione esito incerto |
| `3ca3496` | formati V2 e atomicità CSV storico; attenzione: il V2 è un validatore, non un restore |
| `4eeee40` | backup logico a sei fogli e restore |
| `ac6980e` | worker scadenze trasferito nel processo web e login obbligatorio |
| `a3fbaa2`, `e445531`, `8b82b06` | aggiornamenti firmati, hardening e build/rilascio; HEAD 01/11/2026 |

**VERIFICATO:** la working tree era già modificata in 14 file tracciati e conteneva numerosi file nuovi, fra cui catalogo/registro colori, proposta immagini, migrazione 006 e relativi test (`E/git_stato_iniziale.txt:1`). Queste modifiche non sono nei commit sopra. I due exe release/dist hanno stesso SHA256 e coincidono col manifest, ma non è stata verificata la corrispondenza con la working tree (`E/distribuzione.txt:1`). `MagazzinoProfili.spec` è ignorato e non tracciato: la build non è interamente riproducibile dal solo checkout (`.gitignore:10`; `E/git_stato_iniziale.txt:1`).

## 3. Architettura e dati (Fase B)

### 3.1 Separazione effettiva

**VERIFICATO:** esiste uno strato servizi e uno strato tecnico DB, ma non un repository/DAL unico che impedisca accessi diretti dalla UI. Consultazioni e carico/scarico sono prevalentemente nei servizi; la UI apre/chiude sessioni e talvolta legge direttamente modelli con `session.get`. Inoltre il menu Excel reimplementa un export anziché usare il servizio (`magazzino_profili/services/consultazione.py:43`; `magazzino_profili/ui/scheda_profilo.py:297`; `magazzino_profili/ui/tabella_pezzi.py:831`; `magazzino_profili/ui/finestra_principale.py:728`). Il dominio contiene anche la funzione mutante `registra_movimento`, quindi non è un modello puramente passivo (`magazzino_profili/domain/movimento.py:65`).

**Giudizio:** separazione **parziale**, sufficiente per miglioramenti incrementali. I punti fragili sono regole replicate fra importatori, UI e servizi e autorizzazioni applicate alle schede anziché alle azioni (`magazzino_profili/reports/importa_ods.py:226`; `magazzino_profili/services/carico.py:79`; `magazzino_profili/ui/finestra_principale.py:434`).

### 3.2 Schema completo dichiarato

**VERIFICATO nel codice, NON VERIFICATO sul DB installato.** Database operativo PostgreSQL attraverso `postgresql+psycopg`; SQLite serve alle prove (`magazzino_profili/db/config.py:52`; `magazzino_profili/tests/test_carico.py:22`). In tabella **NN** = NOT NULL; **NULL** = opzionale. Salvo indicazione, nessun default SQL: diversi default sono Python/ORM e non proteggono insert SQL esterni. I nomi dei vincoli seguono `magazzino_profili/domain/base.py:9`.

| Tabella | Tutte le colonne | PK, univocità, FK, CHECK e indici | Evidenza |
|---|---|---|---|
| profili | id INTEGER NN; codice VARCHAR(64) NN; descrizione TEXT NN; immagine_sezione VARCHAR(512) NULL; peso_kg_per_metro NUMERIC(10,4) NN; lunghezza_standard_mm INTEGER NN | PK id; indice univoco codice; nessun CHECK positività peso/lunghezza o maiuscolo | `magazzino_profili/domain/profilo.py:18` |
| colori | id INTEGER NN; codice_normalizzato VARCHAR(64) NN; nome_visualizzato VARCHAR(128) NN; colore_hex VARCHAR(7) NULL | PK id; indice univoco codice_normalizzato; nessun CHECK SQL formato hex | `magazzino_profili/domain/colore.py:17`; `migrations/006_colore_hex.sql:3` |
| pezzi | id INTEGER NN; profilo_id INTEGER NN; colore_id INTEGER NN; lunghezza_mm INTEGER NN; quantita INTEGER NN default ORM 0; ubicazione VARCHAR(128) NULL; scorta_minima INTEGER NULL; barcode VARCHAR(255) NN; numero_vassoio VARCHAR(128) NULL; stato VARCHAR(16) NULL; data_ultimo_cambio_stato TIMESTAMPTZ NULL; eliminato_il TIMESTAMPTZ NULL | PK id; UNIQUE combinazione(profilo_id,colore_id,lunghezza_mm); UNIQUE barcode; FK profilo_id→profili.id e colore_id→colori.id con indici singoli; CHECK quantita>=0; CHECK stato NULL o Caricato/Scaricato; indice eliminato_il. Nessun indice composito stato+timestamp, nessun CHECK lunghezza positiva/scorta non negativa/coerenza stato-tempo-quantità | `magazzino_profili/domain/pezzo.py:44`; `migrations/004_campi_giacenza.sql:3`; `migrations/005_vincolo_stato.sql:4` |
| movimenti | id INTEGER NN; pezzo_id INTEGER NN; tipo VARCHAR(16) NN (Enum Python, native_enum=False); quantita INTEGER NN; data_ora TIMESTAMPTZ NN default ORM UTC now; causale TEXT NN; utente TEXT NN | PK id; FK pezzo_id→pezzi.id indicizzata; CHECK quantita>0. Nessuna FK verso utenti; nessun vincolo di immutabilità/triggers; nessun indice data_ora. I valori Python sono CARICO/SCARICO/RETTIFICA, non un enum PostgreSQL | `magazzino_profili/domain/movimento.py:21`, `:38` |
| spezzoni | id INTEGER NN; pezzo_origine_id INTEGER NN; utente VARCHAR senza limite NN; lunghezza_mm INTEGER NN; data_creazione TIMESTAMPTZ NN default ORM UTC now; utilizzato BOOLEAN NN default ORM False | PK id; FK pezzo_origine_id→pezzi.id indicizzata; CHECK lunghezza_mm>0; utente testuale, non FK | `magazzino_profili/domain/spezzone.py:18` |
| impostazioni | chiave VARCHAR(64) NN; valore VARCHAR(255) NN | PK chiave; nessun indice ulteriore. Soglia globale e ultimo ping condividono questa tabella | `magazzino_profili/domain/impostazione.py:12`; `magazzino_profili/services/telefono.py:15` |
| scansioni_telefono | id INTEGER NN (SERIAL nel SQL); barcode VARCHAR(255) NN; utente VARCHAR(64) NN; creata_il TIMESTAMPTZ NN default SQL NOW(); letta BOOLEAN NN default SQL FALSE e ORM False | PK id; nessuna FK, nessun indice letta/creata_il, nessun identificatore di sessione/PC | `magazzino_profili/domain/scansione_telefono.py:14`; `migrations/003_scansioni_telefono.sql:2` |
| utenti | id INTEGER NN; username VARCHAR(64) NN; password_hash VARCHAR(128) NN; ruolo VARCHAR(32) NN default ORM OPERATORE | PK id; indice univoco username; nessun CHECK SQL enum ruolo; hash bcrypt | `magazzino_profili/sicurezza/utenti.py:33` |
| migrazioni_applicate | nome TEXT NN | PK nome; nessun checksum, timestamp o versione minima dell'app | `magazzino_profili/db/migrazioni.py:28` |

**VERIFICATO:** le FK non dichiarano ON DELETE CASCADE o ON UPDATE; le relazioni ORM non rendono automaticamente immutabile lo storico (`magazzino_profili/domain/pezzo.py:83`; `magazzino_profili/domain/movimento.py:44`). La rappresentazione dei PK auto-generati PostgreSQL dipende dal DDL SQLAlchemy; non è stata interrogata la sequenza del database reale.

### 3.3 Migrazioni e versione dello schema

**VERIFICATO:** `create_all` precede sempre le migrazioni nel desktop; crea tabelle mancanti ma non aggiorna da solo colonne esistenti (`magazzino_profili/main.py:53`; `magazzino_profili/db/engine.py:47`). Le sei migrazioni aggiungono scorta_minima, impostazioni, scansioni_telefono, campi ciclo di vita/indice eliminato_il, CHECK stato e colore_hex. Il runner ordina per nome, registra ogni file, apre una transazione per migrazione e usa advisory lock PostgreSQL con ricontrollo dopo il lock (`magazzino_profili/db/migrazioni.py:37`, `:43`, `:48`).

**Fragilità VERIFICATE:** cartella migrations assente → ritorna lista vuota senza avviso (`magazzino_profili/db/migrazioni.py:22`); parsing con `split(';')`, non adatto a funzioni SQL/blocchi complessi (`:42`); migrazioni già registrate non confrontate per hash (`:38`); nessun rollback applicativo o backup automatico precedente alle migrazioni, perché il backup arriva dopo (`magazzino_profili/main.py:54`, `:78`). Il locking copre la migrazione singola, non l'intero provisioning `create_all` concorrente (`magazzino_profili/main.py:53`). Il test PostgreSQL delle migrazioni contiene refusi certi: `applica_migrazazioni` anziché `applica_migrazioni`, chiamata di `crea_engine` con un dict al posto dell'URL, query su `name` anziché `nome` (`magazzino_profili/tests/test_migrazioni_postgres.py:24`, `:32`, `:40`). Non sono stati nascosti dagli skip nel giudizio.

### 3.4 Transazioni, concorrenza e connessioni

**VERIFICATO, punti solidi:** carico e scarico usano transazione esplicita, FOR UPDATE e populate_existing; carico gestisce la creazione concorrente con savepoint e vincoli univoci (`magazzino_profili/services/carico.py:25`, `:43`, `:59`, `:170`; `magazzino_profili/services/scarico.py:34`). Barcode/vassoio/stato bloccano la riga (`magazzino_profili/services/pezzi.py:78`; `magazzino_profili/services/stati.py:50`). Scadenza: verifica e soft delete in un'unica UPDATE condizionata, quindi non elimina un record che nel frattempo è diventato Caricato (`magazzino_profili/services/stati.py:95`). Le sessioni UI sono generalmente chiuse con finally; factory expire_on_commit=False e pool_pre_ping migliorano l'uso di oggetti dopo il commit e il recupero connessioni (`magazzino_profili/db/engine.py:28`, `:44`; `magazzino_profili/ui/scheda_carico.py:344`).

**VERIFICATO, limiti:** l'import ODS storico effettua query/mutazioni proprie, senza FOR UPDATE, e committa riga per riga (`magazzino_profili/reports/importa_ods.py:227`, `:264`, `:296`). La coda telefono legge tutte le righe non lette, poi le marca, senza lock di claim e senza destinatario (`magazzino_profili/services/telefono.py:86`). Il restore XLSX è transazionale con LOCK TABLE e riallineamento sequenze; non è una sostituzione distruttiva dell'intero DB e il merge rifiuta conflitti (`magazzino_profili/reports/backup_excel.py:411`, `:425`, `:437`).

**IPOTESI da confermare su PostgreSQL di test:** carico contemporaneo a import ODS può perdere incrementi; due desktop possono prelevare la stessa scansione; esportazione XLSX può mescolare istanti diversi. L'export fa SELECT separati senza fissare REPEATABLE READ (`magazzino_profili/reports/backup_excel.py:171`; `magazzino_profili/db/engine.py:28`). A READ COMMITTED PostgreSQL consente snapshot diversi fra SELECT: [documentazione PostgreSQL](https://www.postgresql.org/docs/16/transaction-iso.html). Conferma con due connessioni a DB usa e getta, transazioni sincronizzate e verifica dei totali/FK esportati. Non è stato provocato alcun guasto sul DB reale.

**VERIFICATO:** `db/server.start` apre `log_app` senza context manager/chiusura esplicita; su fallimento può restare un handle fino al rilascio dell'oggetto (`magazzino_profili/db/server.py:82`). `main` non chiama engine.dispose e non chiude il pianificatore con un finally globale nei rami anticipati (`magazzino_profili/main.py:102`, `:123`). `PianificatoreBackup.ferma` cancella il timer ma non attende un backup già in esecuzione, nonostante il nome/commento suggeriscano maggiore determinismo (`magazzino_profili/backup/backup_db.py:237`).

### 3.5 Percorsi, configurazioni e backup

| Oggetto | Percorso/regola effettiva | Se manca o non è scrivibile | Evidenza |
|---|---|---|---|
| config DB | esplicito → cwd/config.toml → accanto exe frozen → radice sorgente | errore configurazione; popup nel desktop | `magazzino_profili/db/config.py:59`, `:79`; `magazzino_profili/main.py:39` |
| PostgreSQL locale | `Path.home()/AppData/Local/magazzino_profili/pg_data`; bin in pgsql | start restituisce False se dati/bin assenti; main ignora il bool e tenta poi la connessione | `magazzino_profili/db/server.py:26`, `:79`; `magazzino_profili/main.py:50` |
| backup dump | config letta **solo** dalla radice risolta di backup_db.py; default `backup` relativo alla cwd; 6 ore/7 copie | mkdir; errori loggati, l'app continua | `magazzino_profili/backup/backup_db.py:25`, `:49`, `:97`, `:205`; `config.toml:15` |
| log app | `Path.home()/AppData/Local/magazzino_profili/app.log`, non espansione diretta LOCALAPPDATA | mkdir; fallback stderr | `magazzino_profili/main.py:205` |
| log PostgreSQL | `pg_data/log_app` | possibile errore apertura non gestito nello start | `magazzino_profili/db/server.py:82` |
| catalogo PNG | env MAGAZZINO_CATALOGO_IMMAGINI → [immagini] catalogo → catalogo_immagini accanto sorgenti/exe; relativo a base programma | catalogo vuoto/assente → nessuna proposta; warning in alcuni errori | `magazzino_profili/services/catalogo_immagini.py:26`, `:57`, `:105` |
| copie sezioni | default `immagini_sezioni` relativo alla cwd, poi percorso assoluto nel DB | mkdir; eccezione propagata alla UI | `magazzino_profili/services/anagrafica.py:131`, `:144`, `:151` |
| certificati web | config web, relativi alla cartella del TOML; configurazione reale usa percorsi personali assoluti | server rifiuta avvio senza file | `magazzino_profili/web/app.py:118`, `:313`; `config.toml:36` |
| config web | MAGAZZINO_CONFIG → cwd → radice; non coincide con ricerca frozen DB | errore se file assente | `magazzino_profili/web/app.py:72` |
| scadenze | MAGAZZINO_CONFIG → radice; default 300 secondi | default se file assente; errore intervallo<=0 | `magazzino_profili/services/scadenze.py:63` |
| animazioni | QSettings MagazzinoProfili/MagazzinoProfili, chiave interfaccia/animazioni; env MAGAZZINO_NO_ANIM | preferenza Windows o default | `magazzino_profili/ui/animazioni.py:34`, `:62`, `:75` |
| cache icone/barcode | tempfile/magazzino_profili_icone e magazzino_profili_bc | mkdir; barcode logga eccezioni | `magazzino_profili/ui/icone.py:87`; `magazzino_profili/ui/tabella_pezzi.py:555` |
| aggiornamenti | LOCALAPPDATA/magazzino_profili/aggiornamenti; release relativa al TOML per server | mkdir per cache; feed non leggibile → log e prosecuzione | `magazzino_profili/services/aggiornamenti.py:292`; `magazzino_profili/web/app.py:161`; `magazzino_profili/main.py:145` |

**IPOTESI ad alto impatto nel frozen:** backup_db cerca config dentro la radice del bundle, mentre lo spec esclude config.toml; di conseguenza può ignorare pg_dump assoluto/cartella configurata e ripiegare sul PATH. Conferma costruendo un exe di prova in cartella isolata e registrando il percorso TOML scelto, senza dati reali (`MagazzinoProfili.spec:4`; `magazzino_profili/backup/backup_db.py:25`, `:56`; `magazzino_profili/db/config.py:63`). I percorsi incoerenti fra sottosistemi sono un problema certo del codice; l'effetto sull'installazione specifica rimane da verificare.

**VERIFICATO:** dump custom pg_dump con password in variabile d'ambiente, controllo file non vuoto e opzionale `pg_restore --list`, rotazione dopo la verifica. Non è una prova di restore completo; `--list` ispeziona l'archivio, non ricostruisce un database (`magazzino_profili/backup/backup_db.py:101`, `:137`, `:154`). Nomi al secondo, scrittura direttamente nel nome finale e assenza di lock fra processi rendono possibili collisioni e residui parziali dopo timeout/fallimento; la ripianificazione protegge la continuità del timer, non la bontà di tutte le copie (`:99`, `:116`, `:123`, `:167`).

### 3.6 Significato del modello

**VERIFICATO:** un barcode identifica una **riga aggregata profilo+colore+lunghezza**, non una singola barra fisica; la combinazione è unica e può avere quantità >1 (`magazzino_profili/domain/pezzo.py:37`, `:46`, `:60`). Il vassoio è un testo unico sulla riga, non una tabella né una collocazione distinta per ogni barra (`:71`). Due vassoi della stessa combinazione non possono essere rappresentati come due pezzi separati nello schema corrente.

**VERIFICATO:** il codice profilo è normalizzato in maiuscolo senza spazi e con slash trasformati in trattini; descrizione/nome libero non lo sono (`magazzino_profili/db/normalizzazione.py:16`; `magazzino_profili/services/anagrafica.py:92`). Il colore ha codice normalizzato, nome visualizzato e hex facoltativo (`magazzino_profili/domain/colore.py:20`). Barcode generato deterministico `CODICE-COLORE-lunghezza`, modificabile successivamente sullo stesso ID (`magazzino_profili/db/normalizzazione.py:49`; `magazzino_profili/services/pezzi.py:103`).

**VERIFICATO:** stato barcode e stato scorta sono due concetti distinti. Il primo è nullable Caricato/Scaricato; il secondo è calcolato da quantità/soglie, quindi la UI può mostrare contemporaneamente “OK” e “Scaricato” (`magazzino_profili/domain/pezzo.py:73`; `magazzino_profili/services/consultazione.py:179`; `magazzino_profili/ui/tabella_pezzi.py:989`). I movimenti registrano UTC, tipo, quantità, causale e nome utente testuale; il cambio manuale di stato non crea un movimento e conserva solo l'ultimo timestamp (`magazzino_profili/domain/movimento.py:49`; `magazzino_profili/services/stati.py:43`). Nessuno storico completo delle transizioni di stato.

## 4. Stato delle 15 funzioni richieste

Lo stato descrive il requisito **da un capo all'altro**, non la sola presenza di una funzione Python. “Implementata e funzionante” vale nelle prove specificate; PostgreSQL e hardware restano soggetti ai limiti della sezione 10.

| # / funzione | Stato | Evidenza | Note |
|---|---|---|---|
| 1. Barcode Caricato/Scaricato con data/ora | **Implementata ma con bug — VERIFICATO** | `magazzino_profili/services/stati.py:36`; `magazzino_profili/services/carico.py:108`; `magazzino_profili/services/scarico.py:48`; `E/misure.json:4` | cambio manuale funziona; carico nuovo e scarico totale lasciano stato e tempo NULL; ricarico di Scaricato attivo mantiene stato vecchio. Timestamp non mostrato nel pannello stato (`magazzino_profili/ui/tabella_pezzi.py:635`) |
| 2. Eliminazione dopo 48 ore dei soli Scaricato | **Parziale — VERIFICATO; integrazione con bug critico** | `magazzino_profili/services/stati.py:66`, `:95`; `magazzino_profili/web/app.py:346`; `E/misure.json:18` | UPDATE protegge sempre Caricato; confine a 48h corretto, UTC e persistenza testati. È soft delete, non cancellazione fisica. Dipende da web avviato, controllo ogni 300s; può nascondere quantità positiva rimasta Scaricato |
| 3. Vassoio per barcode | **Parziale — VERIFICATO** | `magazzino_profili/domain/pezzo.py:71`; `magazzino_profili/services/pezzi.py:140`; `magazzino_profili/ui/tabella_pezzi.py:822` | modifica e persistenza presenti e testate; opzionale, non obbligatorio in Carico; vecchio ODS scrive Vassoio nell'ubicazione, non in numero_vassoio (`magazzino_profili/reports/importa_ods.py:283`) |
| 4. Modifica barcode senza nuovo record | **Implementata e funzionante nelle prove SQLite — VERIFICATO** | `magazzino_profili/services/pezzi.py:103`; `magazzino_profili/tests/test_barcode_vassoio.py:43`; `E/esiti/test_barcode_vassoio.xml:1` | ricerca per ID, mantiene relazioni/vassoio, controlla duplicati anche eliminati. Concorrenza reale PG non provata |
| 5. Inventario per colore, anche senza giacenza | **Implementata e funzionante nelle prove UI — VERIFICATO** | `magazzino_profili/ui/tabella_pezzi.py:325`; `magazzino_profili/services/consultazione.py:394`; `magazzino_profili/tests/test_ui_smoke.py:107` | Tutti + tab per ogni colore, conteggi e mantenimento selezione; non è paginazione |
| 6. Nome/codice sempre maiuscolo su ogni percorso | **Parziale — VERIFICATO** | `magazzino_profili/db/normalizzazione.py:16`; `magazzino_profili/ui/validatori.py:16`; `magazzino_profili/services/anagrafica.py:92`; `magazzino_profili/reports/backup_excel.py:433` | codice normalizzato su UI/import usuali; descrizione resta libera. Nessun vincolo DB o normalizzazione nel restore XLSX/Core insert. Telefono non crea profili. Aggiornamento codice profilo non esposto da aggiorna_profilo |
| 7. Associazione automatica PNG da catalogo 211 | **Parziale — VERIFICATO nel codice; catalogo reale NON VERIFICABILE** | `magazzino_profili/services/catalogo_immagini.py:144`; `magazzino_profili/ui/scheda_profilo.py:362`, `:447`; `magazzino_profili/reports/importa_ods.py:240`; `E/rilievi_statici.txt:267` | proposta UI e nuovi profili da ODS; crea_profilo da servizio da solo non associa. Cartella effettiva vuota, indice non consultato dal codice |
| 8. Pallini corrispondenti al colore | **Parziale — VERIFICATO** | `magazzino_profili/ui/registro_colori.py:57`; `magazzino_profili/services/colori_base.py:10`; `E/esiti/test_registro_colori.txt:23` | codice corrente usa hex confermato→suggerimento→?; mappa molto incompleta, mancano AN007/RAL7016/RAL9005/RAL8014; bicolore solo suggerito, hex persistito singolo; errore RGB di 1 livello nel test sbiadito |
| 9. Apertura immagini di sezione | **Parziale — VERIFICATO** | `magazzino_profili/ui/scheda_profilo.py:276`, `:320` | selezione PNG e anteprima ridimensionata presenti; nessun visualizzatore separato, zoom/pan o apri esterno nel percorso UI letto |
| 10. Paginazione vera | **Assente — VERIFICATO** | `magazzino_profili/services/consultazione.py:169`; `magazzino_profili/ui/tabella_pezzi.py:951` | nessun limit/offset/cursore inventario; footer N di N descrive filtri, non pagine |
| 11. Login/autenticazione | **Implementata ma con bug autorizzativo — VERIFICATO** | `magazzino_profili/main.py:100`; `magazzino_profili/sicurezza/utenti.py:138`; `magazzino_profili/web/auth.py:151`; `E/prove_aggiuntive.json:2` | bcrypt e ruoli, token web e rate limit. Sola lettura conserva azioni mutanti in Inventario. Piano rimozione in 8.4 |
| 12. Import/export ODS/CSV | **Parziale — VERIFICATO** | `magazzino_profili/reports/export_csv.py:120`; `magazzino_profili/reports/formato_v2.py:1`; `magazzino_profili/reports/ods_v2.py:94`; `magazzino_profili/reports/importa_ods.py:227` | CSV storico atomico additivo; ODS storico parziale; V2 export+validazione, senza applicazione import; nessun menu integrato; vedi 8.3 |
| 13. Backup Excel multi-foglio | **Parziale — VERIFICATO** | `magazzino_profili/reports/backup_excel.py:43`, `:150`, `:411`; `magazzino_profili/ui/finestra_principale.py:730` | servizio a sei fogli e restore testati; menu usa un foglio. PNG, utenti, impostazioni, coda e configurazioni esclusi: non è backup completo dell'installazione |
| 14. Background/tray/avvio automatico | **Parziale — VERIFICATO** | `magazzino_profili/ui/finestra_principale.py:535`; `magazzino_profili/db/server.py:84`; `magazzino_profili/services/scadenze.py:92` | PostgreSQL può restare processo separato, web solo se lanciato esternamente; nessuna tray o registrazione autostart nel codice censito, chiusura desktop interrompe polling e backup desktop |
| 15. Popup aggiornamenti | **Parziale — VERIFICATO nel codice, distribuzione NON VERIFICATA** | `magazzino_profili/main.py:127`; `magazzino_profili/ui/dialogo_aggiornamento.py:86`; `config.toml:55`; `release/manifest.json:3` | feed firmato Ed25519, download verificato SHA/size, popup e QThread; URL localhost/certificato locale, avvio dell'exe in cache senza sostituzione stabile; non dimostrato aggiornamento installato end-to-end |

## 5. Telefono e barcode (Fase D)

### 5.1 Architettura attuale

**VERIFICATO:** browser mobile → HTTPS FastAPI su PC → servizi → stesso PostgreSQL. Le chiamate sono HTTP JSON, non WebSocket. In modalità Lettore, POST `/api/scansione` scrive una coda nel DB; Qt la legge ogni 1.500 ms e consegna alla scheda corrente. POST `/api/telefono/ping` aggiorna una sola impostazione globale ogni 10 s; la UI considera collegato un ping negli ultimi 30 s (`magazzino_profili/web/routes_barcode.py:248`, `:262`; `magazzino_profili/ui/collega_telefono.py:39`, `:84`; `magazzino_profili/services/telefono.py:15`; `magazzino_profili/web/static/scansione.js:53`).

**VERIFICATO:** modalità mobile Carico/Scarico invocano direttamente i servizi; il carico remoto non crea pezzi nuovi. Consulta usa GET `/api/pezzi/{barcode}`. Accesso Bearer dopo login sulle stesse utenze desktop; il token resta in memoria JS e scade dopo 3.600 s nella configurazione corrente (`magazzino_profili/web/routes_barcode.py:135`, `:183`, `:190`, `:218`; `magazzino_profili/web/static/scansione.js:22`; `config.toml:34`).

**VERIFICATO:** il server è configurato per `0.0.0.0:8443`, quindi il codice non impone loopback; `0.0.0.0` è un indirizzo di ascolto, non l'URL da inserire nel telefono. Non esiste rilevamento automatico dell'IP locale nel percorso di collegamento: l'URL viene letto dal TOML e trasformato in QR (`config.toml:30`; `magazzino_profili/services/telefono.py:99`; `magazzino_profili/ui/collega_telefono.py:116`). La documentazione presume uso remoto da rete dati; LAN e accesso esterno devono essere configurati esplicitamente (`magazzino_profili/web/app.py:20`). Non risulta alcuna configurazione firewall/router/VPN automatica nei moduli o negli script censiti.

### 5.2 Diagnosi ordinata, con prove da effettuare

Le prime due condizioni sono accertate; le successive sono **IPOTESI** finché non si eseguono i test sull'ambiente reale. Non confondere “pagina non raggiungibile”, “login rifiutato”, “fotocamera negata” e “scansione non consegnata”.

| Ordine | Causa | Stato/evidenza | Test di conferma e risultato atteso |
|---|---|---|---|
| 1 | URL pubblico mancante: niente QR e niente ascolto desktop avviato dal pulsante | **VERIFICATO**, `config.toml:28`, `magazzino_profili/ui/finestra_principale.py:508`, `magazzino_profili/ui/collega_telefono.py:185`; `E/ambiente.txt:9` | aprire Collega telefono: deve comparire “Indirizzo del server web non configurato”. In una configurazione di prova, assegnare URL HTTPS raggiungibile dal telefono e verificare il QR |
| 2 | Certificato valido solo per localhost/127.0.0.1 | **VERIFICATO** SAN e soggetto/emittente locali; fiducia del telefono **NON VERIFICABILE**, `config.toml:36`; `E/ambiente.txt:4` | aprire sul telefono l'URL con nome/IP effettivo e controllare errore certificato. Non usare localhost sul telefono: indicherebbe il telefono stesso. Serve identità TLS corrispondente all'URL e attendibile |
| 3 | Processo web non avviato o non supervisionato | **IPOTESI molto probabile**, desktop non lo avvia (`magazzino_profili/main.py:81`; `magazzino_profili/web/app.py:290`) | su PC reale verificare listener TCP 8443 e processo proprietario; avvio controllato del modulo web con database di test. HTTPS deve restituire la pagina. Nessuna conclusione sul listener reale dal sandbox |
| 4 | URL errato: 127.0.0.1/localhost/0.0.0.0, IP cambiato o porta omessa | **IPOTESI**, manca discovery/validazione di raggiungibilità (`magazzino_profili/services/telefono.py:110`; `magazzino_profili/ui/collega_telefono.py:185`) | confrontare URL QR con IPv4 LAN/DNS scelto e porta 8443; telefono e PC devono risolvere la stessa destinazione. Preferire hostname stabile |
| 5 | Firewall Windows o isolamento Wi-Fi guest/AP | **IPOTESI**, ascolto su tutte le interfacce non apre il firewall (`magazzino_profili/web/app.py:370`) | stesso Wi-Fi non guest, verificare HTTPS da altro dispositivo; regola in ingresso TCP 8443 limitata alla rete privata/dispositivi previsti. Non disabilitare globalmente il firewall. Confrontare rete principale e guest |
| 6 | Telefono su rete mobile senza VPN/tunnel/port forwarding; CGNAT | **IPOTESI**, esposizione deliberatamente esterna al codice (`magazzino_profili/web/app.py:20`) | prova prima in LAN, poi su rete mobile con URL VPN/tunnel; se LAN funziona e WAN no, isolare DNS/instradamento/esposizione, senza esporre PostgreSQL |
| 7 | Pagina aperta HTTP, browser non in secure context o permesso camera negato | **IPOTESI sul dispositivo**, uso camera e messaggio presenti (`magazzino_profili/web/static/scansione.js:197`) | verificare `window.isSecureContext`, `navigator.mediaDevices`, autorizzazione fotocamera, camera posteriore. Un server HTTP su IP LAN non è una soluzione equivalente a HTTPS |
| 8 | Login, ruolo o token scaduto | **IPOTESI**, 401/403 e ping richiede carico (`magazzino_profili/web/routes_barcode.py:110`, `:265`; `magazzino_profili/web/auth.py:151`) | provare utente operatore valido su DB di prova e controllare codice HTTP; Sola lettura non può inviare ping/lettore. Il client avvia ping anche per quel ruolo: può mostrare l'app ma non risultare collegato |
| 9 | Scan accodata ma desktop sulla scheda sbagliata, coda vecchia o ascolto spento | **VERIFICATO come comportamento**, `magazzino_profili/services/telefono.py:62`, `:78`; `magazzino_profili/ui/finestra_principale.py:522` | aprire Carico/Scarico, attivare collegamento, inviare barcode noto; controllare risposta POST e consegna UI separatamente. Le righe già lette non vengono riproposte, quelle oltre 120s sono scartate |
| 10 | Configurazioni discordanti fra processi, DB indisponibile o schema non aggiornato | **IPOTESI**, ricerche TOML differenti e web non migra (`magazzino_profili/web/app.py:72`, `:339`; `magazzino_profili/db/config.py:59`) | registrare percorsi config effettivi senza password; stesso DB di test e migrazioni applicate; 503 deve essere leggibile sul telefono |

**VERIFICATO nell'ambiente letto:** i due file TLS esistono; il certificato è CN=localhost, SAN DNS localhost e IP 127.0.0.1, intervallo 29/10/2026–27/10/2036. Non è scaduto alla data dell'audit, ma manca il nome/IP usato da un telefono remoto (`E/ambiente.txt:2`). Le interrogazioni PowerShell di rete/firewall non hanno restituito righe nel sandbox: **NON VERIFICABILE** se ciò dipenda da visibilità/permessi; non si conclude che firewall o server siano assenti (`E/ambiente.txt:10`).

Per il requisito browser, consultata la [documentazione MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia): camera disponibile solo in contesto sicuro e con autorizzazione. La presenza di TLS non rende automaticamente attendibile un certificato locale su un altro dispositivo. La prova HTTPS esistente genera esplicitamente la propria CA attendibile per il client di test; non dimostra la fiducia di Safari/Chrome sul telefono (`magazzino_profili/tests/test_web_https_reale.py:111`).

### 5.3 QR, errori e affidabilità delle scansioni

**VERIFICATO:** il QR contiene solo l'URL configurato; non effettua pairing, non include un token monouso, non seleziona PC/utente. Generazione qrcode con correzione M, bordo 2, matrice ingrandita; lettura reale del QR da fotocamera **NON VERIFICATA** (`magazzino_profili/ui/collega_telefono.py:116`). L'assenza di URL viene spiegata nel dialogo; il dialogo di attesa ricorda che il server deve essere avviato ma non controlla endpoint o certificato (`:185`, `:234`).

**VERIFICATO:** timeout fetch 15 s, messaggi di esito incerto per movimenti, 503 per DB, 422 tradotti e 401 per token; ping ignora gli errori diversi da 401. Il timeout viene cancellato dopo `fetch`, prima di attendere il body JSON: non copre necessariamente l'intera lettura della risposta (`magazzino_profili/web/static/scansione.js:36`, `:42`, `:70`, `:96`; `magazzino_profili/web/app.py:169`, `:242`). Lo script JS commenta ancora “CDN”, ma il caricamento reale della libreria è locale (`magazzino_profili/web/static/scansione.js:5`; `magazzino_profili/web/templates/scansione.html:93`).

**Fragilità VERIFICATE:** la conferma “Inviato al PC” certifica l'accodamento, non il movimento desktop (`magazzino_profili/web/routes_barcode.py:260`). Le scansioni vengono marcate lette **prima** dell'azione UI e senza ACK finale; una scheda non operativa le consuma mostrando un toast. Se Scarico non ha causale, l'azione si ferma ma il messaggio è già consumato. Nessuna chiave di idempotenza: ritentare un POST dopo perdita della risposta può duplicare movimento o scansione (`magazzino_profili/services/telefono.py:93`; `magazzino_profili/ui/finestra_principale.py:528`; `magazzino_profili/ui/scheda_scarico.py:241`; `magazzino_profili/web/routes_barcode.py:58`).

**VERIFICATO:** ping e coda sono globali, non associati a destinatario; il polling non filtra l'utente e non reclama righe con lock (`magazzino_profili/services/telefono.py:15`, `:87`). **IPOTESI ad alto impatto:** più telefoni/desktop possono interferire o duplicare scarichi. Conferma con due client desktop di test e una scansione, misurando consegne e movimenti. Anche il timeout di una scan Lettore ha potenziale effetto incerto ma il client lo tratta come semplice errore ripetibile (`magazzino_profili/web/static/scansione.js:122`, `:248`).

### 5.4 Alternative e raccomandazione

Le alternative sono **proposte**, basate sui punti di estensione verificati in `magazzino_profili/web/app.py:192`, `magazzino_profili/web/routes_barcode.py:248`, `magazzino_profili/services/telefono.py:78` e `magazzino_profili/ui/collega_telefono.py:84`.

| Architettura | Pro | Contro | Impatto incrementale |
|---|---|---|---|
| A. HTTPS in LAN + coda DB migliorata | conserva quasi tutto il codice; dati sul PC; latenza prevedibile in magazzino | richiede hostname/IP stabile, certificato attendibile sui telefoni, firewall privato e PC acceso | basso/medio: config unica, diagnostica, supervisione server, pairing e claim/ACK scansioni |
| B. HTTPS tramite rete privata/VPN o tunnel protetto + API esistente | accesso anche fuori Wi-Fi; endpoint stabile; può semplificare gestione certificato del browser | dipendenza da infrastruttura/account; occorre progettare chi può raggiungere l'endpoint; non risolve da solo perdite/duplicati della coda | medio: configurazione ingresso TLS coerente, trust proxy controllato, autenticazione/pairing; riuso servizi e pagina mobile |
| C. Canale persistente WebSocket con pairing per singolo PC | consegna diretta con ACK, meno polling, sessioni esplicite, stato collegamento significativo | riconnessione/heartbeat/backpressure e idempotenza più complessi; HTTPS/WSS rimane necessario alla camera | medio/alto: nuovo hub FastAPI e client Qt, mantenendo servizi carico/scarico e fallback HTTP |

**Raccomandazione:** prima A se l'uso è nello stesso magazzino; B se serve davvero rete mobile. Conservare FastAPI e i servizi, aggiungere URL stabile, TLS valido, avvio supervisionato, diagnostica raggiungibilità e pairing per destinazione, quindi claim/ACK e idempotenza. Valutare C soltanto dopo aver misurato limiti del polling: WebSocket non corregge un certificato errato o un server spento. Evitare la rimozione indiscriminata dell'autenticazione su un endpoint raggiungibile in rete; il bisogno di pairing deve essere deciso separatamente dal login desktop.

## 6. Prestazioni (Fase E)

### 6.1 Misure effettive e loro limiti

**VERIFICATO:** Windows/Python dell'ambiente, SQLite in memoria, Qt offscreen, dati sintetici; dataset con un profilo, un colore e combinazioni distinte per lunghezza, quantità 10. Le lunghezze 1..12.000 sono artificiose e non una validazione del limite fisico ODS 6.500 mm. Niente DB reale, rete telefono o disco di produzione. Mediana di 3 letture per KPI/lista; una misura per operazioni UI/export/import. Misure raccolte mentre erano in corso anche altri test: indicative della macchina, non benchmark isolato di laboratorio (`E/misure.py:79`; `E/prove_aggiuntive.py:25`).

| Operazione | 1.000 righe | 12.000 righe | Dettaglio/evidenza |
|---|---:|---:|---|
| Query KPI aggregata | 0,0011 s | 0,0072 s | 1 query per esecuzione, `E/misure.json:37`, `:62` |
| Lettura completa pezzi + relazioni | 0,0081 s | 0,1175 s | 3 query su questo dataset, `E/misure.json:45`, `:70` |
| Costruzione scheda Inventario | 0,286 s | 3,634 s | query + creazione widget, `E/misure.json:52`, `:77` |
| Ricostruzione tabella | 0,282 s | 4,063 s | 3 query, `E/misure.json:53`, `:78` |
| Export CSV V2 | 0,036 s | 0,132 s | `E/misure.json:55`, `:80` |
| Export ODS V2 | 0,346 s | 5,420 s | DOM odfpy e serializzazione, `E/misure.json:56`, `:81` |
| Backup XLSX multi-foglio | 0,109 s | 0,980 s | dataset senza storico voluminoso, `E/misure.json:57`, `:82` |
| Import CSV storico | 1,202 s | 14,569 s | transazione unica, query per riga, `E/prove_aggiuntive.json:3` |

**VERIFICATO:** import dei moduli misurati 1,233 s in un processo nuovo; non è il tempo totale di avvio del programma (`E/misure.json:3`). Avvio completo **NON MISURATO** perché coinvolgerebbe PostgreSQL/backup/login reali. Dal codice: pg_isready ha timeout 15 s per chiamata, tentativo di start ripete controlli fino a TIMEOUT_START=30; il primo backup può attendere pg_dump fino a 600 s più verifica 120 s; feed ha timeout 8 s. Sono limiti/attese configurate, non tempi osservati né un limite globale semplice di 30 s (`magazzino_profili/db/server.py:30`, `:61`, `:95`; `magazzino_profili/backup/backup_db.py:121`, `:150`; `magazzino_profili/main.py:144`).

**Stima dichiarata:** consegna scansione al desktop aggiunge da quasi 0 a circa 1,5 s di attesa polling, oltre a rete, DB ed elaborazione Qt. Il lettore continuo attende inoltre 1,2 s prima di riavviare la camera; analisi immagini 10 fps. Nessun tempo reale camera/decodifica misurato (`magazzino_profili/ui/collega_telefono.py:39`; `magazzino_profili/web/static/scansione.js:201`, `:249`). Apertura schede già create: non ripete il provisioning, ma esegue una dissolvenza da 140 ms; tempo percepito sul monitor reale **NON VERIFICATO** (`magazzino_profili/ui/finestra_principale.py:252`; `magazzino_profili/ui/animazioni.py:30`).

### 6.2 Colli di bottiglia e correzioni

| Collo di bottiglia | Stato/evidenza | Impatto stimato | Correzione incrementale e verifica |
|---|---|---|---|
| Tutti i risultati inventario in memoria, tutte le righe renderizzate | VERIFICATO, `magazzino_profili/services/consultazione.py:169`; `magazzino_profili/ui/tabella_pezzi.py:951` | alto, ~4 s a 12k | limit/cursore ordinato stabile, count separato, QAbstractTableModel/QTableView; controllare righe residenti e latenza su 12k/100k sintetici |
| Un widget Pillola per ogni riga | VERIFICATO, `magazzino_profili/ui/tabella_pezzi.py:1000` | alto in scala | delegate per disegno della pillola; confronto stesso dataset e memoria residente |
| Ricerca ad ogni carattere e filtro Profili dopo fetch completo | VERIFICATO, `magazzino_profili/ui/tabella_pezzi.py:242`; `magazzino_profili/ui/scheda_profilo.py:89`, `:207`, `:218` | medio/alto | debounce 200–300 ms, ricerca DB con pagina; misura numero query durante digitazione |
| LIKE %termine%, EXISTS su profili/colori e trim/upper ubicazione | VERIFICATO query; piano reale NON VERIFICATO, `magazzino_profili/services/consultazione.py:127`, `:149` | medio/alto su molti dati | EXPLAIN su copia PG; solo dopo scegliere pg_trgm/indici funzionali, senza aggiungere indici indiscriminati |
| Stato/time scadenze e coda senza indici dedicati | VERIFICATO schema, `magazzino_profili/domain/pezzo.py:75`; `magazzino_profili/domain/scansione_telefono.py:16` | medio, cresce con storico | valutare indice parziale Scaricato attivo+timestamp e non-letto/id; EXPLAIN e costo scritture |
| Ultimi movimenti ordinati per data senza indice data_ora | VERIFICATO, `magazzino_profili/services/consultazione.py:354`; `magazzino_profili/domain/movimento.py:49` | medio quando lo storico cresce | indice (data_ora,id), eventualmente (pezzo_id,data_ora,id); misurare query globale e per pezzo |
| Query nei cicli import CSV/ODS | VERIFICATO, `magazzino_profili/reports/export_csv.py:152`; `magazzino_profili/reports/importa_ods.py:230`, `:251`, `:265` | alto: 14,57 s/12k CSV | cache anagrafiche per import, prevalidazione batch e upsert controllati mantenendo lock/storico; test equivalenza contabile e concorrenza |
| Eliminazione scaduti: una lettura + transazione per ID | VERIFICATO, `magazzino_profili/services/scadenze.py:118`, `:119` | medio su molti scaduti | batch condizionato con RETURNING o piccoli lotti, preservando ri-verifica atomica |
| Primo backup nel thread chiamante prima della UI | VERIFICATO, `magazzino_profili/main.py:78`; `magazzino_profili/backup/backup_db.py:235` | alto all'avvio | worker vero con stato visibile; non sacrificare protezione pre-migrazione, usare splash/progresso |
| Cambio tema ricrea tutte le schede, filtri e query | VERIFICATO, `magazzino_profili/ui/finestra_principale.py:603` | alto con molti dati; perde form non salvati | applicare palette/stile ai widget esistenti; test conservazione form/selezione e conteggio query |
| Immagine sezione caricata due volte, decodifica a risoluzione intera | VERIFICATO, `magazzino_profili/ui/scheda_profilo.py:277`, `:278` | basso oggi, medio con PNG grandi | QImageReader con scaledSize, cache limitata; misurare PNG reali quando disponibili |
| Generazione PNG barcode e scrittura temp a ogni selezione | VERIFICATO, `magazzino_profili/ui/tabella_pezzi.py:555` | medio con selezioni rapide | cache per barcode/dimensioni, invalidazione dopo modifica; evitare rigenerazione identica |
| Polling DB nel thread Qt ogni 1,5 s | VERIFICATO, `magazzino_profili/ui/collega_telefono.py:47`, `:90` | medio, alto con DB lento | spostare I/O su worker; backoff quando offline; niente polling quando disattivo (già rispettato) |
| Avvisi: widget per ogni riferimento sotto soglia | VERIFICATO, `magazzino_profili/ui/avvisi.py:1`; `magazzino_profili/services/consultazione.py:447` | medio/alto se molti avvisi | modello/lista virtuale e limiti/pagine; verificare 10k avvisi |
| Export completi in RAM, ODS DOM e V2 .all | VERIFICATO, `magazzino_profili/reports/formato_v2.py:129`; `magazzino_profili/reports/ods_v2.py:50` | medio/alto | export su worker, lettura a batch/snapshot coerente; openpyxl backup è write_only ma query senza yield_per |
| Log app senza rotazione; eccezioni ricorrenti worker/polling | VERIFICATO configurazione, `magazzino_profili/main.py:214`; `magazzino_profili/services/scadenze.py:122` | basso/medio | RotatingFileHandler, segnalazione degrado e rate limit errori identici; dimensione log nel tempo |

**VERIFICATO:** non c'è N+1 per ogni pezzo nella lettura inventario misurata: selectinload recupera profili/colori, KPI aggrega una query (`magazzino_profili/services/consultazione.py:17`, `:249`; `E/misure.json:69`). Su molti profili/colori selectinload può suddividere i batch: “3 query” non è una garanzia per qualsiasi dataset. Esistono query aggiuntive per selezione/anteprima e per split ambiguo barcode (`magazzino_profili/services/consultazione.py:315`, `:332`). Non è stato trovato un timer di refresh inventario a frequenza elevata; i timer principali sono quelli telefono e scadenze sopra citati.

## 7. UI reale vs mockup (Fase F)

### 7.1 Materiale disponibile e verifica visiva

**NON VERIFICABILE:** confronto diretto schermata-per-schermata con l'HTML originale, perché `magazzino-mockup-grande.html` manca; `web/templates/scansione.html` è la pagina mobile operativa, non quel mockup (`E/rilievi_statici.txt:271`; `CHANGELOG-fase4.md:26`). Sono disponibili la specifica testuale `_prompt_fase5.md` e screenshot storici; possono documentare l'intento ma non sostituiscono l'originale.

**VERIFICATO:** renderizzate tutte e cinque le schede Qt in entrambi i temi a 1700×1000, con tre profili e movimenti sintetici. All'inizio il backend offscreen non vedeva font e produceva quadratini; il rilievo ha poi caricato **solo nel processo di prova** Segoe UI/Arial dai file Windows, senza installare font o modificare l'applicazione. Le immagini `E/qa_*.png` sono quelle leggibili da considerare; le precedenti `E/ui_*.png` non sono una prova di difetto dei font dell'app reale (`E/qa_ui.json:2`; `E/schermate.py:17`). Sono state ispezionate direttamente le schermate Inventario chiaro, Carico scuro, Scarico chiaro e Profili scuro; gli altri render sono disponibili, ma non costituiscono una verifica manuale esaustiva di ogni stato/tema.

### 7.2 Confronto per schermata

| Schermata | UI attuale VERIFICATA | Confronto con intento documentato / differenze |
|---|---|---|
| Inventario | quattro KPI orizzontali, chip colore, ricerca/filtri, tabella, aside 495 px, dettagli barcode/movimenti, vassoio e stato aggiunti | intento `_prompt_fase5.md:996`; implementazione `magazzino_profili/ui/tabella_pezzi.py:252`, `:481`, `:625`. Le colonne extra richiedono scorrimento orizzontale già a 1700 px; titolo/descrizione profilo stretti e troncati, ricerca compressa. Evidenza render `E/qa_chiaro_inventario.png`, geometrie `magazzino_profili/ui/tabella_pezzi.py:434` |
| Carico | form a sinistra con barcode grande, campi manuali e causali; movimenti a destra; Collega telefono | intento `_prompt_fase5.md:1011`; `magazzino_profili/ui/scheda_carico.py:69`. A 1700×1000 la parte bassa/Salva richiede scroll; larghezza fissa 660 px e molti margini consumano spazio. Manca campo numero_vassoio dedicato nel form; ubicazione non è lo stesso dato |
| Scarico | barcode, quantità, causale obbligatoria, chip, anteprima e bottone rosso; movimenti a destra | `magazzino_profili/ui/scheda_scarico.py:65`, `:247`; intento `_prompt_fase5.md:1011`. Il vecchio testo della specifica prevedeva anche tabella pezzi se cliccabile; il codice corrente concentra il flusso sul barcode. Conferma totale presente. Nessun numero vassoio editabile qui |
| Profili | elenco sinistro e form destro largo 540 px; anteprima PNG più in basso | `magazzino_profili/ui/scheda_profilo.py:91`, `:119`, `:276`; intento `_prompt_fase5.md:1023`. Righe elenco ~native, visivamente molto più piccole delle righe Inventario da 76 px; immagine e relativi controlli sotto la piega, manca apertura ingrandita |
| Telefono | dialogo Qt con QR/istruzioni o errore URL; pagina mobile bianca con login, Carico/Scarico/Lettore/Consulta | `magazzino_profili/ui/collega_telefono.py:172`; `magazzino_profili/web/templates/scansione.html:21`, `:93`. Nessun tema scuro mobile, nessun pairing QR, nessuna diagnostica TLS/rete nel dialogo; confronto visivo originale NON VERIFICABILE |
| Avvisi, aggiuntiva | scheda autonoma con soglia e righe; badge nell'header | `magazzino_profili/ui/avvisi.py:1`; `magazzino_profili/ui/finestra_principale.py:474`. Badge “0” resta visibile nei render; difformità dall'intento di nasconderlo senza avvisi (`_prompt_fase5.md:1039`) |

**VERIFICATO:** scala corrente già ingrandita: base 20 px, bottoni 20/21/18 px, suggerimenti 19, testo secondario 17–18, KPI 32, barcode 27, card radius 18 (`magazzino_profili/ui/tema.py:16`, `:36`, `:71`, `:88`). L'intento documentato era 1rem=24 px, body ~20, rispetto a vecchi 15 px (`_prompt_fase5.md:15`). Non sarebbe corretto affermare che oggi tutta la UI è ancora a 15 px. Il requisito “molto più grande” va tradotto in una misura desiderata e una risoluzione/DPI; uno scaling uniforme ulteriore peggiorerebbe gli spazi già insufficienti. `SCALA=1.0` è una costante, non un'impostazione utente persistente; `M.RIGA_INV=76` e alcuni numeri non passano da rem (`magazzino_profili/ui/tema.py:16`, `:82`).

### 7.3 Contrasti, temi e transizioni

**VERIFICATO per le coppie misurate:** testo principale/carta 13,71:1 scuro e 17,43:1 chiaro; testo_dim/carta 6,27 e 6,35; testo_debole/carta2 4,89 e 4,95. I token principali non dimostrano il problema generalizzato “testo chiaro illeggibile” delle vecchie versioni. Sono rapporti calcolati dai token RGB, non una certificazione di tutte le superfici/hover/stati (`E/qa_ui.json:13`; `magazzino_profili/ui/tema.py:154`, `:180`).

**VERIFICATO visivamente:** i placeholder dei campi vuoti sono più deboli delle etichette, soprattutto nel tema chiaro su campo quasi bianco; sulle tabelle troncamento e sovraffollamento riducono la leggibilità più del contrasto dei testi normali (`E/qa_chiaro_scarico.png`; `E/qa_chiaro_inventario.png`; `magazzino_profili/ui/tema.py:397`). **IPOTESI:** alcuni placeholder ereditano un colore traslucido nativo anziché il token atteso; confermare campionando palette effettiva e colori su monitor/DPI reale. Il badge helper impone bianco fisso indipendentemente dal fondo, ma non è nel percorso attuale verificato: rischio di riuso, non bug visibile accertato (`magazzino_profili/ui/tema.py:506`).

**VERIFICATO:** esistono dissolvenze schede 140 ms, transizione tema 240, contatori/scossa fino a 320 e animazioni toast; spegnibili con env/QSettings e rispettano impostazione Windows (`magazzino_profili/ui/animazioni.py:30`, `:57`, `:115`; `magazzino_profili/ui/finestra_principale.py:253`). Nei test ordinari sono disattivate; i test dedicati le accendono senza salvare impostazioni (`magazzino_profili/tests/conftest.py:5`; `magazzino_profili/tests/test_animazioni.py:20`). Non sono assenti. **Bug VERIFICATO nel codice:** il cambio tema ricostruisce schede e perde form/filtri correnti (`magazzino_profili/ui/finestra_principale.py:603`); la fluidità a DPI elevati e con dati reali resta **NON VERIFICATA**.

## 8. Bug, rischi e sicurezza (Fase G)

### 8.1 Registro ordinato per gravità

| ID / gravità | Stato | Problema e conseguenza | Evidenza | Correzione/verifica proposta |
|---|---|---|---|---|
| G01 **critico** | VERIFICATO e riprodotto | ricarico di Scaricato attivo mantiene stato vecchio; dopo 48h soft delete nasconde anche 5 pezzi nuovi. Riattivazione successiva somma al vecchio saldo, prova 5+2=7 | `magazzino_profili/services/carico.py:108`, `:130`; `magazzino_profili/services/stati.py:99`; `E/misure.json:14` | definire transizioni coerenti col carico e proteggere quantità positive; regressione su riavvio/DST/concorrenza |
| G02 **alto** | VERIFICATO e riprodotto | Sola lettura può scrivere stato, vassoio/barcode e cancellare dal pannello Inventario; mancato controllo autorizzativo sulle azioni | `magazzino_profili/ui/finestra_principale.py:440`; `magazzino_profili/ui/tabella_pezzi.py:653`, `:765`; `E/prove_aggiuntive.json:2` | autorizzare ogni comando, disabilitare/hide controlli e testare scritture negabili; menu colore contestuale incluso |
| G03 **alto** | VERIFICATO | stato e timestamp non assegnati al carico nuovo o scarico totale; scadenza non parte su normali movimenti | `magazzino_profili/services/carico.py:126`; `magazzino_profili/services/scarico.py:48`; `E/misure.json:4` | regola unica transazionale; distinguere scarico parziale da esaurimento |
| G04 **alto** | VERIFICATO nel codice; collisione IPOTESI | dump finale scritto direttamente, nome al secondo; due istanze possono sovrascrivere stessa destinazione e ruotare copie in gara; backup fallito può lasciare parziale non marcato | `magazzino_profili/backup/backup_db.py:99`, `:123`, `:167` | nomi unici, temporaneo+rename, lock fra processi, pulizia sicura, prova collisione su copie sintetiche |
| G05 **alto** | VERIFICATO | backup iniziale blocca avvio fino a timeout estesi; stato del backup non mostrato all'utente; parametri frozen incoerenti | `magazzino_profili/main.py:78`; `magazzino_profili/backup/backup_db.py:25`, `:235`; `MagazzinoProfili.spec:4` | config unica, worker/progresso, stato backup, ripristino verificato prima di migrare |
| G29 **alto** | VERIFICATO nel codice e con subprocess simulato; effetto autenticazione reale NON VERIFICATO | setup non idempotente sulle credenziali: il primo init cancella pg_pass; il secondo genera una password diversa ma salta initdb se pg_data esiste. La nuova password non viene applicata al server e resta in un file in chiaro nel ramo anticipato | `setup_database.py:50`, `:75`, `:95`, `:204`; `E/prova_setup.json:2` | rilevare installazione esistente prima di generare credenziali; riusare config valida senza scrivere password temporanee inutili; prova doppio setup su cluster usa e getta |
| G06 **alto** | VERIFICATO | ODS storico committa per riga, salta invalidi, errore solo print; secondo import somma ancora; può restituire successo CLI pur con errori | `magazzino_profili/reports/importa_ods.py:216`, `:227`, `:307`; `importa_ods.py:44` | anteprima e modalità esplicita, transazione atomica quando richiesta, errori strutturati e codice uscita coerente |
| G07 **alto** | IPOTESI fondata | import ODS senza lock può perdere aggiornamenti concorrenti; coda letta da più desktop senza claim | `magazzino_profili/reports/importa_ods.py:264`; `magazzino_profili/services/telefono.py:87` | test PG a due connessioni; riuso helper carico con lock, destinazione+claim+ACK scansioni |
| G08 **alto** | VERIFICATO | scansioni consumate prima della UI, perse su scheda errata/causale mancante; messaggio mobile “Inviato” non certifica scarico | `magazzino_profili/services/telefono.py:93`; `magazzino_profili/ui/finestra_principale.py:528`; `magazzino_profili/ui/scheda_scarico.py:241` | coda con stati e ACK, errori visibili sul telefono, pairing per sessione |
| G09 **alto** | VERIFICATO assenza; duplicazione IPOTESI | nessuna idempotenza POST; ritentare dopo risposta persa può ripetere movimento | `magazzino_profili/web/routes_barcode.py:58`, `:135`; `magazzino_profili/web/static/scansione.js:83` | ID richiesta univoco e risultato persistente; prova commit seguito da disconnessione e retry |
| G10 **alto** | VERIFICATO configurazione | telefono senza URL, certificato localhost, nessun avvio/supervisione automatico | `config.toml:28`; `magazzino_profili/main.py:81`; `E/ambiente.txt:8` | diagnosi 5.2, non cambiare host a caso: 0.0.0.0 è già corretto per ascolto LAN |
| G11 **alto** | VERIFICATO | backup “completo” XLSX non raggiungibile dal menu e non include PNG/config/utenti/impostazioni; restore su altra macchina perde immagini da percorsi assoluti | `magazzino_profili/reports/backup_excel.py:6`, `:43`; `magazzino_profili/ui/finestra_principale.py:730`; `magazzino_profili/services/anagrafica.py:151` | distinguere report/backup dati/backup installazione; pacchetto asset e prova disaster recovery |
| G12 **medio** | VERIFICATO | pulsante PDF importa `genera_pdf_inventario`, ma reports esporta `esporta_inventario_pdf`; il menu segnala indisponibilità invece di generare | `magazzino_profili/ui/finestra_principale.py:698`; `magazzino_profili/reports/__init__.py:4`; `magazzino_profili/reports/export_pdf.py:34` | collegare funzione corretta e contratto ritorno; test azione menu su destinazione temporanea |
| G13 **medio** | VERIFICATO | export Excel storico interpreta descrizione `=1+1` come formula; anche export menu usa ws.append diretto | `magazzino_profili/reports/export_excel.py:49`; `magazzino_profili/ui/finestra_principale.py:735`; `E/misure.json:25` | forzare tipo testo come backup_excel._scrivi; prova carichi formula =,+,-,@. Per CSV valutare policy spreadsheet-safe |
| G14 **medio** | VERIFICATO | CSV export storico/V2 senza BOM, malgrado descrizione commit dica BOM; V2 import soltanto validazione | `magazzino_profili/reports/export_csv.py:47`; `magazzino_profili/reports/formato_v2.py:144`, `:253`; `E/rilievi_statici.txt:639` | dichiarare codifica e aggiungere BOM se necessario a Excel; separare validazione e applicazione import |
| G15 **medio** | VERIFICATO | numero_vassoio resta NULL in ODS storico; valore colonna Vassoio convertito in ubicazione | `magazzino_profili/reports/importa_ods.py:120`, `:283` | mapping esplicito, migrazione dati solo con decisione dell'utente e anteprima |
| G16 **medio** | VERIFICATO | profilo e immagine salvati in transazioni distinte; errore copia/associazione può lasciare profilo già creato; fallback filename con id non ricontrolla conflitto | `magazzino_profili/ui/scheda_profilo.py:429`, `:447`; `magazzino_profili/services/anagrafica.py:52`, `:150` | staging atomico, cleanup/compensazione e salvataggio unico; test terzo file diverso con stesso nome e id |
| G17 **medio** | VERIFICATO assenza; exploit NON VERIFICATO | validazioni distribuite, niente CHECK DB peso/lunghezza positiva o uppercase; restore inserisce valori testuali grezzi | `magazzino_profili/domain/profilo.py:21`; `magazzino_profili/reports/backup_excel.py:265`, `:433` | normalizzare/validare confini e vincoli selettivi, prima audit dati su copia |
| G18 **medio** | VERIFICATO | cambio tema perde form e filtri; ricerche/rendering sul thread UI e niente pagine | `magazzino_profili/ui/finestra_principale.py:603`; `magazzino_profili/ui/tabella_pezzi.py:951` | conservazione stato e modello paginato; benchmark stesso dataset |
| G19 **medio** | VERIFICATO | server web può fallire ma restituire exit code 0 dopo except; supervisore può credere arresto regolare | `magazzino_profili/web/app.py:381`, `:385` | exit nonzero ed healthcheck; prova certificato malformato su server di test |
| G20 **medio** | VERIFICATO; effetti reali NON VERIFICATI | update lancia exe dalla cache, non aggiorna collegamento/installazione; feed localhost e certificato locale; finestra chiudibile durante worker senza gestione esplicita di cancellazione/attesa | `magazzino_profili/services/aggiornamenti.py:292`, `:316`; `magazzino_profili/ui/dialogo_aggiornamento.py:158`; `config.toml:55` | protocollo installazione/percorso stabile e rollback; test chiusura popup durante download e riavvio successivo |
| G21 **medio** | IPOTESI | snapshot XLSX inconsistente con scritture parallele; .tmp con nome fisso può collidere fra export contemporanei | `magazzino_profili/reports/backup_excel.py:169`, `:176`; `magazzino_profili/reports/formato_v2.py:143` | REPEATABLE READ read-only, file temporaneo univoco, prova concorrente |
| G22 **medio** | VERIFICATO | migrazioni applicate prima del backup, assenza dir ignorata; test PG migrazione difettoso ma saltato | `magazzino_profili/main.py:54`; `magazzino_profili/db/migrazioni.py:22`; `magazzino_profili/tests/test_migrazioni_postgres.py:32` | preflight e snapshot pre-migrazione; test schema dedicato |
| G23 **medio** | VERIFICATO | due copie di config con credenziali e dump in dist, chiave firma locale nella cartella progetto; .gitignore protegge Git ma non uno ZIP della cartella | `config.toml:5`, `:46`; `dist/config.toml:5`; `.gitignore:34`; `E/distribuzione.txt:3` | separare segreti/backup dalla consegna, ACL e distribuzione minima; nessun segreto riprodotto nel report |
| G24 **basso/medio** | VERIFICATO | ora movimenti formattata senza conversione esplicita al fuso locale; UTC del modello può essere mostrato come ora locale implicita | `magazzino_profili/domain/movimento.py:49`; `magazzino_profili/ui/componenti.py:445` | astimezone prima della visualizzazione e indicazione fuso; prova estate/inverno e PG timezone diverso |
| G25 **basso** | VERIFICATO | avviso password di esempio confronta stringa letta con costante intera 1234, quindi non scatta | `magazzino_profili/db/config.py:33`, `:94`, `:104` | confronto coerente e placeholder reale; prova config.example non personalizzata |
| G26 **basso/medio** | VERIFICATO | client quantità usa parseInt: `1.5` può diventare 1 anziché essere rifiutato; StrictInt server vede già 1 | `magazzino_profili/web/static/scansione.js:260`; `magazzino_profili/web/routes_barcode.py:62` | validazione stringa intero completo prima del parse; prova JS con decimali/suffissi |
| G27 **basso** | VERIFICATO | worker scadenze attivo usa int(intervallo), ferma join con timeout senza verificare alive; una eccezione ferma il resto del lotto | `magazzino_profili/services/scadenze.py:119`, `:122`, `:139`, `:157` | validare intervallo intero, isolamento errori per ID, shutdown osservabile; mock clock e DB lento |
| G28 **basso** | VERIFICATO | pallini incompleti, nome colore ignorato dal suggeritore, premoltiplicazione alpha altera RGB di un livello, doppie copie/helper | `magazzino_profili/services/colori_base.py:67`, `:73`; `E/esiti/test_registro_colori.txt:23`; `magazzino_profili/db/__init__.py:7` | mappa confermata dall'utente, test tolleranza alpha appropriata, pulizia solo dopo riferimenti |

### 8.2 Errori, sicurezza e perdita dati

**VERIFICATO:** molte catture generiche sono almeno visibili/loggate: `ui/messaggi.mostra_errore` registra dettaglio e mostra messaggio, web traduce errori DB in 503, backup continua a ripianificare (`magazzino_profili/ui/messaggi.py:54`; `magazzino_profili/web/app.py:242`; `magazzino_profili/backup/backup_db.py:205`). Non tutte le eccezioni generiche sono necessariamente sbagliate; il problema è distinguere recupero, parziale successo e stato degradato.

**VERIFICATO, punti deboli:** ODS stampa errori per riga e restituisce contatori, immagini opzionali possono fallire soltanto nel log, start DB ritorna False senza dettaglio, animazioni ignorano errori Windows con fallback, ping JS tace su rete/403, menu Excel non ha except attorno al salvataggio; login desktop non intercetta gli errori del DB (`magazzino_profili/reports/importa_ods.py:80`, `:307`; `magazzino_profili/db/server.py:63`; `magazzino_profili/ui/animazioni.py:54`; `magazzino_profili/web/static/scansione.js:42`; `magazzino_profili/ui/finestra_principale.py:743`, `:135`). Il worker attivo cattura l'eccezione dell'intero giro, quindi un ID guasto rinvia anche quelli successivi (`magazzino_profili/services/scadenze.py:114`).

**VERIFICATO:** query utente tramite ORM/parametri e LIKE escaped; non è emersa SQL injection diretta nei percorsi letti. Le f-string SQL del restore usano nomi da mapping fisso, non testo utente (`magazzino_profili/services/consultazione.py:83`; `magazzino_profili/db/migrazioni.py:50`; `magazzino_profili/reports/backup_excel.py:404`, `:428`). Questo non equivale a pentest. La normalizzazione non è whitelist universale di caratteri o lunghezze; i controlli barcode sono più stretti solo nel servizio modifica (`magazzino_profili/db/normalizzazione.py:16`; `magazzino_profili/services/pezzi.py:111`).

**VERIFICATO:** protezioni web significative: bcrypt, limite password nuove 8 caratteri/72 byte, HMAC token con scadenza e verifica utente/ruolo corrente, rate limit in memoria, limiti body dichiarato, header CSP/Permissions-Policy e no-store API; libreria scanner locale (`magazzino_profili/sicurezza/utenti.py:67`; `magazzino_profili/web/auth.py:151`; `magazzino_profili/web/sicurezza_web.py:117`, `:160`, `:180`; `magazzino_profili/web/templates/scansione.html:93`). Rate limit per processo non è protezione distribuita; il middleware si affida al Content-Length per alcune condizioni e non è stato sottoposto a fuzzing (`magazzino_profili/web/sicurezza_web.py:160`).

**VERIFICATO:** il catalogo costruisce la mappa leggendo la cartella, evitando di concatenare il codice utente a un path arbitrario; controlla firma PNG e dimensione <=20 MB, non una decodifica completa (`magazzino_profili/services/catalogo_immagini.py:72`, `:113`, `:144`). L'associazione manuale controlla soltanto estensione/esistenza prima della copia; il file system e la transazione DB non sono atomici fra loro (`magazzino_profili/services/anagrafica.py:138`, `:150`, `:153`). ZIP/XML ODS storico vengono caricati interamente senza limite dimensione o espansione; input malevolo potrebbe saturare memoria: **IPOTESI da testare con file sintetici**, non con i dati utente (`magazzino_profili/reports/importa_ods.py:115`, `:186`).

**Rischi di dati VERIFICATI nel codice:** soft delete può nascondere saldo positivo senza movimento, export storici sovrascrivono direttamente il file finale, import additivi ripetuti gonfiano quantità, backup non comprende asset/config, nessun backup specifico prima di eliminazione manuale/import/migrazione (`magazzino_profili/services/stati.py:105`, `:111`; `magazzino_profili/reports/export_csv.py:47`; `magazzino_profili/reports/export_excel.py:65`; `magazzino_profili/reports/export_csv.py:130`; `magazzino_profili/main.py:54`). La cancellazione a 48h è logica: righe/movimenti rimangono, dunque recupero potenzialmente possibile con procedura controllata; non esiste una UI di cestino/ripristino nel percorso esaminato (`magazzino_profili/tests/test_stati_scadenze.py:199`; `magazzino_profili/services/carico.py:115`).

### 8.3 Import/export e backup: cosa funziona davvero

**CSV storico — VERIFICATO nelle prove:** lettura UTF-8 con/senza BOM, separatore `;`, header obbligatori esatti “Codice profil”, “Colore”, “Lunghezza (mm)”, “Quantita”; stripping header, righe vuote ignorate, errori multipli raccolti, numeri interi ASCII positivi, profili preesistenti e transazione unica. File non UTF-8 solleva errore, non c'è fallback cp1252 o rilevamento separatore (`magazzino_profili/reports/export_csv.py:65`, `:77`, `:101`, `:143`, `:151`). Barcode importato ignorato, duplicati e reimport si sommano: non è sincronizzazione inventario e non è idempotente (`:130`; `magazzino_profili/tests/test_csv_legacy_fase10.py:92`). Export UTF-8 senza BOM, sette colonne e senza stato/vassoio/timestamp, scrittura non atomica (`:27`, `:47`). Quantità zero esportata ma rifiutata dal relativo import: round-trip storico non completo (`:105`; `magazzino_profili/services/consultazione.py:43`).

**CSV/ODS V2 — VERIFICATO:** 14 colonne, ID e campi ciclo di vita inclusi, anche eliminati; timestamp ISO 8601 UTC; CSV `;`, export senza BOM, import lettura utf-8-sig; validazione header/ordine esatti, ID/barcode duplicati, numeri e fuso delle date; ODS reale con odfpy, numeri da office:value e testi preservati. Export tramite .tmp+os.replace (`magazzino_profili/reports/formato_v2.py:34`, `:129`, `:139`, `:191`, `:215`, `:253`; `magazzino_profili/reports/ods_v2.py:33`, `:47`, `:65`). Il codice dichiara esplicitamente che restore/merge **non è implementato**: `valida_csv_v2`/`valida_ods_v2` non scrivono in DB (`magazzino_profili/reports/formato_v2.py:3`; `magazzino_profili/reports/ods_v2.py:94`). I controlli non impongono tutte le lunghezze stringa, relazione stato/timestamp o normalizzazione finale; leggere un file valido non prova che sia applicabile al DB reale (`magazzino_profili/reports/formato_v2.py:221`, `:239`).

**ODS storico — VERIFICATO:** lettura ZIP/content.xml con ElementTree, cerca intestazione “Profilo” nelle prime 10 righe, ignora Riepilogo/fogli senza header; legge Profilo/Colore/Vassoio/Dimensione_mm/Pezzi e note. Crea profili con peso segnaposto 1 kg/m e lunghezza standard 6000, da correggere; limita lunghezza a 6500; converte Vassoio in ubicazione; committa ogni riga e prosegue sugli errori (`magazzino_profili/reports/importa_ods.py:90`, `:120`, `:144`, `:191`, `:216`, `:234`, `:307`). Non è lo stesso import V2, non garantisce all-or-nothing. I conteggi di profili/colori/immagini creati vengono incrementati prima dell'esito definitivo della transazione: **IPOTESI** di contatori sovrastimati in caso di rollback; confermare forzando un vincolo sull'ultima scrittura (`:243`, `:245`). Nessun ODS reale dell'utente è presente nella cartella: file esterno predefinito non aperto (`importa_ods.py:31`).

**XLSX multi-foglio — VERIFICATO:** Metadati, Profili, Colori, Pezzi, Movimenti, Spezzoni; include anche eliminati e hex colore; intestazioni in grassetto, testo forzato come testo, timestamp UTC, limiti celle/righe Excel e scrittura atomica. Validazione FK/univocità e restore db_vuoto/merge con rollback, lock PG e sequenze (`magazzino_profili/reports/backup_excel.py:43`, `:125`, `:140`, `:150`, `:274`, `:367`, `:411`). Test retrocompatibilità colore_hex assente presente (`magazzino_profili/tests/test_backup_excel_colori.py:62`). Non include utenti, impostazioni, scansioni, PNG o config e non è diviso in fogli per colore come le tab Inventario: è organizzato per entità (`magazzino_profili/reports/backup_excel.py:6`, `:43`). Va deciso se l'utente vuole backup tecnico ripristinabile, consultazione per colore, o entrambi.

### 8.4 Mappa per rimuovere il login in sicurezza

Questa è una proposta di intervento, **nessuna rimozione eseguita**. Dipendenze **VERIFICATE**:

| Area | Cosa dipende dall'accesso | Evidenza |
|---|---|---|
| Avvio desktop | verifica utenze, DialogoAccesso, passaggio ruolo/nome, controllo update dopo accesso | `magazzino_profili/main.py:86`, `:98`, `:111`, `:116` |
| UI | DialogoAccesso; selezione schede; identità barra stato; azioni/telefono; apertura gestione colori | `magazzino_profili/ui/finestra_principale.py:63`, `:78`, `:213`, `:429`, `:507` |
| DB | tabella utenti; hash/ruoli; nessuna FK da Movimento.utente/Spezzone.utente/ScansioneTelefono.utente | `magazzino_profili/sicurezza/utenti.py:33`; `magazzino_profili/domain/movimento.py:54`; `magazzino_profili/domain/spezzone.py:27`; `magazzino_profili/domain/scansione_telefono.py:18` |
| Provisioning e CLI | primo utente in setup; crea_utente CLI | `setup_database.py:184`; `magazzino_profili/crea_utente.py:1` |
| Web | login, token HMAC, verifica utente esistente e ruolo, Depends e permessi carico/inventario; rate limit | `magazzino_profili/web/routes_barcode.py:108`; `magazzino_profili/web/auth.py:151`; `magazzino_profili/web/sicurezza_web.py:117` |
| Mobile | form utente/password, token in memoria, timeout sessione/esci, ping | `magazzino_profili/web/templates/scansione.html:47`; `magazzino_profili/web/static/scansione.js:137`, `:167` |
| Config | segrete_token e durata_token_secondi; non esiste un'opzione generale “login disabilitato” nel percorso letto | `magazzino_profili/web/app.py:104`; `config.example.toml:51` |
| Storico e backup | nomi utenti testuali da preservare; dump fisico include utenti; XLSX li esclude già | `magazzino_profili/domain/movimento.py:54`; `magazzino_profili/backup/backup_db.py:105`; `magazzino_profili/reports/backup_excel.py:7` |
| Test | web_auth/routes, sicurezza fase14, UI smoke/fase4, ciclo vita e helper setup | `magazzino_profili/tests/test_web_auth.py:1`; `magazzino_profili/tests/test_sicurezza_fase14.py:451`; `magazzino_profili/tests/test_ciclo_vita_fase12.py:185`; `magazzino_profili/tests/test_ui_smoke.py:235` |

**Sequenza consigliata:** decidere prima se togliere solo login desktop; introdurre un contesto operatore locale esplicito senza credenziali, preservare il campo storico; sostituire gli agganci di avvio e autorizzazione UI, correggendo comunque G02; mantenere inizialmente tabella utenti senza cancellarla; sostituire sul web password con pairing/token di dispositivo revocabile se richiesto; aggiornare test e documentazione; rimuovere dati/vecchi moduli solo con migrazione separata e backup verificato. Non eliminare bcrypt/auth o tabella utenti mentre API e telefono continuano a usarli. Non convertire automaticamente endpoint di movimento in accesso anonimo.

### 8.5 Test esistenti e risultati effettivi

**VERIFICATO:** raccolti **654 casi** della suite canonica; esecuzione per modulo con limite 35 s, log verbose/XML, senza modificare i test. Una prima esecuzione complessiva non terminata è stata interrotta e **non entra nei conteggi**. I moduli rimasti in timeout sono stati classificati bloccati, non falliti. Dopo il timeout sicurezza sono stati recuperati separatamente 25 casi indipendenti da TestClient: 24 passati e 1 skip. Registro: `E/raccolta_test.txt:656`, `E/esegui_isolato.py:1`, `E/esiti_riepilogo.json:1`, `E/recupera_test.py:1`, `E/riassumi_test.py:1`.

| Categoria | Numero | Interpretazione |
|---|---:|---|
| Superati | **528** | SQLite, logica pura, UI offscreen, import/export sintetici, JS e verifiche locali; non convalida dispositivi/PG reali |
| Falliti | **6** | dettagli sotto, separati fra difetti test e ambiente |
| Saltati / non eseguiti per requisito ambiente | **49** | 48 PG/semantica specifica PG e 1 backup reale PG con tool/URL dedicato assenti |
| Bloccati | **69** | timeout dei percorsi TestClient: routes_update 8, sicurezza 8, web_auth 6, web_routes_barcode 23, web_telefono 24 |
| Errore di setup | **1** | test HTTPS reale: uvicorn non raggiunge server.started entro ~10 s; causa non determinata |
| Escluso dall'esecuzione controllata | **1** | test_avanzamento_barra del popup: downloader simulato, ma esegui non iniettato, può tentare lancio del falso exe |
| Totale | **654** | `E/riepilogo_test.json:2` |

I 69 bloccati non provano un guasto del server applicativo: i test si fermano al primo percorso TestClient e non producono diagnosi sufficiente. **IPOTESI:** incompatibilità del runtime asincrono o limiti del sandbox; conferma con app FastAPI minima nello stesso ambiente e poi su Windows normale, versioni fissate. Non sono state installate versioni alternative per far apparire verde la suite (`E/esiti/test_routes_update.txt:9`; `E/esiti/test_sicurezza_fase14.txt:24`). Il test HTTPS ha prodotto un errore di setup, non una risposta API errata (`E/esiti/test_web_https_reale.txt:14`).

| Test fallito | Risultato e giudizio | Evidenza |
|---|---|---|
| test_backup_excel_colori::test_valore_non_valido_blocca_il_ripristino | validazione dell'hex sembra raggiungere l'eccezione prevista; controllo finale usa ScalarResult.count inesistente. Difetto certo del test, non prova di restore corrotto | `magazzino_profili/tests/test_backup_excel_colori.py:96`; `E/esiti/test_backup_excel_colori.txt:18` |
| test_ciclo_vita_fase12::test_web_main_avvia_e_ferma_il_worker | attende 0 ma ottiene 1 per config DB assente nella copia; mock non isola tutte le dipendenze | `magazzino_profili/tests/test_ciclo_vita_fase12.py:141`, `:159`; `E/esiti/test_ciclo_vita_fase12.txt:27` |
| test_ciclo_vita_fase12::test_main_non_usa_account_predefinito_when_utenze_esse | QApplication già esistente, ramo errore config ne crea una seconda | `magazzino_profili/tests/test_ciclo_vita_fase12.py:185`; `magazzino_profili/main.py:40`; `E/esiti/test_ciclo_vita_fase12.txt:45` |
| test_ciclo_vita_fase12::test_main_solleva_errore_leggibile_when_nessuna_utente | attende messaggio utenti ma fallisce prima per stesso singleton Qt/config; non dimostra il ramo utenti | `magazzino_profili/tests/test_ciclo_vita_fase12.py:207`; `E/esiti/test_ciclo_vita_fase12.txt:49` |
| test_inventario_colori::test_chip_cambia_dopo_imposta_e_aggiorna | il test apre una transazione con SELECT e chiama servizio che ne apre un'altra; InvalidRequestError | `magazzino_profili/tests/test_inventario_colori.py:85`; `magazzino_profili/services/colori.py:29`; `E/esiti/test_inventario_colori.txt:23` |
| test_registro_colori::test_pixmap_sbiadito_cambia_solo_alfa | RGB effettivo (182,58,49), atteso (182,58,50): arrotondamento alpha, differenza minima ma test fallisce realmente | `magazzino_profili/tests/test_registro_colori.py:119`; `magazzino_profili/ui/registro_colori.py:101`; `E/esiti/test_registro_colori.txt:23` |

**VERIFICATO:** wrapper JS superato; esegue `node --test` sul client e non usa una fotocamera (`magazzino_profili/tests/test_web_client_javascript.py:14`; `E/esiti/test_web_client_javascript.xml:1`). I test duplicati nello snapshot `fase6-file-modificati/` non sono stati rieseguiti: il file test_animazioni è identico alla suite canonica (`E/rilievi_statici.txt:281`).

Le prove aggiuntive dell'audit non aumentano i 654 casi della suite: riproducono stato/ricarico/48h, modifica dal ruolo Sola lettura, formula nell'export storico, prestazioni e doppio setup con eseguibili PostgreSQL completamente simulati. Quest'ultima conferma la rigenerazione incoerente delle credenziali, ma non tenta autenticazione su un server reale (`E/misure.py:39`; `E/prove_aggiuntive.py:18`; `E/prova_setup.py:1`).

**Coperture mancanti o insufficienti, VERIFICATE confrontando test e flussi:** i test di ruolo controllano le schede ma non tutte le mutazioni nell'Inventario; i test ciclo vita hanno mock/testi che non dimostrano la gara descritta; manca una prova completa scarico→ricarico→48h che avrebbe trovato G01; nessuna copertura reale telefono/firewall/camera/tray/autostart/installazione update; nessun test eseguito di restore dei dump originali, fedeltà catalogo/indice o benchmark PG reale (`magazzino_profili/tests/test_sicurezza_fase14.py:460`; `magazzino_profili/tests/test_ciclo_vita_fase12.py:22`; `magazzino_profili/tests/test_stati_scadenze.py:164`; `E/riepilogo_test.json:1`).

## 9. Piano di intervento proposto, ordinato per priorità

Ogni fase è una **proposta**, da realizzare su copie e con regressioni mirate. Non si propone una riscrittura totale: servizi, ORM, FastAPI e componenti Qt possono essere conservati. Le motivazioni sono i riscontri Gxx della sezione 8.

| Priorità | Obiettivo concreto | File coinvolti / evidenza del punto d'intervento | Rischio | Come verificare il successo |
|---|---|---|---|---|
| **1. Protezione dati e backup** | config unica; backup pre-migrazione; dump atomici con nomi unici e lock; stato backup visibile; includere asset/config nel piano di ripristino | `magazzino_profili/backup/backup_db.py:74`; `magazzino_profili/main.py:49`; `magazzino_profili/db/config.py:59`; `MagazzinoProfili.spec:4` | medio: cambia ciclo di vita, non quantità | ripristino completo in DB usa e getta, confronto conteggi/FK/hash PNG; simulare timeout/disco pieno/due istanze, preservando copie buone |
| **2. Bug critici** | bloccare perdita di visibilità G01, autorizzazioni G02 e avvio instabile; correggere collegamento PDF | `magazzino_profili/services/carico.py:108`; `magazzino_profili/services/stati.py:95`; `magazzino_profili/ui/tabella_pezzi.py:765`; `magazzino_profili/ui/finestra_principale.py:698` | medio/alto per regole dati | prova ricarico prima scadenza, quantità positiva mai nascosta indebitamente; Sola lettura non può alterare nessuna riga; menu PDF produce file valido |
| **3. Database** | stabilire schema atteso e versione minima; migrazioni con preflight/checksum; vincoli selettivi; test PG corretti; snapshot export coerente | `magazzino_profili/db/migrazioni.py:19`; `migrations/001_scorta_minima.sql:3`; `magazzino_profili/domain/pezzo.py:45`; `magazzino_profili/tests/test_migrazioni_postgres.py:24` | alto se dati legacy incoerenti | database dedicato: schema da zero e upgrade da snapshot precedente, confronto schema completo, doppio avvio, rollback su errore; mai normalizzare dati reali senza anteprima |
| **4. Barcode e vassoio** | chiarire identità aggregata/barra/vassoio; conservare ID in modifica; rendere vassoio coerente in UI, ODS e API | `magazzino_profili/domain/pezzo.py:46`; `magazzino_profili/services/pezzi.py:103`; `magazzino_profili/ui/scheda_carico.py:314`; `magazzino_profili/reports/importa_ods.py:283` | medio; alto se si decide più vassoi per stessa combinazione | modifica mantiene ID/storico, niente duplicati barcode; casi due vassoi gestiti secondo decisione esplicita; import non confonde ubicazione e numero |
| **5. Stati e 48 ore** | unificare transizioni carico/scarico/manuali; UTC e visualizzazione locale; clock condiviso; worker indipendente e osservabile | `magazzino_profili/services/stati.py:36`; `magazzino_profili/services/scadenze.py:114`; `magazzino_profili/services/scarico.py:48`; `magazzino_profili/ui/componenti.py:445` | alto: policy di cancellazione | test 47:59:59.999999/48:00:00, passaggio ora legale, clock non UTC, riavvio e ricarico; nessun Caricato eliminato, storico preservato e UI aggiornata |
| **6. Telefono** | URL/TLS raggiungibili, avvio supervisionato, diagnostica a livelli, pairing destinatario, claim/ACK e idempotenza | `magazzino_profili/web/app.py:290`; `magazzino_profili/ui/collega_telefono.py:172`; `magazzino_profili/services/telefono.py:78`; `magazzino_profili/web/routes_barcode.py:248`; `magazzino_profili/web/static/scansione.js:70` | medio/alto per rete e duplicati | prove Android/iOS in LAN e, se richiesto, rete mobile; disconnessione prima/dopo commit; due desktop; scansione su scheda errata recuperabile senza doppio scarico |
| **7. CSV e ODS** | unificare contratti e anteprima; scelta additivo/snapshot; import V2 effettivo; ODS atomico con errori completi; BOM compatibile dove deciso | `magazzino_profili/reports/export_csv.py:120`; `magazzino_profili/reports/importa_ods.py:165`; `magazzino_profili/reports/formato_v2.py:185`; `magazzino_profili/reports/ods_v2.py:94` | alto per quantità/import | file sintetici con accenti, ;, newline, BOM, cp1252 esplicito, zero/duplicati/barcode modificati/stati; rollback totale su errore e replay senza sorprese |
| **8. Backup Excel multi-foglio** | collegare backup/restore al menu con nomi distinti da report; decidere fogli per entità e/o vista colore; proteggere formule e asset | `magazzino_profili/reports/backup_excel.py:150`, `:411`; `magazzino_profili/ui/finestra_principale.py:357`, `:717` | medio/alto sul restore | round-trip completo in DB isolato, incluse righe eliminate, hex e sequenze; prova dati formula e immagini ricollocabili; file vecchi gestiti esplicitamente |
| **9. Interfaccia, contrasti e animazioni** | recuperare HTML originale; dimensioni grandi ma adattive, placeholder leggibili, azioni visibili; viewer PNG; cambio tema senza perdita form | `magazzino_profili/ui/tema.py:33`; `magazzino_profili/ui/scheda_profilo.py:276`; `magazzino_profili/ui/finestra_principale.py:603` | basso/medio | confronto screenshot con originale a risoluzioni/DPI concordati; test tastiera/focus/tema e form non salvato; immagine apribile e zoomabile |
| **10. Prestazioni e paginazione** | pagine reali e delegate, query su worker, debounce, batch export/import, indici da EXPLAIN | `magazzino_profili/services/consultazione.py:89`; `magazzino_profili/ui/tabella_pezzi.py:911`; `magazzino_profili/reports/formato_v2.py:129` | medio | 12k/100k dati sintetici, righe residenti limitate, UI reattiva; confronto tempi/query/memoria e risultati equivalenti |
| **11. Background** | decidere cosa resta attivo; tray se richiesta; server/worker/backup supervisionati e autostart esplicito | `magazzino_profili/ui/finestra_principale.py:535`; `magazzino_profili/web/app.py:346`; `magazzino_profili/backup/backup_db.py:226` | medio | chiusura finestra, logout Windows, riavvio PC, crash web: stato servizi visibile e recupero senza doppie istanze |
| **12. Aggiornamenti** | endpoint reale, catena firma/TLS, installazione stabile con rollback, gestione chiusura popup e vecchia versione | `magazzino_profili/services/aggiornamenti.py:119`, `:316`; `magazzino_profili/ui/dialogo_aggiornamento.py:158`; `firme/README.md:7` | alto se cambia distribuzione | pacchetto test separato, manifest alterato rifiutato, download interrotto, installazione e secondo avvio aprono nuova versione; recupero vecchia versione e config |
| **13. Sicurezza e test** | completare hardening/CI, pin versioni, correggere test difettosi e sbloccare TestClient/HTTPS; decisione login; controlli input/path | `requirements.txt:1`; `magazzino_profili/tests/test_sicurezza_fase14.py:451`; `magazzino_profili/tests/test_migrazioni_postgres.py:24`; `magazzino_profili/web/sicurezza_web.py:152` | medio | suite verde su runtime fissato con PG dedicato, nessun test su DB reale, prove permessi per azione, segreti esclusi dai pacchetti e test retry/idempotenza |

La collocazione della sicurezza/test come fase 13 segue l'ordine richiesto: **non rinvia** l'autorizzazione G02 o i test di regressione indispensabili alle fasi precedenti. Ogni fase deve essere verificata prima di passare a dati reali.

## 10. Domande aperte e cose non verificabili

### Decisioni necessarie

1. **Identità del barcode:** rappresenta barra singola, lotto aggregato o combinazione profilo/colore/lunghezza? Sono ammessi più vassoi per la stessa combinazione? Oggi lo schema li unifica (`magazzino_profili/domain/pezzo.py:46`, `:71`).
2. **Regola Scaricato:** deve significare quantità zero o comando indipendente? Uno scarico parziale cambia stato? Una ricarica deve sempre tornare Caricato? È accettabile eliminazione logica con quantità >0? Oggi le regole sono indipendenti e producono G01 (`magazzino_profili/services/scarico.py:48`; `magazzino_profili/services/stati.py:99`).
3. **48 ore:** intervallo trascorso esatto o due giorni di calendario? Il codice implementa 48 ore trascorse UTC e controllo periodico, non esecuzione puntuale al secondo né due mezzanotti (`magazzino_profili/services/stati.py:22`; `magazzino_profili/services/scadenze.py:60`).
4. **Maiuscolo:** solo codice o anche descrizione/nome? La descrizione oggi resta libera e il codice non è modificabile dal servizio aggiorna_profilo (`magazzino_profili/services/anagrafica.py:101`, `:114`).
5. **Telefono:** uso solo stesso Wi-Fi o anche rete dati? Quanti telefoni e PC contemporanei? È disponibile un hostname/dominio o una rete privata gestita? L'architettura corrente presume raggiungibilità remota ma non la realizza (`magazzino_profili/web/app.py:20`; `magazzino_profili/services/telefono.py:87`).
6. **Login:** rimuovere solo desktop o anche password sul telefono? Quale identità operatore deve restare nello storico e quale pairing sostituisce il login web? Dipendenze in 8.4 (`magazzino_profili/domain/movimento.py:54`; `magazzino_profili/web/routes_barcode.py:108`).
7. **Import:** le righe sono carichi aggiuntivi o fotografia da riconciliare? Come trattare duplicati/reimport e profili con peso ignoto? Oggi sommano e ODS usa 1 kg/m segnaposto (`magazzino_profili/reports/export_csv.py:130`; `magazzino_profili/reports/importa_ods.py:91`).
8. **Backup:** richiesto ripristino tecnico completo con asset/segreti protetti, oppure documento Excel diviso per colori, o entrambi? Quanti giorni conservare e su quale destinazione separata? Oggi sette copie ogni sei ore non sono sette giorni garantiti (`config.toml:17`; `magazzino_profili/reports/backup_excel.py:43`).
9. **UI grande:** risoluzione minima, scala Windows, dimensione caratteri desiderata e uso touch? Oggi min 1280×760, base 20 px, colonne fisse e scroll (`magazzino_profili/ui/finestra_principale.py:232`; `magazzino_profili/ui/tema.py:36`).
10. **Background/update:** tray deve chiudere soltanto la finestra o tutto? Chi gestisce servizio web/backup? L'aggiornamento deve sostituire stabilmente l'exe o essere portabile con scelta manuale? Oggi chiudere desktop ferma polling, update lancia dalla cache (`magazzino_profili/ui/finestra_principale.py:535`; `magazzino_profili/services/aggiornamenti.py:292`).

### Materiale e ambiente mancanti

**Ulteriore incongruenza del materiale disponibile — VERIFICATO:** `Profili_cataloghi/Riepilogo.csv` contiene 225 codici unici, senza duplicati testuali; 196 sono indicati come non estratti con sicurezza e 29 come immagini disponibili. Nessuno dei 29 PNG con quei codici è presente nella cartella, che contiene solo `_atl150_p21_source.png`; esempi AZ2035, AZ4517, AZ4546 risultano dichiarati disponibili nel CSV (`Profili_cataloghi/Riepilogo.csv:15`, `:73`, `:82`; `E/catalogo_rilievo.json:2`; `E/rilievi_statici.txt:273`). AZ46431 compare alla riga 100 di questo riepilogo, mentre TO3108 non compare: ciò **non prova** l'anomalia dell'indice aggiornato assente e non autorizza a correggere il codice per somiglianza (`Profili_cataloghi/Riepilogo.csv:100`; `E/catalogo_rilievo.json:9`). Inoltre il default applicativo è `catalogo_immagini`, non `Profili_ritagliati`: anche fornendo i PNG nella seconda cartella occorre configurare `[immagini] catalogo` coerentemente (`magazzino_profili/services/catalogo_immagini.py:20`, `:57`).


- **Catalogo completo NON VERIFICABILE:** `Profili_ritagliati/`, i 211 PNG e `Indice_profili_aggiornato.csv` non sono presenti nel censimento. Non posso confermare TO3108 fuori indice, correggere AZ46431 o dichiarare altre differenze su file non disponibili. Esiste invece `Profili_cataloghi/Riepilogo.csv` con esiti di estrazione, che non è l'indice richiesto (`E/rilievi_statici.txt:267`; `Profili_cataloghi/Riepilogo.csv:1`).
- **Procedura proposta per quel controllo:** su copia degli originali, confrontare insiemi di codici normalizzati CSV↔stem PNG; contare file e codici unici, duplicati normalizzati/case, PNG mancanti/extra, header/encoding, file corrotti e hash duplicati; verificare TO3108 e confrontare AZ46431 con catalogo tecnico/ODS senza rinominare per sola somiglianza. Il catalogo applicativo oggi indicizza i file, non l'indice CSV: anche un PNG fuori indice può essere proposto (`magazzino_profili/services/catalogo_immagini.py:113`, `:126`).
- **Mockup HTML NON VERIFICABILE:** manca l'originale e non è stata usata documentazione storica come prova di equivalenza esatta (`E/rilievi_statici.txt:271`; `_prompt_fase5.md:3`).
- **PostgreSQL reale NON VERIFICATO:** schema installato, versione, timezone server, dimensioni, indici effettivi, piano query, concorrenza, integrità dati e restore dei dump richiedono ambiente dedicato; non sono stati letti i dati reali. Test PG disattivati deliberatamente (`E/riepilogo_test.json:2`; `magazzino_profili/tests/test_integrazione_postgres.py:1`).
- **Telefono/hardware NON VERIFICABILI:** Android/iOS/browser, camera, permessi, messa a fuoco, stampa e scanner fisico, Wi-Fi, NAT, firewall, DNS e fiducia certificato; test suggeriti in 5.2 (`magazzino_profili/tests/test_web_https_reale.py:1`).
- **Eseguibile/installazione NON VERIFICATI:** uguaglianza hash release/dist accertata, contenuto runtime e corrispondenza ai sorgenti locali no; nessun programma installato avviato (`E/distribuzione.txt:1`). Non si può attribuire all'exe un miglioramento presente solo nei file non committati.
- **Sicurezza completa NON VERIFICATA:** nessun pentest, fuzzing, audit ACL, revoca/distribuzione reale chiavi o nuova scansione vulnerabilità. La presenza di hardening e dei commenti in requirements non è certificazione (`requirements.txt:5`; `magazzino_profili/web/sicurezza_web.py:152`).

Le appendici automatiche seguenti rendono consultabili moduli/import e risultati per file senza dover interpretare i soli riassunti; nessuna di esse sostituisce le limitazioni dichiarate.

### Appendice A — Moduli e import interni, censimento statico

**VERIFICATO:** tabella generata dall’AST di tutti i moduli Python applicativi; esclusi i test e lo snapshot di consegna. `M` = import a livello modulo, `R` = import ritardato in funzione, `T` = solo TYPE_CHECKING. Un re-export di pacchetto può rendere il grafo più connesso degli usi effettivi. Evidenza di generazione: `E/rilievo.py:1`, dettaglio `E/rilievi_statici.txt:283`.

| Modulo / funzione dichiarata | Import interni diretti (destinazione, riga sorgente, tipo) |
|---|---|
| `magazzino_profili/__init__.py:1` — Pacchetto del progetto "Magazzino Profili". | nessun import interno esplicito |
| `magazzino_profili/backup/__init__.py:1` — Pacchetto backup: copia automatica del database PostgreSQL. | `magazzino_profili.backup.backup_db` (3, M) |
| `magazzino_profili/backup/backup_db.py:1` — Backup automatico del database PostgreSQL tramite ``pg_dump``. | nessun import interno esplicito |
| `magazzino_profili/barcode/__init__.py:1` — Pacchetto barcode: generazione Code 128, etichette PDF e scanner. | `magazzino_profili.barcode.etichette` (14, M); `magazzino_profili.barcode.generazione` (19, M); `magazzino_profili.barcode.scanner` (20, M) |
| `magazzino_profili/barcode/etichette.py:1` — Etichette PDF per i pezzi, generate con reportlab. | `magazzino_profili.domain` (23, M); `magazzino_profili.barcode.generazione` (24, M) |
| `magazzino_profili/barcode/generazione.py:1` — Generazione dell'immagine barcode Code 128 da un valore. | nessun import interno esplicito |
| `magazzino_profili/barcode/scanner.py:1` — Widget Qt per la lettura di barcode da scanner USB. | nessun import interno esplicito |
| `magazzino_profili/crea_utente.py:1` — Crea un utente del Magazzino Profili (con ruolo). | `magazzino_profili.db` (19, M); `magazzino_profili.sicurezza` (25, M) |
| `magazzino_profili/db/__init__.py:1` — Pacchetto di accesso al database: configurazione, engine, utilità. | `magazzino_profili.db.config` (3, M); `magazzino_profili.db.engine` (4, M); `magazzino_profili.db.normalizzazione` (5, M); `magazzino_profili.db.server` (6, M); `magazzino_profili.db.server` (7, M) |
| `magazzino_profili/db/config.py:1` — Lettura della configurazione del database da ``config.toml``. | nessun import interno esplicito |
| `magazzino_profili/db/engine.py:1` — Creazione dell'engine SQLAlchemy e del factory di sessioni. | `magazzino_profili.domain` (9, M); `magazzino_profili.db.config` (10, M) |
| `magazzino_profili/db/migrazioni.py:1` — Applicazione delle migrazioni SQL. | nessun import interno esplicito |
| `magazzino_profili/db/normalizzazione.py:1` — Funzioni pure di normalizzazione di codici e colori, e generazione | nessun import interno esplicito |
| `magazzino_profili/db/server.py:1` — Gestione del server PostgreSQL locale usato dall’applicazione. | nessun import interno esplicito |
| `magazzino_profili/domain/__init__.py:1` — Pacchetto del dominio: entità SQLAlchemy del gestionale. | `magazzino_profili.domain.base` (3, M); `magazzino_profili.domain.colore` (4, M); `magazzino_profili.domain.impostazione` (5, M); `magazzino_profili.domain.movimento` (6, M); `magazzino_profili.domain.pezzo` (7, M); `magazzino_profili.domain.profilo` (8, M); `magazzino_profili.domain.scansione_telefono` (9, M); `magazzino_profili.domain.spezzone` (10, M) |
| `magazzino_profili/domain/base.py:1` — Base dichiarativa condivisa da tutti i modelli del dominio. | nessun import interno esplicito |
| `magazzino_profili/domain/colore.py:1` — Anagrafica dei colori (finiture) dei profili. | `magazzino_profili.domain.base` (8, M); `magazzino_profili.domain.pezzo` (11, T) |
| `magazzino_profili/domain/impostazione.py:1` — Impostazioni globali dell'applicazione (coppie chiave/valore). | `magazzino_profili.domain.base` (6, M) |
| `magazzino_profili/domain/movimento.py:1` — Movimenti di magazzino (carichi, scarichi, rettifiche) e servizio | `magazzino_profili.domain.base` (14, M); `magazzino_profili.domain.pezzo` (15, M); `magazzino_profili.domain.pezzo` (18, T) |
| `magazzino_profili/domain/pezzo.py:1` — Giacenza: un pezzo è la combinazione profilo + colore + lunghezza. | `magazzino_profili.db.normalizzazione` (9, M); `magazzino_profili.domain.base` (10, M); `magazzino_profili.domain.colore` (13, T); `magazzino_profili.domain.movimento` (14, T); `magazzino_profili.domain.profilo` (15, T); `magazzino_profili.domain.spezzone` (16, T) |
| `magazzino_profili/domain/profilo.py:1` — Anagrafica dei profili in alluminio/PVC. | `magazzino_profili.domain.base` (9, M); `magazzino_profili.domain.pezzo` (12, T) |
| `magazzino_profili/domain/scansione_telefono.py:1` — Barcode letti dal telefono e in attesa di essere consegnati al programma desktop. | `magazzino_profili.domain.base` (8, M) |
| `magazzino_profili/domain/spezzone.py:1` — Scarti derivati da un taglio: i pezzi residui di una lavorazione. | `magazzino_profili.domain.base` (9, M); `magazzino_profili.domain.pezzo` (12, T) |
| `magazzino_profili/launch_app.py:1` — Launcher alternativo per avviare il programma ed essere usato dal confezionamento. | `magazzino_profili.main` (10, M) |
| `magazzino_profili/main.py:1` — Punto di avvio dell'applicazione "Magazzino Profili". | `magazzino_profili.backup` (24, M); `magazzino_profili.db` (25, M); `magazzino_profili.db.server` (26, M); `magazzino_profili.db.migrazioni` (27, M); `magazzino_profili.ui` (28, M); `magazzino_profili.ui.finestra_principale` (98, R); `magazzino_profili` (137, R); `magazzino_profili.services` (138, R); `magazzino_profili.services.aggiornamenti` (138, R); `magazzino_profili.ui.dialogo_aggiornamento` (151, R); `magazzino_profili.sicurezza` (166, R); `magazzino_profili.backup` (176, R) |
| `magazzino_profili/reports/__init__.py:1` — Pacchetto report: esportazioni del inventario (Excel, PDF, CSV) e backup. | `magazzino_profili.reports.export_excel` (3, M); `magazzino_profili.reports.export_pdf` (4, M); `magazzino_profili.reports.export_csv` (5, M); `magazzino_profili.reports.importa_ods` (6, M); `magazzino_profili.reports.formato_v2` (7, M); `magazzino_profili.reports.ods_v2` (14, M); `magazzino_profili.reports.backup_excel` (15, M) |
| `magazzino_profili/reports/backup_excel.py:1` — Backup logico completo in XLSX (multi-foglio) e ripristino. | `magazzino_profili.domain` (33, M); `magazzino_profili.services.stati` (34, M); `magazzino_profili.reports.export_excel` (35, M) |
| `magazzino_profili/reports/export_csv.py:1` — Esportazione e importazione dell'inventario in CSV. | `magazzino_profili.db.normalizzazione` (21, M); `magazzino_profili.domain` (22, M); `magazzino_profili.services.carico` (23, M); `magazzino_profili.services.consultazione` (24, M); `magazzino_profili.services.eccezioni` (25, M) |
| `magazzino_profili/reports/export_excel.py:1` — Esportazione dell'inventario completo in Excel (openpyxl). | `magazzino_profili.services.consultazione` (12, M) |
| `magazzino_profili/reports/export_pdf.py:1` — Esportazione dell'inventario in PDF (reportlab), for printing. | `magazzino_profili.services.consultazione` (15, M) |
| `magazzino_profili/reports/formato_v2.py:1` — Formato V2 dell'inventario: esportazione CSV e validazione (solo lettura). | `magazzino_profili.db.normalizzazione` (29, M); `magazzino_profili.domain` (30, M) |
| `magazzino_profili/reports/importa_ods.py:1` — Importazione dell'inventario da un file ODS (LibreOffice Calc). | `magazzino_profili.db.normalizzazione` (34, M); `magazzino_profili.domain` (39, M); `magazzino_profili.services.anagrafica` (46, M); `magazzino_profili.services.catalogo_immagini` (47, M) |
| `magazzino_profili/reports/ods_v2.py:1` — Esportazione e validazione ODS del formato V2 (libreria: odfpy). | `magazzino_profili.reports.formato_v2` (20, M) |
| `magazzino_profili/services/__init__.py:1` — Pacchetto dei servizi di magazzino: carico, scarico, spezzoni e giacenza. | `magazzino_profili.domain` (3, M); `magazzino_profili.services.carico` (4, M); `magazzino_profili.services.eccezioni` (5, M); `magazzino_profili.services.pezzi` (12, M); `magazzino_profili.services.scarico` (13, M); `magazzino_profili.services.scadenze` (14, M); `magazzino_profili.services.stati` (19, M); `magazzino_profili.services.spezzoni` (27, M) |
| `magazzino_profili/services/aggiornamenti.py:1` — Sistema di aggiornamento (Fase 13 completa). | `magazzino_profili.db.config` (189, R) |
| `magazzino_profili/services/anagrafica.py:1` — Anagrafica profili: creazione, aggiornamento e immagine sezione. | `magazzino_profili.db.normalizzazione` (15, M); `magazzino_profili.domain` (16, M) |
| `magazzino_profili/services/carico.py:1` — Servizio di carico: inserimento facilitato della giacenza. | `magazzino_profili.db.normalizzazione` (19, M); `magazzino_profili.domain` (20, M); `magazzino_profili.services.eccezioni` (21, M); `magazzino_profili.services.stati` (22, M) |
| `magazzino_profili/services/catalogo_immagini.py:1` — Catalogo delle immagini di sezione: ricerca per codice profilo normalizzato. | `magazzino_profili.db.normalizzazione` (16, M) |
| `magazzino_profili/services/colori.py:1` — Anagrafica colori: lettura e impostazione del colore mostrato (``colore_hex``). | `magazzino_profili.domain` (8, M); `magazzino_profili.services.colori_base` (9, M) |
| `magazzino_profili/services/colori_base.py:1` — Colori di partenza (approssimati) dedotti dal codice colore: solo suggerimenti. | nessun import interno esplicito |
| `magazzino_profili/services/consultazione.py:1` — Consultazioni di sola lettura per la UI: inventario e avvisi. | `magazzino_profili.domain` (11, M); `magazzino_profili.db.normalizzazione` (12, M); `magazzino_profili.services.impostazioni` (14, M) |
| `magazzino_profili/services/controllo_scadenze.py:1` — Controllo periodico delle scadenze (barcode «Scaricato» da almeno 48 ore). | `magazzino_profili.services.stati` (14, M) |
| `magazzino_profili/services/eccezioni.py:1` — Eccezioni dedicate dei servizi di magazzino. | nessun import interno esplicito |
| `magazzino_profili/services/impostazioni.py:1` — Impostazioni globali: soglia di sotto scorta. | `magazzino_profili.domain` (7, M) |
| `magazzino_profili/services/pezzi.py:1` — Servizi di rettifica diretta dei pezzi (scorta minima, barcode, vassoio). | `magazzino_profili.barcode.generazione` (22, M); `magazzino_profili.domain` (23, M); `magazzino_profili.services.eccezioni` (24, M) |
| `magazzino_profili/services/proposta_immagine.py:1` — Stato dell'immagine di un NUOVO profilo (logica pura, testabile senza Qt). | `magazzino_profili.db.normalizzazione` (8, M); `magazzino_profili.services.catalogo_immagini` (9, M) |
| `magazzino_profili/services/scadenze.py:1` — Controllo delle scadenze barcode (48 ore in stato «Scaricato») — Fase 12. | `magazzino_profili.services.stati` (27, M); `magazzino_profili.services.stati` (28, M); `magazzino_profili.services.stati` (29, M) |
| `magazzino_profili/services/scarico.py:1` — Servizio di scarico: uscita di merce da un pezzo esistente. | `magazzino_profili.domain` (10, M); `magazzino_profili.services.eccezioni` (11, M) |
| `magazzino_profili/services/spezzoni.py:1` — Servizio spezzoni: registrazione degli scarti di taglio e loro | `magazzino_profili.domain` (6, M); `magazzino_profili.services.eccezioni` (7, M) |
| `magazzino_profili/services/stati.py:1` — Stati del barcode (Caricato / Scaricato) e cancellazione logica. | `magazzino_profili.domain` (16, M); `magazzino_profili.services.pezzi` (17, M) |
| `magazzino_profili/services/telefono.py:1` — Telefono come lettore barcode: coda delle scansioni e stato del collegamento. | `magazzino_profili.db` (12, M); `magazzino_profili.db.config` (12, M); `magazzino_profili.domain` (13, M) |
| `magazzino_profili/sicurezza/__init__.py:1` — Pacchetto sicurezza: utenti e permessi (ruoli). | `magazzino_profili.sicurezza.utenti` (3, M) |
| `magazzino_profili/sicurezza/utenti.py:1` — Utenti e permessi del magazzino (ruoli). | `magazzino_profili.domain.base` (22, M) |
| `magazzino_profili/ui/__init__.py:1` — Pacchetto interfaccia utente (PySide6). | `magazzino_profili.ui.finestra_principale` (7, M) |
| `magazzino_profili/ui/animazioni.py:1` — Animazioni di transizione: brevi, sobrie, spegnibili. | nessun import interno esplicito |
| `magazzino_profili/ui/avvisi.py:1` — Scheda Avvisi: pezzi esauriti o sotto scorta minima. | `magazzino_profili.services` (24, M); `magazzino_profili.services.consultazione` (24, M); `magazzino_profili.services.impostazioni` (24, M); `magazzino_profili.ui.componenti` (25, M); `magazzino_profili.ui` (26, M); `magazzino_profili.ui.animazioni` (26, M); `magazzino_profili.ui.icone` (27, M); `magazzino_profili.ui.tema` (28, M) |
| `magazzino_profili/ui/collega_telefono.py:1` — Collegamento del telefono come lettore barcode: controllo, dialogo e pulsante. | `magazzino_profili.services` (18, M); `magazzino_profili.services.telefono` (18, M); `magazzino_profili.ui.componenti` (19, M); `magazzino_profili.ui.icone` (20, M); `magazzino_profili.ui.tema` (21, M) |
| `magazzino_profili/ui/componenti.py:1` — Componenti riutilizzabili dell'interfaccia (stile del mockup). | `magazzino_profili.ui` (39, M); `magazzino_profili.ui.animazioni` (39, M); `magazzino_profili.ui.registro_colori` (39, M); `magazzino_profili.ui.icone` (40, M); `magazzino_profili.ui.tema` (41, M) |
| `magazzino_profili/ui/dialogo_aggiornamento.py:1` — Popup "Aggiornamento disponibile" (Fase 13 completa). | `magazzino_profili` (30, M); `magazzino_profili.services` (31, M); `magazzino_profili.services.aggiornamenti` (31, M) |
| `magazzino_profili/ui/finestra_principale.py:1` — Finestra principale: barra del titolo, schede e barra di stato. | `magazzino_profili.sicurezza` (41, M); `magazzino_profili.ui` (42, M); `magazzino_profili.ui.animazioni` (42, M); `magazzino_profili.ui.tema` (42, M); `magazzino_profili.ui.tema` (43, M); `magazzino_profili.ui.icone` (44, M); `magazzino_profili.services` (45, M); `magazzino_profili.services.telefono` (45, M); `magazzino_profili.ui.avvisi` (46, M); `magazzino_profili.ui.collega_telefono` (47, M); `magazzino_profili.ui.componenti` (48, M); `magazzino_profili.ui.scheda_carico` (49, M); `magazzino_profili.ui.scheda_profilo` (50, M); `magazzino_profili.ui.scheda_scarico` (51, M); `magazzino_profili.ui.tabella_pezzi` (52, M); `magazzino_profili.ui.gestione_colori` (283, R); `magazzino_profili.ui` (309, R); `magazzino_profili.ui.registro_colori` (309, R); `magazzino_profili.services` (627, R); `magazzino_profili.services.consultazione` (627, R); `magazzino_profili.services.impostazioni` (627, R); `magazzino_profili.services` (648, R); `magazzino_profili.services.consultazione` (648, R); `magazzino_profili.services.impostazioni` (648, R); `magazzino_profili.reports` (698, R); `magazzino_profili.services` (724, R); `magazzino_profili.services.consultazione` (724, R) |
| `magazzino_profili/ui/gestione_colori.py:1` — Fase 8: dialogo «Gestione colori» e azioni del menu contestuale dei chip colore. | `magazzino_profili.services` (34, M); `magazzino_profili.services.colori` (34, M); `magazzino_profili.ui` (35, M); `magazzino_profili.ui.registro_colori` (35, M); `magazzino_profili.ui.componenti` (36, M); `magazzino_profili.ui.messaggi` (37, M); `magazzino_profili.ui.tema` (38, M) |
| `magazzino_profili/ui/icone.py:1` — Icone a tratto: gli STESSI SVG del mockup (viewBox 24x24, tratto 2, estremi arrotondati). | nessun import interno esplicito |
| `magazzino_profili/ui/messaggi.py:1` — Messaggi per l'utente: errori comprensibili e conferme delle operazioni pericolose. | `magazzino_profili.domain` (15, M); `magazzino_profili.services.anagrafica` (16, M); `magazzino_profili.services.eccezioni` (17, M) |
| `magazzino_profili/ui/registro_colori.py:1` — Colori mostrati nell'interfaccia: un'unica fonte per chip, tabelle e pillole. | `magazzino_profili.services.colori_base` (15, M); `magazzino_profili.domain` (89, R) |
| `magazzino_profili/ui/scheda_carico.py:1` — Scheda Carico: scannerizzazione/inserimento barcode e giacenza. | `magazzino_profili.services` (28, M); `magazzino_profili.services.consultazione` (28, M); `magazzino_profili.ui.collega_telefono` (29, M); `magazzino_profili.ui.componenti` (30, M); `magazzino_profili.ui.messaggi` (40, M); `magazzino_profili.ui.tema` (41, M) |
| `magazzino_profili/ui/scheda_profilo.py:1` — Scheda Profili: elenco, ricerca, creazione, modifica e immagine della sezione. | `magazzino_profili.domain` (31, M); `magazzino_profili.services` (32, M); `magazzino_profili.services.anagrafica` (32, M); `magazzino_profili.services` (33, M); `magazzino_profili.services.consultazione` (33, M); `magazzino_profili.services.catalogo_immagini` (34, M); `magazzino_profili.services.proposta_immagine` (35, M); `magazzino_profili.ui.componenti` (36, M); `magazzino_profili.ui.icone` (41, M); `magazzino_profili.ui.tema` (42, M); `magazzino_profili.ui.validatori` (43, M); `magazzino_profili.ui.messaggi` (340, R); `magazzino_profili.ui.messaggi` (451, R) |
| `magazzino_profili/ui/scheda_scarico.py:1` — Scheda Scarico: riduzione di giacenza da barcode, con causale. | `magazzino_profili.services` (16, M); `magazzino_profili.services.consultazione` (16, M); `magazzino_profili.ui` (17, M); `magazzino_profili.ui.registro_colori` (17, M); `magazzino_profili.ui.collega_telefono` (18, M); `magazzino_profili.ui.componenti` (19, M); `magazzino_profili.ui.messaggi` (28, M); `magazzino_profili.ui.tema` (29, M) |
| `magazzino_profili/ui/tabella_pezzi.py:1` — Scheda Inventario: card KPI, chip colore, tabella e pannello laterale. | `magazzino_profili.services` (54, M); `magazzino_profili.services.consultazione` (54, M); `magazzino_profili.services.impostazioni` (54, M); `magazzino_profili.services.eccezioni` (62, M); `magazzino_profili.ui` (63, M); `magazzino_profili.ui.animazioni` (63, M); `magazzino_profili.ui.registro_colori` (63, M); `magazzino_profili.ui.tema` (63, M); `magazzino_profili.ui.tema` (64, M); `magazzino_profili.ui.icone` (65, M); `magazzino_profili.ui.componenti` (66, M); `magazzino_profili.ui` (311, R); `magazzino_profili.ui.gestione_colori` (311, R); `magazzino_profili.barcode` (557, R); `magazzino_profili.barcode.generazione` (557, R); `magazzino_profili.barcode` (744, R); `magazzino_profili.barcode.etichette` (744, R) |
| `magazzino_profili/ui/tema.py:1` — Tema grafico dell'interfaccia (design "grande" del mockup). | `magazzino_profili.ui.registro_colori` (225, R); `magazzino_profili.ui.icone` (280, R) |
| `magazzino_profili/ui/validatori.py:1` — Validatori dei campi di testo. | nessun import interno esplicito |
| `magazzino_profili/web/__init__.py:1` — Pacchetto web: scansione barcode dal telefono, accesso solo remoto. | `magazzino_profili.web.app` (19, M) |
| `magazzino_profili/web/app.py:1` — Avvio del server web di scansione da telefono (processo separato). | `magazzino_profili.db` (46, M); `magazzino_profili.services` (47, M); `magazzino_profili.web.routes_barcode` (48, M); `magazzino_profili.web.routes_update` (49, M); `magazzino_profili.web.sicurezza_web` (50, M) |
| `magazzino_profili/web/auth.py:1` — Autenticazione del modulo web: login e token con scadenza. | `magazzino_profili.sicurezza` (23, M) |
| `magazzino_profili/web/routes_barcode.py:1` — Endpoint API per la scansione dal telefono: login, carico, scarico. | `magazzino_profili.domain` (34, M); `magazzino_profili.domain.pezzo` (35, M); `magazzino_profili.services` (36, M); `magazzino_profili.services.consultazione` (36, M); `magazzino_profili.services.carico` (37, M); `magazzino_profili.services.eccezioni` (38, M); `magazzino_profili.services.scarico` (39, M); `magazzino_profili.services` (40, M); `magazzino_profili.services.telefono` (40, M); `magazzino_profili.web.auth` (41, M); `magazzino_profili.web.sicurezza_web` (48, M) |
| `magazzino_profili/web/routes_update.py:1` — Feed di aggiornamento (Fase 13 completa) — rotte ``/update/...``. | nessun import interno esplicito |
| `magazzino_profili/web/sicurezza_web.py:1` — Protezioni del modulo web: segrete dei token, limite ai tentativi di login, | nessun import interno esplicito |

### Appendice B — Risultati per modulo di test

**VERIFICATO:** i numeri includono il recupero dei test sicurezza senza TestClient, senza duplicare casi; `setup` è distinto da assertion fallita. Per ogni modulo, log/XML sotto `E/esiti/`. Fonte conteggi: `E/riepilogo_test.json:1`; codice aggregazione `E/riassumi_test.py:1`.

| File sorgente | Superati | Falliti | Saltati | Bloccati | Setup errore | Esclusi |
|---|---:|---:|---:|---:|---:|---:|
| `magazzino_profili/tests/test_aggiornamenti.py:1` | 45 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_anagrafica.py:1` | 5 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_anagrafica_fase7.py:1` | 4 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_animazioni.py:1` | 8 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_backup.py:1` | 8 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_backup_excel.py:1` | 32 | 0 | 33 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_backup_excel_colori.py:1` | 2 | 1 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_barcode.py:1` | 5 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_barcode_etichette.py:1` | 3 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_barcode_generazione.py:1` | 3 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_barcode_postgres.py:1` | 0 | 0 | 2 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_barcode_validita.py:1` | 6 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_barcode_vassoio.py:1` | 33 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_carico.py:1` | 7 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_catalogo_immagini.py:1` | 13 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_ciclo_vita_fase12.py:1` | 10 | 3 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_colori_base.py:1` | 9 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_consultazione.py:1` | 32 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_csv.py:1` | 4 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_csv_legacy_fase10.py:1` | 12 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_db_config_frozen.py:1` | 2 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_dialogo_aggiornamento.py:1` | 7 | 0 | 0 | 0 | 0 | 1 |
| `magazzino_profili/tests/test_etichette.py:1` | 4 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_export.py:1` | 1 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_fase8_colori.py:1` | 12 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_formato_v2_fase10.py:1` | 22 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_importa_ods_fase7.py:1` | 4 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_impostazioni.py:1` | 5 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_input_numerici.py:1` | 6 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_integrazione_postgres.py:1` | 0 | 0 | 3 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_inventario_colori.py:1` | 3 | 1 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_migrazioni_postgres.py:1` | 0 | 0 | 2 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_normalizzazione.py:1` | 17 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_pezzi.py:1` | 5 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_pezzo_campi_giacenza.py:1` | 6 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_proposta_immagine.py:1` | 6 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_registro_colori.py:1` | 7 | 1 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_regressione_fase3.py:1` | 16 | 0 | 2 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_regressione_fase3b.py:1` | 8 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_regressione_fase3b_ui.py:1` | 2 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_report_pdf.py:1` | 2 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_riepilogo_equivalenza.py:1` | 4 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_routes_update.py:1` | 0 | 0 | 0 | 8 | 0 | 0 |
| `magazzino_profili/tests/test_scarico.py:1` | 3 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_scheda_profilo_catalogo.py:1` | 8 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_servizio_colori.py:1` | 5 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_sicurezza_fase14.py:1` | 39 | 0 | 1 | 8 | 0 | 0 |
| `magazzino_profili/tests/test_spezzoni.py:1` | 4 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_stati_postgres.py:1` | 0 | 0 | 6 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_stati_scadenze.py:1` | 38 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_telefono.py:1` | 10 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_ui_fase4.py:1` | 11 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_ui_fase7a.py:1` | 3 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_ui_fase7b.py:1` | 7 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_ui_smoke.py:1` | 9 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_ui_vassoio_stati.py:1` | 7 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_validatore_maiuscolo.py:1` | 3 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_web_auth.py:1` | 0 | 0 | 0 | 6 | 0 | 0 |
| `magazzino_profili/tests/test_web_client_javascript.py:1` | 1 | 0 | 0 | 0 | 0 | 0 |
| `magazzino_profili/tests/test_web_https_reale.py:1` | 0 | 0 | 0 | 0 | 1 | 0 |
| `magazzino_profili/tests/test_web_routes_barcode.py:1` | 0 | 0 | 0 | 23 | 0 | 0 |
| `magazzino_profili/tests/test_web_telefono.py:1` | 0 | 0 | 0 | 24 | 0 | 0 |

### Appendice C — DDL PostgreSQL ricavato dai modelli

**VERIFICATO come schema dichiarato, NON VERIFICATO sul server installato.** Compilazione SQLAlchemy, nessuna esecuzione SQL. Tutti i nomi di indici/vincoli sono esplicitati; i default Python non compaiono come DEFAULT SQL. Fonti: `magazzino_profili/domain/base.py:18`, modelli elencati in 3.2 e `E/completa_report.py:1`. Le migrazioni storiche possono dare nomi diversi ai vincoli già esistenti; serve introspezione su copia per confronto.

```sql
CREATE TABLE colori (
	id SERIAL NOT NULL,
	codice_normalizzato VARCHAR(64) NOT NULL,
	nome_visualizzato VARCHAR(128) NOT NULL,
	colore_hex VARCHAR(7),
	CONSTRAINT pk_colori PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_colori_codice_normalizzato ON colori (codice_normalizzato);
CREATE TABLE impostazioni (
	chiave VARCHAR(64) NOT NULL,
	valore VARCHAR(255) NOT NULL,
	CONSTRAINT pk_impostazioni PRIMARY KEY (chiave)
);
CREATE TABLE profili (
	id SERIAL NOT NULL,
	codice VARCHAR(64) NOT NULL,
	descrizione TEXT NOT NULL,
	immagine_sezione VARCHAR(512),
	peso_kg_per_metro NUMERIC(10, 4) NOT NULL,
	lunghezza_standard_mm INTEGER NOT NULL,
	CONSTRAINT pk_profili PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_profili_codice ON profili (codice);
CREATE TABLE scansioni_telefono (
	id SERIAL NOT NULL,
	barcode VARCHAR(255) NOT NULL,
	utente VARCHAR(64) NOT NULL,
	creata_il TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	letta BOOLEAN DEFAULT false NOT NULL,
	CONSTRAINT pk_scansioni_telefono PRIMARY KEY (id)
);
CREATE TABLE utenti (
	id SERIAL NOT NULL,
	username VARCHAR(64) NOT NULL,
	password_hash VARCHAR(128) NOT NULL,
	ruolo VARCHAR(32) NOT NULL,
	CONSTRAINT pk_utenti PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_utenti_username ON utenti (username);
CREATE TABLE pezzi (
	id SERIAL NOT NULL,
	profilo_id INTEGER NOT NULL,
	colore_id INTEGER NOT NULL,
	lunghezza_mm INTEGER NOT NULL,
	quantita INTEGER NOT NULL,
	ubicazione VARCHAR(128),
	scorta_minima INTEGER,
	barcode VARCHAR(255) NOT NULL,
	numero_vassoio VARCHAR(128),
	stato VARCHAR(16),
	data_ultimo_cambio_stato TIMESTAMP WITH TIME ZONE,
	eliminato_il TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_pezzi PRIMARY KEY (id),
	CONSTRAINT combinazione UNIQUE (profilo_id, colore_id, lunghezza_mm),
	CONSTRAINT ck_pezzi_quantita_non_negativa CHECK (quantita >= 0),
	CONSTRAINT ck_pezzi_stato_valido CHECK (stato IS NULL OR stato IN ('Caricato', 'Scaricato')),
	CONSTRAINT fk_pezzi_profilo_id FOREIGN KEY(profilo_id) REFERENCES profili (id),
	CONSTRAINT fk_pezzi_colore_id FOREIGN KEY(colore_id) REFERENCES colori (id),
	CONSTRAINT uq_pezzi_barcode UNIQUE (barcode)
);
CREATE INDEX ix_pezzi_colore_id ON pezzi (colore_id);
CREATE INDEX ix_pezzi_eliminato_il ON pezzi (eliminato_il);
CREATE INDEX ix_pezzi_profilo_id ON pezzi (profilo_id);
CREATE TABLE movimenti (
	id SERIAL NOT NULL,
	pezzo_id INTEGER NOT NULL,
	tipo VARCHAR(16) NOT NULL,
	quantita INTEGER NOT NULL,
	data_ora TIMESTAMP WITH TIME ZONE NOT NULL,
	causale TEXT NOT NULL,
	utente TEXT NOT NULL,
	CONSTRAINT pk_movimenti PRIMARY KEY (id),
	CONSTRAINT ck_movimenti_quantita_positiva CHECK (quantita > 0),
	CONSTRAINT fk_movimenti_pezzo_id FOREIGN KEY(pezzo_id) REFERENCES pezzi (id)
);
CREATE INDEX ix_movimenti_pezzo_id ON movimenti (pezzo_id);
CREATE TABLE spezzoni (
	id SERIAL NOT NULL,
	pezzo_origine_id INTEGER NOT NULL,
	utente VARCHAR NOT NULL,
	lunghezza_mm INTEGER NOT NULL,
	data_creazione TIMESTAMP WITH TIME ZONE NOT NULL,
	utilizzato BOOLEAN NOT NULL,
	CONSTRAINT pk_spezzoni PRIMARY KEY (id),
	CONSTRAINT ck_spezzoni_lunghezza_positiva CHECK (lunghezza_mm > 0),
	CONSTRAINT fk_spezzoni_pezzo_origine_id FOREIGN KEY(pezzo_origine_id) REFERENCES pezzi (id)
);
CREATE INDEX ix_spezzoni_pezzo_origine_id ON spezzoni (pezzo_origine_id);
CREATE TABLE migrazioni_applicate (nome TEXT PRIMARY KEY);
```

Fonte della tabella non ORM: `magazzino_profili/db/migrazioni.py:28`.
