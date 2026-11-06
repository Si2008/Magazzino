# Commesse e lista di prelievo — versione 2.3.0

## Uso

1. Chiudere la vecchia versione, anche dall’area di notifica, e aprire `C:/Users/Simone/Desktop/MagazzinoProfili-2.3.0.exe`.
2. Aprire **Commesse → Carica commessa PDF** e selezionare la lista materiali.
3. In **Misure richieste** controllare profilo, misura in millimetri e quantità. Sono ammessi i decimali, per esempio **632,8 mm**. Le righe si possono aggiungere, correggere o eliminare.
4. Associare la finitura del documento al colore del magazzino. Se non coincide esattamente, la scelta rimane vuota. Una scelta esplicita si applica alle altre righe con la stessa finitura del documento. Il programma non equipara automaticamente finiture diverse che condividono il numero RAL.
5. Lasciare attivo **Usa anche pezzi più lunghi e spezzoni** per coprire più misure con lo stesso pezzo disponibile. Disattivandolo si cercano soltanto pezzi della misura esatta.
6. Confermare la verifica e premere **Trova pezzi e vassoi**. In **Pezzi e vassoi** sono mostrati, nell’ordine: **profilo, colore, misura del pezzo da prendere, vassoio, barcode** e le misure della commessa coperte da quel pezzo.
7. Scegliere **Mancanti** per vedere ciò che non è disponibile. **Salva lista CSV** esporta prelievi e mancanti, con codifica UTF-8 con BOM e separatore punto e virgola.

**Esempio:** la riga «AZ4557 | RAL9010SOFT | 6500 mm | vassoio 2 | MP-…» indica di prendere proprio quel pezzo da **6500 mm**, identificato dal suo barcode, nel vassoio **2**. La misura da prendere è quella del pezzo disponibile, distinta dalle misure richieste dalla commessa.

Come richiesto, la funzione non chiede né considera specifiche di taglio, lama o rifilo. Sceglie in base alle sole misure nominali della commessa e del magazzino. Non modifica o scarica automaticamente il materiale.

La commessa e il piano restano nella sessione aperta; non è stata aggiunta una cronologia persistente delle commesse. Il PDF originale resta nella sua posizione. La lista CSV è salvata soltanto nella destinazione scelta dall’utente. Il modulo non carica il PDF su Vercel o altri servizi.

Evidenze: `magazzino_profili/ui/scheda_commesse.py:20`, funzioni `_colore_scelto`, `_calcola`, `_mostra_risultati` e `_esporta` dello stesso file; `magazzino_profili/services/commesse.py:82`.

## Regole di scelta

**VERIFICATO:** analisi in sola lettura, senza prenotazioni o movimenti impliciti. Due operatori possono ricevere proposte sullo stesso pezzo: ricalcolare e verificare la disponibilità prima del prelievo.

**VERIFICATO:** vengono scelti pezzi unitari Caricato, con quantità positiva e non eliminati logicamente. Profilo e colore devono coincidere con quelli confermati nelle richieste. Le giacenze aggregate vengono escluse e segnalate: il loro barcode non identifica un singolo pezzo fisico. I pezzi corti con barcode sono candidati come le barre lunghe.

**VERIFICATO:** gli spezzoni della tabella storica sono considerati solo se non utilizzati e con pezzo di origine a saldo zero. Non hanno un barcode proprio né un vassoio aggiornato: sono indicati come **SPEZZONE #ID, vassoio Da confermare**, con i dati dell’origine nelle note e nei suggerimenti. Non si attribuisce loro una posizione attuale non dimostrata. L’opzione per includerli è disattivabile.

**VERIFICATO:** le richieste sono ordinate dalla più lunga. Si utilizza il residuo nominale compatibile più piccolo; quando serve un altro pezzo si sceglie il candidato compatibile più corto. Lo stesso identificativo fisico compare una sola volta nella lista, anche quando copre più misure della commessa. Il calcolo usa decimi di millimetro interi. Il residuo serve internamente alla scelta e non viene presentato come specifica di lavorazione.

**Limite:** è una selezione euristica, non una garanzia dell’ottimo matematico. La funzione riguarda esclusivamente il prelievo del materiale. La lavorazione resta estranea al calcolo, secondo l’indicazione dell’utente.

Evidenze: `magazzino_profili/services/commesse.py:17`, `magazzino_profili/services/commesse.py:82`; query in `calcola_prelievo` nello stesso file.

## Lettura del PDF

**VERIFICATO:** l’adattatore supporta la **Lista ottimizzata Blitz** del documento fornito. Legge testo e diagrammi; per le misure raster usa l’OCR locale di Windows 10/11, senza servizi cloud o installazioni globali. Rimuove i bordi grafici dalle fasce delle misure e controlla che il numero di diagrammi coincida con il numero di barre dichiarato per profilo, anche a cavallo di due pagine. I diagrammi ripetuti rappresentano barre distinte e vengono conteggiati. Le quantità dell’abaco non sono moltiplicate nuovamente.

