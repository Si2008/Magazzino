# Magazzino Profili 2.4.4 — installer Windows

## Stato della consegna

**VERIFICATO:** implementato e compilato il setup Inno per Windows x64. Controllati payload, risorse, 211 PNG, schema 12, metadati EXE, identità, firma Ed25519 e SHA-256. **794 test Python superati, 0 falliti, 1 non eseguito** dopo aver integrato suite generale e prove PostgreSQL. Esiti individuali: [ESITI_INSTALLER_20261106.json](C:/Users/Simone/Desktop/magazzino/docs/ESITI_INSTALLER_20261106.json:1); controlli artefatto: [VERIFICA_PACCHETTO_INSTALLER_20261106.json](C:/Users/Simone/Desktop/magazzino/docs/VERIFICA_PACCHETTO_INSTALLER_20261106.json:1).

**BLOCCATO:** il Passo D su Windows pulito non è completato: non è disponibile un PC/VM pulito. Il tentativo di apertura del wizard tramite computer-use ha restituito `Computer Use app approval timed out`, senza una finestra verificabile. Nessuna installazione o disinstallazione del programma è stata eseguita sul PC di sviluppo. Il pacchetto non viene dichiarato collaudato tramite installazione reale. Checklist completa: [installer/README.md](C:/Users/Simone/Desktop/magazzino/installer/README.md:1).

Autorizzazione usata: richiesta allegata e successivo «completa tutto, ti autorizzo». Sono state adottate A1, B1 e la sincronizzazione tramite cartella condivisa già approvata. Non sono stati pubblicati rilasci online, modificati servizi PostgreSQL, credenziali operative o file di altri programmi. Le numerose modifiche preesistenti del repository sono state conservate; l'elenco sotto riguarda questo intervento.

## Passo A — analisi e rilievi

| Punto | Riscontro ed evidenza |
|---|---|
| Inno Setup | Inizialmente assente da PATH e percorsi standard cercati. Preparato il compilatore ufficiale **7.1.1 x64 in modalità portabile** dentro `dist/strumenti-installer/inno-7.1.1`; non usata un'installazione globale. Provenienza: [download ufficiale](https://jrsoftware.org/isdl.php), [script portabile ufficiale](https://github.com/jrsoftware/issrc/blob/is-7_1_1/isportable.iss). Firma Authenticode del download valida, Pyrsys B.V.; SHA-256 `8A5A6711C3766A6E5FB74F280BA0E3551E719CE94538D901FDBD1F8F9920B3F0`. Preparazione registrata in [preparazione-compiler.log](C:/Users/Simone/Desktop/magazzino/dist/strumenti-installer/preparazione-compiler.log:1). |
| Programma iniziale | Distribuzione PyInstaller 2.4.3 già presente in `dist/UI-2.4.3-20261106-finale/MagazzinoProfili-2.4.3`. La nuova pipeline costruisce una nuova cartella senza sovrascriverla: [compila_windows.py](C:/Users/Simone/Desktop/magazzino/tools/compila_windows.py:12). |
| Risorse | Spec già comprensiva di migrazioni, icona, web, OCR e PNG/CSV: [MagazzinoProfili.spec](C:/Users/Simone/Desktop/magazzino/MagazzinoProfili.spec:8). Icona riutilizzata: `icona.ico`. Nessuna nuova immagine profilo duplicata manualmente; il catalogo viene distribuito come risorsa dell'applicazione. |
| Versione | Fonte applicativa unica [__init__.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/__init__.py:7). La build genera i metadati Windows da questa fonte; il precedente `version_info.txt` radice non è letto: [compila_windows.py](C:/Users/Simone/Desktop/magazzino/tools/compila_windows.py:20). |
| Configurazione precedente | Versione portabile: percorso esplicito, ambiente, cartella corrente/eseguibile/repository. Non adatta a un'installazione immutabile; mantenuta per compatibilità portabile, esclusa nella versione installata: [config.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/config.py:58). |
| Dati precedenti | Commessa secondaria/log/cache in `%LOCALAPPDATA%\magazzino_profili`; immagini aggiunte relative alla configurazione; preferenze Qt nel registro. Ora esiste un ramo installato separato: [percorsi_installazione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/percorsi_installazione.py:17), [anagrafica.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/anagrafica.py:161). |
| Database | PostgreSQL esterno; il modulo legacy può avviare un cluster dell'applicazione. Il setup non contiene o installa il server: [server.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/server.py:1). Nella versione installata quel tentativo di avvio è disabilitato: è un cambiamento esplicito del comportamento, il server configurato deve essere disponibile. |
| Versione schema | Esistevano già 12 file SQL e il registro `migrazioni_applicate`. Aggiunta verifica dei checksum e schema dichiarato nel pacchetto, senza alterare i file SQL distribuiti: [migrazioni.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/migrazioni.py:76). |
| Aggiornamenti | Già presenti GitHub Releases, verifica Ed25519 e download verificati. Il vecchio meccanismo installava copie portabili nella cache: ora il ramo installato accetta setup sulla stessa cartella: [aggiornamenti.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/aggiornamenti.py:376). |

