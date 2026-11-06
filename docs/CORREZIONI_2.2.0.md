# Magazzino Profili 2.2.0 — correzioni e verifica

Data: 5 novembre 2026. Questa relazione integra l'analisi iniziale; non significa che hardware, dati operativi e ogni possibile difetto siano stati verificati.

## Risultato delle richieste

| Richiesta | Stato | Evidenza e verifica |
|---|---|---|
| Immagini visibili nell'elenco Profili | VERIFICATO | Miniature 48×48 accanto al codice: `magazzino_profili/ui/scheda_profilo.py:106`, `magazzino_profili/ui/scheda_profilo.py:251`. Provate 211 miniature su anagrafiche sintetiche e PNG del catalogo, senza modificare il database operativo. |
| Anteprima della sezione subito visibile e intera | VERIFICATO | Anteprima spostata sopra i campi, altezza 200; ridimensionamento sulle dimensioni effettive del contenitore: `magazzino_profili/ui/scheda_profilo.py:176`, `magazzino_profili/ui/scheda_profilo.py:308`. Test contro il taglio dell'immagine e schermata `docs/PROFILI_2.2.0.png`. |
| Associazione automatica ai nuovi pezzi dello stesso profilo | VERIFICATO sul catalogo disponibile | Risoluzione per codice, indipendente dall'assegnazione manuale al singolo pezzo: `magazzino_profili/services/catalogo_immagini.py:147`. La distribuzione comprende i 211 PNG. Mappa e checksum: `docs/CATALOGO_ASSOCIAZIONI.csv:1`. |
| Togliere descrizione e peso dalle tabelle | VERIFICATO | Colonne nascoste in Profili e peso nascosto in Inventario; tolta la sottodescrizione del delegato: `magazzino_profili/ui/scheda_profilo.py:99`, `magazzino_profili/ui/tabella_pezzi.py:1148`. I dati anagrafici salvati restano disponibili. |
| Togliere descrizione e peso da Excel/ODS | VERIFICATO per gli export inventario | Intestazioni Excel a sei colonne: `magazzino_profili/reports/export_excel.py:18`; ODS senza Descrizione e senza campo peso: `magazzino_profili/reports/ods_v2.py:30`. Il backup tecnico completo conserva i campi necessari al ripristino: non è l'export inventario. |
| Un foglio Excel/ODS per colore | VERIFICATO | Raggruppamento per codice colore, distinto anche a parità di nome visualizzato: `magazzino_profili/reports/export_excel.py:58`, `magazzino_profili/reports/ods_v2.py:65`. Nomi validi, collisioni e limite 31 caratteri: `magazzino_profili/reports/fogli_colore.py:5`. Inventario vuoto: un foglio con intestazioni. |
| Reimportare ODS con più fogli | VERIFICATO | Lettura di tutti i fogli e rifiuto delle intestazioni incoerenti prima dell'importazione: `magazzino_profili/reports/ods_v2.py:85`. Test di andata/ritorno e duplicati: `magazzino_profili/tests/test_export_colori.py:1`. |
| Cambiare la tonalità | VERIFICATO | Pulsante **Modifica tonalità** accanto alle schede colore: `magazzino_profili/ui/tabella_pezzi.py:237`. Selezionare un colore e premere il pulsante; nella scheda Tutti apre la gestione completa. Salvataggio HEX e aggiornamento delle viste: `magazzino_profili/ui/gestione_colori.py:66`. Corretto l'uso errato di `QColor.isNull()` con `isValid()`: `magazzino_profili/ui/gestione_colori.py:101`. Annullare non salva. |
| Pagina telefono pubblicata e collegata al PC | VERIFICATO con dati inventati | [Pagina Vercel](https://magazzino-profili-telefono.vercel.app). QR con identificativo del PC: `magazzino_profili/ui/finestra_principale.py:500`. Collegamento in uscita: `magazzino_profili/ui/ponte_vercel.py:19`. Nessuna porta del PC pubblicata su Internet. |
| Accesso senza login e barcode individuali | VERIFICATO nelle prove automatiche e remote | Prova pubblica: creazione di due seriali, ripetizione idempotente, scarico di un solo pezzo e PNG sintetica. Prova dell'eseguibile: tre seriali, pagina telefono, immagini, scarico e avvio desktop. Evidenze allegate nella cartella Documentazione della distribuzione. |

## Collegamento Vercel

**VERIFICATO:** il PC avvia il servizio telefono su loopback, con porta locale dedicata (`magazzino_profili/ui/server_telefono.py:41`), e legge una coda privata Vercel tramite HTTPS. La funzione pubblica inoltra richieste e risposte; il database autorevole resta sul PC. **Informazioni dei pezzi e immagini richieste transitano e possono essere memorizzate temporaneamente nello storage privato**, non soltanto nel browser (`magazzino_profili/web/vercel/api/ponte.mjs:14`). Le credenziali dello storage sono nell'ambiente Vercel e non nel QR o nell'eseguibile.

**VERIFICATO:** il collegamento non applica autenticazione utente, come richiesto. Chi possiede il QR può eseguire le operazioni offerte dalla pagina; l'identificativo serve a indirizzare il PC. L'assenza di login è una scelta funzionale, non una protezione contro l'accesso di terzi. L'API applica una lista di percorsi consentiti e limiti alle dimensioni (`magazzino_profili/services/percorsi_remoti.py:1`, `magazzino_profili/web/vercel/api/ponte.mjs:6`).

**VERIFICATO:** le richieste hanno validità di 60 secondi; il PC scarta quelle già scadute prima di eseguirle (`magazzino_profili/ui/ponte_vercel.py:27`). Gli ID delle operazioni sono conservati nei tentativi ripetuti, per evitare movimenti doppi (`magazzino_profili/web/static/scansione.js:172`). Le risposte consumate e le richieste elaborate vengono eliminate; la pulizia dei residui più vecchi di cinque minuti è opportunistica e programmata ogni giorno, con massimo 1.000 oggetti per passaggio. Non è una garanzia di cancellazione entro cinque minuti (`magazzino_profili/web/vercel/api/ponte.mjs:28`, `tools/prepara_telefono_vercel.py:1`).

**VERIFICATO:** polling ogni due secondi su un lavoro separato dal thread grafico; arresto dopo due minuti senza richieste. Per riattivare usare **Collega telefono** (`magazzino_profili/ui/ponte_vercel.py:55`, `magazzino_profili/ui/ponte_vercel.py:64`). PC acceso e Internet su entrambi i dispositivi sono necessari. Dopo il riavvio generare un nuovo QR.

**Limite operativo:** Vercel Functions e Blob hanno quote e costi; il polling e le letture/scritture della coda consumano operazioni. Il piano gratuito non va considerato illimitato o già validato per un turno di lavoro continuo. Non è stato attivato alcun abbonamento a pagamento. Verificare le metriche del progetto prima dell'uso continuativo. Fonti ufficiali: [storage privato](https://vercel.com/docs/vercel-blob/private-storage), [quote e prezzi](https://vercel.com/docs/vercel-blob/usage-and-pricing).

## Prove e limiti

- **VERIFICATO:** riepilogo automatico: **688 superati, 0 falliti, 0 errori, 1 saltato**. Il salto riguarda un caso esclusivo PostgreSQL nella parametrizzazione SQLite; la variante PostgreSQL è stata eseguita. Elenco e hash delle evidenze: `docs/ESITI_TEST_2.2.0.json:1`. Le prove JavaScript includono 15 scenari, contati come un test nel riepilogo pytest.
- **VERIFICATO:** ulteriori quattro test finali su tonalità, percorsi consentiti, scadenza dei lavori e QR tutti superati; nove controlli finali sulle immagini superati. Sono riesecuzioni di casi già nel totale, non nuovi test da sommare.
- **VERIFICATO:** eseguibile finale su PostgreSQL sintetico separato, servizio pronto in **1,621 secondi**; launcher, API mobile, barcode e PNG, retry senza duplicazione, scarico, backup di avvio e finestra desktop senza errori. Il tempo riguarda il servizio su questo PC, non l'avvio completo su hardware vecchio.
- **VERIFICATO:** build a cartella, lettura miniature ridimensionata e cache limitata a 256 immagini (`magazzino_profili/ui/visualizzatore_immagine.py:19`); non serve estrarre tutte le librerie a ogni avvio.
- **NON VERIFICABILE senza dispositivo:** fotocamera, lettura ottica delle etichette, permessi del browser e utilizzo effettivo tramite SIM. La prova Internet è stata effettuata con client HTTPS automatici, non con un telefono fisico.
- **NON VERIFICABILE senza prova sul PC indicato:** memoria e reattività reali su Windows 10/11 x64 con 4 GB. Le ottimizzazioni non equivalgono a una misura su quell'hardware.
- **NON VERIFICATO intenzionalmente:** lettura/modifica dei dati operativi, migrazione del magazzino reale e modifica della configurazione reale. Nessun database completo o backup operativo è stato pubblicato.
- **Limite del catalogo:** non sono state inventate immagini per codici senza PNG né corretto automaticamente il presunto refuso AZ46431. Il catalogo disponibile comprende 211 file; la corrispondenza con ogni codice effettivamente presente nel magazzino operativo resta da controllare. Per un codice mancante viene mostrato un messaggio esplicito, non un'immagine di un altro profilo (`magazzino_profili/ui/scheda_profilo.py:308`).

## Uso della consegna

Chiudere la vecchia versione, anche dall'icona nell'area di notifica, e aprire `C:/Users/Simone/Desktop/MagazzinoProfili-2.2.0.exe`. Lasciare la cartella omonima accanto al lanciatore. In Profili selezionare una riga per l'anteprima grande; le miniature sono già nell'elenco. Per il telefono usare **Collega telefono** e scansionare il QR generato dal programma; aprire soltanto l'URL senza parametri mostra le istruzioni ma non associa un PC.

Per configurazione, backup preventivo alle migrazioni e percorso dei log consultare `docs/PROVA_E_TELEFONO.md:1`. La compilazione non sostituisce PostgreSQL né esegue automaticamente la migrazione del database operativo durante la consegna.