**VERIFICATO:** se mancano barre rispetto al totale dichiarato, l’importazione si interrompe. Se una misura non è affidabile oppure manca l’OCR, viene richiesta la barra originale intera, con nota esplicita. Si possono inserire le misure corrette manualmente. La conferma umana resta necessaria: la coerenza della somma non dimostra l’esattezza di ogni cifra riconosciuta.

**Limiti di formato:** altri modelli PDF, PDF interamente scannerizzati e documenti protetti non sono supportati automaticamente da questo adattatore. Per questi casi è disponibile l’inserimento manuale. L’assenza della lingua OCR o una restrizione di Windows viene mostrata esplicitamente. Fonte Microsoft: [motore OCR e lingue locali](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrengine.trycreatefromuserprofilelanguages?view=winrt-28000).

Evidenze: `magazzino_profili/services/lettura_commessa.py:24`, `magazzino_profili/services/lettura_commessa.py:49`, `magazzino_profili/services/lettura_commessa.py:68`; controlli sulle quantità e gestione delle misure incerte nella seconda metà dello stesso file.

## Verifiche

| Prova | Stato | Risultato |
|---|---|---|
| PDF allegato, lettura locale completa | VERIFICATO | 35 barre originali, 8 codici, 21 combinazioni di misura e 151 pezzi richiesti; nessuna barra rimasta in ripiego. Lettura 1,426 s su questo PC. Non equivale alla certificazione di ogni cifra OCR. |
| Nuovi test commesse | VERIFICATO | 24 superati: misure decimali, barcode univoci nella lista, disponibilità, misure nominali, più richieste sullo stesso pezzo, esclusione Scaricato/eliminati, spezzoni storici, continuazione pagina, PDF incompleto, OCR assente, conferma, colori, paginazione e CSV. |
| Regressioni collegate | VERIFICATO | Altri 41 test superati in otto moduli. Totale finale: **65 superati, 0 falliti, 0 saltati**, per modulo in processi separati sulla copia temporanea. Non è una nuova esecuzione dell’intera suite 2.2.0. |
| Eseguibile finale | VERIFICATO dopo la prova di consegna | Avvio desktop e API mobile su PostgreSQL sintetico, launcher, tre barcode individuali, idempotenza, immagini, scarico e arresto regolare. Moduli commesse e script OCR controllati nella distribuzione. La lettura PDF è stata provata sul sorgente allineato alla build, non mediante click nella finestra dell’eseguibile. Numeri nel file degli esiti. |
| Interfaccia | VERIFICATO | Schermate chiare/scure a 1280×800 con inventario sintetico. Liste paginate a 100 righe. Misura da prendere e vassoio sono colonne distinte e visibili. |
| Calcolo puro: 10.000 richieste e 50.000 candidati | VERIFICATO | 0,064 s su questo PC, esclusi SQL, OCR e rendering. Non è una misura su hardware con 4 GB. |
| Magazzino operativo | NON VERIFICATO intenzionalmente | Nessun accesso ai dati operativi, nessuna migrazione e nessuna modifica a `config.toml`. Serve verificare fisicamente la corrispondenza tra vassoi registrati e materiale. |
| PC vecchio e restrizioni OCR aziendali | NON VERIFICABILE qui | Serve la prova sul dispositivo destinato all’uso. |

Esiti e hash delle evidenze: `docs/ESITI_COMMESSE_2.3.0.json:1`. Test: `magazzino_profili/tests/test_commesse.py:1`. Schermate con dati sintetici: `docs/COMMESSE_2.3.0_MISURE.png`, `docs/COMMESSE_2.3.0_PRELIEVO.png`, `docs/COMMESSE_2.3.0_SCURO.png`.

Trasparenza sulle verifiche intermedie: un test UI aveva ancora l’aspettativa delle cinque vecchie schede ed è stato aggiornato alle sei schede effettive. Un’esecuzione cumulativa di più moduli Qt ha fallito il controllo del registro colori; gli stessi moduli passano separatamente. **IPOTESI:** interferenza dei registri/segnali Qt globali tra finestre di test; la suite completa nello stesso processo non è dichiarata superata (`magazzino_profili/ui/registro_colori.py:78`). Due invocazioni iniziali del runner dal repository hanno completato i casi sintetici ma non hanno potuto scrivere l’XML sul Desktop; le prove finali documentate provengono dalla copia esterna con percorsi corretti. Nessuna ha usato il database operativo.

## Distribuzione

Nuovi moduli: `services/commesse.py` (scelta e query), `services/lettura_commessa.py` (PDF), `services/ocr_commessa.ps1` (OCR locale), `ui/scheda_commesse.py` (interfaccia), `tests/test_commesse.py` (regressioni). Integrazione nella finestra con caricamento differito: `magazzino_profili/ui/finestra_principale.py:388`. Script OCR incluso dalla specifica di compilazione. Nessuna nuova dipendenza Python né modifica dello schema.

Lasciare la cartella `MagazzinoProfili-2.3.0` accanto al lanciatore sul Desktop. PostgreSQL e la configurazione già esistente restano necessari. Il PDF del cliente non viene incorporato nella distribuzione. La documentazione 2.2.0 resta valida per telefono, immagini, export e backup; aprire la nuova versione dal lanciatore **2.3.0**.
