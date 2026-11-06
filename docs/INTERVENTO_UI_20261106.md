# Magazzino Profili — intervento UI 2.4.3, 6 novembre 2026

## Stato e perimetro

**VERIFICATO:** implementate le cinque richieste nel sorgente; schermate Qt del principale renderizzate su SQLite sintetico ed esaminate nei temi chiaro/scuro. Build Windows 2.4.3 completata. **321 test Python superati, 35 non eseguiti; 18 test JavaScript superati; 100 coppie di contrasto superate.** Gli esiti individuali sono in `docs/ESITI_UI_20261106.json:1`; le misure in `docs/CONTRASTI_UI_20261106.json:1`.

**BLOCCATO / NON VERIFICABILE:** confronto visivo nel browser col mockup: il browser ha rifiutato `file://`. L'originale approvato non è stato reperito, neppure includendo file ignorati, nascosti ed estensioni maiuscole; il nuovo HTML è dichiaratamente ricostruito. La finestra dell'eseguibile secondario è stata osservata nell'inventario Windows; il successivo controllo grafico interattivo è stato bloccato dalla scadenza dell'autorizzazione computer-use. Nessuna verifica dell'eseguibile principale sul database operativo o su telefono fisico. Queste verifiche non vengono dichiarate completate.

La richiesta successiva «devi completare tutto» ha autorizzato a proseguire oltre l'analisi: sono state adottate le soluzioni conservative descritte nel Passo B. In questa fase non sono stati modificati database operativi, colonne esistenti, migrazioni, impostazioni Windows, altri programmi, librerie di terze parti o configurazioni reali. I test hanno lavorato su una copia esterna, con dati e preferenze isolati (`tools/cattura_ui_novembre.py:1`, `magazzino_profili/tests/test_ui_novembre.py:1`). Il repository conteneva già numerose modifiche: sono state conservate, senza reset.

## Passo A — rilievo iniziale

I numeri in questa sottosezione sono quelli rilevati **prima dell'intervento**; i riferimenti correnti sono riportati nel Passo C.

### Navigazione e funzioni Profili

| Punto iniziale | Evidenza rilevata | Funzione presente |
|---|---|---|
| Navigazione superiore | `magazzino_profili/ui/finestra_principale.py:392`, `:408` | Sei schede, inclusa Profili; costruzione differita dei widget. |
| Elenco profili | `magazzino_profili/ui/scheda_profilo.py:87`, `:97`, `:219` | Ricerca per codice/descrizione, selezione, lunghezza standard, giacenza e miniature. |
| Anagrafica | `magazzino_profili/ui/scheda_profilo.py:92`, `:141`, `:164`, `:432` | Nuovo profilo, modifica descrizione/misure e salvataggio. Non è emerso un comando di eliminazione dell'intero profilo. |
| Immagini | `magazzino_profili/ui/scheda_profilo.py:168`, `:174`, `:181`, `:201`, `:204`, `:306`, `:321` | Anteprima, apertura/zoom, import PNG e rimozione dell'associazione. Il file originale non viene cancellato dalla rimozione dell'associazione. |
| Associazione automatica | `magazzino_profili/ui/scheda_profilo.py:250`, `:396`; `magazzino_profili/services/immagini.py:34`, `:41`; `magazzino_profili/services/catalogo_immagini.py:108`, `:147` | Codice normalizzato → nome PNG; eventuale percorso manuale valido ha precedenza. |
| Inventario | `magazzino_profili/ui/tabella_pezzi.py:621` | Esisteva già un pulsante per aprire il PNG, ma non l'anteprima completa nel pannello; il pannello era inizialmente nascosto. |

**Precisazione sul catalogo:** il codice già esistente costruiva un indice in memoria dai nomi PNG; non usava `Indice_profili_aggiornato.csv` per decidere l'associazione. Il CSV esiste in `catalogo_immagini/Indice_profili_aggiornato.csv:1`, intestazione `Codice;Stato immagine;Fogli ODS`. La risoluzione della cartella era già configurabile con `[immagini] catalogo` o `MAGAZZINO_CATALOGO_IMMAGINI` (`services/catalogo_immagini.py:55`). Non è stata cambiata la priorità dei percorsi: la cartella `Profili_ritagliati`, quando configurata, continua a funzionare. Nessun PNG è stato rinominato, duplicato per l'Inventario o aggiunto al catalogo.

