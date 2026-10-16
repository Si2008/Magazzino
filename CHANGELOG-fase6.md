# Fase 6: contrasti temi, correzioni layout, animazioni di transizione

Branch: `fase6-contrasti-animazioni` (creato da `fase5-ui-mockup`, commit `76f5ca5`, working tree pulito al momento della creazione; un stash preesistente `stash@{0}` non è stato toccato).

## Test

| | superati | falliti | saltati |
|---|---|---|---|
| Baseline (prima di applicare Fase 6) | 158 | 0 | 5 |
| Dopo l'applicazione (con i nuovi test `test_animazioni.py` e `conftest.py`) | 166 | 0 | 5 |

I 5 saltati sono i test PostgreSQL (DB non disponibile in questo ambiente). Nessuna modifica ai test degli altri moduli; nessun test indebolito.

## File applicati da `fase6-file-modificati.zip`

| File | Tipo | Note |
|---|---|---|
| `magazzino_profili/ui/animazioni.py` | nuovo | Dissolvenza, transizione tema, conta-su, scuoti, toast; NO-OP se `attive()` è False; rispetta l'impostazione Windows "Mostra animazioni" (SPI_GETCLIENTAREAANIMATION) e `MAGAZZINO_NO_ANIM=1` |
| `magazzino_profili/ui/tema.py` | modificato | Nuove palette a contrasto (testo debole più chiaro/scuro, `bordo_campo` con contrasto ≥ 3:1 per WCAG 1.4.11, `pericolo`/`ok`/`avviso` ritoccati), `palette_tema()` per i widget non coperti dal QSS |
| `magazzino_profili/ui/componenti.py` | modificato | `Pillola` usa il proprio font (non più tagliata dal QSS globale), toast con dissolvenza/scossa, `bordo_campo` |
| `magazzino_profili/ui/finestra_principale.py` | modificato | Dissolvenza al cambio scheda, voce menu "Animazioni di transizione", `setPalette` al cambio tema, `toast.entra()` |
| `magazzino_profili/ui/tabella_pezzi.py` | modificato | Rendering righe con padding uniforme, elisione testo, linea di riga, `bordo_campo` |
| `magazzino_profili/ui/avvisi.py` | modificato | Barra "cresce" alla prima comparsa, niente scrollbar orizzontale, righe alte quanto il contenuto |
| `magazzino_profili/tests/conftest.py` | nuovo | (fornito nello zip) |
| `magazzino_profili/tests/test_animazioni.py` | nuovo | (fornito nello zip) |

### Differenze integrate a mano

**Nessuna.** Per ogni file esistente, il diff contro la versione dello zip (`diff --strip-trailing-cr`) conteneva solo le modifiche Fase 6 (aggiunte/sostituzioni coerenti con il contenuto già commitato di Fase 5); non erano presenti nel repository modifiche successive a Fase 5 (working tree pulito rispetto al commit `76f5ca5`), quindi ogni file è stato sovrascritto direttamente. Le terminazioni di riga (CRLF) dei file esistenti sono state preservate: le versioni dello zip sono anch'esse CRLF, identiche per riga.

### File modificati oltre allo zip

- `screenshot_fase5.py` (istruito dal task):
  - il cambio tema ora chiama `finestra._cambia_tema()` invece di `tema.alterna_tema()` (che non riapplica QSS/palette e produceva screenshot "chiaro" sbagliati);
  - impostato `MAGAZZINO_NO_ANIM=1` all'inizio: **necessario**, perché la nuova dissolvenza delle schede (`dissolvenza` al `currentChanged`) parte con opacità 0 e un `grab()` immediato produceva schede completamente vuote (verificato: `QGraphicsOpacityEffect` a opacità 0 sul widget della scheda). Con l'env var tutte le transizioni sono NO-OP e lo stato finale è identico;
  - `app.processEvents()` extra dopo il cambio tema.

## Screenshot (prefisso `fase6`, cartella `fase5/`)

Generati: `fase5/fase6_{scuro,chiaro}_{inventario,carico,scarico,profili,avvisi}.png`.

Verifiche a vista (eseguite su 10/10 immagini):
- ✅ Niente sfondi grigi chiari dentro le card in tema scuro;
- ✅ Testi leggibili in entrambi i temi;
- ✅ Riga di Avvisi alta quanto il contenuto (non allungata a tutta l'altezza);
- ✅ Pillola/testo "Sotto scorta" non tagliato nella riga Avvisi;
- ✅ Nessuna barra di scorrimento orizzontale in Avvisi (presente solo quella verticale, come previsto).

Osservazione preesistente (non una regressione Fase 6, già presente negli screenshot `dopo_*` di Fase 5): nella tabella Inventario la pillola STATO "Sotto scorta" tocca il bordo destro della card e appare leggermente troncata a 1700 px di larghezza.

## Cosa NON ho potuto verificare

- **Comportamento delle animazioni in esecuzione reale** (dissolvenza scheda, transizione tema, crescita della barra, scuoti del toast): i test unitari coprono la logica, ma non le ho *viste* in una finestra mostrata; negli screenshot sono disattivate (`MAGAZZINO_NO_ANIM=1`) appositamente.
- **Lettura dell'impostazione Windows "Mostra animazioni"** (SPI_GETCLIENTAREAANIMATION via ctypes): non eseguita/verificata su una sessione interattiva di Windows.
- **Font Segoe UI**: gli screenshot su questa macchina usano il fallback di font disponibile (la piattaforma offscreen non lo carica); le misure di pillola/elisione sono corrette in testa ai test, ma non ho potuto confermare visivamente con Segoe UI.
- **Persistenza `QSettings`** del toggle animazioni su una nuova sessione: coperto dai test, non verificato in app reale.
- Comportamento su database PostgreSQL (i 5 test relativi restano saltati in questo ambiente).
