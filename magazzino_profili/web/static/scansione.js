"use strict";
// Accesso libero: nessun token e nessuna credenziale. La richiesta pendente
// viene conservata nella sola scheda per poter riprendere dopo un reload.
const STATO = {attivo:true, ruolo:"AMMINISTRATORE", modalita:null, scanner:null,
  in_corso:false, destinatario:null, pendente:null, storico:[], immagini:[], remoto:false};
globalThis.STATO = STATO;
const $ = id => document.getElementById(id);
const TIMEOUT_RICHIESTA_MS = 15000;
let timerPing = null, timerProfili = null;
function indirizzoAPI(percorso) {
  if(!percorso.startsWith("/api/"))throw new Error("Percorso del servizio non valido");
  return percorso;
}
function stessaSessione(pendente){return (pendente.destinatario||null)===STATO.destinatario;}
async function fetchPonte(percorso,opzioni={}){
  indirizzoAPI(percorso);
  if(!STATO.remoto)return fetch(percorso,opzioni);
  if(!STATO.destinatario)throw new Error("Apri il QR del programma sul PC");
  const id=identificativo();
  const inviata=await fetch("/api/ponte",{method:"POST",signal:opzioni.signal,headers:{"Content-Type":"application/json"},cache:"no-store",credentials:"omit",
    body:JSON.stringify({pc:STATO.destinatario,id,metodo:opzioni.method||"GET",percorso,dati:opzioni.body?JSON.parse(opzioni.body):null})});
  if(!inviata.ok)return inviata;
  while(true){
    await attendi(700);
    const r=await fetch("/api/ponte?pc="+encodeURIComponent(STATO.destinatario)+"&id="+encodeURIComponent(id),{signal:opzioni.signal,cache:"no-store",credentials:"omit"});
    if(r.status===202)continue;
    if(!r.ok)return r;
    const corpo=await r.json();
    return new Response(Uint8Array.from(atob(corpo.contenuto),c=>c.charCodeAt(0)),{status:corpo.stato,headers:{"Content-Type":corpo.tipo}});
  }
}
const attendi = ms => new Promise(resolve => setTimeout(resolve, ms));
function identificativo() {
  return globalThis.crypto?.randomUUID?.() || (Date.now().toString(36) + "-" + Math.random().toString(36).slice(2));
}
function visibile(id, valore) { const nodo=$(id); if(nodo) nodo.hidden=!valore; }
function scrivi(id, testo) { const nodo=$(id); if(nodo) nodo.textContent=testo; }
function statoRete(testo, ok) {
  scrivi("stato-rete", testo);
  if($("indicatore-rete")) $("indicatore-rete").className="pallino " + (ok ? "ok":"no");
}
async function inviaRichiesta(url, opzioni, esitoIncerto) {
  const controllo=new AbortController();
  const timer=setTimeout(()=>controllo.abort(),TIMEOUT_RICHIESTA_MS);
  try {
    const risposta=await fetchPonte(indirizzoAPI(url),{...opzioni,signal:controllo.signal,cache:"no-store",credentials:"omit"});
    let corpo;
    try { corpo=await risposta.json(); }
    catch(e) { if(risposta.ok) throw new TypeError("Risposta incompleta"); corpo={}; }
    if(!risposta.ok) {
      const errore=new Error(typeof corpo.detail === "string" ? corpo.detail : "Richiesta non riuscita ("+risposta.status+").");
      errore.codice=risposta.status; throw errore;
    }
    return corpo;
  } catch(originale) {
    if(originale.codice) throw originale;
    const errore=new Error(esitoIncerto
      ? "Connessione interrotta: esito incerto. Tocca «Riprendi la stessa richiesta»: il codice di richiesta evita un doppio movimento. Puoi verificare la giacenza con Consulta dopo aver risolto la richiesta."
      : "Connessione assente o interrotta: riprovare tra poco.");
    errore.codice=0; errore.esitoIncerto=Boolean(esitoIncerto); throw errore;
  } finally { clearTimeout(timer); }
}
async function chiedi(url,payload) {
  const headers={"Content-Type":"application/json"};

  return inviaRichiesta(url,{method:"POST",headers,body:JSON.stringify(payload)},
    ["/api/carico","/api/scarico","/api/scansione","/api/pezzi"].includes(url));
}
async function chiediGet(url) {
  const headers={};
  return inviaRichiesta(url,{method:"GET",headers},false);
}
async function ping() {
  if(!STATO.attivo) return;
  try {
    if(STATO.ruolo==="SOLA_LETTURA") { await chiediGet("/api/salute"); statoRete("Servizio raggiungibile · sola lettura",true); return; }
    const q=STATO.destinatario ? "?destinatario="+encodeURIComponent(STATO.destinatario) : "";
    const risposta=await chiedi("/api/telefono/ping"+q,{});
    statoRete(STATO.destinatario ? (risposta.pc_collegato ? "PC collegato · pronto a ricevere" : "Servizio online · PC non in ascolto") : "Servizio online · operazioni dirette disponibili",true);
  } catch(e) { statoRete("Collegamento interrotto",false);  }
}
function avviaPing(){fermaPing();ping();timerPing=setInterval(ping,10000);}
function fermaPing(){if(timerPing){clearInterval(timerPing);timerPing=null;}}
function pulisciImmagini(){for(const url of STATO.immagini) URL.revokeObjectURL(url);STATO.immagini=[];}
function esci() {
  STATO.attivo=!STATO.attivo;
  if(!STATO.attivo){fermaPing();STATO.in_corso=false;fermiScanner();statoRete("Collegamento in pausa",false);}
  else avviaPing();
  scrivi("btn-esci",STATO.attivo?"Pausa":"Riprendi");
}
function conservaPendente(){
  try {
    if(STATO.pendente) globalThis.sessionStorage?.setItem("magazzino_richiesta_pendente",JSON.stringify({...STATO.pendente,destinatario:STATO.destinatario}));
    else globalThis.sessionStorage?.removeItem("magazzino_richiesta_pendente");
  }catch(e){/* memoria del browser non disponibile: la richiesta resta in memoria */}
}
function mostraMessaggio(testo,classe) { const nodo=$("esito");nodo.textContent=testo;nodo.className="esito"+(classe?" "+classe:""); }
function registraStorico(testo) {
  STATO.storico.unshift({testo,ora:new Date().toLocaleTimeString("it-IT",{hour:"2-digit",minute:"2-digit"})});
  STATO.storico=STATO.storico.slice(0,20);
  const lista=$("lista-storico");if(!lista?.replaceChildren) return;
  lista.replaceChildren();visibile("storico-vuoto",false);
  for(const voce of STATO.storico){const li=document.createElement("li"),b=document.createElement("b"),small=document.createElement("small");b.textContent=voce.testo;small.textContent=voce.ora;li.append(b,small);lista.append(li);}
}
function scegliModalita(modo) {
  if(STATO.in_corso || STATO.pendente) {mostraMessaggio("Prima completa o riprendi la richiesta in corso.","errore");return;}
  fermiScanner();STATO.modalita=modo;
  for(const b of document.querySelectorAll("[data-modo]")) b.setAttribute("aria-pressed",String(b.dataset.modo===modo));
  visibile("parametri-movimento",modo==="carico"||modo==="scarico");
  visibile("form-nuovo",modo==="nuovo");visibile("zona-scanner",modo!=="nuovo");visibile("barcode-creati",false);
  const note={lettore:"Lettore PC: in Carico compila il pezzo; in Scarico esegue l'uscita con quantità e causale impostate sul PC. Il telefono aspetta la conferma.",consulta:"Leggi un barcode per vedere profilo, colore, lunghezza, vassoio e stato. Nessuna modifica.",scarico:"Scansiona il singolo pezzo da scaricare. Vedrai il dettaglio prima della conferma. Un'etichetta unitaria scarica un solo pezzo.",carico:"Rientro di un pezzo già etichettato: il suo barcode resta lo stesso. Per nuovi pezzi usa «Nuovi pezzi».",nuovo:"Ogni pezzo fisico riceve un barcode seriale univoco. Puoi creare più pezzi uguali: le etichette saranno tutte diverse."};
  scrivi("nota-modalita",note[modo]);mostraMessaggio("");
  const titoli={lettore:"Il telefono diventa lettore.",consulta:"Tutte le informazioni del pezzo.",scarico:"Scarica un pezzo.",carico:"Rimetti un pezzo in magazzino.",nuovo:"Nuovi pezzi, nuove etichette."};
  scrivi("titolo-operazione",titoli[modo]);
  if(modo==="nuovo") cercaProfili();
}
async function fermiScanner() {
  const scanner=STATO.scanner;STATO.scanner=null;
  if(scanner){try{await scanner.stop();await scanner.clear();}catch(e){/* può essere già fermo */}}
  visibile("camera-riposo",true);visibile("btn-ferma",false);scrivi("btn-scansiona","Apri fotocamera");
}
async function avviaScansione(modalita) {
  if(!STATO.attivo||STATO.in_corso||STATO.pendente) return;
  await fermiScanner();STATO.modalita=modalita;STATO.in_corso=true;
  if(!globalThis.isSecureContext || !globalThis.navigator?.mediaDevices?.getUserMedia) {
    STATO.in_corso=false;mostraMessaggio("Fotocamera non disponibile: apri l'indirizzo HTTPS con certificato riconosciuto in Safari o Chrome e consenti la fotocamera. Puoi inserire il barcode a mano.","errore");return;
  }
  try {
    const scanner=new Html5Qrcode("lettore-barcode");STATO.scanner=scanner;
    visibile("camera-riposo",false);visibile("btn-ferma",true);scrivi("btn-scansiona","Fotocamera attiva…");
    await scanner.start({facingMode:"environment"},{fps:8,qrbox:(w,h)=>({width:Math.min(w-24,280),height:Math.min(h-24,130)})},testo=>onLettura(testo),()=>{});
    mostraMessaggio("Punta la fotocamera sul barcode del pezzo.");
  } catch(e) {STATO.in_corso=false;await fermiScanner();mostraMessaggio("Impossibile avviare la fotocamera. Consenti l'accesso nelle impostazioni del browser, controlla HTTPS o usa l'inserimento manuale. Dettaglio: "+String(e),"errore");}
}
async function onLettura(testo) {
  if(!STATO.in_corso) return;STATO.in_corso=false;await fermiScanner();
  if(STATO.modalita==="consulta"){try{await consultaBarcode(testo.trim());}catch(e){/* messaggio già mostrato */}}
  else await inviaMovimento(testo.trim());
}
function descrivi(corpo){return corpo.codice_profilo+" — "+corpo.descrizione+"\nColore: "+corpo.colore+" · "+corpo.lunghezza_mm+" mm\nGiacenza: "+corpo.quantita_giacenza+"\nVassoio: "+(corpo.numero_vassoio??"—")+"\nStato: "+(corpo.stato??"—")+(corpo.unitario?"\nBarcode del singolo pezzo":"\nBarcode storico di giacenza aggregata");}
async function consultaBarcode(barcode) {
  if(!barcode){mostraMessaggio("Nessun barcode letto.","errore");return;}
  mostraMessaggio("Consultazione in corso…");
  try{const corpo=await chiediGet("/api/pezzi/"+encodeURIComponent(barcode));mostraMessaggio(descrivi(corpo),"successo");return corpo;}
  catch(e){mostraMessaggio(e.message,"errore");throw e;}
}
async function inviaMovimento(barcode) {
  if(!STATO.attivo||STATO.in_corso) return;
  if(STATO.pendente){mostraMessaggio("Richiesta ancora in corso: usa «Riprendi la stessa richiesta».","errore");return;}
  barcode=(barcode||"").trim().toUpperCase();if(!barcode){mostraMessaggio("Nessun barcode letto.","errore");return;}
  const modo=STATO.modalita;
  if(!["lettore","carico","scarico"].includes(modo)) return;
  let payload={barcode};
  if(modo==="lettore") {
    if(!STATO.destinatario){mostraMessaggio("Apri prima il QR del PC: manca il destinatario della scansione.","errore");return;}
    payload.destinatario=STATO.destinatario;
  } else {
    const testo=$("campo-quantita").value.trim(),q=/^[0-9]+$/.test(testo)?Number(testo):NaN;
    if(!Number.isSafeInteger(q)||q<=0||q>2147483647){mostraMessaggio("Inserire una quantità intera e maggiore di zero.","errore");return;}
    payload.quantita=q;const causale=$("campo-causale").value.trim();if(causale)payload.causale=causale;
    // Conferma sul dispositivo reale. La guardia blocca doppi tap anche durante il GET.
    if(typeof globalThis.confirm==="function") {
      STATO.in_corso=true;
      try {
        const pezzo=await chiediGet("/api/pezzi/"+encodeURIComponent(barcode));
        if(pezzo.unitario && q!==1) {mostraMessaggio("Questo barcode identifica un pezzo: la quantità deve essere 1.","errore");return;}
        if(!globalThis.confirm((modo==="scarico"?"SCARICO":"RIENTRO")+" di "+q+" pezzo/i\n\n"+descrivi(pezzo)+"\n\nConfermi l'operazione?")) return;
      } catch(e){mostraMessaggio(e.message,"errore");return;}
      finally{STATO.in_corso=false;}
    }
  }
  payload.richiesta_id=identificativo();STATO.pendente={url:modo==="lettore"?"/api/scansione":"/api/"+modo,payload,modo};
  conservaPendente();await riprendiRichiesta();
}
async function attendiConferma(richiesta,corpo) {
  for(let i=0;i<15;i++) {
    if(!STATO.attivo || STATO.pendente!==richiesta) return false;
    const esito=await chiediGet("/api/scansioni/"+corpo.id);
    if(esito.esito!=="in_attesa") {
      const ok=["completata","compilata"].includes(esito.esito);
      mostraMessaggio(esito.dettaglio+"\nBarcode: "+esito.barcode,ok?"successo":"errore");
      registraStorico(esito.barcode+" · "+esito.dettaglio);return true;
    }
    mostraMessaggio("Barcode ricevuto dal server. In attesa della conferma dal PC…");await attendi(1000);
  }
  mostraMessaggio("Il PC non ha ancora confermato. Apri Carico o Scarico sul PC e tocca «Riprendi la stessa richiesta». Il barcode non viene inviato due volte.","errore");return false;
}
async function riprendiRichiesta() {
  if(!STATO.attivo||STATO.in_corso||!STATO.pendente) return;
  const richiesta=STATO.pendente;STATO.in_corso=true;visibile("btn-riprova",false);
  mostraMessaggio("Invio in corso…");
  try {
    const corpo=richiesta.risposta || await chiedi(richiesta.url,richiesta.payload);
    if(STATO.pendente!==richiesta) return;
    richiesta.risposta=corpo;conservaPendente();
    if(richiesta.modo==="lettore") {
      if(!await attendiConferma(richiesta,corpo)) return;
    } else if(richiesta.modo==="nuovo") {
      mostraMessaggio(corpo.dettaglio,"successo");registraStorico(corpo.dettaglio);
      await mostraBarcodeCreati(corpo.pezzi);
    } else {mostraMessaggio((corpo.dettaglio||"Movimento registrato.")+"\n"+descrivi(corpo),"successo");registraStorico(corpo.barcode+" · "+richiesta.modo);}
    STATO.pendente=null;
  } catch(e) {
    mostraMessaggio(e.message,"errore");

    // Un errore applicativo 4xx rifiuta la richiesta senza modifiche.
    if(e.codice>=400 && e.codice<500) STATO.pendente=null;
  } finally {STATO.in_corso=false;visibile("btn-riprova",Boolean(STATO.pendente));conservaPendente();}
}
async function cercaProfili(){
  if(!STATO.attivo || STATO.modalita!=="nuovo") return;
  const valore=$("nuovo-profilo").value.trim();
  try{const righe=await chiediGet("/api/profili?cerca="+encodeURIComponent(valore));
    if($("nuovo-profilo").value.trim()!==valore)return;
    const lista=$("elenco-profili");lista.replaceChildren();
    for(const riga of righe){const o=document.createElement("option");o.value=riga.codice;o.textContent=riga.descrizione;lista.append(o);}
    const profilo=righe.find(r=>r.codice===valore.toUpperCase().replace(/\s/g,""));
    visibile("anteprima-sezione",Boolean(profilo?.url_immagine));
    if(profilo?.url_immagine){
      if(!STATO.remoto)$("immagine-profilo").src=profilo.url_immagine;
      else {
        const controllo=new AbortController(),timer=setTimeout(()=>controllo.abort(),15000);
        try{const risposta=await fetchPonte(profilo.url_immagine,{method:"GET",signal:controllo.signal});
          if(risposta.ok && $("nuovo-profilo").value.trim()===valore){const url=URL.createObjectURL(await risposta.blob());STATO.immagini.push(url);$("immagine-profilo").src=url;}
        }finally{clearTimeout(timer);}
      }
    }
    scrivi("dettaglio-profilo",profilo?profilo.descrizione+" · "+profilo.peso_kg_per_metro+" kg/m":"Seleziona un profilo esistente o apri «Crea l'anagrafica».");
  }catch(e){scrivi("dettaglio-profilo",e.message);}
}
function interoCampo(id,min,max){const t=$(id).value.trim();if(!/^[0-9]+$/.test(t))throw new Error("Controlla i numeri: usare valori interi.");const n=Number(t);if(!Number.isSafeInteger(n)||n<min||n>max)throw new Error("Valore numerico fuori intervallo.");return n;}
async function creaPezzi(evento){
  evento.preventDefault();if(!STATO.attivo||STATO.in_corso||STATO.pendente)return;
  try {
    const payload={richiesta_id:identificativo(),codice_profilo:$("nuovo-profilo").value.trim().toUpperCase(),colore:$("nuovo-colore").value.trim().toUpperCase(),lunghezza_mm:interoCampo("nuovo-lunghezza",1,2147483647),quantita:interoCampo("nuovo-numero",1,1000),numero_vassoio:$("nuovo-vassoio").value.trim(),ubicazione:$("nuovo-ubicazione").value.trim()||null,scorta_minima:$("nuovo-scorta").value.trim()?interoCampo("nuovo-scorta",0,2147483647):null,causale:$("nuovo-causale").value.trim()};
    if(!payload.codice_profilo||!payload.colore||!payload.numero_vassoio||!payload.causale)throw new Error("Compila profilo, colore, vassoio e causale.");
    if($("crea-anagrafica").checked){const t=$("nuovo-peso").value.trim().replace(",",".");if(!/^[0-9]+(?:\.[0-9]+)?$/.test(t)||Number(t)<=0)throw new Error("Peso kg/m non valido.");payload.nuovo_profilo={descrizione:$("nuovo-descrizione").value.trim(),peso_kg_per_metro:Number(t),lunghezza_standard_mm:interoCampo("nuovo-standard",1,2147483647)};if(!payload.nuovo_profilo.descrizione)throw new Error("Descrizione obbligatoria per il nuovo profilo.");}
    if(!globalThis.confirm("Creare "+payload.quantita+" pezzi di "+payload.codice_profilo+", "+payload.colore+", "+payload.lunghezza_mm+" mm?\nOgni pezzo avrà un barcode diverso. Carico iniziale nel vassoio "+payload.numero_vassoio+"."))return;
    STATO.pendente={url:"/api/pezzi",payload,modo:"nuovo"};conservaPendente();await riprendiRichiesta();
  }catch(e){mostraMessaggio(e.message,"errore");}
}
async function mostraBarcodeCreati(pezzi){
  pulisciImmagini();const lista=$("lista-barcode");lista.replaceChildren();visibile("barcode-creati",true);
  for(const pezzo of pezzi){const card=document.createElement("div"),titolo=document.createElement("strong"),codice=document.createElement("code"),b=document.createElement("button");card.className="etichetta-pezzo";titolo.textContent=pezzo.codice_profilo+" · "+pezzo.colore+" · "+pezzo.lunghezza_mm+" mm";codice.textContent=pezzo.barcode;b.textContent="Visualizza e salva etichetta PNG";b.type="button";card.append(titolo,document.createElement("br"),codice,b);lista.append(card);
    b.addEventListener("click",async()=>{b.disabled=true;try{const controllo=new AbortController(),timer=setTimeout(()=>controllo.abort(),15000);let risposta;try{risposta=await fetchPonte(indirizzoAPI("/api/barcode/"+encodeURIComponent(pezzo.barcode)+"/immagine"),{signal:controllo.signal,cache:"no-store"});}finally{clearTimeout(timer);}if(!risposta.ok)throw new Error("Etichetta non disponibile: riprova.");const url=URL.createObjectURL(await risposta.blob());STATO.immagini.push(url);const img=document.createElement("img"),a=document.createElement("a");img.src=url;img.alt="Barcode "+pezzo.barcode;a.href=url;a.download=pezzo.barcode+".png";a.textContent="Salva PNG ↓";card.append(img,a);b.remove();}catch(e){mostraMessaggio(e.message,"errore");b.disabled=false;}});
  }
}
document.addEventListener("DOMContentLoaded",()=>{
  $("btn-tema").addEventListener("click",()=>{const radice=document.documentElement;const scuro=radice.dataset.tema?radice.dataset.tema==="scuro":globalThis.matchMedia("(prefers-color-scheme:dark)").matches;radice.dataset.tema=scuro?"chiaro":"scuro";});
  const pc=new URLSearchParams(globalThis.location.search).get("pc");STATO.destinatario=/^[a-f0-9]{32}$/.test(pc||"")?pc:null;
  STATO.remoto=Boolean(globalThis.location.hostname?.endsWith(".vercel.app"));
  if(STATO.remoto && !STATO.destinatario){
    mostraMessaggio("Apri questa pagina dal QR del programma sul PC: il codice contiene il collegamento al tuo magazzino.","errore");
    scrivi("titolo-operazione","Collegati dal QR del PC.");
    scrivi("nota-modalita","Nel programma sul PC premi Collega telefono e scansiona il QR: la pagina si collegherà al tuo magazzino.");
    for(const b of document.querySelectorAll("button"))if(b.id!=="btn-tema")b.disabled=true;
    statoRete("In attesa del QR del PC",false);STATO.attivo=false;return;
  }
  try {
    const salvata=JSON.parse(globalThis.sessionStorage?.getItem("magazzino_richiesta_pendente")||"null");
    if(salvata && ["/api/pezzi","/api/carico","/api/scarico","/api/scansione"].includes(salvata.url) && typeof salvata.payload?.richiesta_id==="string"){
      if(stessaSessione(salvata))STATO.pendente=salvata;
      else globalThis.sessionStorage?.setItem("magazzino_richiesta_altro_pc",JSON.stringify(salvata));
    }
  }catch(e){/* dato assente o non valido: nessuna richiesta automatica */}
  if(STATO.pendente){STATO.modalita=STATO.pendente.modo;visibile("btn-riprova",true);mostraMessaggio("C'è una richiesta della precedente apertura da verificare. Tocca «Riprendi la stessa richiesta» prima di procedere.","errore");}
  else scegliModalita(STATO.destinatario?"lettore":"scarico");
  avviaPing();visibile("anagrafica-nuova",true);
  for(const b of document.querySelectorAll("[data-modo]"))b.addEventListener("click",()=>scegliModalita(b.dataset.modo));
  $("btn-scansiona").addEventListener("click",()=>avviaScansione(STATO.modalita));
  $("btn-ferma").addEventListener("click",()=>{STATO.in_corso=false;fermiScanner();});
  $("form-manuale").addEventListener("submit",async e=>{e.preventDefault();if(STATO.in_corso||STATO.pendente)return;const barcode=$("campo-barcode").value.trim();if(STATO.modalita==="consulta"){try{await consultaBarcode(barcode);}catch(e){}}else await inviaMovimento(barcode);});
  $("btn-esci").addEventListener("click",esci);$("btn-riprova").addEventListener("click",riprendiRichiesta);$("form-nuovo").addEventListener("submit",creaPezzi);
  $("nuovo-profilo").addEventListener("input",()=>{clearTimeout(timerProfili);timerProfili=setTimeout(cercaProfili,300);});
  globalThis.addEventListener("pagehide",()=>{STATO.in_corso=false;fermiScanner();fermaPing();});
  document.addEventListener("visibilitychange",()=>{if(document.hidden){STATO.in_corso=false;fermiScanner();fermaPing();}else if(STATO.attivo)avviaPing();});
  chiediGet("/api/salute").then(()=>statoRete("Servizio raggiungibile · accesso libero",true)).catch(()=>statoRete("Servizio non disponibile",false));
});
