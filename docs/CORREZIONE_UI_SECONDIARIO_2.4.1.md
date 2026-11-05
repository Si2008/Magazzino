# Correzione interfaccia del PC secondario — 2.4.1

Il PC secondario usa ora la stessa finestra e la stessa navigazione del principale: barra superiore, tema chiaro/scuro e schede Inventario, Carico, Scarico, Profili, Avvisi e Commesse. Nelle prime cinque schede è spiegato che il magazzino resta sul PC principale. Commesse rimane utilizzabile per salvare localmente, inviare e verificare la ricezione.

L’avvio esplicitamente secondario non richiede `config.toml`, non legge il database, non avvia backup o servizio barcode locale. Questo corregge il caso in cui l’icona avviava il ruolo principale e mostrava “Impossibile leggere il file config.toml”: per avviare il secondario usare il ruolo salvato oppure `MagazzinoProfili.exe --secondario`. Un avvio configurato come principale continua invece a richiedere la configurazione PostgreSQL.

## Prove

- `magazzino_profili/tests/test_commesse_multiple.py`: **21 superati**, compreso l’avvio applicativo secondario senza configurazione, sei schede e cambio tema.
- `magazzino_profili/tests/test_commesse.py`: **23 superati** nella stessa esecuzione combinata.
- Eseguibile 2.4.1 avviato in modalità secondaria da copia temporanea, con `config.toml` assente e PATH senza Python; processo UI attivo. L’ambiente di prova non aveva accesso DNS al feed GitHub, quindi il controllo aggiornamenti ha scritto un errore di rete nei log; tale errore non ha impedito l’apertura della finestra.
- Sono stati verificati i 1526 file della cartella consegnata con SHA-256. La versione 2.4.0 resta disponibile.

## Percorsi coinvolti

- `magazzino_profili/ui/finestra_principale.py`: modalità secondaria con barra, temi e navigazione condivisi; schermate chiare quando i dati appartengono al principale.
- `magazzino_profili/ui/postazione.py`: finestra secondaria derivata dalla principale e schede informative.
- `magazzino_profili/tests/test_commesse_multiple.py`: regressione di avvio, schede e tema.
- `magazzino_profili/__init__.py`: versione unica avanzata a 2.4.1.
- `README.md`: comportamento e avvio del PC secondario documentati.

La cartella condivisa fra due PC fisici non è stata provata in questa correzione.
