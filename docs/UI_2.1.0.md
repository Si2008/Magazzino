# Interfacce desktop e telefono — 2.1.0

5 novembre 2026. Aggiornamento grafico incrementale, senza modifiche allo schema
o alle regole di magazzino. Nessun dato/configurazione operativo utilizzato nelle prove.

## Desktop — VERIFICATO

- Inventario con ricerca sempre disponibile, filtri aggiuntivi apribili e dettagli
  laterali richiudibili. La tabella utilizza inizialmente l'intera larghezza.
  Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:399`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:548`.
- Colonna profilo larga inizialmente 240 px e ridimensionabile: il codice non viene
  compresso nello spazio residuo dalle altre colonne. Per le colonne eccedenti
  resta lo scorrimento orizzontale della tabella. Evidenza:
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tabella_pezzi.py:502`.
- Margini, riepiloghi e barre più compatti, mantenendo i testi principali a 20 px;
  form Carico/Scarico da 600 px e form Profili da 456 px. La finestra è stata
  verificata a 1024×768 e 1280×760 con entrambi i temi. Evidenze:
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tema.py:37`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tema.py:66`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:159`.
- Menu «Strumenti e backup», barra superiore correttamente stilizzata come QFrame,
  focus tastiera visibile e pulsanti di apertura evidenziati. Evidenze:
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:240`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:265`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/tema.py:425`.

## Telefono — VERIFICATO nella simulazione browser

- Barra inferiore fissa con Al PC, Consulta, Rientro, Scarico e Nuovi; titolo che
  descrive l'operazione corrente. «Rientro» conserva il barcode del pezzo esistente;
  «Nuovi» crea etichette distinte. Evidenze:
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/templates/scansione.html:17`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/static/scansione.js:91`.
- Form organizzato in tre sezioni numerate: profilo, pezzi, collocazione. Testi
  secondari più leggibili, campi alti almeno 56 px, navigazione con tasti da 66 px.
  Evidenze: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/templates/scansione.html:30`,
  `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/static/telefono.css:10`.
- Tema blu coerente con il desktop, versioni chiara/scura, stato rete più leggibile
  e spazio riservato alla barra inferiore. Nessun nuovo font scaricato, libreria
  grafica o effetto di sfocatura. Animazione d'ingresso dei pannelli disattivata.
  Evidenza: `C:/Users/Simone/Desktop/magazzino/magazzino_profili/web/static/telefono.css:11`.

## Verifica e prestazioni

**VERIFICATO:** 44 test superati negli otto moduli UI/client selezionati, zero
fallimenti/errori/salti. Copia esterna: `verifica_ui_210.py`, `risultati_ui_210.json`
e XML `esiti/test_ui_*.xml`, `test_inventario_colori.xml`,
`test_regressione_fase3b_ui.xml`, `test_web_client_javascript.xml`.
Le prove PostgreSQL complete delle versioni precedenti non sono conteggiate come
nuovamente eseguite per questa modifica grafica.

**VERIFICATO:** render mobile a 320×740 e 390×844, temi chiaro/scuro; nessuna
fuoriuscita orizzontale rilevata (contenuto 305 e 375 px, rispettivamente).
Screenshot di esempio:
`C:/Users/Simone/Desktop/magazzino/docs/UI_2.1.0_PC.png`,
`C:/Users/Simone/Desktop/magazzino/docs/UI_2.1.0_TELEFONO.png`.

**VERIFICATO:** su 12.000 pezzi sintetici, query pagina 200 righe in 0,0206 s e
costruzione finestra in 0,2270 s, oltre all'importazione delle librerie. Resta la
creazione differita delle schede, senza nuove query periodiche o effetti Qt pesanti.
È una misura singola su questo PC, non una garanzia sul PC più vecchio.
Evidenze: `benchmark_finale.json` nella copia esterna e
`C:/Users/Simone/Desktop/magazzino/magazzino_profili/ui/finestra_principale.py:358`.

Cartella delle prove:
`C:/Users/Simone/.codex/visualizations/2026/11/04/01a1a805-2281-70a3-b843-3ab704fdf9a3/copia_temporanea_correzioni`.
La prova della build è registrata separatamente in `eseguibile_qa_210/esito.json`.

**NON VERIFICABILE qui:** tastiera virtuale, fotocamera e browser su telefono fisico,
resa su hardware vecchio e rete mobile senza tunnel HTTPS/VPN. Accesso applicativo
sempre libero; requisiti della build invariati: Windows 10/11 a 64 bit.
