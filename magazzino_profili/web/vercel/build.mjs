import {mkdirSync,copyFileSync,cpSync} from 'node:fs';
import {resolve} from 'node:path';
const out=resolve(process.cwd(),'public');
mkdirSync(out,{recursive:true});
copyFileSync(new URL('../templates/scansione.html',import.meta.url),resolve(out,'index.html'));
cpSync(new URL('../static/',import.meta.url),resolve(out,'static'),{recursive:true});
console.log('Pagina telefono pronta in '+out);