Il download del compilatore e la sua estrazione portabile sono stati necessari alla build autorizzata. Non sono state aggiunte associazioni, scorciatoie del compilatore o una sua installazione globale. Il codice del compilatore non è stato modificato.

## Passo B — decisioni attuate

| Decisione | Scelta e motivazione |
|---|---|
| A | **Per utente**, `%LOCALAPPDATA%\Programs\Magazzino Profili`, `PrivilegesRequired=lowest`: non richiede amministratore; aggiornamenti della stessa installazione. Cartella personalizzabile alla prima installazione. [MagazzinoProfili.iss](C:/Users/Simone/Desktop/magazzino/installer/MagazzinoProfili.iss:21). |
| B | **Setup senza firma Authenticode**, nessun certificato ricevuto. Supporto opzionale signtool predisposto. Il manifest di aggiornamento è invece firmato Ed25519 con la chiave già prevista dal progetto: [crea_installer.py](C:/Users/Simone/Desktop/magazzino/tools/crea_installer.py:37). SmartScreen e certificazione restano distinti. |
| C | **Cartella condivisa**, nessuna regola firewall aggiunta o rimossa. Nessuna modifica di servizi, associazioni file o chiavi di avvio automatico: [MagazzinoProfili.iss](C:/Users/Simone/Desktop/magazzino/installer/MagazzinoProfili.iss:79). |
| Identità | AppId permanente `MagazzinoProfili.7FCFE24E-DAF6-45F0-85D5-888801F37BA4`, dichiarato in un solo modulo e passato al compilatore. **Non cambiarlo** nelle release successive: [distribuzione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/distribuzione.py:2). |
| Dati | Separati in `%LOCALAPPDATA%\Magazzino Profili`, conservati in aggiornamento e disinstallazione silenziosa; eliminazione GUI soltanto con doppia conferma, identità cartella e controllo reparse point. [percorsi_installazione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/percorsi_installazione.py:24), [MagazzinoProfili.iss](C:/Users/Simone/Desktop/magazzino/installer/MagazzinoProfili.iss:203). |
| Migrazioni | Dump preventivo verificato e conservato, poi **un'unica transazione per l'intero lotto**, lock PostgreSQL e rollback su errore. Recupero automatico tramite rollback, non tramite un `pg_restore --clean` distruttivo sul database operativo. Ripristino fisico da dump provato su database vuoto separato. [main.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:106), [migrazioni.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/migrazioni.py:87). |

**Scostamento esplicito dalla formulazione del requisito:** in caso di migrazione fallita il programma ripristina automaticamente lo stato precedente tramite rollback SQL, conservando il backup, e non avvia il magazzino. Non esegue un ripristino fisico automatico che potrebbe cancellare o sovrascrivere dati concorrenti. Il recupero del dump è stato testato realmente, ma soltanto in una base vuota di prova. Non viene dichiarato effettuato sul database operativo.

**Perimetro delle scritture:** file interni in installazione/dati; il normale funzionamento richiede anche scritture esplicite verso il database PostgreSQL configurato, condivisioni ed export scelti dall'utente. Il setup usa i normali temporanei di Windows e crea collegamenti Start/Desktop e registro di disinstallazione: queste eccezioni sono necessarie ai requisiti stessi. Non è quindi sostenibile interpretare il vincolo come divieto assoluto di ogni scrittura esterna, incluse quelle espressamente richieste. L'avvio automatico Windows è disabilitato nel menu della versione installata; tray e funzioni applicative restano presenti: [background.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/background.py:48).

## Passo C — implementazione

### Script e politica di aggiornamento

Lo script contiene tutte le sezioni richieste: Setup, Languages, Tasks, Files, Icons, Run, Registry, UninstallDelete e Code. Italiano unico, Windows 10+ x64, collegamento desktop opzionale, Start, disinstallazione, riepilogo e avvio finale. Registro limitato alle informazioni gestite automaticamente da Inno; nessun wildcard di cancellazione dell'installazione o dei dati. Il codice impedisce installazione nella cartella dati/altre cartelle non vuote senza identità, duplicazione della posizione registrata e downgrade. Attende la chiusura dell'applicazione tramite mutex senza terminare processi: [MagazzinoProfili.iss](C:/Users/Simone/Desktop/magazzino/installer/MagazzinoProfili.iss:21), [controlli](C:/Users/Simone/Desktop/magazzino/installer/MagazzinoProfili.iss:127).

