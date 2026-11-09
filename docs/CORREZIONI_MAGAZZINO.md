# Correzioni Magazzino Profili — versione 2.0.0

Aggiornamento successivo: la verifica 2.0.1 ha trovato e corretto due difetti nel
backup ZIP. Dettagli e prove in `C:/Users/Simone/Desktop/magazzino/docs/VERIFICA_BUG_2.0.1.md:1`.
I conteggi sotto si riferiscono alla verifica 2.0.0.

Data: 5 novembre 2026. Il documento `C:/Users/Simone/Desktop/magazzino/docs/ANALISI_MAGAZZINO.md`
conserva l'analisi precedente agli interventi. Le successive richieste dell'utente
hanno autorizzato modifiche, rimozione del login, barcode per singolo pezzo, nuova
pagina mobile, immagini automatiche, ottimizzazioni e compilazione sul Desktop.

## Esito e limiti

**VERIFICATO:** interventi applicati e provati su dati sintetici; nessun database
operativo usato, nessuna migrazione sui dati reali, nessuna modifica a configurazione
operativa, chiavi private, backup reali, catalogo originale o vecchi eseguibili.
I riferimenti nelle tabelle identificano codice e regressioni eseguite. Gli XML
consolidati sono elencati in `C:/Users/Simone/Desktop/magazzino/docs/ESITI_TEST_MAGAZZINO.json:1`.

**NON VERIFICABILE:** telefono fisico, fotocamera, stampante/scanner, rete mobile,
PC più vecchio e magazzino operativo. Il collegamento WAN reale richiede ancora un
URL HTTPS/VPN/tunnel, che l'utente non possiede. Non è stato pubblicato il magazzino
su Internet. La build attuale richiede Windows 10/11 a 64 bit: non soddisfa Windows
7/8 o 32 bit. Vedere requisiti e fonti nella guida
`C:/Users/Simone/Desktop/magazzino/docs/PROVA_E_TELEFONO.md:91`.

## Protezione dei dati

| Stato | Intervento | Evidenza |
|---|---|---|
| VERIFICATO | Scritture su temporaneo univoco, fsync e sostituzione atomica; file precedente conservato in caso di errore. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/file_sicuri.py:13`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:93` |
| VERIFICATO | Lock OS tra processi, separato per cartella: un dump non blocca la copia di immagini altrove. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/file_sicuri.py:30`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:198` |
| VERIFICATO | Backup verificato prima delle migrazioni sul DB esistente; errore interrompe l'aggiornamento. Backup periodici su worker. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:98`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/backup/backup_db.py:98` |
| VERIFICATO | Lock PostgreSQL e checksum delle migrazioni; aggiornamenti additivi 007–011 e conservazione dei record nella prova. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/migrazioni.py:31`; `C:/Users/Simone/Desktop/magazzino/migrations/007_indici_operativi.sql:1`; `C:/Users/Simone/Desktop/magazzino/migrations/010_barcode_unitari.sql:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_postgres.py:30` |
| VERIFICATO | Configurazione condivisa, percorsi relativi alla configurazione, password DB riutilizzata dal setup e chiusura engine/worker. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/config.py:65`; `C:/Users/Simone/Desktop/magazzino/setup_database.py:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:83` |

