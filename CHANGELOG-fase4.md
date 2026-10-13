# Registro modifiche — Fase 4 (interfaccia grafica)

Patch cumulativa: `fase3-e-4-patch.patch` (Fase 3 + Fase 4, generata con
`git diff --ignore-cr-at-eol HEAD` sul commit base `a2bb74f`).
Applicazione: `git apply --ignore-whitespace fase3-e-4-patch.patch`.
Questa patch sostituisce `fase3-correzioni.patch`, che è contenuta in essa.

> Applicazione nel repository locale: branch `fase3-e-4` creato da `a2bb74f`;
> patch applicata il 2026-10-13; suite verificata su Windows (PostgreSQL 16
> locale, DB di test `magazzino_profili_test`, DB reale non toccato).

## Esiti dei test

| Esecuzione | Superati | Falliti | Saltati |
|---|---|---|---|
| Suite completa, copia di lavoro, con PostgreSQL 16 | 163 | 0 | 0 |
| Patch su copia pulita del commit base, con PostgreSQL | 163 | 0 | 0 |
| Suite senza PostgreSQL (ultima esecuzione prima della verifica finale) | 158 | 0 | 5 |

Nuovi test: `tests/test_ui_fase4.py` (11 test).
Ambiente: Linux, Python 3.12, PostgreSQL 16 locale, font Noto/Liberation.
Non eseguiti: test su Windows, font Segoe UI, interazione manuale con il mouse.

## Confronto con il mockup

Riferimento: `magazzino-mockup-grande.html`, renderizzato con Qt WebEngine
(cliccando le schede). Immagini in `fase4/`: `ref_mockup_*.png` e `app_*.png`.

| Area | Mockup | Prima | Dopo |
|---|---|---|---|
| Card KPI | Tessere con icona a tratto | Campi di input; stile propagato alle etichette | Card con icona disegnata, etichette corrette |
| Stato nella tabella | Badge colorati | Testo colorato | Badge (OK, Sotto scorta, Esaurito) |
| Schede colore | Nomi completi | Troncati (`BIANCO (…`) | Interi, scorrimento se necessario |
| Filtro ubicazione | Testo leggibile | Campo vuoto | "Tutte le ubicazioni" |
| Carico, campi | Etichette sopra i campi | Solo segnaposto | Etichette e segnaposto con esempi |
| Movimenti | Frecce verdi/rosse, tipo | Solo +/− | CARICATO (verde), SCARICATO (rosso), RETTIFICA |
| Scarico, tabella | Testo leggibile | Testo bianco su righe bianche | Colori del tema |
| Scarico, anteprima | Pezzo e giacenza | Mai riempita | Pezzo, giacenza, ubicazione |
| Avvisi | Badge e pulsante | Pulsante a tutta cella, troncato | Badge e pulsante di dimensione fissa |
| Profili | Etichette | Solo segnaposto | Etichette sopra i campi |
| Schede principali | Icone | Solo testo | Icona a tratto per scheda |

## Modifiche

- **Inventario:** card KPI corrette con icone; badge di stato; schede colore intere;
  ricerca con icona; intestazioni a sinistra; messaggio "nessun risultato con i
  filtri attuali" nel piè di pagina.
- **Carico:** etichette; movimenti CARICATO/SCARICATO/RETTIFICA; errori in italiano.
- **Scarico:** anteprima del pezzo con giacenza; conferma per lo scarico totale
  (pulsante predefinito "Annulla"); colori corretti per le righe alternate; etichette.
- **Avvisi:** badge di stato; pulsante "Dettagli" di dimensione fissa; altezza righe.
- **Profili:** etichette; conferma prima di rimuovere l'immagine (il file non
  viene cancellato, la rimozione è definitiva solo al salvataggio).
- **Messaggi (`ui/messaggi.py`):** `testo_per_utente` traduce le eccezioni in frasi
  comprensibili; `mostra_errore` registra l'errore completo in `app.log` e mostra il
  dettaglio tecnico nel riquadro "Dettagli"; `chiedi_conferma` per le operazioni pericolose.
- **Componenti:** `icona_linea` (icone disegnate con QPainter, nessuna risorsa
  esterna), `pillola` (badge di stato).
- **Tema:** regola `#CardKPI` e `QLabel { background: transparent }`.

## Bug corretti durante la verifica

- **Segnaposto "—" salvato come ubicazione (scheda Carico).** Il bug era presente
  quando il database contiene già delle ubicazioni: il campo partiva con la voce
  "—" selezionata e il carico la salvava come ubicazione reale. La Fase 1 lo aveva
  classificato come non riproducibile: la conclusione era sbagliata, perché il test
  era stato eseguito su un database senza ubicazioni. Corretto e coperto da
  `test_ubicazione_non_scelta_non_salva_il_segnaposto`.
- **Filtro ubicazione** non applicato dopo l'impostazione dell'indice predefinito:
  il filtro ora usa il testo visibile.
- **Tabella dello scarico** con testo illeggibile sulle righe alternate.

## Non fatto, e perché

- **"Collega telefono" del mockup:** non implementato. Nel programma non esiste
  un accoppiamento via QR; non ho aggiunto un pulsante senza comportamento.
- **Stati "Caricato" e "Scaricato" dei pezzi:** nel codice esistono come tipi di
  movimento, non come stati dei pezzi. La distinzione è mostrata sui movimenti.
  Gli stati per pezzo richiedono una decisione di prodotto.
- **Eliminazione manuale:** non esiste nel codice alcuna funzione di eliminazione
  di pezzi o profili; non c'era nulla da confermare.
- **Report PDF:** i suoi messaggi di errore mostrano ancora il testo tecnico.
- **Font e icone:** il mockup usa Segoe UI e icone SVG; qui Noto/Liberation e
  icone disegnate. La resa su Windows non è verificata.
- **Tema chiaro:** verificato sulla scheda Carico. Le altre schede non sono state
  fotografate in tema chiaro.
- **Risoluzioni:** catture a 1152x720, 1320x840 e 1920x1080. Le catture a 1920x1080
  non sono state riviste in dettaglio.
