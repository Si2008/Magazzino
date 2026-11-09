# Prompt operativo per Pi Agent — Magazzino Profili

Lavora esclusivamente nel repository `C:\Users\Simone\Desktop\magazzino`.

Il checkout corrente, il codice e i test sono la fonte di verità. I documenti di piano sono requisiti di riferimento: verifica ogni loro affermazione nel codice prima di applicarla. Esegui soltanto l'obiettivo esplicitamente indicato alla fine di questo documento. Non accorpare fasi o attività non richieste.

## Formato obbligatorio della risposta

Scrivi **solo le soluzioni realizzate e verificate**. Non fare una sintesi, non ripetere il problema, non spiegare il requisito ricevuto e non aggiungere premesse generiche.

Per ogni attività completata usa esclusivamente questo formato:

```text
### Soluzione: <nome concreto della modifica>

- File modificati: <elenco>
- Modifica applicata: <comportamento o codice introdotto>
- Test eseguiti: <comando e risultato>
- Stato: SUPERATO | FALLITO | NON ESEGUITO | BLOCCATO
```

Se una parte non può essere implementata perché manca una decisione funzionale, scrivi solo:

```text
### Blocco

<una domanda concreta indispensabile per continuare>
```

Non dichiarare mai un test superato se non lo hai eseguito.

## Operazioni iniziali obbligatorie

Prima di ogni modifica, esegui:

```powershell
git status --short --branch
git stash list
git diff --stat
git diff --check
rg --files
```

Leggi l'implementazione e i test interessati prima di modificare un file. Non usare mai `git reset --hard`, `git checkout -- <file-esistente>` o `git clean -fd`. Non applicare, eliminare o alterare stash preesistenti. Non stampare, copiare o committare `config.toml`, password, token, segreti o URL di database.

## Contratti vincolanti del dominio

### Pezzo

File: `magazzino_profili/domain/pezzo.py`

Una riga di giacenza è identificata univocamente da:

```python
UniqueConstraint(
    "profilo_id",
    "colore_id",
    "lunghezza_mm",
    name="combinazione",
)
```

La quantità non può diventare negativa:

```python
CheckConstraint("quantita >= 0", name="quantita_non_negativa")
```

I campi già presenti sono:

```python
id
profilo_id
colore_id
lunghezza_mm
quantita
ubicazione
scorta_minima
barcode
```

Conserva `Pezzo.id` come chiave delle relazioni. Il barcode è univoco ma non sostituisce la chiave primaria o le foreign key.

### Giacenza e movimenti

File: `magazzino_profili/domain/movimento.py`

L'unico punto che può aggiornare la giacenza è:

```python
def registra_movimento(
    session: Session,
    pezzo: Pezzo,
    tipo: TipoMovimento,
    quantita: int,
    causale: str,
    utente: str = "",
) -> Movimento:
```

Usa sempre questa funzione. Non introdurre aggiornamenti diretti come:

```python
pezzo.quantita = valore
```

in servizi, API, import o UI.

I soli tipi validi sono:

```python
TipoMovimento.CARICO
TipoMovimento.SCARICO
TipoMovimento.RETTIFICA
```

Ogni modifica della quantità deve creare il relativo `Movimento` nella stessa transazione.

### Carico

Mantieni questa firma pubblica:

```python
def carica(
    session: Session,
    codice: str,
    colore: str,
    lunghezza_mm: int,
    quantita: int,
    utente: str,
    causale: str,
    ubicazione: str | None = None,
    crea_se_mancante: bool = True,
) -> Pezzo:
```

`carica()` apre già una transazione con `with session.begin():`. Non racchiuderla dentro un'altra `session.begin()`. Quando occorre un import atomico, estrai un helper interno che partecipi alla transazione già aperta dal chiamante; conserva firma e comportamento pubblico di `carica()`.

### Scarico

Mantieni questa firma pubblica:

```python
def scarica(
    session: Session,
    barcode: str,
    quantita: int,
    utente: str,
    causale: str,
) -> Movimento:
```

Lo scarico identifica il pezzo soltanto tramite barcode normalizzato in maiuscolo e usa un lock di riga. Quantità superiore alla giacenza deve lasciare invariati giacenza e movimenti.

### Barcode

File: `magazzino_profili/db/normalizzazione.py`

Genera i barcode con la funzione già presente:

```python
def genera_barcode(profilo: object, colore: object, lunghezza_mm: int) -> str:
    return f"{codice}-{colore_n}-{lunghezza_mm}"
```

Formato verificato:

```text
AB12-AN007-6000
```

In caso di modifica barcode, aggiorna tutte le ricerche e i test dipendenti. Il barcode precedente non deve continuare a identificare il record, salvo requisito esplicito di storico o reindirizzamento.

## API telefono

File: `magazzino_profili/web/routes_barcode.py`

Mantieni le route esistenti:

```text
POST /api/login
POST /api/carico
POST /api/scarico
Authorization: Bearer <token>
```

Payload dei movimenti:

```json
{
  "barcode": "AB12-AN007-6000",
  "quantita": 1,
  "causale": "testo facoltativo"
}
```

Mantieni gli status: `401` token assente/non valido/scaduto, `403` ruolo non autorizzato, `404` barcode inesistente, `409` scarico superiore alla giacenza, `422` payload non valido.

Il carico remoto deve continuare a usare:

```python
pezzo = carica(
    session,
    codice=codice_profilo,
    colore=codice_colore,
    lunghezza_mm=lunghezza_mm,
    quantita=payload.quantita,
    utente=utente.username,
    causale=payload.causale or "Carico da telefono",
    crea_se_mancante=False,
)
```

Il telefono non crea nuovi pezzi. Per una consultazione da telefono, crea solo una route separata, autenticata, senza movimenti e con test dedicati. Non alterare le POST esistenti per farle diventare letture.

## Migrazioni

Le migrazioni sono file SQL in `migrations/`, applicati in ordine lessicografico e registrati nella tabella `migrazioni_applicate`.

Per ogni cambiamento di schema:

1. crea una nuova migrazione SQL additiva con prefisso numerico;
2. aggiorna il modello SQLAlchemy corrispondente;
3. aggiorna servizi, API, UI e import/export che usano il campo;
4. aggiungi test su schema nuovo e dati già esistenti;
5. non modificare migrazioni potenzialmente già applicate.

