# Magazzino Profili 2.4.6

La scansione da telefono delle etichette Code 128 lunghe ora usa l'intera inquadratura e una lettura periodica del fotogramma a risoluzione maggiore. Il precedente ritaglio e la riduzione del video alla larghezza dello schermo potevano impedire la lettura dei seriali `MP-…` generati dal programma.

- Autofocus continuo e pulsante luce quando supportati dalla fotocamera.
- Alternativa **Leggi una foto del barcode**, decodificata sul telefono: la foto non viene caricata sul server.
- Arresto corretto della fotocamera, anche durante l'avvio; una lettura produce una sola richiesta.
- Scarico con dettaglio e conferma; barcode univoco per ogni pezzo e chiave contro richieste duplicate.
- Inclusi gli interventi precedenti: pannelli desktop ridimensionabili, elenco profili più grande, immagini automatiche, commesse, export per colore e installer Windows per utente.

**Test di questo rilascio:** 813 Python superati, 1 skip previsto solo su SQLite; 24 JavaScript superati; 5 prove browser superate con decoder reale, foto/video e API sintetiche. Verificati anche backup, migrazione e recupero su PostgreSQL di prova. Nessuna modifica al magazzino operativo durante i test.

**Limiti dichiarati:** fotocamera fisica e installazione su PC/VM pulito non collaudate qui. La prova sintetica riproduce e risolve il mancato riconoscimento del seriale lungo; messa a fuoco, riflessi e qualità di stampa richiedono la prova sul telefono reale. Restano avvisi PySide nel teardown dei test, documentati negli esiti.

Per provare la pagina aggiornata, chiudere la vecchia scheda sul telefono e riaprirla dal QR del programma. Scegliere **Scarico**, avviare la fotocamera e inquadrare tutte le barre, inclusi i margini bianchi; confermare il pezzo mostrato. Se necessario usare la lettura da foto.

Installazione: scaricare `MagazzinoProfili-2.4.6-setup.exe`, chiudere il programma anche nell'area di notifica e avviare il setup. Gli aggiornamenti conservano i dati. Il PC principale richiede PostgreSQL già configurato; l'installer include Python/Qt, non il server database. Il setup non ha firma Authenticode; il manifest degli aggiornamenti è firmato Ed25519. Istruzioni complete in [guida installer](../installer/README.md).

SHA-256 del setup: `02cd614e9f27b8454a31a3fd9f7347b4407aade442897b70b876f102915d538a`.

Evidenze nel sorgente: `magazzino_profili/web/static/scansione.js` (`configurazioneLettore`, `configurazioneCamera`, `avviaAltaDefinizione`, `leggiFoto`); test in `magazzino_profili/tests/js/scansione.test.mjs` e `tools/verifica_barcode_browser.cjs`; risultati dettagliati in `docs/ESITI_RILASCIO_2.4.6.json`.

La pubblicazione comprende i sorgenti correnti, le risorse del programma, i test e la documentazione tecnica. Configurazioni reali, database, backup, chiavi private, documenti personali e PDF delle commesse rimangono locali. Il repository di lavoro originale non viene resettato: la pubblicazione usa un checkout separato della repository Si2008/Magazzino.

Riferimento tecnico: [configurazione fotocamera Html5Qrcode](https://scanapp.org/html5-qrcode-docs/docs/apis/interfaces/Html5QrcodeCameraScanConfig) e [API di lettura](https://scanapp.org/html5-qrcode-docs/docs/apis/classes/Html5Qrcode).