**Limite:** `pg_restore --list` verifica la leggibilità del dump, non un ripristino
completo su un altro PC. I test di ripristino Excel/ZIP sono distinti e usano dati
sintetici. Excel/ZIP copre dati applicativi e immagini, non tutte le tabelle tecniche
del DB o le credenziali. Un backup sullo stesso disco non protegge dal guasto di quel
disco. Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:212`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/backup_excel.py:161`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/archivio.py:18`.

## Stato delle 15 funzioni

| Funzione | Stato dopo le correzioni | Evidenza e note |
|---|---|---|
| 1. Barcode, stati e data/ora | VERIFICATO, implementata nei percorsi provati | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/domain/movimento.py:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:35`. Scarico/rientro conservano la stessa identità. |
| 2. Scadenza dopo 48 ore | VERIFICATO, cancellazione logica protetta | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/stati.py:60`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/stati.py:82`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:56`. Solo Scaricato, saldo zero e data scaduta UTC; UPDATE condizionale e worker desktop/web. |
| 3. Vassoio per barcode | VERIFICATO, implementata | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/pezzi_unitari.py:11`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/templates/scansione.html:35`. Separato dall'ubicazione. |
| 4. Modifica barcode esistente | VERIFICATO, modifica in posto | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/pezzi.py:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_barcode_vassoio.py:1`. ID e storico restano collegati. |
| 5. Inventario per colore | VERIFICATO, schede colore e filtri SQL | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:910`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_inventario_colori.py:1`. |
| 6. Profilo maiuscolo | VERIFICATO, normalizzazione centrale | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/domain/profilo.py:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_validatore_maiuscolo.py:1`. Anche assegnazioni ORM, import e API. |
| 7. Immagine automatica | VERIFICATO per 211 PNG; PARZIALE per 24 codici senza file | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/immagini.py:34`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/immagini.py:41`; `C:/Users/Simone/Desktop/magazzino/docs/CATALOGO_ASSOCIAZIONI.csv:1`. Funziona sui profili storici senza percorso salvato. |
| 8. Pallini colore | VERIFICATO, mappatura esplicita senza hash arbitrario | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/registro_colori.py:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/colori_base.py:1`. Tinte RAL approssimate; codici proprietari sconosciuti da confermare. |
| 9. Apertura sezione | VERIFICATO, miniatura e viewer zoom/pan/adatta | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/visualizzatore_immagine.py:1`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/scheda_carico.py:1`. Anteprima automatica anche sul telefono. |
| 10. Paginazione | VERIFICATO su Inventario/Avvisi | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:220`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/avvisi.py:164`. 200 pezzi e 30 materiali per pagina, COUNT SQL. |
| 11. Login rimosso | VERIFICATO, accesso libero desktop e API | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:112`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/accesso_libero.py:1`. Tabelle utenti/hash storici conservati per compatibilità; non consultati per accedere. |
| 12. CSV/ODS | VERIFICATO nei round-trip e import provati | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/export_csv.py:70`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/importa_ods.py:212`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:74`. CSV UTF-8 BOM e `;`, transazioni, numeri rigorosi, duplicati segnalati. |
| 13. Excel multi-foglio | VERIFICATO, dieci fogli e restore logico | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/backup_excel.py:161`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/backup_excel.py:222`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:213`. ZIP aggiunge immagini/checksum. |
| 14. Background/autostart | VERIFICATO nel codice e nei test; PC reale NON VERIFICABILE | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/background.py:22`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/background.py:49`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/server_telefono.py:18`. Opzioni volontarie; nessuna chiave Run modificata automaticamente. |
| 15. Aggiornamenti popup | VERIFICATO con firme/file sintetici; distribuzione reale NON VERIFICABILE | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/aggiornamenti.py:357`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_aggiornamento.py:10`. Feed asincrono, annullamento, staging e verifica; nessuna release reale pubblicata/firmata. |

## Barcode unitario e dati storici

**VERIFICATO:** i nuovi barcode sono seriali `MP-` + UUID esadecimale; non codificano
quantità o proprietà modificabili. Il form può creare più pezzi uguali, ciascuno con
saldo 0/1 e una diversa etichetta. Le informazioni si recuperano dal DB tramite il
seriale. Giacenze aggregate storiche conservate; conversione guidata con backup,
elenco nuove etichette, saldo/storico preservati e rifiuto dei piani obsoleti. Le
scorte si calcolano sulla somma del materiale, non sul singolo saldo 1. Evidenze:
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/pezzi_unitari.py:11`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/pezzi_unitari.py:54`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/consultazione.py:43`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:135`.

**VERIFICATO:** l'import ODS della UI non inventa più il peso di nuovi profili: se il
formato storico non contiene i dati anagrafici, chiede di creare prima il profilo
con valori reali, senza importare parzialmente. Il vecchio helper di compatibilità
`unitari=False` conserva il comportamento storico e non viene usato dal menu normale.
Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/importa_ods.py:237`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:881`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:228`.

## Telefono e rete mobile

**VERIFICATO:** FastAPI/uvicorn con API HTTP/HTTPS e polling asincrono; pagina mobile
locale nel pacchetto, nessun login. Modalità Lettore PC, Consulta, Carico, Scarico e
Nuovi pezzi; nuova anagrafica con descrizione/peso/lunghezza, vassoio, ubicazione,
scorta, etichette PNG e sezione automatica. Richieste di modifica con chiave
idempotente, hash e ricevuta nella stessa transazione; test anche fra due processi
PostgreSQL. Coda PC con destinatario di sessione, claim atomico, ACK dopo il lavoro UI,
scadenza e stato incerto, senza ripetizione automatica di operazioni dall'esito ambiguo.
Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/templates/scansione.html:1`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/routes_barcode.py:67`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/idempotenza.py:1`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/telefono.py:136`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_postgres.py:74`.

Cause residue da verificare, in ordine:

1. **VERIFICATO il prerequisito mancante:** nessun URL HTTPS pubblico/VPN disponibile;
   la configurazione reale ha URL pubblico vuoto. IP privati del PC non sono
   raggiungibili dalla rete mobile. Conferma: attivare tunnel e aprire `/api/salute`
   dal telefono prima del QR. Codice: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/telefono.py:121`.
