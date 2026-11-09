// Decoder reale nel browser, solo immagini e API sintetiche. Nessuna fotocamera fisica.
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(path.resolve(process.argv[2]));
const fixture=path.resolve(process.argv[3]),out=path.resolve(process.argv[4]);
const root=path.resolve(__dirname,'..'),web=path.join(root,'magazzino_profili/web');
fs.mkdirSync(out,{recursive:true});
const codici=['AB12-AN007-6000','MP-0123456789ABCDEF0123456789ABCDEF'];
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.MAGAZZINO_CHROMIUM});
 const risultati=[];
 try{
  const ctx=await browser.newContext({viewport:{width:390,height:844}});
  let richiesteMovimento=0,ultimoMovimento=null;
  await ctx.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!=='https://barcode-test.invalid')return route.abort();
   let file;
   if(url.pathname==='/')file=path.join(web,'templates/scansione.html');
   else if(url.pathname.startsWith('/static/'))file=path.join(web,url.pathname.slice(1));
   else if(url.pathname.startsWith('/fixture/'))file=path.join(fixture,path.basename(url.pathname));
   if(file&&fs.existsSync(file))return route.fulfill({status:200,body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.png')?'image/png':'text/html'});
   if(url.pathname.startsWith('/api/')){
    if(['/api/scarico','/api/carico','/api/pezzi'].includes(url.pathname)){
      richiesteMovimento++;ultimoMovimento=route.request().postDataJSON();
      return route.fulfill({status:200,json:{barcode:ultimoMovimento.barcode,codice_profilo:'TEST-SINTETICO',descrizione:'Prova',colore:'BIANCO',lunghezza_mm:6000,quantita_giacenza:0,stato:'Scaricato',dettaglio:'Scarico sintetico confermato'}});
    }
    const barcode=decodeURIComponent(url.pathname.split('/').at(-1));
    const corpo=url.pathname.startsWith('/api/pezzi/')?{barcode,codice_profilo:'TEST-SINTETICO',colore:'BIANCO',lunghezza_mm:6000,quantita_giacenza:1,numero_vassoio:'TEST',stato:'Caricato',unitario:true}:{};
    return route.fulfill({status:200,json:corpo});
   }
   return route.fulfill({status:404,body:'Risorsa di test assente'});
  });
  const page=await ctx.newPage();
  await page.goto('https://barcode-test.invalid');
  await page.locator('[data-modo="consulta"]').click();
  for(let i=0;i<codici.length;i++){
   await page.locator('#foto-barcode').setInputFiles(path.join(fixture,`barcode-${i}.png`));
   try{
    await page.waitForFunction(c=>!document.querySelector('#scheda-pezzo').hidden&&document.querySelector('#scheda-pezzo').textContent.includes(c),codici[i],{timeout:10000});
    risultati.push({test:'Foto Code128 '+(i?'seriale lungo':'storico'),stato:'superato',barcode:codici[i]});
   }catch(e){risultati.push({test:'Foto Code128 '+i,stato:'fallito',motivo:await page.locator('#esito').textContent()});}
  }
  await page.screenshot({path:path.join(out,'foto-barcode.png'),fullPage:true});
  // La fotocamera di prova e un canvas, con etichetta lunga larga il 90% del frame.
  await page.addInitScript(()=>{
   Object.defineProperty(navigator,'mediaDevices',{value:{
    async getUserMedia(){
     const c=document.createElement('canvas');c.width=1920;c.height=1080;
     const p=c.getContext('2d'),img=new Image();img.src='/fixture/barcode-1.png';await img.decode();
     function disegna(){p.fillStyle='white';p.fillRect(0,0,c.width,c.height);const h=img.height*1728/img.width;p.drawImage(img,96,(1080-h)/2,1728,h);}
     disegna();setInterval(disegna,100);return c.captureStream(15);
    },async enumerateDevices(){return [];}
   }});
  });
  await page.reload();await page.locator('[data-modo="consulta"]').click();await page.locator('#btn-scansiona').click();
  try{
   await page.waitForFunction(c=>!document.querySelector('#scheda-pezzo').hidden&&document.querySelector('#scheda-pezzo').textContent.includes(c),codici[1],{timeout:12000});
   risultati.push({test:'Video sintetico: seriale lungo, intera inquadratura',stato:'superato'});
  }catch(e){risultati.push({test:'Video sintetico: seriale lungo',stato:'fallito',motivo:await page.locator('#esito').textContent()});}
  await page.evaluate(()=>{STATO.in_corso=false;return fermiScanner()});
  if(richiesteMovimento!==0)throw Error('La prova di consultazione ha generato un movimento');
  risultati.push({test:'Nessun movimento di magazzino, nessun servizio reale contattato',stato:'superato'});
  page.on('dialog',dialogo=>dialogo.accept());
  await page.locator('[data-modo="scarico"]').click();
  await page.locator('#foto-barcode').setInputFiles(path.join(fixture,'barcode-1.png'));
  await page.waitForFunction(()=>document.querySelector('#esito').textContent.includes('Scarico sintetico confermato'));
  if(richiesteMovimento!==1||ultimoMovimento.barcode!==codici[1]||ultimoMovimento.quantita!==1||!ultimoMovimento.richiesta_id)
    throw Error('Scarico sintetico duplicato o payload errato');
  risultati.push({test:'Foto -> conferma -> un solo scarico unitario idempotente, API simulata',stato:'superato'});
  await ctx.close();
 }finally{
  await browser.close();fs.writeFileSync(path.join(out,'esiti.json'),JSON.stringify(risultati,null,2));console.log(JSON.stringify(risultati,null,2));
 }
 if(risultati.some(r=>r.stato!=='superato'))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
