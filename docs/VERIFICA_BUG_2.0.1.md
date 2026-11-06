# Seconda verifica dei bug gravi — 2.0.1

5 novembre 2026. Controllo mirato di carico/scarico, ricevute idempotenti, import V2,
restore Excel/ZIP, scadenze e conversione dei barcode. Non costituisce una prova di
assenza di tutti i bug. Dati, configurazione e backup operativi non utilizzati.

## Bug trovati e corretti

| Gravità | Stato | Problema e correzione | Evidenza |
|---|---|---|---|
| Alta | VERIFICATO prima e dopo la correzione | Il ZIP leggeva l'immagine per archiviarla, poi la rileggeva per il checksum. Una modifica concorrente produceva un manifest incompatibile con il contenuto: ripristino rifiutato. Ora il file viene letto una sola volta; verifica, ZIP e SHA256 usano gli stessi byte. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/archivio.py:19`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/archivio.py:57`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_integrita_archivio.py:22` |
| Alta | VERIFICATO prima e dopo la correzione | Se l'immagine referenziata esisteva ma era danneggiata/non PNG, l'export pubblicava comunque un archivio che il restore avrebbe rifiutato. Ora il contenuto viene verificato prima della pubblicazione e l'errore indica il profilo. Il backup precedente resta intatto. | `C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/archivio.py:19`; `C:/Users/Simone/Desktop/magazzino/magazzino_profili/tests/test_integrita_archivio.py:48` |

La lettura è limitata a 30 MB per immagine; sono ammessi PNG con massimo 25 milioni
di pixel. Si conserva in memoria una sola immagine per volta, evitando di caricare
l'intero catalogo. Non sono cambiati schema DB o formati ZIP. Evidenza:
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/reports/archivio.py:24`.

## Prove

**VERIFICATO:** i due nuovi test fallivano sulla versione precedente. Il primo forza
un cambio dell'immagine durante la creazione dello ZIP; il secondo fornisce un file
non valido e verifica che non sovrascriva il backup precedente. Dopo la correzione:
**53 test superati, 0 falliti, 33 saltati** nei moduli integrità archivio, regressioni
dati e backup Excel. I 33 casi saltati richiedono PostgreSQL o non sono applicabili
a SQLite; non vengono presentati come eseguiti in questa nuova sessione.

XML delle prove prima/dopo, su copia esterna:
`C:/Users/Simone/.codex/visualizations/2026/11/04/01a1a805-2281-70a3-b843-3ab704fdf9a3/copia_temporanea_correzioni/esiti/archivio_prima.xml`,
`C:/Users/Simone/.codex/visualizations/2026/11/04/01a1a805-2281-70a3-b843-3ab704fdf9a3/copia_temporanea_correzioni/esiti/archivio_dopo.xml`.

Il conteggio di 676 test del report precedente riguarda la verifica 2.0.0; non è
stato rieseguito integralmente per questa correzione circoscritta. La nuova build
2.0.1 viene verificata separatamente su configurazione e database sintetici;
l'esito è registrato in `eseguibile_qa_201/esito.json` nella stessa copia esterna.

## Ambito e limiti

Sono emersi bug gravi: il lavoro di questa sessione si è quindi concentrato sulla
loro correzione, come richiesto. La UI desktop/telefono non è stata ridisegnata in
questa versione. Nessun altro bug grave confermato nei percorsi esaminati; ciò non
garantisce che non ne esistano altri.

Restano NON VERIFICABILI qui telefono/fotocamera/stampante reali, PC più vecchio,
magazzino operativo e accesso da rete mobile senza tunnel/VPN HTTPS. La 2.0.1
mantiene i requisiti Windows 10/11 a 64 bit e l'accesso applicativo libero della
2.0.0. Il precedente eseguibile sul Desktop viene conservato; usare la nuova versione.