### Carico e Scarico

| Punto iniziale | Evidenza rilevata | Limite |
|---|---|---|
| Carico: form sinistro | `magazzino_profili/ui/scheda_carico.py:66`, `:115`, `:168` | Barcode o inserimento diretto del codice; nessun elenco ricercabile cliccabile. |
| Carico: colonna destra | `magazzino_profili/ui/scheda_carico.py:174`, `:181`, `:191` | Immagine e movimenti recenti. |
| Scarico: form sinistro | `magazzino_profili/ui/scheda_scarico.py:62`, `:96`, `:130` | Selezione tramite barcode; nessuna ricerca per nome/codice. |
| Scarico: colonna destra | `magazzino_profili/ui/scheda_scarico.py:136` | Movimenti recenti. |

**VERIFICATO:** i form erano a sinistra, anche se la richiesta descriveva la colonna destra come form. L'intervento ha mantenuto questo impianto: ricerca e dati della selezione a destra, campi e conferma dell'operazione a sinistra.

### Tutti i punti interessati dal peso

| Ambito | Evidenza iniziale | Stato iniziale |
|---|---|---|
| Inventario | `ui/tabella_pezzi.py:75`, `:103`, `:282`, `:299`, `:681`, `:682`, `:800`, `:1085`, `:1150` | Colonna nascosta ma ancora calcolata; KPI, dettagli e testi guida ancora presenti. Nessun filtro specifico per peso trovato. |
| Editor Profili | `ui/scheda_profilo.py:45`, `:147`, `:157`, `:248`, `:297`, `:436`, `:443`, `:471`, `:481` | Colonna nascosta, campo e obbligatorietà ancora attivi. |
| Telefono | `web/templates/scansione.html:31`, `web/static/scansione.js:247`, `:256`; stesse copie in `public/` e `web/vercel/public/`; `anteprima-telefono.html` | Campo, dettaglio del profilo e validazione richiesta al cliente. |
| API | `web/routes_barcode.py:63`, `:139`, `:181` | Obbligatorio per una nuova anagrafica ed esposto nell'elenco profili. |
| Backup Excel | `reports/backup_excel.py:63`, `:468` | Campo fisico nel foglio Profili, formato 4 e controlli del restore. |
| Export inventario | `reports/export_csv.py:28`, `reports/export_excel.py:18`, `reports/ods_v2.py:30`, `reports/export_pdf.py:18` | Già privi di peso: nessuna rimozione fittizia dichiarata. CSV/ODS V2 rifiutavano però intestazioni con colonne aggiuntive (`reports/formato_v2.py:196`). |
| Import ODS storico | `reports/importa_ods.py:96`, `:239`, `:246` | Compatibilità interna con valore storico tecnico; istruzione utente ancora riferita a peso e scheda Profili. |
| Dominio e servizi | `domain/profilo.py:26`, `:39`; `services/anagrafica.py:75`, `:91`, `:120`; `services/consultazione.py:223`, `:244`, `:269`; `migrations/008_vincoli_nuove_scritture.sql:3` | Colonna non nulla, validazione e vincolo positivo; calcoli interni ancora richiamabili. Cancellarla sarebbe stato un intervento distruttivo non necessario. |
| Documentazione storica | `docs/ANALISI_MAGAZZINO.md:200`, `:462`; `docs/CORREZIONI_2.2.0.md:12`, `:13`; `docs/CORREZIONI_MAGAZZINO.md:78`, `:90`; `_prompt_fase5.md:20` | Resoconti di versioni precedenti, non specifica dell'interfaccia attuale. Conservati e indicati come storici nel README aggiornato. Anche gli esiti JSON e i dati dei vecchi test mantengono i riferimenti storici. |

I prefissi abbreviati `ui/`, `web/`, `reports/`, `domain/`, `services/` nelle tabelle indicano sottocartelle di `magazzino_profili/`. La funzione `ui/tema.py:233` chiamava `peso` un coefficiente di mescolamento RGB: non si tratta del peso del materiale e la funzione non è stata alterata per una coincidenza lessicale.

