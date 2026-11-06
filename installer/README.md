# Installer Windows di Magazzino Profili

## Pacchetto disponibile

Build di questa consegna: `dist/installer-2.4.6-barcode-20261106/`.
Usare preferibilmente `MagazzinoProfili-2.4.6-setup.exe`; `setup.exe` è una copia identica.
`SHA256SUMS.txt` contiene gli hash, `manifest.json` è firmato Ed25519 per il programma.
La release online non è stata pubblicata da questa procedura.

Il setup è **senza firma Authenticode**: Windows può mostrare SmartScreen. Verificare provenienza e hash prima di avviarlo. Se Windows lo blocca e non è possibile verificare la provenienza, fermarsi; non disabilitare protezioni. La firma Ed25519 del manifest non sostituisce un certificato riconosciuto da Windows.

## Installazione e aggiornamento

Windows 10/11 x64, installazione per l'utente corrente, senza amministratore o Python preinstallato. Default:

```text
%LOCALAPPDATA%\Programs\Magazzino Profili
```

La procedura italiana permette di scegliere una cartella nuova e il collegamento desktop, mostra il riepilogo e propone l'avvio finale. Il menu Start e la voce di disinstallazione vengono creati dal setup.

**PC principale:** PostgreSQL deve essere già disponibile e configurato. L'installer non installa PostgreSQL, non modifica servizi, password o database. Al primo avvio selezionare il `config.toml` valido già usato dal magazzino: viene copiato nei dati locali. Servono `pg_dump` e `pg_restore` compatibili con il server per i backup e prima delle migrazioni. Il PC secondario non richiede un database locale. La cartella di rete condivisa va configurata nell'applicazione.

Chiudere il programma, anche nell'area di notifica, prima dell'aggiornamento. Usare sempre il setup nuovo: stesso AppId, stessa installazione registrata. Lo spostamento di un'installazione già registrata e il downgrade sono bloccati. Vecchie cartelle portabili non vengono eliminate né disinstallate automaticamente.

```bat
MagazzinoProfili-2.4.6-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
MagazzinoProfili-2.4.6-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="D:\Applicazioni\Magazzino Profili" /TASKS="desktopicon" /LOG="C:\percorso-scrivibile\setup.log"
```

Il secondo comando serve alla prima installazione in una cartella nuova; negli aggiornamenti mantenere la cartella precedente. Controllare il codice di uscita: `0` indica successo, qualsiasi altro valore richiede il controllo del log. Il setup aspetta fino a 20 secondi la chiusura dell'app e non termina processi forzatamente. In modalità silenziosa non avvia l'applicazione; `/RIAVVIA=1` è il parametro usato dall'aggiornamento interno per riaprirla dopo un aggiornamento riuscito. Nessun riavvio di Windows viene richiesto.

## Politica dei dati

```text
%LOCALAPPDATA%\Magazzino Profili\
  config.toml                       configurazione importata, credenziali incluse
  config-precedente-<id>.toml        copie prima di sostituire la configurazione
  preferenze\MagazzinoProfili\      INI: ruolo, opzioni desktop e animazioni
  immagini_sezioni\                immagini aggiunte dall'utente
  commesse_secondario\             commesse persistenti locali
  backup\prima-migrazione\         dump preventivi conservati
  backup\                          backup periodici conservati
  log\                             registri applicazione e telefono
  aggiornamenti\                   download verificati
  temporanei\                      cache/temporanei del programma
```

Catalogo PNG/CSV e risorse di sola lettura restano nell'installazione. I vecchi dati di `%LOCALAPPDATA%\magazzino_profili` e il file TOML originale restano intatti; preferenze e commesse vengono copiate al primo avvio. Le immagini relative in `immagini_sezioni` vengono copiate senza sovrascrivere immagini omonime differenti. Un conflitto sospende l'importazione con errore. Configurazioni non valide non sostituiscono quelle buone.

