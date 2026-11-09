# Prova della versione 2.3.0 e collegamento del telefono

## Avvio dal Desktop

Aprire `C:/Users/Simone/Desktop/MagazzinoProfili-2.3.0.exe`. La cartella
`C:/Users/Simone/Desktop/MagazzinoProfili-2.3.0` deve restare accanto all'eseguibile:
contiene il programma, le librerie e le immagini. La distribuzione in cartella evita
l'estrazione delle librerie a ogni avvio.

Il lanciatore riutilizza `C:/Users/Simone/Desktop/magazzino/config.toml` se non esiste
una configurazione nella nuova cartella. Non contiene password incorporate.
Il programma richiede PostgreSQL già configurato. Al primo avvio con uno schema
precedente crea e verifica il backup prima delle migrazioni. Se il backup fallisce,
interrompe l'aggiornamento e mostra l'errore. Non sono state eseguite migrazioni sul
magazzino operativo durante lo sviluppo.

Evidenze: `C:/Users/Simone/Desktop/magazzino/tools/launcher_windows.cs:44`,
`C:/Users/Simone/Desktop/magazzino/tools/compila_windows.py:30`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:98`.

Non avviare contemporaneamente vecchia e nuova versione sullo stesso magazzino.
Per il ritorno alla versione precedente dopo una migrazione, utilizzare il backup
preventivo su una destinazione separata e verificarlo: cambiare soltanto eseguibile
non ripristina lo schema. L'avvio automatico di Windows si abilita soltanto dalla
voce del menu Strumenti e backup, dopo aver verificato la versione nuova.

## Prova delle operazioni

1. In Profili verificare i codici esistenti e aprire la sezione. I 211 PNG disponibili
   sono associati per codice; non occorre assegnarli a ogni pezzo.
2. In Carico inserire profilo, colore, lunghezza, vassoio e numero di pezzi. Ogni
   pezzo riceve un barcode seriale differente. Stampare e applicare una sola etichetta
   a ciascun pezzo.
3. Scaricare un'etichetta: soltanto quel pezzo deve risultare Scaricato, con saldo
   zero e data/ora. Un rientro usa la stessa etichetta.
4. Prima di convertire le giacenze storiche aggregate, usare Strumenti e backup → Archivio dati
   e immagini ZIP. La conversione guidata produce anche l'elenco delle nuove
   etichette. I record storici non sono stati convertiti automaticamente.
5. Per PC lenti disattivare Strumenti e backup → Animazioni di transizione. Inventario mostra
   200 righe per pagina; Avvisi 30 materiali per pagina. Sui monitor piccoli sono
   disponibili barre di scorrimento, senza ridurre la dimensione dei testi.

Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/services/pezzi_unitari.py:11`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:300`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:220`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/avvisi.py:164`.

## Telefono anche su rete dati mobile

La pagina è https://magazzino-profili-telefono.vercel.app e non richiede login.
Aprire Collega telefono sul PC: il programma avvia un canale HTTPS in uscita verso
Vercel e genera il QR con l'identificativo della sessione del PC. Scansionare quel
QR, anziché aprire soltanto la pagina senza parametri. Non occorre aprire porte
sul router o installare programmi di tunnel. Dopo un riavvio generare un nuovo QR.
Il database resta sul PC; richieste e risposte passano temporaneamente nel ponte
privato Vercel. Il collegamento richiede Internet e il PC acceso. Il canale inattivo
si ferma dopo due minuti senza richieste; Collega telefono lo riattiva.

Il ponte usa Vercel Functions e Blob privato per la coda temporanea. Le credenziali
tecniche dello storage restano su Vercel e non sono inserite nell'applicazione o
nel QR. Non sono credenziali utente: l'accesso applicativo resta libero, con tutti
i privilegi per chi usa il collegamento. Le quote del piano Vercel limitano il
numero di richieste disponibili: verificare l'uso effettivo prima dell'impiego
continuativo. Nessun upgrade di abbonamento è stato richiesto.

Fonti: [storage privato](https://vercel.com/docs/vercel-blob/private-storage),
[quote e prezzi](https://vercel.com/docs/vercel-blob/usage-and-pricing).

## Compatibilità dei PC vecchi

La build attuale usa Python 3.14 e PySide6/Qt 6.12, per Windows a 64 bit.
Richiede Windows 10 compatibile o Windows 11; **non è una build per Windows 7,
Windows 8 o Windows a 32 bit**. Qt indica Windows 10 1809 o successivo nella propria
[tabella di supporto](https://doc.qt.io/qt-6.12/windows.html); Python 3.14 richiede
[Windows 10 o successivo](https://docs.python.org/3.14/using/windows.html).
La compatibilità del PC più vecchio e il consumo con la sua RAM restano da provare.
Non è necessario installare Python per usare l'eseguibile; PostgreSQL e la sua
configurazione restano necessari. Non sono inclusi un servizio tunnel né un installer
di PostgreSQL.

## Dati e diagnostica

Configurazione effettiva: quella indicata da `MAGAZZINO_CONFIG`, oppure quella
ricercata dal lanciatore. Backup automatici: cartella `[backup] cartella`, relativa
alla configurazione. Log: `%LOCALAPPDATA%/magazzino_profili/app.log` e
`telefono-server.log`. Preferenze grafiche: QSettings dell'utente Windows.
Un eventuale errore di backup o configurazione va corretto prima di riprovare una
migrazione; conservare il vecchio eseguibile e i backup.

Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/db/config.py:65`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/main.py:231`,
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/server_telefono.py:40`.


Per la lista di prelievo delle commesse consultare `COMMESSE_2.3.0.md`.