### Colori iniziali e cause di contrasto

Fonte iniziale: `magazzino_profili/ui/tema.py:151` (SCURO), `:178` (CHIARO).

| Token | Scuro iniziale | Chiaro iniziale |
|---|---|---|
| sfondo | `#12141a` | `#e9ecf2` |
| superficie | `#171a21` | `#f3f5f9` |
| carta | `#1e222b` | `#ffffff` |
| carta2 | `#252a35` | `#f1f3f8` |
| bordo | `#2c323e` | `#dde1ea` |
| bordo_forte | `#3b4354` | `#c6ccda` |
| bordo_campo | `#6a748a` | `#7d889d` |
| testo | `#eceef2` | `#161a22` |
| testo_dim | `#9ba3b1` | `#556073` |
| testo_debole | `#8d97ab` | `#5d6a7d` |
| accento | `#5b8dff` | `#2b62e0` |
| accento_sfondo | `#243350` | `#e3ebfc` |
| ok | `#3ccb82` | `#117a48` |
| avviso | `#f0b04a` | `#8f5900` |
| pericolo | `#f47a74` | `#c43832` |
| accento_inchiostro | `#0b1633` | `#ffffff` |
| ok_inchiostro | `#06261a` | `#ffffff` |
| pericolo_inchiostro | `#2c0a08` | `#ffffff` |
| accento_vel | `rgba(91,141,255,36)` | `rgba(43,98,224,26)` |
| ok_vel | `rgba(60,203,130,36)` | `rgba(17,122,72,28)` |
| avviso_vel | `rgba(240,176,74,38)` | `rgba(201,125,0,36)` |
| pericolo_vel | `rgba(244,122,116,36)` | `rgba(196,56,50,26)` |

Gli alfa Qt in tabella sono interi 0–255, non percentuali.

| Problema iniziale verificato nel codice | Evidenza iniziale |
|---|---|
| `QColor(t.accento_vel)` non interpreta le stringhe CSS rgba: selezione dipinta con colore invalido. | `ui/tabella_pezzi.py:132`, `:179` |
| Anteprime rich text conservavano colori del tema precedente; il cambio tema aggiornava solo movimenti e altre parti. | `ui/scheda_scarico.py:188`, `:203`; `ui/finestra_principale.py:754` |
| Colore testo chip scelto con soglia di luminosità non WCAG e due colori fissi. | `ui/scheda_scarico.py:212` |
| Helper badge con bianco fisso, anche su colori chiari; non risultavano chiamate correnti all'helper. | `ui/tema.py:509`, `:513` |
| Veli delle pillole trasparenti: contrasto dipendente dalla selezione sottostante. | `ui/componenti.py:151`, `:168` |
| Palette web diversa e ripetuta, camera sempre scura e pulsanti disabilitati con opacità ridotta. | `web/static/telefono.css:1`, `:63`, `:66` e copie in `public/`, `web/vercel/public/` |
| Bianco per miniature, QR e fogli tecnici. | `ui/visualizzatore_immagine.py:26`; `ui/collega_telefono.py:201` |

L'ultimo punto è intenzionale per la leggibilità del disegno e la decodifica QR. I colori materiali, il neutro `#9aa0a8` del registro e il grigio iniziale del selettore colore (`ui/gestione_colori.py:101`) rappresentano materiali/valori del selettore, non testi o superfici del tema.

## Passo B — piano adottato

