# Configurazione del PC principale — 2.4.2

La schermata “Configura postazione” consentiva di salvare il ruolo principale anche quando non era stato scelto un file `config.toml`. All’avvio successivo la ricerca falliva e compariva il messaggio “Impossibile leggere il file config.toml”, come nell’immagine inviata.

Ora il ruolo principale non può essere confermato finché non si seleziona un TOML esistente, leggibile e con la sezione `[database]` completa. Il selettore conserva il percorso in QSettings e l’avvio lo usa come configurazione database. La configurazione non viene creata o sovrascritta dall’app, perché host, database, utente e password dipendono dall’installazione PostgreSQL dell’utente. Sul PC secondario il file non serve.

Per questo PC: nella schermata **Strumenti → Configura postazione e cartella di rete**, lascia **PC principale**, premi **Seleziona config.toml del PC principale…** e scegli il file TOML già usato dal magazzino. Nel workspace corrente esiste già `C:\Users\Simone\Desktop\magazzino\config.toml`; selezionalo tramite la finestra. Il file contiene credenziali, quindi non va copiato nella cartella pubblica o inviato.

## Prove

- `test_commesse_multiple.py` e `test_commesse.py`: 46 superati insieme. I casi nuovi verificano file assente, TOML incompleto e configurazione valida.
- Nessun database operativo è stato aperto o modificato durante i test.
- La build 2.4.2 viene consegnata con il launcher e la cartella completa. Il principale deve ancora raggiungere il proprio server PostgreSQL; la validazione del TOML non verifica credenziali, rete o stato del servizio.

La build è pubblicata come [release 2.4.2](https://github.com/Si2008/Magazzino/releases/tag/v2.4.2), ora la più recente. Sul Desktop sono disponibili i collegamenti **PC principale 2.4.2** e **PC secondario 2.4.2**, oltre all’eseguibile e alla cartella completa. I 1526 file sono stati verificati; le versioni precedenti sono conservate. Evidenza: `docs/CONSEGNA_MAGAZZINO_2.4.2.json:1`.

Per il principale, il selettore può puntare al file già presente sul Desktop nel progetto `magazzino/config.toml`. Selezionalo dalla finestra; non copiare la configurazione nel repository pubblico.

Evidenze nel codice: `magazzino_profili/ui/postazione.py:1`, `magazzino_profili/services/postazione.py:1`, `magazzino_profili/tests/test_commesse_multiple.py:167`.
