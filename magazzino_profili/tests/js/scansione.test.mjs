// Client mobile: rete simulata, nessun server o dato reale.
import {test} from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
const src=readFileSync(fileURLToPath(new URL("../../web/static/scansione.js",import.meta.url)),"utf8");
function nodo(){return {textContent:"",className:"",value:"",hidden:false,checked:false,children:[],append(...n){this.children.push(...n)},replaceChildren(){this.children=[]},addEventListener(){},setAttribute(){}};}
function carica(fetchFinto){
 const elementi={},memoria=new Map();
 const ctx=vm.createContext({document:{getElementById(id){return elementi[id]??=nodo()},createElement(){return nodo()},addEventListener(){},querySelectorAll(){return []}},fetch:fetchFinto,AbortController,setTimeout,clearTimeout,setInterval,clearInterval,console,sessionStorage:{setItem(k,v){memoria.set(k,v)},getItem(k){return memoria.get(k)||null},removeItem(k){memoria.delete(k)}}});
 vm.runInContext(src,ctx);return ctx;
}
const pezzo={barcode:"MP-TEST",codice_profilo:"AB12",descrizione:"Profilo",colore:"RAL7016",lunghezza_mm:6000,quantita_giacenza:1,numero_vassoio:"4",stato:"Caricato",unitario:true};
const risposta=(status,corpo)=>({ok:status<400,status,json:async()=>corpo});

test("la pagina Vercel passa solo dal ponte con il PC del QR",async()=>{
 let n=0;const c=carica(async(u,o)=>{n++;if(n===1){assert.equal(u,"/api/ponte");const p=JSON.parse(o.body);assert.equal(p.pc,"a".repeat(32));assert.equal(p.percorso,"/api/pezzi/MP-TEST");return risposta(202,{id:p.id});}return risposta(200,{stato:200,tipo:"application/json",contenuto:btoa(JSON.stringify(pezzo))});});
 c.Response=Response;c.atob=atob;c.STATO.remoto=true;c.STATO.destinatario="a".repeat(32);
 await c.consultaBarcode("MP-TEST");assert.equal(n,2);
});