| Richiesta | Soluzione adottata | Rischio / tutela dei dati |
|---|---|---|
| Togliere Profili dal menu | Rimuovere solo la pagina dalla lista navigabile; editor conservato in un dialogo aperto da Inventario → Gestisci profili. | Nessuna anagrafica eliminata; funzione interna `scheda_profilo` conservata. |
| Immagini in Inventario | Miniatura sulla riga e anteprima nel pannello dettagli del pezzo. Immagine cliccabile e pulsante di ingrandimento. Pannello con scorrimento verticale. | Stesso risolutore, stessa cartella, nessuna copia PNG per questa funzione. Il CSV originale è letto anche per distinguere le anomalie. |
| Ricerca Carico/Scarico | Componente indipendente in ciascuna colonna destra, codice/descrizione senza distinzione maiuscole, ritardo 180 ms e 50 risultati per pagina. In Scarico elenco dei singoli pezzi disponibili con misura/colore/vassoio. | Solo SELECT fino alla conferma dell'operazione esistente. Filtro che esclude la selezione svuota i dati precompilati, evitando un barcode invisibile ancora pronto allo scarico. |
| Peso | Togliere tutti i campi e output visibili, conservare colonna e valori già presenti. Default tecnico positivo `1.0000` solo per nuovi profili che devono rispettare il vincolo storico. Nuovo Excel formato 5 senza colonna, lettura formati 1–4. | Nessuna migrazione distruttiva. Il default non è una misura reale. Un nuovo XLSX non conserva questo metadato omesso: per archiviarlo integralmente serve il dump PostgreSQL. |
| Contrasti | Fonte unica Qt, generazione palette CSS, conversione rgba corretta, aggiornamento rich text al cambio tema, pillole opache con contrasto stabile e hover adeguato al testo bianco. | Nessun effetto sui dati del magazzino o sui colori materiali assegnati dall'utente. |

Palette finale: invariati tutti i token iniziali salvo **accento scuro `#7aa4ff`**, relativo velo `rgba(122,164,255,36)`, **pericolo chiaro `#b92e29`**. Aggiunti nella stessa definizione centrale: `sfondo_disegno=#ffffff`, `inchiostro_chiaro=#ffffff`, `inchiostro_scuro=#161a22`. I valori sono in `ui/tema.py:125`; l'HTML li riceve da `tools/genera_temi.py:1`.

## Passo C — implementazione e collocazione delle funzioni

### Navigazione, immagini e ricerca

- **VERIFICATO:** nessuna voce Profili nelle schede superiori (`ui/finestra_principale.py:392`). L'editor è ancora costruibile attraverso l'API interna, senza creare una tab fuori elenco. Il dialogo di gestione è in `ui/tabella_pezzi.py:560`.
- **VERIFICATO:** elenco/ricerca anagrafica, Nuovo profilo, modifica descrizione/lunghezza, salvataggio, import PNG, rimozione dell'associazione e zoom restano nell'editor `ui/scheda_profilo.py:50`. Non sono state eliminate funzioni di gestione. Non è stato inventato un comando di eliminazione del profilo che il codice non aveva.
- **VERIFICATO:** miniature nella colonna Profilo, anteprima del profilo collegato al barcode selezionato e pannello dettagli autoaperto alla selezione (`ui/tabella_pezzi.py:637`, `ui/visualizzatore_immagine.py:43`). Il pannello può essere nascosto con Nascondi dettagli. Il clic sulla sezione apre il visualizzatore esistente con zoom/panoramica.
- **VERIFICATO:** senza PNG appare il segnaposto; codice in CSV senza PNG produce il messaggio specifico; PNG non indicizzato resta utilizzabile e viene segnalato come tale. Indice assente/illeggibile segnalato senza nascondere un PNG valido (`services/immagini.py:55`, `:63`). I file originali e il CSV non sono stati modificati.
- **VERIFICATO:** anche un secondo clic sulla stessa riga ricompila il form dopo il suo azzeramento; quattro test dedicati (Carico/Scarico × due temi) superati. Ricerca separata per scheda (`ui/ricerca_profili.py:30`, `:32`, `:108`), integrazione Carico (`ui/scheda_carico.py:187`, `:225`) e Scarico (`ui/scheda_scarico.py:149`, `:251`). Nessun filtro dell'Inventario o dell'altra scheda viene modificato. Gli errori DB svuotano la selezione e producono un messaggio comprensibile.

### Punti in cui il peso è stato rimosso

