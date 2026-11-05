# Versione telefono su Vercel

Collegare il progetto Vercel esistente magazzino-profili-telefono al repository Si2008/Magazzino, branch di produzione main. La configurazione supporta sia Root Directory vuota (radice repository) sia magazzino_profili/web/vercel. Framework: Other; build: npm run build; output: public.

Conservare la connessione Blob privata e le variabili di ambiente già presenti nel progetto. Le credenziali restano su Vercel. Il database autorevole rimane sul PC, che deve essere acceso e collegato tramite il QR del programma aggiornato.

La build copia soltanto il template telefono e gli asset statici. Il percorso /api/ponte usa la funzione Node esistente.

Un commit su main attiva il deploy solo se il progetto Vercel è effettivamente collegato al repository. La sola presenza dei file GitHub non crea quel collegamento.