Le migrazioni dichiarate in `installazione.json` devono corrispondere ai file incorporati. Schema attuale: 12; registro storico `migrazioni_applicate` e hash `migrazioni_checksum`. Un database esistente con migrazioni pendenti richiede prima un dump leggibile tramite `pg_restore --list`. Tutto il lotto DDL/dati/registro è transazionale e serializzato su PostgreSQL. In caso di errore il rollback ripristina lo stato precedente e l'app non apre il magazzino. Non viene eseguito un `pg_restore --clean` automatico sul database operativo: il backup è conservato per recupero controllato. La prova del ripristino fisico è eseguita su un database vuoto separato.

La conservazione automatica non elimina backup nella versione installata: monitorare lo spazio occupato. I dump possono contenere dati riservati. Il database PostgreSQL esterno continua a vivere nella propria cartella amministrata; non viene spostato dal setup.

Disinstallazione: per default conserva tutti i dati. Nell'interfaccia si può richiederne l'eliminazione con **due conferme**; sono rimossi soltanto i dati della cartella locale identificata dal marcatore del programma, senza junction/symlink. In modalità silenziosa i dati vengono sempre conservati. Nessuna rimozione del database esterno, delle condivisioni, dei dati portabili o degli export.

Il limite delle scritture interne riguarda file di programma e dati locali. Sono necessarie le normali operazioni Windows dell'installer: estrazione temporanea, collegamenti Start/Desktop, registro di disinstallazione. Restano inoltre le scritture richieste dall'utente verso export, stampe, cartella condivisa e database configurato. Nessuna regola firewall, associazione di file o avvio automatico Windows viene aggiunto. L'opzione di avvio automatico Windows è disabilitata nella versione installata per rispettare questo perimetro.

## Compilare una versione successiva

Prerequisiti locali: ambiente virtuale con dipendenze del progetto e PyInstaller, compilatore C# .NET Framework di Windows, Inno Setup 7.1.1 x64. Il compilatore Inno usato qui è portabile dentro `dist/strumenti-installer/inno-7.1.1`, non è un'installazione globale. È possibile usare un compilatore già presente con `--iscc` o `ISCC_PATH`.

1. Cambiare soltanto `__version__` in `magazzino_profili/__init__.py`.
2. Aggiungere nuove migrazioni quando servono; non modificare quelle già distribuite. **Non cambiare APP_ID** in `magazzino_profili/distribuzione.py`.
3. Eseguire i test su copia esterna e poi la build verso una cartella non esistente:

```bat
installer\build.bat --destinazione dist\installer-nuova-versione --iscc "C:\percorso\Inno Setup 7\ISCC.exe"
installer\build.bat --destinazione dist\installer-nuova-versione-firmata --chiave-manifest "C:\percorso-protetto\chiave_privata.pem"
```

Il secondo comando richiede la chiave Ed25519 corrispondente alla pubblica incorporata. Non distribuirla. Per firma Authenticode facoltativa aggiungere `--certificato THUMBPRINT --signtool "C:\percorso\signtool.exe"`; il certificato deve essere già disponibile nello store dell'utente. Non è richiesto nella scelta attuale.

La build esegue compilazione PyInstaller, controllo sintassi e payload, dichiarazione schema/identità, verifica risorse, compilazione Inno, firma facoltativa e calcolo SHA-256. Al primo errore termina. Non contiene configurazione reale, dump, database, chiavi private o test; include runtime Python/Qt, dipendenze, icona, web, migrazioni, catalogo immagini e configurazione d'esempio. I metadati EXE e installer derivano dalla versione unica. Il vecchio `version_info.txt` alla radice non viene letto da questa build.

Per gli aggiornamenti online caricare nella stessa GitHub Release il setup con nome versionato e il relativo `manifest.json`, dopo i test del Passo D. Il programma installato accetta solo il manifest verificato con `tipo: setup`, controlla dimensione e SHA-256 e avvia il setup sulla stessa cartella. Un pacchetto ZIP portabile viene rifiutato nella versione installata. La build non pubblica file automaticamente.