Il percorso distribuito è:

```text
C:\Users\Simone\Desktop\magazzino\dist\installer-2.4.4-finale-20261106\setup.exe
C:\Users\Simone\Desktop\magazzino\dist\installer-2.4.4-finale-20261106\MagazzinoProfili-2.4.4-setup.exe
```

I due file sono identici, **81.559.015 byte**, SHA-256 `0c4f6a64f61474c6242fae6342efadff7ba54615d8a04af1d41803d41b32859c`. Preferire il nome versionato per la distribuzione: il compilatore Inno segnala rischi di compatibilità/caricamento DLL per eseguibili genericamente denominati `setup.exe`; la compilazione finale usa il nome versionato e crea l'alias richiesto dopo. L'output preliminare `dist/installer-2.4.4-20261106` è una build di prova superata e **non è la consegna da distribuire**. Evidenze: [log Inno finale](C:/Users/Simone/Desktop/magazzino/dist/installer-2.4.4-finale-20261106/inno-setup.log:1), [controlli artefatto](C:/Users/Simone/Desktop/magazzino/docs/VERIFICA_PACCHETTO_INSTALLER_20261106.json:1).

Metadati verificati sull'EXE applicativo: FileVersion/ProductVersion `2.4.4.0`, ProductName `Magazzino Profili`, CompanyName `Si2008`; architettura PE x64. Sono generati da [compila_windows.py](C:/Users/Simone/Desktop/magazzino/tools/compila_windows.py:28). Il manifest Ed25519 generato è un file locale; l'URL GitHub al suo interno indica la futura release, **non prova che sia già pubblicata**.

Il build BAT chiama la pipeline e termina al primo errore. Sono inclusi Python/Qt/librerie, migrazioni, OCR, web, icona, 211 immagini e indice, configurazione d'esempio. Sono esclusi configurazioni reali, dump, database, chiavi private e test. Il payload viene controllato prima del compilatore: [build.bat](C:/Users/Simone/Desktop/magazzino/installer/build.bat:1), [controlli payload](C:/Users/Simone/Desktop/magazzino/tools/crea_installer.py:20).

### Migrazione dei percorsi e compatibilità

Preferenze in INI espliciti: `QSettings(org, app)` non rispetta la selezione del formato di default su questa piattaforma; il primo test lo ha dimostrato e tutti gli usi applicativi interessati sono stati convertiti al costruttore con file e formato. Configurazione valida copiata atomicamente; password preservata, percorsi relativi catalogo/certificati/pg_dump resi assoluti, precedenti configurazioni conservate. Archivi secondari e immagini copiati senza sovrascritture silenziose. Originali portabili e registro precedente rimangono intatti: [percorsi_installazione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/percorsi_installazione.py:42), [importazione](C:/Users/Simone/Desktop/magazzino/magazzino_profili/percorsi_installazione.py:70).

I backup automatici installati sono confinati ai dati e non eliminano quelli precedenti. I preventivi sono separati in `backup/prima-migrazione`. La versione portabile conserva il precedente comportamento di retention. Nessuna colonna di magazzino eliminata né file SQL di migrazione modificato: [backup_db.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/backup/backup_db.py:52), [main.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:216).

### File creati o modificati in questa fase