2. **IPOTESI sul dispositivo:** certificato locale non attendibile o permesso camera
   negato. Conferma: URL HTTPS con certificato pubblico e permesso del browser.
   Controlli/errori: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/static/scansione.js:98`.
3. **IPOTESI sull'ambiente:** servizio spento, porta occupata o PC sospeso. Conferma:
   log del servizio e salute locale. Gestione processo:
   `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/server_telefono.py:18`.
4. **IPOTESI in LAN:** firewall o isolamento Wi-Fi. Conferma: altro client sulla
   stessa rete, IP/porta corretti, verifica isolamento AP. Nessuna regola firewall
   cambiata; host configurabile in `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/app.py:82`.

**Raccomandazione:** pagina browser attuale più tunnel HTTPS/VPN: riusa API e UI e
consente rete mobile. HTTPS diretto LAN richiede certificato attendibile e non risolve
da solo la WAN. Un server cloud sincronizzato darebbe maggiore indipendenza dal PC,
ma richiederebbe conflitti/offline e una seconda copia dei dati; non è giustificata
una riscrittura per questa fase. Procedura/fonti:
`C:/Users/Simone/Desktop/magazzino/docs/PROVA_E_TELEFONO.md:49`.

**Scelta esplicita dell'utente:** chi raggiunge l'URL ha tutti i privilegi. Il QR è
un identificatore di consegna, non una credenziale. Una VPN limita la raggiungibilità
senza introdurre login nel programma. Nessun tunnel installato o magazzino pubblicato.
Evidenza: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/accesso_libero.py:1`.

## Catalogo immagini

**VERIFICATO:** 211 PNG validi, senza duplicati di codice o contenuto SHA256;
indice aggiornato di 234 codici, 210 abbinati e 24 senza PNG. `TO3108.png`, fuori
indice, viene trovato dal nome. La copia inclusa nel programma preserva gli originali.
Il test su 211 profili sintetici senza percorso immagine risolve tutti i PNG e
verifica due nuovi pezzi TO3108 con la stessa sezione. Elenco/hash:
`C:/Users/Simone/Desktop/magazzino/docs/CATALOGO_ASSOCIAZIONI.csv:1`;
implementazione: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/immagini.py:41`.
Esito esterno: `esito_catalogo_completo.json`.

**NON VERIFICABILE senza altri file:** AZ2841, AZ3109, AZ46431, AZ4667, AZ4913,
AZ4914, AZ4918, AZ5023, AZ5024, AZ5025, AZ5026, AZ6508, NC2635, NC2698, NC4645,
NG6602, SW1613, T3223, TO1069, TO1313, TO9100, TT1622, TT1623, TT1645.
**IPOTESI:** AZ46431 è forse un refuso; non è stato inventato un alias. Verificare
con catalogo tecnico/fornitore. Anche i colori proprietari sconosciuti richiedono
conferma; non sono stati assegnati arbitrariamente.

## Prestazioni, UI e confezionamento

**VERIFICATO:** schede create al primo uso; pagine SQL 200/30; ricerca con debounce
250 ms; scorte aggregate e badge COUNT; export CSV/XLSX/PDF a blocchi 500, Excel
write-only, immagini ridimensionate; lavori lunghi e feed su worker. Evidenze:
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:358`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:248`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/consultazione.py:84`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/export_excel.py:36`.

Misura reale su questo PC, SQLite in memoria, 12.000 pezzi, 100 profili, 10 colori,
Qt offscreen e animazioni disattivate (`benchmark_finale.json` esterno):

| Operazione | Tempo |
|---|---:|
| Import librerie Python/Qt/SQL/UI | 0,9884 s |
| Query pagina 200 pezzi | 0,0194 s |
| Costruzione finestra, solo Inventario | 0,2011 s |
| Prima costruzione Carico / Scarico | 0,0140 / 0,0066 s |
| Prima costruzione Profili / Avvisi | 0,0250 / 0,0230 s |

Il test export con 1.201 pezzi verifica massimo 550 oggetti ORM residenti e massimo
10 query, evitando N+1: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_dati.py:240`.
Non estrapolare questi tempi al PC vecchio o al DB reale. **Limiti:** odfpy conserva
ancora il documento ODS in memoria; import valida l'intero file prima della scrittura;
elenchi anagrafici/filtri sono completi e alcune query brevi della UI sincrone. RAM
complessiva, grandi import, dump e avvio su disco lento non misurati sul destinatario.
Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/ods_v2.py:52`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/importa_ods.py:172`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/consultazione.py:94`.

**VERIFICATO:** testi grandi, temi e placeholder leggibili, cambio tema senza
ricreare i form, viewer zoom/pan, animazioni disattivabili. A 1024×768 è previsto
scorrimento orizzontale; i form lunghi scorrono verticalmente. Screenshot esterni
`anteprime_desktop` e `anteprime_telefono`; mobile controllato a 390×844, contenuto
375 px senza fuoriuscita orizzontale. Android/iPhone reali NON VERIFICABILI.
Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tema.py:180`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:169`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:659`.