test("una richiesta pendente non passa a un altro magazzino dopo un nuovo QR",()=>{
 const c=carica(async()=>risposta(200,pezzo));c.STATO.destinatario='pc-nuovo';
 assert.equal(c.stessaSessione({destinatario:'pc-vecchio'}),false);
 assert.equal(c.stessaSessione({destinatario:c.STATO.destinatario}),true);
});
test("consultazione senza credenziali né Authorization",async()=>{
 let opzioni;const c=carica(async(u,o)=>{opzioni=o;return risposta(200,pezzo)});
 await c.consultaBarcode("MP-TEST");assert.equal(opzioni.method,"GET");assert.equal(opzioni.headers.Authorization,undefined);assert.match(c.document.getElementById("esito").textContent,/Vassoio: 4/);
});
test("rete interrotta nella consultazione segnala errore",async()=>{
 const c=carica(async()=>{throw new TypeError("rete")});await assert.rejects(()=>c.consultaBarcode("X"),e=>e.codice===0&&!e.esitoIncerto);assert.match(c.document.getElementById("esito").textContent,/Connessione/);
});
test("404 applicativo mostrato senza interpretare HTML",async()=>{
 const c=carica(async()=>risposta(404,{detail:"<script>non trovato</script>"}));await assert.rejects(()=>c.consultaBarcode("X"));assert.equal(c.document.getElementById("esito").textContent,"<script>non trovato</script>");
});
test("quantità decimale rifiutata senza richieste",async()=>{
 let n=0;const c=carica(async()=>{n++;return risposta(200,pezzo)});c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1.5";await c.inviaMovimento("X");assert.equal(n,0);assert.match(c.document.getElementById("esito").textContent,/quantità intera/);
});
test("movimento invia una chiave idempotenza e nessuna credenziale",async()=>{
 let chiamata;const c=carica(async(u,o)=>{chiamata={u,o};return risposta(200,pezzo)});c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1";await c.inviaMovimento("MP-TEST");const p=JSON.parse(chiamata.o.body);assert.equal(chiamata.u,"/api/scarico");assert.equal(p.quantita,1);assert.ok(p.richiesta_id);assert.equal(chiamata.o.headers.Authorization,undefined);assert.equal(c.STATO.pendente,null);
});
test("retry dopo rete interrotta riusa esattamente la stessa richiesta",async()=>{
 const invii=[];let n=0;const c=carica(async(u,o)=>{invii.push(o.body);if(n++===0)throw new TypeError("rete");return risposta(200,pezzo)});c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1";await c.inviaMovimento("MP-TEST");assert.ok(c.STATO.pendente);const chiave=c.STATO.pendente.payload.richiesta_id;await c.inviaMovimento("ALTRO");assert.equal(invii.length,1);await c.riprendiRichiesta();assert.equal(invii[0],invii[1]);assert.ok(chiave);assert.equal(c.STATO.pendente,null);
});
test("il doppio tap durante l'invio produce una sola richiesta",async()=>{
 let risolvi,n=0;const c=carica(()=>{n++;return new Promise(r=>risolvi=r)});c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1";const prima=c.inviaMovimento("MP-TEST");await c.inviaMovimento("MP-TEST");assert.equal(n,1);risolvi(risposta(200,pezzo));await prima;
});
test("lettore senza QR non invia a un PC casuale",async()=>{
 let n=0;const c=carica(async()=>{n++;return risposta(200,{})});c.STATO.modalita="lettore";await c.inviaMovimento("X");assert.equal(n,0);assert.match(c.document.getElementById("esito").textContent,/QR del PC/);
});
test("accodamento non equivale a esecuzione: attende ACK del PC",async()=>{
 let consultazioni=0;const c=carica(async(u)=>{if(u==="/api/scansione")return risposta(200,{id:7});consultazioni++;return risposta(200,{esito:"compilata",dettaglio:"Campi compilati: conferma il carico sul PC",barcode:"MP-TEST"})});c.STATO.modalita="lettore";c.STATO.destinatario="a".repeat(32);await c.inviaMovimento("MP-TEST");assert.equal(consultazioni,1);assert.match(c.document.getElementById("esito").textContent,/conferma il carico sul PC/);assert.equal(c.STATO.pendente,null);
});
test("risposta JSON interrotta conserva richiesta pendente",async()=>{
 const c=carica(async()=>({ok:true,status:200,json:async()=>{throw new TypeError("troncata")}}));c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1";await c.inviaMovimento("X");assert.ok(c.STATO.pendente);assert.match(c.document.getElementById("esito").textContent,/incerto/);
});
test("rifiuto 409 libera la richiesta senza retry automatico",async()=>{
 const c=carica(async()=>risposta(409,{detail:"Pezzo già scaricato"}));c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1";await c.inviaMovimento("X");assert.equal(c.STATO.pendente,null);assert.match(c.document.getElementById("esito").textContent,/già scaricato/);
});
test("pausa blocca nuove operazioni senza chiedere login",async()=>{
 let n=0;const c=carica(async()=>{n++;return risposta(200,pezzo)});c.esci();c.STATO.modalita="scarico";c.document.getElementById("campo-quantita").value="1";await c.inviaMovimento("X");assert.equal(n,0);assert.equal(c.STATO.attivo,false);
});
test("nuovi pezzi: numero pezzi separato dal barcode",async()=>{
 let inviato;const c=carica(async(u,o)=>{inviato=JSON.parse(o.body);return risposta(200,{dettaglio:"Creati 5 pezzi",pezzi:[]})});c.confirm=()=>true;
 for(const [id,v] of Object.entries({"nuovo-profilo":"ab12","nuovo-colore":"RAL7016","nuovo-lunghezza":"6000","nuovo-numero":"5","nuovo-vassoio":"4","nuovo-causale":"Carico"}))c.document.getElementById(id).value=v;
 await c.creaPezzi({preventDefault(){}});assert.equal(inviato.quantita,5);assert.equal(inviato.codice_profilo,"AB12");assert.equal(inviato.barcode,undefined);assert.ok(inviato.richiesta_id);
});
