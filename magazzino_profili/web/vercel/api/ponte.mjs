import {get,put,list,del} from '@vercel/blob';
const TTL=60000;
const PC=/^[a-f0-9]{32}$/;
const ID=/^[A-Za-z0-9-]{1,64}$/;
const prefix='magazzino-ponte/';
function percorsoValido(metodo,path){
  if(typeof path!=='string'||path.length>2000||!path.startsWith('/api/')||/[\x00-\x1f\\]/.test(decodeURIComponent(path)))return false;
  const u=new URL(path,'https://interno.invalid');
  if(u.origin!=='https://interno.invalid'||u.hash)return false;
  if(metodo==='POST')return ['/api/pezzi','/api/carico','/api/scarico','/api/scansione','/api/telefono/ping'].includes(u.pathname);
  return metodo==='GET'&&(['/api/salute','/api/profili'].includes(u.pathname)||/^\/api\/(?:pezzi\/[A-Za-z0-9%-]+|barcode\/[A-Za-z0-9%-]+\/immagine|profili\/[A-Za-z0-9%-]+\/sezione|scansioni\/[0-9]+)$/.test(u.pathname));
}
async function leggi(nome){
  const r=await get(nome,{access:'private',useCache:false});
  return r?.statusCode===200?await new Response(r.stream).json():null;
}
async function scrivi(nome,dati){
  return put(nome,JSON.stringify(dati),{access:'private',addRandomSuffix:false,allowOverwrite:true,contentType:'application/json',cacheControlMaxAge:60});
}
export default async function handler(req,res){
  res.setHeader('Cache-Control','no-store');res.setHeader('Content-Type','application/json');
  const rispondi=(stato,dati)=>{res.statusCode=stato;res.end(JSON.stringify(dati));};
  try{
    const u=new URL(req.url,'https://interno.invalid');
    let corpo=req.body;
    if(typeof corpo==='string')corpo=JSON.parse(corpo);
    const modo=u.searchParams.get('modo')||'';
    if(modo==='pulisci'){
      const pagina=await list({prefix,limit:1000});
      const scaduti=pagina.blobs.filter(b=>Date.now()-new Date(b.uploadedAt).getTime()>300000).map(b=>b.url);
      if(scaduti.length)await del(scaduti);
      return rispondi(200,{rimossi:scaduti.length});
    }
    const pc=corpo?.pc||u.searchParams.get('pc');
    if(!PC.test(pc||''))return rispondi(422,{detail:'Identificativo PC non valido: usa il QR del programma'});
    const base=prefix+pc+'/';
    if(req.method==='GET'&&modo==='pc'){
      const pagina=await list({prefix:base+'richieste/',limit:20});const lavori=[];
      for(const b of pagina.blobs){
        const lavoro=await leggi(b.pathname);
        if(!lavoro||Date.now()>lavoro.scadenza){await del(b.url);continue;}
        lavori.push(lavoro);
      }
      return rispondi(200,{lavori});
    }
    if(req.method==='POST'&&modo==='risposta'){
      const {id,stato,tipo,contenuto}=corpo;
      if(!ID.test(id||'')||!Number.isInteger(stato)||stato<200||stato>599||!['application/json','image/png'].some(t=>String(tipo).startsWith(t))||typeof contenuto!=='string'||contenuto.length>2700000)
        return rispondi(422,{detail:'Risposta del PC non valida'});
      if(!await leggi(base+'richieste/'+id+'.json'))return rispondi(410,{detail:'Richiesta non più attiva'});
      await scrivi(base+'risposte/'+id+'.json',{stato,tipo,contenuto,scadenza:Date.now()+TTL});
      await del(base+'richieste/'+id+'.json');
      return rispondi(200,{ok:true});
    }
    if(req.method==='POST'&&!modo){
      const {id,metodo,percorso,dati}=corpo;
      if(!ID.test(id||'')||!percorsoValido(metodo,percorso)||JSON.stringify(dati??null).length>64000)
        return rispondi(422,{detail:'Operazione non valida'});
      await scrivi(base+'richieste/'+id+'.json',{id,metodo,percorso,dati,scadenza:Date.now()+TTL});
      return rispondi(202,{id});
    }
    if(req.method==='GET'&&!modo){
      const id=u.searchParams.get('id');if(!ID.test(id||''))return rispondi(422,{detail:'Richiesta non valida'});
      const risultato=await leggi(base+'risposte/'+id+'.json');
      if(!risultato)return rispondi(202,{in_attesa:true});
      if(Date.now()>risultato.scadenza){await del(base+'risposte/'+id+'.json');return rispondi(410,{detail:'Risposta scaduta: controllare la giacenza e riprendere la richiesta'});}
      await del(base+'risposte/'+id+'.json');
      return rispondi(200,risultato);
    }
    return rispondi(405,{detail:'Metodo non consentito'});
  }catch(errore){
    console.error('Ponte non disponibile:',errore.name);
    return rispondi(503,{detail:'Collegamento Vercel non disponibile: verificare configurazione e quota del servizio'});
  }
}