Non eseguire migrazioni né test distruttivi sul database reale. `test_integrazione_postgres.py` usa `Base.metadata.drop_all(engine)`: eseguilo soltanto se `MAGAZZINO_TEST_DB_URL` è stato verificato come database isolato, dedicato e sacrificabile.

## CSV, ODS, Excel e restore

Conserva il comportamento legacy del CSV finché non è introdotta una modalità nuova, dichiarata e testata:

```text
separatore: ;
codifica: UTF-8
import attuale: registra carichi
```

Non presentare un import CSV come restore se aggiunge quantità tramite carichi.

Per un backup XLSX ripristinabile conserva ID e relazioni. Il formato deve includere almeno:

```text
Metadati
Profili
Colori
Pezzi
Movimenti
Spezzoni
```

Il restore deve validare integralmente il file prima di scrivere, rispettare l'ordine delle foreign key, lavorare in transazione e fare rollback su errore. Il report XLSX a foglio singolo resta un report, non un backup completo.

## Scelte che richiedono una richiesta di chiarimento

Fermati e fai una sola domanda concreta se serve definire:

- il significato di `Caricato` e `Scaricato` con scarichi parziali;
- se il numero vassoio può essere testo oppure soltanto numero;
- la politica di merge o sostituzione durante import e restore;
- la conservazione di movimenti e spezzoni quando un pezzo viene eliminato;
- la sorgente, firma e installer di un sistema di aggiornamento;
- le categorie aziendali reali, se richieste per export o UI.

## Verifica obbligatoria

Scrivi prima o insieme alla modifica i test pertinenti. Esegui i test mirati e, quando l'ambiente è sicuro, l'intera suite:

```powershell
.\.venv\Scripts\python.exe -m pytest magazzino_profili\tests\test_carico.py -q
.\.venv\Scripts\python.exe -m pytest magazzino_profili\tests\test_scarico.py -q
.\.venv\Scripts\python.exe -m pytest magazzino_profili\tests\test_web_routes_barcode.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Esegui al termine:

```powershell
git diff --check
git status --short
```

Non fare commit salvo istruzione esplicita.

## Specifica completa delle funzioni da creare o modificare

Questa sezione è vincolante e prevale sulle indicazioni generiche precedenti. Descrive tutte le funzioni nuove o modificate previste dal piano. Non cambiare firme, comportamento o ordine delle operazioni senza aggiornare prima questa specifica e i test relativi.

### 1. Schema `Pezzo` e migrazione additiva

In `magazzino_profili/domain/pezzo.py` aggiungi i campi seguenti a `Pezzo`:

```python
numero_vassoio: Mapped[str | None] = mapped_column(String(128), nullable=True)
stato: Mapped[str | None] = mapped_column(String(16), nullable=True)
data_ultimo_cambio_stato: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
eliminato_il: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, index=True
)
```

Inserisci anche questo vincolo nella stessa tupla `__table_args__` già esistente:

```python
CheckConstraint(
    "stato IS NULL OR stato IN ('Caricato', 'Scaricato')",
    name="stato_valido",
)
```

Crea una sola nuova migrazione, con il primo prefisso numerico disponibile, che aggiunga esclusivamente le quattro colonne. Non modificare `001_scorta_minima.sql`. Per l'eventuale vincolo SQL, prima verifica che nessuna riga esistente abbia un valore incompatibile; se il dialect non permette di aggiungere il vincolo senza ricreare la tabella, conserva il vincolo ORM e documenta la limitazione invece di ricostruire `pezzi`.

Non valorizzare campi nuovi nei dati esistenti. I `NULL` sono il valore legacy corretto. La migrazione non modifica `id`, `profilo_id`, `colore_id`, `lunghezza_mm`, `barcode`, `ubicazione`, `quantita`, movimenti o spezzoni.

### 2. Cancellazione logica obbligatoria

`Pezzo` ha FK verso `Movimento` e `Spezzone`. Per preservare dati e storico, “eliminare un barcode” significa cancellazione logica: impostare `eliminato_il` e nascondere il record dai flussi attivi. Non usare `session.delete(Pezzo)`, non aggiungere `ON DELETE CASCADE` e non cancellare movimenti o spezzoni.

Il barcode resta nel record eliminato e resta univoco. Non riutilizzarlo automaticamente per un nuovo record. Il backup logico include anche `eliminato_il`; inventario, ricerca, telefono, carico e scarico trattano i record eliminati come non disponibili.

### 3. Nuove eccezioni e servizi anagrafici del pezzo

In `magazzino_profili/services/eccezioni.py` aggiungi:

```python
class BarcodeDuplicatoError(Exception):
    def __init__(self, barcode: str) -> None:
        self.barcode = barcode
        super().__init__(f"Barcode già assegnato a un altro pezzo: '{barcode}'.")


class PezzoEliminatoError(Exception):
    def __init__(self, pezzo_id: int) -> None:
        self.pezzo_id = pezzo_id
        super().__init__(f"Pezzo eliminato: id {pezzo_id}.")
```

Esportale da `magazzino_profili/services/__init__.py` insieme alle altre eccezioni.

In `magazzino_profili/services/pezzi.py` aggiungi questo helper privato:

```python
def _testo_opzionale(valore: str | None, nome: str, massimo: int = 128) -> str | None:
    if valore is None:
        return None
    if not isinstance(valore, str):
        raise ValueError(f"{nome} deve essere un testo")
    pulito = valore.strip()
    if not pulito:
        return None
    if len(pulito) > massimo:
        raise ValueError(f"{nome} non può superare {massimo} caratteri")
    return pulito