| File | Motivo |
|---|---|
| [installer/MagazzinoProfili.iss](C:/Users/Simone/Desktop/magazzino/installer/MagazzinoProfili.iss:1) — nuovo | Setup, aggiornamento, mutex, disinstallazione e protezione dati. |
| [installer/build.bat](C:/Users/Simone/Desktop/magazzino/installer/build.bat:1) — nuovo | Entrata build con arresto su errore. |
| [installer/Informazioni.txt](C:/Users/Simone/Desktop/magazzino/installer/Informazioni.txt:1) — nuovo | Informazioni italiane, prerequisito PostgreSQL e dati. Nessuna licenza inventata. |
| [installer/README.md](C:/Users/Simone/Desktop/magazzino/installer/README.md:1) — nuovo | Installazione, build, aggiornamenti, silent e checklist. |
| [tools/crea_installer.py](C:/Users/Simone/Desktop/magazzino/tools/crea_installer.py:1) — nuovo | PyInstaller → verifica payload → Inno → firma opzionale → hash/manifest. |
| [tools/verifica_migrazioni_installer.py](C:/Users/Simone/Desktop/magazzino/tools/verifica_migrazioni_installer.py:1) — nuovo | Cluster PostgreSQL sintetico, migrazione, rollback, restore e test saltati. |
| [tools/compila_windows.py](C:/Users/Simone/Desktop/magazzino/tools/compila_windows.py:28) | Metadati Windows completi e traduzione italiana della risorsa versione. |
| [distribuzione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/distribuzione.py:1) — nuovo | Identità permanente AppId/editore/mutex. |
| [percorsi_installazione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/percorsi_installazione.py:1) — nuovo | Percorsi installati, import conservativo, INI, temporanei e mutex runtime. |
| [__init__.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/__init__.py:7) | Versione unica 2.4.4. |
| [MagazzinoApp.py](C:/Users/Simone/Desktop/magazzino/MagazzinoApp.py:6) | Preparazione runtime prima di desktop/server telefono. |
| [main.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:18) | Percorsi/log, transazione migrazioni, backup protetto, messaggi avvio corretti senza suggerire script Python nell'installazione. |
| [db/config.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/config.py:58) | Versione installata legge soltanto la propria configurazione dati, salvo percorso esplicito. |
| [db/server.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/server.py:100) | Non avvia/amministra il cluster legacy dalla versione installata; requisito server esplicito. |
| [db/migrazioni.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/migrazioni.py:1) | Separazione SQL corretta, schema dichiarato, checksum, transazione atomica e lock. |
| [backup/backup_db.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/backup/backup_db.py:52) | Dati separati e opzione per conservare tutti i dump. |
| [services/postazione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/postazione.py:1) | Archivio/config/INI nei dati installati. |
| [services/anagrafica.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/anagrafica.py:161) | Upload immagini nei dati, non nel catalogo installato. |
| [services/aggiornamenti.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/aggiornamenti.py:298) | Cache dati e aggiornamento setup sulla medesima installazione; preservata compatibilità portabile. |
| [ui/dialogo_aggiornamento.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/dialogo_aggiornamento.py:163) | Avvio setup quando il manifest firmato dichiara quel tipo. |
| [ui/postazione.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/postazione.py:55) | Scrittura preferenze tramite file INI installato. |
| [ui/background.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/background.py:48) | Preferenze separate; disabilita modifiche all'avvio automatico Windows nella versione installata. |
| [ui/animazioni.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/animazioni.py:58) | Preferenza animazioni nel file INI installato. |
| [ui/server_telefono.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/server_telefono.py:48) | Log del sottoprocesso nella cartella dati. |
| [conftest.py](C:/Users/Simone/Desktop/magazzino/conftest.py:25) | Preferenze di test effettivamente isolate anche con costruttori Qt espliciti. |
| [tests/conftest.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/conftest.py:21) | Registro e segnali colore separati per test e DB sintetico. |
| [tests/test_installer.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_installer.py:1) — nuovo | 25 casi raccolti: percorsi, import, mutex, SQL atomico, backup, setup e aggiornamento. |
| [tests/test_animazioni.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_animazioni.py:135) | Test Avvisi seleziona la pagina per nome dopo precedente rimozione della scheda Profili. |
| [tests/test_regressione_fase3b_ui.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_regressione_fase3b_ui.py:28) | La postazione simulata dichiara `_secondario=False`, come la finestra reale. |
| [README.md](C:/Users/Simone/Desktop/magazzino/README.md:6) | Rimando all'installer e al prerequisito database. |
| Questo report e i JSON `ESITI_INSTALLER`, `VERIFICA_PACCHETTO_INSTALLER`, `FILE_INSTALLER` in `docs/` | Evidenze, esiti, impronte dei file e limiti della consegna. |
| `dist/strumenti-installer/`, `dist/installer-2.4.4-20261106/`, `dist/installer-2.4.4-finale-20261106/` | Compiler portabile, build preliminare e output definitivo; nessun dato reale incluso. |

Nessun file o cartella preesistente è stato eliminato. Le cancellazioni nei test riguardano soltanto script/database sintetici nella copia esterna. I precedenti interventi all'interfaccia e al mockup non sono stati riscritti; questa fase non modifica layout o palette desktop/telefono.

## Test e Passo D