| Punto | Rimozione effettuata / evidenza corrente |
|---|---|
| Inventario: intestazione e celle | Eliminata fisicamente dalla struttura della tabella la colonna prima nascosta; riadattati indici di Vassoio/Stato barcode (`ui/tabella_pezzi.py:74`). |
| Inventario: riepilogo | Rimossi KPI e animazione del totale; rimangono tre KPI (`ui/tabella_pezzi.py:270`). |
| Inventario: pannello e aiuto | Rimossi peso unitario/totale, testo guida e formatter UI non più usato (`ui/tabella_pezzi.py`, sezione DETTAGLI). |
| Editor Profili | Tolti colonna nascosta, widget, etichetta, compilazione, richiesta obbligatoria e argomento nei salvataggi. Aggiornare un profilo non riscrive il valore storico (`ui/scheda_profilo.py:44`, metodo `salva_profilo`). |
| Telefono HTML | Rimosso input `nuovo-peso` dal template locale, dai due documenti pubblici e dall'anteprima (`web/templates/scansione.html:31`, `public/index.html:31`, `web/vercel/public/index.html:31`, `anteprima-telefono.html`). |
| Telefono JavaScript | Tolti peso dal dettaglio, validazione del campo e proprietà nel payload, in tutte e tre le copie (`web/static/scansione.js:247`, `:256`; copie `public/static/`, `web/vercel/public/static/`). |
| API | Nessuna proprietà obbligatoria del nuovo profilo, nessuna esposizione nella lista; un payload storico con quel campo aggiuntivo lo ignora (`web/routes_barcode.py:61`, `:155`). Test HTTP di creazione senza peso superati. |
| Excel multi-foglio | Foglio Profili del formato 5 senza colonna; formati precedenti leggibili (`reports/backup_excel.py:39`, `:74`, `:421`). I vecchi XLSX possono conservare il metadato nel restore, mentre il nuovo formato ne usa il default tecnico per i profili inseriti. |
| CSV/ODS | Output già senza peso mantenuti; il validatore V2 ora ignora colonne storiche peso anche non numeriche e continua a rifiutare righe malformate (`reports/formato_v2.py:188`, `:193`; `reports/ods_v2.py:102`). L'import CSV legacy già leggeva solo colonne note. |
| Messaggi e documentazione attuali | Istruzioni per nuovi profili rinviate a Inventario → Gestisci profili; README aggiornato e mockup senza peso (`ui/messaggi.py`, `reports/importa_ods.py`, `README.md:6`, `magazzino-mockup-grande.html:1`). |

**Dati conservati:** `domain/profilo.py:28` conserva la colonna, `services/anagrafica.py` mantiene gli argomenti storici per non rompere chiamanti esistenti; i calcoli interni in `services/consultazione.py` e il vincolo storico in `migrations/008_vincoli_nuove_scritture.sql:3` restano per compatibilità, senza esposizione nella UI. I test verificano esplicitamente che un peso storico `2.5000` resti identico dopo una modifica anagrafica. Non è stato eseguito alcun UPDATE massivo o DROP.

### Contrasto: misure prima/dopo

Rapporti calcolati sulla luminanza relativa sRGB, con linearizzazione dei canali e formula `(Lchiaro+0.05)/(Lscuro+0.05)`: `ui/tema.py:271`. Sono misure sui colori del codice, non letture dei pixel di una vecchia schermata. Il caso rich text è la combinazione teorica prodotta dal cambio tema senza aggiornamento.

| Coppia / correzione | Prima | Dopo | Evidenza |
|---|---:|---:|---|
| Accento scuro su carta2 | 4,58:1 | 5,87:1 | `ui/tema.py:167` |
| Accento scuro sul proprio velo composto sulla carta | **4,13:1** | **5,08:1** | `ui/tema.py`, accento e accento_vel |
| Pericolo chiaro sullo sfondo | **4,48:1** | **5,09:1** | `ui/tema.py:196` |
| Vecchio `testo_dim` scuro rimasto su carta chiara | **2,54:1** | **6,35:1** | `ui/finestra_principale.py:754`, `:759`; `aggiorna_tema` delle schede |
| Testo bianco nell'helper badge su pericolo scuro | **2,66:1** | **6,54:1** | `ui/tema.py`, `qss_badge`; helper non usato dalla navigazione corrente |
| Hover pulsante primario chiaro / bianco | 4,71:1 | 6,02:1 | `ui/tema.py:290` |
| Pillola pericolo: fondo proprio composto sulla carta, indipendente dalla selezione | Prima dipendeva dalla riga sottostante | 5,19:1 chiaro; 4,82:1 scuro | `ui/componenti.py`, `_colori`; `ui/tema.py:276` |
| Delegati selezionati con stringhe rgba | Colore `QColor` invalido | Conversione valida, alfa Qt preservato | `ui/tabella_pezzi.py`, `DelegatoProfilo.paint`, `DelegatoColore.paint` |

