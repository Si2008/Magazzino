# Magazzino Profili

Applicazione Windows 10/11 a 64 bit. La versione è definita esclusivamente in
`magazzino_profili/__init__.py`. Non sono previsti account o login applicativi.

## Installer Windows 2.4.6

Il setup per utente e le istruzioni di build, installazione silenziosa,
aggiornamento e disinstallazione sono in [installer/README.md](installer/README.md).
Il collaudo su un PC/VM pulito resta da eseguire: vedere la checklist del Passo D.
Il principale richiede PostgreSQL già configurato; il setup include Python e Qt,
ma non installa né riconfigura il server database.

La 2.4.5 amplia il dettaglio dell'Inventario e rende trascinabili le colonne.
In Carico/Scarico l'elenco profili occupa lo spazio disponibile, con righe alte
72 pixel; dettagli e movimenti si aprono dal pulsante in fondo all'elenco.

La 2.4.6 corregge la lettura da telefono dei barcode Code 128 lunghi: usa tutta
l'inquadratura e fotogrammi a risoluzione maggiore. Sono disponibili autofocus
continuo e luce se supportati, oltre alla lettura locale di una foto. La foto
non viene inviata al server; lo scarico richiede la conferma del pezzo letto.

## Interfaccia 2.4.3

Le schede superiori sono Inventario, Carico, Scarico, Avvisi e Commesse.
L'anagrafica resta in **Inventario → Gestisci profili**: creazione, modifica,
associazione/importazione/rimozione dell'immagine e ingrandimento restano disponibili.
Selezionando una riga dell'Inventario si apre il pannello con la sezione del profilo;
anche un clic sull'immagine la ingrandisce. Un profilo senza PNG mostra un segnaposto.
Carico e Scarico hanno una ricerca indipendente nella colonna destra, per codice o
nome, con 50 risultati per pagina. In Scarico ogni riga identifica barcode, misura,
colore e vassoio del pezzo specifico. I campi dell'operazione restano a sinistra.

Il peso è dismesso dai campi, dai riepiloghi e dagli output visibili. La colonna
storica del database viene conservata. I nuovi profili usano un valore interno di
compatibilità, che non è una misura reale. Il backup Excel formato 5 omette questo
metadato; i backup precedenti restano leggibili. Per conservare anche il metadato
storico usare il backup tecnico PostgreSQL. Le colonne peso dei CSV/ODS precedenti
vengono ignorate senza aggiornare i valori già salvati.

La build locale di questa fase si avvia con `Avvia_Magazzino_2.4.3.cmd` nella radice
del progetto: usa il `config.toml` esistente e non cambia variabili di sistema.
L'eseguibile è in `dist/UI-2.4.3-20261106-finale/MagazzinoProfili-2.4.3/` con le sue risorse.
Non è stata pubblicata una release online durante questa fase.

Il mockup aggiornato è `magazzino-mockup-grande.html`; è una ricostruzione dichiarata,
perché l'originale approvato non è stato reperito. Palette Qt e HTML condividono
`magazzino_profili/ui/tema.py`. Dopo un cambio palette eseguire:

```powershell
.venv\Scripts\python.exe -B tools\genera_temi.py
.venv\Scripts\python.exe -B tools\verifica_contrasti.py docs\CONTRASTI_UI_20261106.json
```

Esiti, limiti della verifica e riferimenti al codice sono nel
[report della fase](docs/INTERVENTO_UI_20261106.md). Le relazioni precedenti e i
vecchi prompt descrivono versioni storiche: i riferimenti al peso o alla vecchia
scheda Profili in quei documenti non rappresentano l'interfaccia attuale.

## Installazione senza Python