| Gruppo | Stato | Evidenza/limite |
|---|---|---|
| Suite generale sulla copia esterna | **Superato:** 742; **non eseguito:** 53 alla prima esecuzione finale | JUnit `esito-definitivo.xml`, durata 112,15 s. Gli skip PostgreSQL sono stati poi recuperati sotto. |
| Test PostgreSQL saltati, rieseguiti su cluster nuovo | **Superato:** 52; **non eseguito:** 1 | JUnit `postgres-non-eseguiti/esito-postgres.xml`, 23,06 s. Include i 5 già passati nella verifica dedicata precedente, senza contarli due volte. |
| Totale identificativi unici | **794 superati, 0 falliti, 1 non eseguito** | [Esiti individuali](C:/Users/Simone/Desktop/magazzino/docs/ESITI_INSTALLER_20261106.json:1). Lo skip è `test_sequenze_senza_riallineamento_falliscono_su_postgres[sqlite]`: esplicitamente solo PostgreSQL; il corrispondente caso PostgreSQL è superato. |
| Backup e migrazione reale | **Superato** | Cluster nuovo sulla porta loopback 55947: dump verificato, aggiornamento delle 12 migrazioni, conservazione barcode/quantità, idempotenza. [Runner](C:/Users/Simone/Desktop/magazzino/tools/verifica_migrazioni_installer.py:13). |
| Fallimento e recupero | **Superato** | Migrazione 013 fittizia: DDL, modifica dati e registro annullati. Dump ripristinato su database vuoto distinto, verificati schema precedente e dati. Nessun `--clean` o restore su DB reale. |
| Compilazione e integrità pacchetto | **Superato** | PyInstaller, Inno 7.1.1, risorse, x64, schema dichiarato, firma manifest e hash. Nessun certificato Authenticode applicato. |
| Apertura wizard via computer-use | **Bloccato** | Scadenza autorizzazione app; nessuna schermata del wizard verificata. |
| Installazione/disinstallazione/silent/upgrade reali | **Bloccato / non eseguito** | Mancanza PC/VM pulito; non sostituiti da unit test. Tutti i casi sono distinti nella [checklist](C:/Users/Simone/Desktop/magazzino/installer/README.md:1). |
| Snapshot ICON/altri programmi prima/dopo installazione | **Non eseguito** | Nessuna installazione reale effettuata; non si dichiara un confronto hash che non è stato svolto. |
| Pubblicazione e aggiornamento Internet end-to-end | **Non eseguito** | Nessuna pubblicazione effettuata in questa fase. |

**Avvisi non nascosti:** la suite generale produce 11 RuntimeWarning PySide di disconnessione di listener colore nel teardown e un ulteriore avviso a fine processo ([finestra_principale.py](C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:233)). Sono legati all'isolamento dei segnalatori nei test; la suite passa, ma non costituisce verifica dell'assenza di analoghi problemi in uso interattivo. Non è stato modificato il codice della finestra per silenziare gli avvisi.

I tentativi iniziali falliti sono registrati negli esiti: formato Qt errato scoperto e corretto; test Avvisi con indice obsoleto; file mancanti nella prima copia di prova; fixture prive del ruolo e interferenze tra segnali di test; connessione loopback bloccata dalla sandbox, ripetuta con successo in ambiente autorizzato. Sono risultati intermedi corretti, non occultati né conteggiati come successi.

## Problemi aperti e prossima distribuzione

1. **Eseguire il Passo D su Windows pulito** prima di dichiarare l'installer pronto alla distribuzione generale: installazione, avvio dal menu, upgrade con dati inventati, silent, disinstallazione/conservazione/eliminazione controllata e hash altri programmi. Il tentativo computer-use non ha autorizzato alcuna dichiarazione di verifica grafica.
2. **PostgreSQL principale resta un prerequisito.** Il setup include il runtime Python, non un server database. Credenziali o servizio mancanti non vengono riparati inventando password. Conclusione esplicita nell'informativa e nelle istruzioni.
3. **Firma Authenticode assente.** SmartScreen può intervenire. Il manifest Ed25519 protegge gli aggiornamenti applicativi, non elimina gli avvisi Windows. Certificato e signtool opzionali documentati.
4. **Spazio backup:** nella versione installata nessun dump viene cancellato automaticamente; programmare una gestione manuale conforme alla politica dati.
5. **Vecchie versioni portabili:** restano nei loro percorsi; non vengono riconosciute come una precedente installazione Inno. Il primo vero upgrade Inno va provato creando nella VM una versione di collaudo precedente con lo stesso AppId.
6. **Release GitHub ancora da pubblicare:** setup versionato e manifest sono pronti localmente. Non dichiarare raggiungibile l'URL del manifest prima del caricamento della release.

I comandi per le prossime versioni, firma facoltativa, aggiornamento e silent sono nella [guida installer](C:/Users/Simone/Desktop/magazzino/installer/README.md:1). Per cambiare versione modificare soltanto `__version__`; per cambiare schema aggiungere migrazioni nuove; non cambiare l'AppId.