## Verifiche automatiche ripetibili

Eseguire pytest su una copia esterna senza configurazioni o dati reali. Il `conftest.py` isola le preferenze e impone nomi di DB di test. Per la prova PostgreSQL usare una **nuova** cartella fuori dal repository:

```bat
python -B tools\verifica_migrazioni_installer.py --pg-bin "C:\Program Files\PostgreSQL\16\bin" --destinazione "C:\percorso-di-test\prova-nuova" --porta 55947 --pytest
```

Viene creato un cluster distinto, solo su `127.0.0.1:55947`, con dati sintetici, trust limitato al cluster di prova, e viene arrestato al termine. Non usare un cluster operativo né una cartella già esistente. Il comando non installa un servizio e non elimina la cartella di prova. Se il processo viene interrotto esternamente prima del cleanup, verificare il log e arrestare **solo quel cluster** con `pg_ctl -D "...\cluster-sintetico" -m fast -w stop`.

## Checklist Passo D — da eseguire su PC/VM pulito

Questi punti non sono sostituiti dai test Python o dalla compilazione del setup. Usare un ambiente Windows x64 ripristinabile, account standard, senza Python/Magazzino e dati inventati. Per il principale predisporre PostgreSQL di prova; verificare separatamente il secondario senza PostgreSQL locale.

| Prova | Risultato atteso | Stato in questa consegna |
|---|---|---|
| Windows 10 e Windows 11, RAM 4 GB | Wizard italiano, nessun UAC e avvio senza Python | **Bloccato:** PC/VM pulito non disponibile |
| Prima installazione e cambio destinazione | Solo cartella scelta, Start, desktop opzionale, una voce Programmi | **Bloccato:** ambiente pulito mancante |
| Lancio dal menu Start/desktop, principale e secondario | Risorse e immagini presenti, connessione al solo PG di prova | **Bloccato:** ambiente pulito mancante |
| Aggiornamento da precedente installer con stesso AppId | Una voce, stessa cartella, dati e preferenze intatti | **Bloccato:** prima release Inno, precedente installer distribuito assente |
| Reinstallazione e downgrade | Dati preservati; versione precedente bloccata | **Non eseguito** su Windows installato |
| Migrazione fallita durante avvio installato | App non parte, backup presente, dati precedenti intatti | **Non eseguito** da setup; rollback e restore PG sintetico **superati** |
| Installazione silenziosa e `/DIR` | Codice 0, nessun dialogo/avvio salvo `/RIAVVIA=1` | **Non eseguito** su installazione reale |
| App attiva durante setup/uninstall | Errore chiaro, nessun kill o sostituzione dati | **Non eseguito** su installazione reale |
| Disinstallazione GUI conservando dati | Programma/collegamenti rimossi, dati e DB intatti | **Non eseguito** su installazione reale |
| Disinstallazione GUI eliminando dati sintetici | Due conferme; rimosso solo percorso marcato; junction bloccate | **Non eseguito** su installazione reale |
| Disinstallazione silenziosa | Dati sempre conservati | **Non eseguito** su installazione reale |
| Snapshot/hash di ICON e altri programmi prima/dopo | Nessuna differenza | **Non eseguito:** nessuna installazione reale effettuata |
| Download e aggiornamento online end-to-end | Manifest, hash, setup, riavvio e dati conservati | **Non eseguito:** release non pubblicata |

Per confronto aggiornamento costruire nella VM una release di collaudo con numero precedente e lo **stesso AppId**, inserire dati inventati, poi installare la 2.4.6. Non usare o modificare un database operativo. Per verifica di ICON/altri programmi conservare manifest di file/hash prima e dopo fuori dalle loro cartelle, senza modificarli.