Scaricare il pacchetto ZIP dalla [release più recente](https://github.com/Si2008/Magazzino/releases/latest).
Estrarlo completamente in una cartella scrivibile e avviare `MagazzinoProfili.exe`.
La cartella `_internal` e `catalogo_immagini` devono restare accanto al programma.
Non è necessario installare Python.

### PC principale

È l'unico PC che gestisce il magazzino PostgreSQL ufficiale. PostgreSQL deve essere
già disponibile: non viene installato né inizializzato dal pacchetto dell'app.
Selezionare la configurazione TOML esistente da **Strumenti e backup → Configura
postazione e cartella di rete**. Per una nuova installazione, copiare
`config.example.toml` in `config.toml` e completare i parametri del proprio server
e il percorso di `pg_dump`. Non distribuire questa configurazione con credenziali.
La schermata di configurazione non permette di confermare il ruolo principale
finché non è stato selezionato e validato un file TOML con la sezione `[database]`.

L'avvio con migrazioni pendenti richiede prima un backup verificato. In caso di
errore correggere la configurazione e non forzare la migrazione.

### PC secondario

Al primo avvio scegliere **PC secondario**. In alternativa avviare:

```powershell
.\MagazzinoProfili.exe --secondario
```

Il secondario legge e conserva le commesse localmente, senza connessione a
PostgreSQL e senza schermate che modificano il magazzino. Configurare il ruolo
e la cartella condivisa e riavviare se si cambia ruolo.
La finestra secondaria mantiene la stessa barra, tema e schede del principale.
Inventario, Carico, Scarico e Avvisi spiegano che i dati sono disponibili
nel magazzino del principale; la scheda Commesse permette importazione e invio.

### Cartella di rete

Creare e condividere una cartella sul PC principale o su un NAS, con permessi
Windows di lettura/scrittura per le postazioni interessate. Indicare lo stesso
percorso UNC, per esempio `\\PC-PRINCIPALE\Commesse`, nella configurazione di tutti
i PC. La configurazione della condivisione e dei relativi permessi resta una
operazione di Windows; l'app non modifica firewall o autorizzazioni del sistema.

Il secondario usa **Invia / verifica ricezione**. Il principale usa **Ricevi
commesse** e conferma eventuali omonimie. Un file pubblicato in cartella non è
ancora una commessa accettata: il secondario mostra la ricevuta del principale.
Se il principale è spento o la rete manca, la copia locale resta salvata e si può
riprovare. Se la condivisione si trova su un NAS acceso, l'invio può restare in
attesa anche con il principale spento. Non mettere il database nella condivisione.

## Commesse

**Commesse → Carica commessa PDF** aggiunge il documento all'elenco per cognome.
Il cognome viene letto dal campo `Cognome:` oppure `Rif.`/`Riferimento:`.
Se manca o è vuoto, il documento viene rifiutato. Il cognome raggruppa le commesse;
l'identità del documento distingue ordini diversi dello stesso cognome.

Lo stesso documento non viene importato due volte, anche se cambia nome del file.
Per un nuovo documento dello stesso cognome viene chiesto se aggiungerlo al gruppo,
conservando quello precedente. Annullare non scrive dati.

Profilo e colore originali sono conservati nella commessa e non modificabili
nella tabella. I codici non sono limitati a famiglie note o al catalogo immagini.
La selezione del materiale usa il codice o il nome colore esatto e univoco presenti
nel magazzino: nessuna sostituzione approssimata della finitura. Se non trova una
corrispondenza, segnala il materiale mancante.

Il lettore PDF supporta la Lista ottimizzata Blitz già utilizzata; altri layout
sono rifiutati esplicitamente. Per le quote nelle immagini serve l'OCR locale di
Windows e una lingua di riconoscimento disponibile. Documenti incompleti o misure
non affidabili non vengono importati parzialmente. Controllare sempre le quote OCR.

**Trova pezzi e vassoi** indica profilo, colore, misura effettiva del pezzo da
prendere, vassoio e barcode. Il calcolo considera le sole lunghezze nominali,
senza specifiche di lavorazione. **Associa pezzi alla commessa** registra il legame
nel magazzino senza scaricarli. I pezzi associati non vengono proposti per un'altra
commessa. Carico, scarico e dettaglio inventario conservano il collegamento.
Gli spezzoni storici privi di barcode proprio richiedono etichettatura prima
dell'associazione; il vassoio dell'origine non è una posizione attuale verificata.

Il backup Excel formato 4 e l'archivio ZIP includono commesse, righe e associazioni.
I backup precedenti restano leggibili, con archivio commesse inizialmente vuoto.
Nella versione 2.3 le commesse erano soltanto in memoria: i PDF originali vanno
reimportati; non esisteva un archivio persistente da convertire.

## Aggiornamenti online

Per passare dalla 2.3 alla 2.4 estrarre manualmente il nuovo ZIP completo, oppure
usare la nuova cartella consegnata sul Desktop. L'aggiornamento della 2.3 copiava
un solo EXE e non installa questo nuovo pacchetto di librerie. Dalla 2.4 sono
supportati gli aggiornamenti completi ZIP descritti qui sotto.

Il programma confronta la versione installata con il manifest della release
GitHub più recente, in background. Una nuova versione mostra il popup per
scaricarla e installarla. Manifest Ed25519 e SHA-256 verificano autenticità e
integrità; il pacchetto completo viene preparato in una nuova cartella sotto
`%LOCALAPPDATA%\magazzino_profili\versioni`, preservando la versione precedente.
Non interrompere un'operazione o un backup per aggiornare.

Per un feed personalizzato impostare `[update] sorgente = "personalizzata"` e il
proprio `feed_url`; `abilitato = false` disattiva il controllo. Il vecchio URL
locale predefinito viene sostituito logicamente dal feed GitHub, senza riscrivere
la configurazione del magazzino. La chiave privata di firma resta sul PC del
pubblicatore e non deve essere caricata nel repository o nei pacchetti.

## Build e rilascio

Sul PC di sviluppo, in un ambiente virtuale con le dipendenze di `requirements.txt`
e PyInstaller, usare una destinazione nuova:

```powershell
.venv\Scripts\python.exe -B tools\compila_windows.py --destinazione C:\Build\Magazzino-nuova-versione
```

Il comando genera EXE, librerie, immagini e metadati Windows dalla stessa versione
Python. La compilazione non legge né incorpora `config.toml`, database o backup.
Per preparare il pacchetto firmato:

```powershell
.venv\Scripts\python.exe -B tools\prepara_release.py --cartella C:\Build\Magazzino-nuova-versione\MagazzinoProfili-VERSIONE --destinazione C:\Build\Release-nuova --chiave C:\PercorsoPrivato\chiave_privata.pem
```

Pubblicare lo ZIP prodotto e `manifest.json` come asset di una GitHub Release.
La sorgente documentata per i download stabili è
`https://github.com/Si2008/Magazzino/releases/latest/download/manifest.json`.

## Checklist su un PC pulito

- Windows 10/11 x64; almeno 4 GB RAM; estrazione completa dello ZIP.
- Avvio secondario senza Python e senza PostgreSQL installati.
- Scelta di ruolo e cartella di rete; riavvio e persistenza delle impostazioni.
- Importazione di due cognomi, reimportazione e omonimia senza sovrascrittura.
- Secondario senza rete: dati locali conservati; nuovo invio dopo il ripristino.
- Principale: ricevuta, immutabilità del colore e prelievo con misura/vassoio/barcode.
- Associazione commessa visibile dopo carico, scarico e riavvio.
- Backup completo e ripristino su un database di prova separato.
- Download firmato da una versione precedente, aggiornamento e riavvio.

Le prove su due PC fisici, su una VM pulita e sull'hardware più vecchio devono
essere annotate separatamente dai test automatici: la sola build non le dimostra.
# Richiamo vassoi ICON

**Rimanda vassoio**, nella barra in alto, apre il pannello di ICON per il
rientro del vassoio presente in baia. Usa il comando di rientro nel pannello.

In Inventario, usare **Chiama vassoio** direttamente sulla riga del pezzo.
Il pulsante è disponibile anche in Scarico dopo aver inserito il barcode e
in Commesse nella scheda **Pezzi e vassoi**. Il programma ricontrolla la
disponibilità prima del richiamo. Gli
spezzoni storici senza barcode proprio e i vassoi incerti sono esclusi.

L'impostazione predefinita è la simulazione: mostra la conferma e registra
l'operazione, senza aprire ICON o inviare richieste di rete. Per abilitare ICON
sulla postazione del magazzino, aggiungere a `config.toml`:

```toml
[icon]
modalita = "icon"
origine = "http://localhost"

[icon.mappa_vassoi]
# "1" = "0001"  # solo dopo aver verificato questa corrispondenza su ICON
```

La credenziale generica di Windows Credential Manager deve essere predisposta
una volta per l'utente Windows che avvia l'app, con destinazione
`MagazzinoProfili/ICON`, nome utente ICON e password ICON. L'app la legge soltanto.
Nessuna password va inserita in `config.toml` o nei file del progetto.

La ricerca automatica richiede che la pagina autenticata esponga un solo form
con azione `/Search/Search_UDS_main_doSearch` e un solo campo di ricerca visibile.
Se la versione ICON installata usa altri controlli, il richiamo si ferma: occorre
verificare il DOM della pagina prima di adattare il selettore. L'esito mostrato
è la risposta della pagina ICON; non certifica l'arrivo fisico del vassoio.
Il registro privo di credenziali si trova in `richiami_vassoio.jsonl` nella
cartella dati dell'app.