**VERIFICATO:** tutte le 100 coppie finali considerate superano 4,5:1 per i testi e 3:1 per i bordi dei controlli; comprendono superfici, testi secondari, veli, pulsanti normali/hover e bordi (`docs/CONTRASTI_UI_20261106.json:1`). Test aggiuntivi verificano le pillole anche sulle righe selezionate. Questo non certifica ogni possibile combinazione di dati, icone e colori materiali personalizzati.

Il tema web usa la stessa fonte generata. La camera e i pulsanti disabilitati ora usano token, evitando pannelli scuri fissi nel tema chiaro. I disegni restano su bianco intenzionalmente; QR e barcode conservano il proprio contrasto necessario alla scansione.

### File modificati e motivo

| File | Motivo |
|---|---|
| `magazzino_profili/__init__.py` | Versione unica 2.4.3 per distinguere la build. |
| `magazzino_profili/ui/finestra_principale.py` | Navigazione senza Profili; conservazione della fabbrica interna; refresh completo al cambio tema. |
| `magazzino_profili/ui/tabella_pezzi.py` | Editor contestuale, immagini/miniature, peso rimosso, selezione rgba e pannello senza sovrapposizioni o larghezza eccessiva. |
| `magazzino_profili/ui/scheda_profilo.py` | Rimozione peso dall'editor senza eliminare le funzioni anagrafiche/immagini. |
| `magazzino_profili/ui/scheda_carico.py` | Ricerca, selezione, dati del profilo, area destra scorrevole e refresh tema. |
| `magazzino_profili/ui/scheda_scarico.py` | Ricerca di pezzi disponibili, misura/vassoio/barcode, refresh tema, testo chip con contrasto calcolato. |
| `magazzino_profili/ui/ricerca_profili.py` (nuovo) | Ricerca e paginazione locali alle schede, gestione selezione ed errori DB. |
| `magazzino_profili/ui/visualizzatore_immagine.py` | Anteprima cliccabile riusabile e sfondo tecnico centralizzato. |
| `magazzino_profili/ui/tema.py` | Palette, contrasto WCAG, composizione opaca, badge/hover e controlli adattati al tema. |
| `magazzino_profili/ui/componenti.py` | Fondo delle pillole stabile anche sulla selezione. |
| `magazzino_profili/ui/messaggi.py` | Nuova collocazione dell'anagrafica nei messaggi di errore. |
| `magazzino_profili/services/immagini.py` | Diagnostica CSV/PNG senza cambiare il risolutore o copiare immagini. |
| `magazzino_profili/domain/profilo.py` | Default interno del dato storico, senza modifica dello schema DB. |
| `magazzino_profili/services/anagrafica.py` | Compatibilità dei chiamanti e creazione senza richiesta peso. |
| `magazzino_profili/web/routes_barcode.py` | DTO e risposte senza peso; default tecnico per nuove anagrafiche. |
| `magazzino_profili/reports/backup_excel.py` | Formato 5, compatibilità 1–4 e correzione errore su lunghezza Excel non valida. |
| `magazzino_profili/reports/formato_v2.py` | Ignorare le colonne peso storiche mantenendo le altre validazioni. |
| `magazzino_profili/reports/ods_v2.py` | Intestazioni ODS con colonne storiche ignorabili e larghezza gestita correttamente. |
| `magazzino_profili/reports/importa_ods.py` | Messaggio utente senza requisito peso e nuova collocazione editor. |
| `magazzino_profili/web/templates/scansione.html` | Form telefono senza peso. |
| `magazzino_profili/web/static/scansione.js` | Dettagli e invii telefono senza peso. |
| `magazzino_profili/web/static/telefono.css` | Token condivisi, camera e stati disabilitati leggibili. |
| `magazzino_profili/web/static/palette.css` (nuovo) | Output generato dalla palette Qt. |
| `public/index.html`, `public/static/scansione.js`, `public/static/telefono.css`, `public/static/palette.css` | Stesse modifiche nella distribuzione telefono pubblicabile. |
| `magazzino_profili/web/vercel/public/index.html`, `magazzino_profili/web/vercel/public/static/scansione.js`, `magazzino_profili/web/vercel/public/static/telefono.css`, `magazzino_profili/web/vercel/public/static/palette.css` | Stesse modifiche nella seconda distribuzione Vercel del progetto. |
| `anteprima-telefono.html` | Anteprima HTML senza peso, CSS rigenerato dalla fonte condivisa. |
| `magazzino-mockup-grande.html` (nuovo) | Mockup ricostruito con navigazione, immagini, editor, ricerca e temi aggiornati. |
| `docs/palette-mockup.css` (nuovo) | Token generati per il mockup. |
| `tools/genera_temi.py` (nuovo) | Generazione ripetibile palette CSS e anteprima mobile. |
| `tools/verifica_contrasti.py` (nuovo) | Misure ripetibili e controllo delle soglie. |
| `tools/cattura_ui_novembre.py` (nuovo) | Screenshot su SQLite e preferenze temporanee, font caricati solo nel processo di verifica. |
| `Avvia_Magazzino_2.4.3.cmd` (nuovo) | Avvia la nuova build con il config del progetto, senza modificare l'ambiente Windows globale. |
| `README.md` | Navigazione attuale, uso, compatibilità, build e limiti del mockup. |
| Test `test_ui_novembre.py` (nuovo), `test_ui_smoke.py`, `test_ui_vassoio_stati.py`, `test_commesse_multiple.py`, `test_scheda_profilo_catalogo.py` | Nuove regressioni e contratti UI adeguati alle richieste. |
| Test `test_backup_excel.py`, `test_correzioni_dati.py`, `test_sicurezza_fase14.py`, `test_input_numerici.py` | Contratti formato/navigazione aggiornati; i modali inattesi nei test numerici producono un fallimento invece di bloccare la suite. |
| Test `test_correzioni_telefono.py`, `tests/js/scansione.test.mjs` | Creazione di nuova anagrafica senza peso e compatibilità del payload storico. |
| Questo report, `docs/ESITI_UI_20261106.json`, `docs/CONTRASTI_UI_20261106.json`, `docs/VERIFICA_BUILD_UI_20261106.json`, `docs/verifica-ui-20261106/*` | Evidenze e risultati della fase. |