```

Implementa `aggiorna_barcode` in `services/pezzi.py` con questa firma e questa sequenza esatta:

```python
def aggiorna_barcode(session: Session, pezzo_id: int, barcode: str) -> Pezzo:
    if not isinstance(barcode, str):
        raise ValueError("Il barcode deve essere un testo")
    barcode_n = barcode.strip().upper()
    if not barcode_n:
        raise ValueError("Il barcode non può essere vuoto")
    if len(barcode_n) > 255:
        raise ValueError("Il barcode non può superare 255 caratteri")

    with session.begin():
        pezzo = session.scalar(
            select(Pezzo)
            .where(Pezzo.id == pezzo_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if pezzo is None:
            raise PezzoNonTrovatoError(f"id {pezzo_id}")
        if pezzo.eliminato_il is not None:
            raise PezzoEliminatoError(pezzo_id)
        duplicato = session.scalar(
            select(Pezzo.id).where(
                Pezzo.barcode == barcode_n,
                Pezzo.id != pezzo_id,
            )
        )
        if duplicato is not None:
            raise BarcodeDuplicatoError(barcode_n)
        pezzo.barcode = barcode_n
        session.flush()
    return pezzo
```

Racchiudi soltanto l'assegnazione e `flush()` in un savepoint se serve tradurre l'`IntegrityError` prodotto dalla race concorrente in `BarcodeDuplicatoError`. Non convertire altri `IntegrityError` nella stessa eccezione.

Implementa `imposta_numero_vassoio`:

```python
def imposta_numero_vassoio(
    session: Session,
    pezzo_id: int,
    numero_vassoio: str | None,
) -> Pezzo:
```

Logica obbligatoria: valida con `_testo_opzionale(numero_vassoio, "Il numero di vassoio")`; blocca il `Pezzo` con `with_for_update()`; solleva `PezzoNonTrovatoError` se assente e `PezzoEliminatoError` se eliminato; assegna il valore validato; esegue `flush()`; ritorna lo stesso record. Non aggiorna `ubicazione`, `barcode`, `quantita`, stato o movimenti.

### 4. Servizio degli stati e cancellazione logica

Crea `magazzino_profili/services/stati.py`. Non mettere questa logica nella UI o nelle route FastAPI.

```python
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

STATI_BARCODE = frozenset({"Caricato", "Scaricato"})

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _ora_utc(clock: Callable[[], datetime]) -> datetime:
    momento = clock()
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("Il clock deve restituire un datetime con timezone")
    return momento.astimezone(timezone.utc)
```

Implementa:

```python
def imposta_stato(
    session: Session,
    pezzo_id: int,
    stato: str,
    *,
    now: Callable[[], datetime] = utc_now,
) -> Pezzo:
```

Ordine obbligatorio:

1. rifiuta uno stato fuori da `STATI_BARCODE` con `ValueError("Stato non valido")`;
2. apri `with session.begin()`;
3. carica `Pezzo.id == pezzo_id` con `with_for_update()` e `populate_existing=True`;
4. solleva `PezzoNonTrovatoError` se assente e `PezzoEliminatoError` se `eliminato_il` non è `None`;
5. se `pezzo.stato == stato`, non modificare timestamp e non creare movimenti;
6. se diverso, calcola `momento = _ora_utc(now)`, poi imposta entrambi `pezzo.stato = stato` e `pezzo.data_ultimo_cambio_stato = momento`;
7. non chiamare il clock se lo stato non cambia;
8. `session.flush()` e ritorno del record dopo il commit.

Carico e scarico di magazzino non chiamano `imposta_stato()` automaticamente. Una variazione quantitativa e un cambio di stato restano eventi distinti.

Implementa la selezione scaduti come funzione di lettura:

```python
def lista_scaduti_per_eliminazione(
    session: Session,
    *,
    now: Callable[[], datetime] = utc_now,
) -> list[int]:
```

Calcola una sola volta `soglia = _ora_utc(now) - timedelta(hours=48)` e restituisci soltanto gli ID con tutte queste condizioni SQL: `eliminato_il IS NULL`, `stato == "Scaricato"`, `data_ultimo_cambio_stato IS NOT NULL`, `data_ultimo_cambio_stato <= soglia`. Ordina per `Pezzo.id`. Non caricare movimenti o spezzoni.

Implementa la singola cancellazione automatica:

```python
def elimina_scaduto(
    session: Session,
    pezzo_id: int,
    *,
    now: Callable[[], datetime] = utc_now,
) -> bool:
```

Calcola `momento = _ora_utc(now)` una sola volta prima della transazione. Apri transazione, rileggi il record con lock, ricontrolla tutte le quattro condizioni di scadenza usando `momento - timedelta(hours=48)`, poi assegna soltanto `pezzo.eliminato_il = momento`. Restituisci `True` se aggiornato; `False` se non trovato, già eliminato, Caricato, timestamp nullo o non scaduto. Non sollevare eccezione per un record semplicemente non più candidabile: questo evita race tra worker e nuova transizione.

Implementa l'eliminazione manuale:

```python
def elimina_manualmente(
    session: Session,
    pezzo_id: int,
    confermato: bool,
    *,
    now: Callable[[], datetime] = utc_now,
) -> Pezzo:
```

Se `confermato is not True`, solleva `ValueError("Eliminazione non confermata")` prima di aprire la transazione. Calcola `momento = _ora_utc(now)`, poi blocca il record, rifiuta assente o già eliminato con eccezione dedicata, assegna `eliminato_il = momento`, esegue flush e ritorna il record. Non considera stato o scadenza e non cancella righe collegate.

Esporta le quattro funzioni pubbliche e `STATI_BARCODE` da `services/__init__.py`.

### 5. Query attive e ricerca

Un record con `eliminato_il` valorizzato non deve comparire nei flussi attivi. Aggiungi un helper privato in `services/consultazione.py`:

```python
def _condizione_pezzo_attivo():
    return Pezzo.eliminato_il.is_(None)
```

Applica la condizione in `lista_pezzi`, `pezzi_sotto_scora`, `cerca_pezzi`, `pezzo_per_barcode`, `pezzo_per_combinazione`, `candidati_da_barcode`, `lista_ubicazioni`, `lista_profili_con_giacenza`, `lista_colori_con_conteggio` e `pezzi_da_riordinare`. Mantieni i movimenti storici nelle query `ultimi_movimenti`: la loro lettura non rende di nuovo attivo un `Pezzo` eliminato.

Non riutilizzare il parametro esistente `stato` di `cerca_pezzi()`: quel parametro filtra lo **stato di scorta** (`ok`, `sotto`, `esaurito`, `riordino`). Se serve filtrare `Caricato` o `Scaricato`, aggiungi un parametro finale compatibile:

```python
stato_barcode: str | None = None,
```

Accetta soltanto `None`, `Caricato` e `Scaricato`; se diverso, solleva `ValueError`. Aggiungi `Pezzo.stato == stato_barcode` alle condizioni senza cambiare i filtri di scorta esistenti.

In `services/carico.py`, la ricerca della combinazione deve includere il record logico eliminato. Se lo trova, non creare una seconda combinazione: bloccalo, annulla solo `eliminato_il`, conserva ID, barcode, vassoio, stato, timestamp e relazioni, poi registra il nuovo movimento con la logica esistente. In `services/scarico.py`, un barcode eliminato deve essere trattato come non trovato e non può essere riattivato da uno scarico.

### 6. UI desktop: inventario, modifica e conferma

`TabellaPezzi` ha un contratto testato: la colonna Barcode resta indice `0` e Colore indice `2`. Non spostare queste colonne. Aggiungi `Vassoio` e `Stato barcode` soltanto dopo l'ultima colonna attuale, aggiornando `_COLONNE`, la creazione delle righe e i test UI.

Nella sezione dettagli di `_riempi_laterale()`, aggiungi queste due righe senza togliere `Ubicazione`:

```python
("Vassoio", pezzo.numero_vassoio or "—"),
("Stato barcode", pezzo.stato or "—"),
```

Aggiungi azioni distinte per:

```text
Modifica barcode
Modifica vassoio
Imposta Caricato
Imposta Scaricato
Elimina barcode
```

Ogni azione deve usare `pezzo.id`, mai il barcode come identificatore del record. Dopo successo: chiudi la sessione, chiama `TabellaPezzi.aggiorna()`, conserva i filtri correnti, svuota la selezione se il record è stato eliminato e mostra un messaggio italiano. In caso di `BarcodeDuplicatoError`, `PezzoNonTrovatoError`, `PezzoEliminatoError` o `ValueError`, non aggiornare la UI e mostra il messaggio dell'eccezione.

Per l'eliminazione manuale usa `QMessageBox.question()` con pulsanti `Yes | No`, default `No`. Chiama `elimina_manualmente(..., confermato=True)` solo per `Yes`; per `No` non aprire sessione e non mostrare successo.

Non confondere la pillola di `stato_scorta(pezzo)` con il nuovo `stato` del barcode: devono restare due informazioni separate, con testi separati e filtri separati.

### 7. API telefono e client web

In `web/routes_barcode.py`, modifica esclusivamente `_dettagli_pezzo()` aggiungendo in coda:

```python
"numero_vassoio": pezzo.numero_vassoio,
"stato": pezzo.stato,
```

Le route POST esistenti mantengono input, status e comportamento. Non aggiungere idempotenza fittizia a carico o scarico.

Aggiungi una sola route di consultazione, separata dai movimenti:

```python
@router.get("/pezzi/{barcode}")
def api_dettaglio_pezzo(
    barcode: str,
    utente: UtenteAutenticato = Depends(utente_autenticato),
) -> dict:
```

La route normalizza con `barcode.strip().upper()`, rifiuta vuoto con `HTTPException(422, ...)`, chiama `verifica_permesso(utente, "inventario")`, cerca il record attivo con `consultazione.pezzo_per_barcode()`, restituisce 404 per assente e `_dettagli_pezzo(pezzo, "Dettaglio disponibile.")` per successo. Non crea `Movimento`, non cambia quantità e non acquisisce lock di scrittura.

Non introdurre una nuova azione `lettura`: la matrice esistente usa già `inventario` per amministratore e sola lettura. L'operatore riceve 403 sulla consultazione finché non viene autorizzato esplicitamente in `AZIONI_CONSENTITE` con modifica e test della matrice.

In `web/static/scansione.js` lascia `chiedi()` invariata per le POST. Aggiungi:

```javascript
async function chiediGet(url) {
  const intestazioni = {};
  if (STATO.token) intestazioni.Authorization = "Bearer " + STATO.token;
  const risposta = await fetch(url, { method: "GET", headers: intestazioni });
  let corpo = {};
  try { corpo = await risposta.json(); } catch (_) {}
  if (!risposta.ok) {
    const errore = new Error(corpo.detail || "Errore non previsto (codice " + risposta.status + ").");
    errore.codice = risposta.status;
    throw errore;
  }
  return corpo;
}
```

Aggiungi modalità `consulta`, un pulsante dedicato nel template e una funzione `consultaBarcode(barcode)`. La funzione chiama `chiediGet("/api/pezzi/" + encodeURIComponent(barcode))` e mostra profilo, descrizione, colore, lunghezza, giacenza, `numero_vassoio ?? "—"` e `stato ?? "—"`. La scansione in modalità `consulta` non legge quantità né causale e non chiama `inviaMovimento()`.

### 8. CSV e ODS

Non cambiare `importa_peczi_csv()` o la sua semantica legacy. Aggiungi un formato versione 2 soltanto attraverso nuove funzioni esplicite; per esempio `esporta_inventario_csv_v2()` e `valida_csv_v2()`. La funzione legacy continua a importare righe come `CARICO`.

Le intestazioni V2 sono, nell'ordine esatto:

```python
(
    "Versione formato", "ID pezzo", "Codice profilo", "Descrizione", "Colore",
    "Lunghezza (mm)", "Quantita", "Ubicazione", "Numero vassoio", "Barcode",
    "Stato barcode", "Data ultimo cambio stato UTC", "Eliminato il UTC",
    "Scorta minima",
)
```

`esporta_inventario_csv_v2(session, percorso_output)` scrive UTF-8, delimitatore `;`, una sola riga header e tutti i `Pezzo`, compresi gli eliminati, ordinati per `id`. Scrive stringa vuota per `None`, datetime in ISO 8601 con offset UTC e testo come valore letterale.

`valida_csv_v2(percorso_input)` legge tutto prima di qualsiasi scrittura, richiede le intestazioni esatte, verifica versione uguale a `2`, ID positivi unici, barcode non vuoto univoco, numeri interi validi, `stato` valido o vuoto, datetime timezone-aware o vuoto e riferimenti a profilo/colore validi. Restituisce una struttura dati immutabile; non apre transazioni di scrittura.

Un restore CSV V2 non è autorizzato finché non è definita modalità `db_vuoto` o `merge`; non implementare una sovrascrittura implicita.

Per ODS, conserva l'import attuale e aggiungi una funzione di export solo dopo avere verificato una libreria ODS installata. L'export deve produrre un archivio ODS valido, con header V2 equivalenti, e il test deve riaprire il file, verificare header, numero righe e valori vassoio/stato/timestamp. Mai scrivere CSV con estensione `.ods`.

### 9. Backup XLSX e restore

Crea `magazzino_profili/reports/backup_excel.py`. Non modificare il comportamento del report esistente `esporta_inventario_excel()`.

Funzioni pubbliche obbligatorie:

```python
def esporta_backup_logico_excel(session: Session, percorso_output: str | Path) -> Path: ...
def valida_backup_logico_excel(percorso_input: str | Path) -> BackupValidato: ...
def ripristina_backup_logico_excel(
    session: Session,
    backup: BackupValidato,
    *,
    modalita: Literal["db_vuoto", "merge"],
) -> None: ...
```

`esporta_backup_logico_excel` crea fogli nell'ordine `Metadati`, `Profili`, `Colori`, `Pezzi`, `Movimenti`, `Spezzoni`. Ogni foglio usa una riga di intestazione in grassetto, nessuna formula generata da dati utente e celle datetime timezone-aware convertite in ISO 8601 UTC. `Metadati` include `versione_formato=1`, timestamp export UTC e nome applicazione. `Pezzi` include ID, FK, tutti i campi esistenti e `numero_vassoio`, `stato`, `data_ultimo_cambio_stato`, `eliminato_il`.

`valida_backup_logico_excel` non scrive nel DB. Controlla workbook apribile, sei fogli esatti, intestazioni, versione, ID unici, FK presenti, barcode unici, stati validi, datetime validi e valori numerici. Se un controllo fallisce, solleva un'eccezione dedicata che indichi foglio, riga e colonna.

`ripristina_backup_logico_excel` accetta soltanto un `BackupValidato`. In modalità `db_vuoto`, verifica prima che ogni tabella applicativa sia vuota. In modalità `merge`, non aggiorna mai record esistenti: rifiuta qualsiasi collisione di ID, unique o FK. Inserisce nell'ordine Profili, Colori, Pezzi, Movimenti, Spezzoni dentro una sola transazione. Dopo l'inserimento riallinea le sequenze PostgreSQL soltanto se il dialect è PostgreSQL. Qualsiasi eccezione causa rollback completo.

Esporta le nuove funzioni da `reports/__init__.py`. Aggiungi test di roundtrip su database isolato e non chiamare il restore su database reale.

### 10. Background, server e login desktop

Il server telefono è già un processo separato avviabile con:

```powershell
python -m magazzino_profili.web.app
```

Non avviarlo in un thread della finestra Qt e non creare un secondo server dentro `main.py`. La finestra desktop deve poter chiudersi senza fermare un server web avviato separatamente. Documenta questo requisito nell'interfaccia e nelle istruzioni di avvio.

Per il backup, correggi `PianificatoreBackup.avvia()` affinché sia idempotente: sotto `_blocco`, se `_attivo` è già `True` ritorna senza avviare backup o timer aggiuntivi; altrimenti imposta `_attivo=True`, poi esegue il backup iniziale una sola volta fuori dal lock. `ferma()` resta idempotente. Aggiungi test start due volte, stop due volte e nessun timer duplicato.

Non implementare un tray icon, un servizio Windows o un autostart finché non sono richiesti esplicitamente. Il processo web separato soddisfa la ricezione dal telefono anche quando la finestra desktop è chiusa; il controllo automatico delle scadenze deve essere un worker separato, avviato nello stesso processo che deve effettivamente rimanere attivo e con start/stop idempotenti analoghi al pianificatore backup.

Crea `magazzino_profili/services/scadenze.py` soltanto dopo avere aggiunto in configurazione un intervallo esplicito positivo per il controllo. Non scegliere un intervallo nascosto nel codice. La classe deve avere questa firma:

```python
class PianificatoreScadenze:
    def __init__(
        self,
        session_factory,
        intervallo_secondi: int,
        *,
        now: Callable[[], datetime] = utc_now,
    ) -> None: ...

    def avvia(self) -> None: ...
    def ferma(self) -> None: ...
```

`__init__` rifiuta un intervallo non intero, booleano o minore di uno. `avvia()` acquisisce un lock, ritorna senza effetti se già attivo, altrimenti imposta attivo e avvia un solo ciclo immediato fuori dal lock. Il ciclo:

```text
1. apre una sessione breve e legge solo gli ID scaduti;
2. chiude quella sessione;
3. per ogni ID apre una nuova sessione breve e chiama elimina_scaduto();
4. chiude sempre la sessione, anche in errore;
5. registra l'errore senza password, token o barcode completo;
6. sotto lock pianifica un solo threading.Timer daemon se ancora attivo.
```

`ferma()` acquisisce il lock, marca inattivo, annulla il timer se presente e ritorna senza errori se era già fermo. Non tiene aperte sessioni, non modifica record Caricato e non usa un loop infinito. Il processo web separato deve chiamare `avvia()` nel suo lifecycle e `ferma()` nello shutdown; la UI desktop non crea né possiede questo worker.

In `ui/finestra_principale.py`, trasforma `DialogoAccesso` da `QWidget` in `QDialog`, importa `QDialog`, sostituisci `self.close()` nel ramo di credenziali valide con `self.accept()` e lascia che chiusura o annullamento restituiscano `Rejected`. Mantieni il metodo `utente()`.

In `main.py`, importa `DialogoAccesso` insieme a `FinestraPrincipale` e usa un solo event loop dell'applicazione:

```python
app = QApplication(sys.argv)
dialogo = DialogoAccesso(factory)
if dialogo.exec() != QDialog.DialogCode.Accepted:
    pianificatore.ferma()
    return 0

utente = dialogo.utente()
if utente is None:
    pianificatore.ferma()
    return 0

finestra = FinestraPrincipale(factory, utente.ruolo, utente.username)
finestra.showMaximized()
codice_uscita = app.exec()
pianificatore.ferma()
return codice_uscita
```

Importa `QDialog` dal modulo PySide6 corretto. Non creare utente amministratore predefinito e non registrare password nei log.

### 11. Aggiornamenti

Non creare moduli, endpoint, URL, download o popup di aggiornamento finché non sono forniti publisher, feed, formato manifest, firma o checksum autenticato, certificato/chiave di verifica e installer. L'unica risposta corretta in assenza di questi dati è `BLOCCATO` con l'elenco preciso dei valori mancanti.

### 12. Test obbligatori per ogni funzione

Ogni nuova funzione ha un file di test dedicato o una sezione chiaramente separata:

```text
test_pezzi.py                 aggiorna_barcode, imposta_numero_vassoio
test_stati.py                 transizioni, clock, 48 ore, delete logico
test_consultazione.py         esclusione record eliminati e filtro stato_barcode
test_web_routes_barcode.py    GET, payload esteso, ruoli, nessun movimento
test_csv.py                   legacy invariato e CSV V2
test_ods.py                   export/import ODS se implementato
test_backup_logico_excel.py   export, validazione, restore, rollback
test_backup.py                pianificatore idempotente
test_ui_*.py                  colonne, dettagli, azioni e conferma
```

Ogni test verifica stato DB prima e dopo: quantità, numero movimenti, ID, FK, barcode, `eliminato_il`, vassoio, stato e timestamp quando pertinenti. Gli scenari concorrenti usano almeno due sessioni distinte sul database di test; una sola sessione non dimostra la gestione della concorrenza.

### 13. Parti senza logica autorizzabile prima di una prova o di un dato esterno

Non esiste una logica corretta da scrivere in anticipo per i seguenti casi. Pi Agent non deve inventarla:

```text
Bug Fase 3                 prima test di regressione riproducibile, poi modifica minima.
Ottimizzazione Fase 5      prima benchmark/profiling comparabile, poi sola correzione della causa misurata.
Aggiornamenti Fase 13      prima feed, publisher, manifest, firma/checksum, chiave/certificato e installer.
Test PostgreSQL distruttivi prima URL di database test verificato e sacrificabile.
Prova telefono reale       prima dispositivo, rete, HTTPS e certificato realmente disponibili.
```

In questi casi la risposta ammessa è solo `BLOCCATO` con prerequisito specifico. Non creare placeholder, endpoint fittizi, cache, indici, thread, URL, file di aggiornamento o risultati di test simulati.

## Istruzioni esecutive per fase

### Fase 2 — protezione, backup e database di test

1. Esegui i comandi iniziali già indicati e registra soltanto branch, hash, file modificati e presenza di stash.
2. Leggi `config.toml` esclusivamente tramite il parser dell'applicazione; non usare `Get-Content`, non mostrare valori e non scrivere il file.
3. Prima di qualunque migrazione o restore, individua database e schema destinazione senza stamparne credenziali. Se il target non è certamente un database di test o il backup non è verificabile, non eseguire l'operazione dipendente.
4. Per i test PostgreSQL, verifica che `MAGAZZINO_TEST_DB_URL` sia definita e punti a un database dedicato; in caso contrario marca soltanto i test PostgreSQL come `BLOCCATO`.
5. Non fare modifiche applicative in questa fase.

### Fase 3 — correzioni di bug

Per ogni bug, applica esattamente questa sequenza:

```text
1. Individua il file e il test correlato con rg.
2. Scrivi un test di regressione che fallisce sul checkout corrente.
3. Esegui esclusivamente quel test e registra il fallimento.
4. Applica la modifica minima nel modulo responsabile.
5. Esegui di nuovo il test di regressione e i test del modulo.
6. Non modificare l'aspettativa del test per nascondere il difetto.
```

Per una validazione di quantità, usa sempre la regola esistente nel dominio:

```python
if not isinstance(quantita, int) or quantita <= 0:
    raise ValueError("La quantità del movimento deve essere un intero positivo")
```

Non catturare `Exception` per restituire un successo apparente. Intercetta soltanto l'eccezione prevista, conserva il traceback delle eccezioni inattese e lascia che la transazione faccia rollback.

### Fase 5 — prestazioni

Non modificare query, indici, cache o thread senza una misura prima e dopo sulla stessa macchina e sullo stesso dataset.

Usa un benchmark isolato con almeno questi dati:

```python
from time import perf_counter
import tracemalloc

tracemalloc.start()
inizio = perf_counter()
risultato = operazione_da_misurare()
durata_secondi = perf_counter() - inizio
memoria_corrente, memoria_picco = tracemalloc.get_traced_memory()
tracemalloc.stop()
```

Registra numero di righe, query o operazione misurata, warm/cold run, durata, memoria di picco, CPU se disponibile e ambiente. Solo dopo la baseline:

1. individua query duplicate o relazioni lazy nel percorso effettivamente lento;
2. applica `selectinload` o `joinedload` solo alla relazione osservata;
3. aggiungi un indice soltanto alla colonna realmente filtrata o ordinata nella query misurata;
4. aggiungi paginazione soltanto quando UI e test dichiarano il contratto di ordinamento e conteggio;
5. ripeti lo stesso benchmark e i test UI/API coinvolti.

### Fase 6 — schema, vassoio, stato e timestamp

I soli stati persistiti sono esattamente `Caricato` e `Scaricato`. `stato` resta nullable per i record storici privi di una transizione dimostrabile; non attribuire loro uno stato o un timestamp inventato.

`numero_vassoio` deve restare un valore testuale nullable fino a quando non è stabilito un vincolo aziendale più stretto. Questa scelta conserva i valori ODS esistenti, inclusi `4`, `Vassoio 4` e descrizioni di ubicazione. Non aggiungere unicità sul vassoio e non modificare `ubicazione` automaticamente.

Quando i valori sono definiti, implementa i campi come nullable per i record esistenti e usa una nuova migrazione, per esempio `002_campi_giacenza.sql`:

```sql
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS numero_vassoio VARCHAR(128);
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS stato VARCHAR(16);
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS data_ultimo_cambio_stato TIMESTAMP WITH TIME ZONE;
ALTER TABLE pezzi ADD COLUMN IF NOT EXISTS eliminato_il TIMESTAMP WITH TIME ZONE;
```

Aggiorna contemporaneamente `magazzino_profili/domain/pezzo.py` con tipi coerenti:

```python
numero_vassoio: Mapped[str | None] = mapped_column(String(128), nullable=True)
stato: Mapped[str | None] = mapped_column(String(16), nullable=True)
data_ultimo_cambio_stato: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

Nel modello SQLAlchemy, impedisci stati diversi da `Caricato` e `Scaricato` per i nuovi valori, lasciando validi i `NULL` storici:

```python
CheckConstraint(
    "stato IS NULL OR stato IN ('Caricato', 'Scaricato')",
    name="stato_valido",
)
```

Verifica prima se il database supporta il vincolo corrispondente e aggiungilo con una nuova migrazione soltanto dopo avere controllato i valori già presenti. Non assegnare stato o timestamp ai record storici se la loro origine non è dimostrabile. Non modificare `ubicazione` per ricavare il vassoio senza una conversione reversibile e testata. La migrazione è conclusa soltanto dopo test su schema vuoto, schema precedente, seconda esecuzione, valori null e conservazione di ID/FK.

### Fase 7 — modifica barcode e vassoio

Implementa un servizio dedicato, senza cancellare e ricreare il `Pezzo`. Il record deve essere cercato con `Pezzo.id`, bloccato e aggiornato nella stessa transazione:

```python
def aggiorna_barcode(session: Session, pezzo_id: int, barcode: str) -> Pezzo:
    barcode_n = barcode.strip().upper()
    if not barcode_n:
        raise ValueError("Il barcode non può essere vuoto")

    with session.begin():
        pezzo = session.scalar(
            select(Pezzo)
            .where(Pezzo.id == pezzo_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if pezzo is None:
            raise PezzoNonTrovatoError(str(pezzo_id))

        duplicato = session.scalar(
            select(Pezzo.id).where(
                Pezzo.barcode == barcode_n,
                Pezzo.id != pezzo.id,
            )
        )
        if duplicato is not None:
            raise BarcodeDuplicatoError(barcode_n)

        pezzo.barcode = barcode_n
        session.flush()
    return pezzo
```

Definisci `BarcodeDuplicatoError` in `magazzino_profili/services/eccezioni.py`, con messaggio italiano. Gestisci anche la race sul vincolo `unique=True`: intercetta solamente l'`IntegrityError` dovuto al barcode duplicato e traducilo nella stessa eccezione; lascia propagare gli altri errori.

Per il vassoio, salva `None` per stringa vuota e il testo ripulito per valori presenti:

```python
numero_vassoio_n = valore.strip() or None
```

Test obbligatori: ID invariato, movimenti invariati, spezzoni invariati, barcode nuovo ricercabile, barcode vecchio non ricercabile, duplicato rifiutato, concorrenza, vassoio nullo/testuale, persistenza dopo riapertura della sessione. Aggiorna UI, API ed export soltanto dopo il servizio e i test del servizio.

### Fase 8 — stati e scadenza dopo 48 ore

Implementa esclusivamente le funzioni della sezione **4. Servizio degli stati e cancellazione logica** e il worker della sezione **10. Background, server e login desktop**. Non derivare lo stato dalla quantità, non cancellare fisicamente record e non aggiungere una seconda implementazione del clock.

Verifica 47h59m, 48h esatte, oltre 48h, record Caricato, ritorno da Scaricato a Caricato, seconda transizione a Scaricato, riavvio worker, concorrenza transizione/cancellazione, delete manuale confermato e annullato, e rollback. Non cambiare l'orologio del computer durante i test.

### Fase 9 — telefono

Applica esclusivamente il contratto della sezione **7. API telefono e client web**. Le POST esistenti restano mutanti, la GET usa il permesso già esistente `inventario`, e ogni risposta di dettaglio include `numero_vassoio` e `stato` come chiavi nullable.

Test obbligatori: token assente/scaduto, ruolo sola lettura, barcode assente, GET senza movimenti, barcode modificato, payload non valido, DB error e chiamate concorrenti. Una prova da dispositivo fisico va riportata separatamente dai test `TestClient`.

### Fase 10 — CSV e ODS

Conserva immutati per la modalità legacy:

```python
INTESTAZIONI = (
    "Codice profil", "Descrizione", "Colore", "Lunghezza (mm)",
    "Quantita", "Ubicazione", "Barcode",
)
```

e:

```python
csv.writer(file, delimiter=";")
open(percorso, encoding="utf-8", newline="")
```

Non rinominare `importa_peczi_csv()` e non cambiarne silenziosamente la semantica: ogni riga continua a essere un carico. Per un restore o merge crea una funzione diversa con nome esplicito, anteprima e policy scelta dall'utente.

Prima della scrittura valida l'intero file: intestazioni, BOM, righe, interi positivi, codici profilo e dati nuovi. Se è richiesta atomicità, non chiamare `carica()` in un ciclo dentro una transazione esterna: estrai un helper transazionale interno e fallo usare da `carica()` e dall'import.

Per ODS conserva `_ubicazione_da_vassoio()` fino a quando non esiste una migrazione e una mappatura testata verso `numero_vassoio`. Una volta introdotto il campo, conserva anche `ubicazione` e non perdere i valori testuali di vassoio.

L'esportazione ODS va aggiunta soltanto se il progetto dispone già di una libreria compatibile o dopo avere aggiunto una dipendenza esplicita e giustificata in `requirements.txt`. Esporta un file ODS reale, non CSV rinominato, con intestazioni stabili e un test che lo riapra con una libreria ODS compatibile. Mantieni una funzione distinta, per esempio `esporta_inventario_ods()`, e non alterare l'import esistente per simulare l'export.

Test obbligatori: UTF-8/BOM, `;`, virgolette, accenti, file vuoto, intestazione mancante, numeri invalidi, quantità zero, profilo assente, duplicati, file legacy, vassoio, stato/timestamp, doppio import, rollback o report parziale dichiarato, CSV e ODS separati.

### Fase 11 — backup logico XLSX e restore

Non rinominare `esporta_inventario_excel()` come backup completo. Mantienilo come report `Inventario` oppure crea nuove funzioni, per esempio:

```python
def esporta_backup_logico_excel(session: Session, percorso_output: str | Path) -> Path:
    ...

def valida_backup_logico_excel(percorso_input: str | Path) -> BackupValidato:
    ...

def ripristina_backup_logico_excel(
    session: Session,
    backup: BackupValidato,
    modalita: Literal["db_vuoto", "merge"],
) -> None:
    ...
```

Usa questi fogli, nello stesso ordine:

```text
Metadati
Profili
Colori
Pezzi
Movimenti
Spezzoni
```

Esporta ID e FK come numeri, timestamp UTC come datetime tipizzati, e testo utente senza farlo diventare formula Excel. Durante restore:

1. apri e valida integralmente il file prima di aprire la transazione di scrittura;
2. verifica versione formato, nomi fogli, intestazioni, ID unici, FK e barcode unici;
3. scrivi nell'ordine Profili, Colori, Pezzi, Movimenti, Spezzoni;
4. preserva gli ID e riallinea le sequenze PostgreSQL;
5. fai rollback completo su qualsiasi errore;
6. rifiuta DB non vuoto salvo modalità merge esplicita e testata.

Test obbligatori: dataset con relazioni, fogli e ordine, reopen openpyxl, conteggi, ID/FK, null, timezone, barcode, vassoio/stato, roundtrip su DB vuoto, file corrotto, conflitto, rollback e file storico a foglio singolo dichiarato come ripristino parziale.

### Fase 12 — background e ciclo di vita

Prima di implementare, scegli e documenta una sola architettura: processo con tray oppure processo separato. Non chiamarla servizio Windows se non è installata come servizio Windows.

L'implementazione deve garantire:

```text
start() è idempotente
stop() è idempotente
un solo worker per processo
sessioni, thread, timer e socket sono chiusi durante stop()
API e worker non dipendono dalla finestra Qt visibile
```

Usa un `threading.Event` o equivalente per lo stop, non un ciclo infinito non interrompibile. Mantieni il riferimento al worker e verifica che una seconda chiamata a start non ne generi un altro.

Test obbligatori: start due volte, stop due volte, chiusura finestra, riapertura, restart dopo errore, assenza di worker duplicati, persistenza del lavoro pianificato e terminazione pulita.

### Fase 13 — aggiornamenti

Non implementare download o installazione finché non sono disponibili tutti questi valori: URL del feed, publisher, formato manifest, versione, algoritmo di firma/checksum, chiave o certificato di verifica, URL installer e procedura di recovery.

Se i valori sono disponibili:

1. scarica manifest e artefatto in file temporanei;
2. verifica firma o checksum autenticato prima di rendere disponibile l'installer;
3. blocca download concorrenti;
4. conserva config e database;
5. mostra solo stato, avanzamento ed errore in italiano;
6. avvia l'installer soltanto dopo verifica riuscita.

Test obbligatori: nessun update, update disponibile, offline, download troncato, firma errata, checksum errato, installazione fallita e conservazione dati su ambiente isolato.

### Fase 14 — sicurezza, packaging e compatibilità

Riattiva il login desktop usando il dialogo già esportato da `magazzino_profili.ui` soltanto dopo aver letto la sua firma e i test UI. Rimuovi la creazione diretta dell'amministratore predefinito in `main.py`:

```python
utente = Utente(username="simone", ruolo=Ruolo.AMMINISTRATORE.value)
```

Il flusso finale deve gestire annullamento login, credenziali errate, apertura UI con ruolo reale e nessun bypass amministratore. Aggiungi test per ogni ruolo e per le schede consentite.

Verifica inoltre: nessun segreto in Git o log, input UI/API/file validati, messaggi italiani, backup e restore con percorsi controllati, TLS e timeout API, dipendenze PyInstaller e avvio del pacchetto sull'OS disponibile. Non dichiarare compatibilità Windows 10/11 senza una prova su quell'OS.

### Fase 15 — verifica integrata

Esegui soltanto le prove compatibili con ambiente e dati sicuri. Per ogni prova riporta comando o procedura, ambiente, database senza segreti, risultato osservato e stato. Non presentare la lettura del codice come test funzionale, né un `TestClient` come prova eseguita su telefono fisico.

La verifica finale deve includere, se implementate: UI e mockup, migrazioni, barcode, vassoio, stati, 48 ore, cancellazione manuale, API telefono, concorrenza, CSV, ODS, XLSX, restore, lifecycle, update, package e benchmark. Riavvia l'applicazione o il componente interessato per verificare persistenza di dati, configurazione e scadenze. Chiudi con `git diff --check` e `git status --short`.

Usa solo questi stati per ogni test:

```text
SUPERATO      prova eseguita e conforme
FALLITO       prova eseguita e non conforme
NON ESEGUITO  prova non effettuata
BLOCCATO      prerequisito mancante
```

Per `FALLITO`, `NON ESEGUITO` e `BLOCCATO` indica la causa concreta e il passaggio necessario per completare la prova.

Il rapporto finale conserva le sezioni A–L richieste, ma ciascuna sezione contiene soltanto soluzioni applicate, evidenze e limiti reali; non ripete o riassume il testo del problema:

```text
A. Stato operativo e soluzioni completate
B. File creati, modificati o eliminati e motivazione tecnica
C. Schema, migrazioni e preservazione dati
D. Interfaccia, mockup e misurazioni
E. Barcode, vassoio, stati, eliminazione automatica e manuale
F. Telefono, endpoint, configurazione e prove
G. CSV, ODS, XLSX, backup e restore
H. Background, arresto e aggiornamenti
I. Tabella test: nome | stato | ambiente | strumenti | evidenza
J. Limiti, bug residui e prerequisiti mancanti
K. Istruzioni reali di avvio e uso
L. Giudizio basato esclusivamente sui test eseguiti
```

Non dichiarare il progetto pronto se un test critico è fallito, bloccato o non eseguito.

## Obiettivo della sessione

> Sostituisci questa riga con una sola attività concreta. Non svolgere attività aggiuntive.
