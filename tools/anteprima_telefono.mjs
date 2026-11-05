// Genera un'anteprima autonoma: nessuna API e nessun dato del magazzino.
import fs from 'node:fs';
const base=new URL('../magazzino_profili/web/',import.meta.url);
let html=fs.readFileSync(new URL('templates/scansione.html',base),'utf8');
const css=fs.readFileSync(new URL('static/telefono.css',base),'utf8');
const source=fs.readFileSync(new URL('static/scansione.js',base),'utf8');
const marker='document.addEventListener("DOMContentLoaded",()=>{';
if(!source.includes(marker))throw new Error('Avvio client non riconosciuto');
const client=source.slice(0,source.indexOf(marker));
const demo=`
// Ogni accesso ai servizi è disabilitato nella demo.
fetchPonte=async()=>{throw new Error('Servizi non disponibili nell’anteprima')};
cercaProfili=()=>{};avviaPing=()=>{};
const campione={barcode:'DEMO-00042',codice_profilo:'AB12',descrizione:'Profilo dimostrativo',colore:'RAL 7016',lunghezza_mm:6000,quantita_giacenza:1,numero_vassoio:'A · 04',stato:'Caricato',unitario:true};
scegliModalita('consulta');statoRete('Anteprima locale · dati dimostrativi',true);
visibile('anagrafica-nuova',true);
$('btn-tema').onclick=cambiaTema;
for(const b of document.querySelectorAll('[data-modo]'))b.onclick=()=>{scegliModalita(b.dataset.modo);$('titolo-operazione').scrollIntoView({block:'start',behavior:'instant'})};
function esempio(){if(STATO.modalita==='consulta'){mostraMessaggio(descrivi(campione),'successo');mostraSchedaPezzo(campione)}else{mostraMessaggio('Simulazione completata. Nessun dato reale modificato.','successo');registraStorico('DEMO-00042 · '+STATO.modalita)}}
$('btn-scansiona').onclick=esempio;
$('form-manuale').onsubmit=e=>{e.preventDefault();esempio()};
$('form-nuovo').onsubmit=e=>{e.preventDefault();esempio()};
$('btn-esci').onclick=()=>mostraMessaggio('Questa è un’anteprima locale. Il collegamento al PC è disattivato.');
$('btn-riprova').onclick=esempio;
for(const [id,v] of Object.entries({'nuovo-profilo':'AB12','nuovo-colore':'RAL7016','nuovo-lunghezza':'6000','nuovo-vassoio':'A04'}))$(id).value=v;
`;
html=html.replace('<link rel="stylesheet" href="/static/telefono.css">','<style>'+css+'</style>').replace(/<script defer[^>]*><\/script>/g,'').replace('</body>','<script>'+client+demo+'</script></body>');
const escaped=html.replaceAll('&','&amp;').replaceAll('"','&quot;');
const wrapper=`<!doctype html><html lang="it"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Anteprima mobile · Magazzino</title><style>*{box-sizing:border-box}body{margin:0;background:#e9eef5;color:#192944;font:15px system-ui;display:grid;justify-items:center;gap:16px;padding:24px}header{text-align:center;max-width:560px}h1{font-size:22px;margin:0 0 8px}p{line-height:1.5;margin:0}iframe{width:390px;max-width:100%;height:780px;height:min(780px,calc(100dvh - 160px));min-height:420px;border:7px solid #25354b;border-radius:32px;box-shadow:0 24px 70px #19294425;background:white}select{font:inherit;padding:7px;margin-top:10px;border:1px solid #bac8dc;border-radius:8px;background:white}@media(max-width:450px){body{padding:12px 6px}iframe{border-width:3px;border-radius:18px}}</style><header><h1>La nuova interfaccia mobile</h1><p>Prova le cinque schede, il tema scuro e una scansione simulata.<br>Solo dati di esempio: nessuna modifica al magazzino.</p><label>Schermo <select id="larghezza"><option value="390">390 px</option><option value="320">320 px</option><option value="430">430 px</option></select></label></header><iframe title="Anteprima interattiva del telefono" srcdoc="${escaped}"></iframe><script>document.getElementById('larghezza').onchange=e=>document.querySelector('iframe').style.width=e.target.value+'px'</script></html>`;
fs.writeFileSync(new URL('../anteprima-telefono.html',import.meta.url),wrapper);
console.log('Anteprima aggiornata: anteprima-telefono.html');