I test Python elencati si trovano in `magazzino_profili/tests/`; il test JavaScript è `magazzino_profili/tests/js/scansione.test.mjs`. L'elenco con tutti i percorsi espliciti e il motivo è anche in `docs/FILE_UI_20261106.json:1`.

Nessun file o cartella preesistente è stato eliminato. `dist/UI-2.4.3-20261106-finale/` contiene solo nuovi output di build, log e file intermedi. Le vecchie installazioni, release, cataloghi PNG e documenti storici restano presenti.

## Passo D — verifiche e uso della build

| Verifica | Esito | Evidenza / limite |
|---|---|---|
| Test Python di UI, dominio interessato, import/export, backup e API | **SUPERATO: 321** | Copia esterna e SQLite; esiti individuali nel JSON. Il loopback è stato autorizzato per superare un blocco del sandbox su `asyncio.socketpair`, non modificando il codice dell'app per aggirarlo. |
| Test PostgreSQL dedicato | **NON ESEGUITO: 35** | Variabili DB di test non impostate. I database operativi non sono stati usati come alternativa. |
| Test JavaScript telefono | **SUPERATO: 18** | Comprendono nuovo profilo senza campo peso, idempotenza, retry e collegamento al PC; rete simulata. |
| Contrasto numerico | **SUPERATO: 100 coppie** | Testo 4,5:1 e controlli 3:1; dati JSON riproducibili. |
| Qt Inventario/Carico/Scarico/editor, due temi | **SUPERATO su dati sintetici** | Dieci screenshot; 1366×768 per la finestra e 1280×740 per l'editor. Controllati anche i due segnaposto senza immagine. |
| Mockup: ID univoci, sintassi JavaScript, assenza campo peso nei form HTML | **SUPERATO** | Parsing statico e `node --check`; non equivale a un confronto visuale browser. |
| Confronto visivo con HTML originale approvato | **BLOCCATO** | Originale non reperito; apertura locale browser rifiutata dalla policy `file://`. Nessun aggiramento eseguito. |
| Build standalone Windows | **SUPERATO** | PyInstaller, log `dist/UI-2.4.3-20261106-finale/compilazione.log`; moduli e risorse controllati in `docs/VERIFICA_BUILD_UI_20261106.json:1`. Nessuna configurazione operativa inclusa. |
| Avvio eseguibile secondario | **SUPERATO limitatamente all'avvio** | Finestra Windows `Magazzino Profili 2.4.3 · PC secondario` osservata. Ambiente app temporaneo; istanza di prova chiusa al termine. |
| Verifica grafica interattiva eseguibile nei due temi | **BLOCCATO** | Approvazione computer-use scaduta prima di acquisire la finestra. Non sostituita con affermazioni non verificate. |
| Avvio principale sul magazzino reale | **NON ESEGUITO** | Nessuna migrazione o scrittura sul DB operativo in questa fase. |
| Telefono reale e rendering web nei due temi | **NON ESEGUITO** | API/JavaScript/palette verificati; nessuna prova hardware o visuale web completata. |