**VERIFICATO:** input numerici e barcode validati, SQL parametrizzato, stringhe
Excel protette dalle formule, restore ZIP con whitelist/checksum, errori visibili
e log rotanti. L'accesso libero resta una scelta di esposizione, non una protezione.
Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/archivio.py:47`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/routes_barcode.py:1`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:231`.

**VERIFICATO:** distribuzione PyInstaller in cartella per evitare estrazione a ogni
avvio, senza QtWebEngine/test, e piccolo lanciatore C# sul Desktop. La prima build
è stata scartata: il PATH aveva fatto raccogliere una DLL ICU estranea di Poppler.
Compilazione corretta isolando il PATH, senza installazioni globali. Evidenze:
`C:/Users/Simone/Desktop/magazzino/tools/compila_windows.py:30`,
`C:/Users/Simone/Desktop/magazzino/MagazzinoProfili.spec:36`,
`C:/Users/Simone/Desktop/magazzino/tools/launcher_windows.cs:44`.

## Test e riproducibilità

Prove su copie esterne, SQLite sintetico e cluster PostgreSQL 16.15 separato su
loopback. Driver PG con guardia su porta/nome DB e moduli sequenziali. QSettings
isolato; test rete eseguiti fuori dal sandbox che impedisce anche socket TestClient
minimali. Nessun database operativo usato. Le chiavi di aggiornamento dei test sono
effimere. Evidenze: `C:/Users/Simone/Desktop/magazzino/conftest.py:1`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_postgres.py:74`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_correzioni_aggiornamento.py:10`.

Conteggi consolidati e SHA256 XML in `C:/Users/Simone/Desktop/magazzino/docs/ESITI_TEST_MAGAZZINO.json:1`.
**VERIFICATO: 676 superati, 0 falliti, 0 errori, 1 saltato** (caso sequenze PG
parametrizzato su SQLite). La prova dell'eseguibile definitivo ha confermato desktop,
lanciatore con propagazione di configurazione/argomenti, pagina e risorse mobile,
creazione di tre pezzi distinti, retry idempotente, PNG barcode/sezione e scarico.
Server pronto in 1,633 s e arrestato con codice 0. Dettaglio:
`C:/Users/Simone/Desktop/magazzino/docs/DISTRIBUZIONE_MAGAZZINO.json:1`.
I retest sostituiscono gli esiti precedenti; un salto senza URL PG non sostituisce
un test effettivamente eseguito. Parametrizzazioni SQLite/PG restano distinte.
Il solo salto residuo previsto riguarda sequenze PostgreSQL nel caso SQLite.

Evidenze esterne:
`C:/Users/Simone/.codex/visualizations/2026/11/04/01a1a805-2281-70a3-b843-3ab704fdf9a3/copia_temporanea_correzioni`.
Contiene XML/stdout `esiti`/`esiti_pg`, driver `verifica*.py`, benchmark, verifiche
catalogo, screenshot e `eseguibile_qa_finale/esito.json` per la distribuzione finale.

## Restante lavoro che richiede il contesto reale

1. Confermare Windows, architettura e RAM del PC più vecchio. Windows 7/8 o 32 bit
   richiederebbe una linea tecnica compatibile diversa dagli attuali Python/Qt.
2. Attivare tunnel/VPN HTTPS e provare QR, fotocamera, lettura e rete mobile sul
   telefono. Nessuna regola firewall o pubblicazione Internet effettuata.
3. Fornire 24 PNG mancanti e confermare AZ46431 e colori proprietari sconosciuti.
4. Verificare stampante, scanner e leggibilità etichette reali.
5. Provare la versione dopo backup e scegliere la conversione delle giacenze storiche;
   nessuna conversione o migrazione del magazzino reale eseguita durante il lavoro.
6. Preparare feed e release firmata per una prova degli aggiornamenti distribuiti.

Guida: `C:/Users/Simone/Desktop/magazzino/docs/PROVA_E_TELEFONO.md:1`.