I primi tentativi hanno evidenziato test con aspettative della vecchia navigazione/colonna nascosta, un errore di validazione Excel poi corretto e due moduli di test non copiati nell'ambiente temporaneo. Sono stati sistemati e rieseguiti. I risultati finali aggregati riportano **zero test falliti**; i tentativi interrotti dal blocco socket del sandbox non sono conteggiati come superati.

Screenshot:

- Inventario: `docs/verifica-ui-20261106/inventario-chiaro.png`, `inventario-scuro.png`.
- Profilo privo di PNG: `inventario-senza-immagine-chiaro.png`, `inventario-senza-immagine-scuro.png`.
- Carico: `carico-chiaro.png`, `carico-scuro.png`.
- Scarico: `scarico-chiaro.png`, `scarico-scuro.png`.
- Editor: `gestione-profili-chiaro.png`, `gestione-profili-scuro.png`.

**Avvio locale:** dalla radice del progetto aprire `Avvia_Magazzino_2.4.3.cmd`. Il launcher imposta `MAGAZZINO_CONFIG` soltanto per il processo figlio e legge il config esistente, senza copiarne la password nell'eseguibile. I vecchi collegamenti Desktop 2.4.2 restano riferiti alla vecchia versione. L'avvio principale applica i normali controlli di backup/migrazione già presenti: questa fase non ne certifica il funzionamento sul database operativo.

**Altri PC:** la cartella `MagazzinoProfili-2.4.3` è standalone con `_internal` e catalogo. Trasferirla intera; scegliere il config adatto alla postazione. Il `.cmd` locale è specifico della posizione di questo progetto. Non è stato pubblicato un aggiornamento online in questa fase.

## Problemi aperti e verifica ancora necessaria

1. Recuperare l'originale HTML approvato, se disponibile con un nome/percorso diverso; confrontarlo con la ricostruzione. Il nuovo file dichiara il limite nel footer.
2. Completare il confronto visuale browser e la prova della UI telefono chiara/scura. Le modifiche web non vengono dichiarate verificate graficamente.
3. Verificare l'eseguibile principale con una copia di PostgreSQL dedicata e, successivamente, l'avvio sul PC operativo con il suo backup protetto. Non sono stati alterati i problemi operativi precedenti per svolgere test UI.
4. Il nuovo XLSX volutamente non archivia il vecchio metadato peso: per un ripristino che includa anche quel dato conservare un dump PostgreSQL o un vecchio backup completo che lo contenga. Nessuna perdita del valore già presente nel database è avvenuta durante questo intervento.

Non è necessario approvare una cancellazione del campo database: la soluzione implementata lo conserva e non introduce una migrazione distruttiva.

Controlli conclusivi: sintassi Python e JavaScript del mockup valida; build locale della pagina telefono superata sulla copia esterna, incluso `palette.css`; copie CSS generate coerenti. `git diff --check` senza errori: soltanto avvisi di normalizzazione LF/CRLF già configurata. L’istanza di prova dell’eseguibile finale è stata chiusa; nessun processo di prova è lasciato in esecuzione.
