// Fase 9 — prove simulate del client di scansione.
// Si esegue scansione.js in un contesto VM isolato con fetch/document finti,
// senza browser né server.
import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
import path, { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT_PATH = path.join(__dirname, "..", "..", "..", "magazzino_profili", "web", "static", "scansione.js");
const SRC = readFileSync(SCRIPT_PATH, "utf8");

// Carica il client in un sandbox VM con document/fetch simulabili.
function carica(fetchFinto) {
  const ctx = vm.createContext({
    document: {
      elementi: {},
      getElementById(id) {
        if (!this.elementi[id]) {
          this.elementi[id] = { id, textContent: "", className: "", value: "" };
        }
        return this.elementi[id];
      },
      addEventListener() {}
    },
    console: console,
    fetch: fetchFinto || (() => { throw new TypeError("fetch failed"); }),
    AbortController: globalThis.AbortController,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    setInterval: setInterval,
    clearInterval: clearInterval,
    Html5Qrcode: class {}
  });
  vm.runInContext(SRC, ctx);
  return ctx;
}

const PEZZO_RESP = {
  barcode: "AB12", codice_profilo: "P001", descrizione: "Profilo A",
  colore: "Rosso", lunghezza_mm: 500, quantita_giacenza: 7,
  numero_vassoio: "V-2", stato: "Caricato"
};

function risp(status, corpo) {
  return { ok: status < 400, status: status, json: async () => corpo };
}

test("rete assente nella consultazione: errore chiaro con messaggio di connessione", async () => {
  const ctx = carica(async () => { throw new TypeError("fetch failed"); });
  await assert.rejects(
    () => ctx.consultaBarcode("AB12"),
    (e) => e.message.includes("Connessione") && e.codice === 0 && e.esitoIncerto === false
  );
  assert.match(ctx.document.getElementById("esito").textContent, /Connessione/);
});

test("rete assente nel carico: messaggio di esito incerto, niente reject", async () => {
  const ctx = carica(async () => { throw new TypeError("fetch failed"); });
  ctx.STATO.modalita = "carico";
  ctx.document.getElementById("campo-quantita").value = "2";
  await ctx.inviaMovimento("AB12"); // gestisce l'errore internamente
  assert.match(ctx.document.getElementById("esito").textContent, /incerto/);
  assert.match(ctx.document.getElementById("esito").textContent, /Consulta/);
});

test("404 dal server: messaggio del server mostrato e propagato", async () => {
  const ctx = carica(async () => risp(404, { detail: "Pezzo non trovato." }));
  await assert.rejects(
    () => ctx.consultaBarcode("AB12"),
    (e) => e.message === "Pezzo non trovato." && e.codice === 404
  );
  assert.match(ctx.document.getElementById("esito").textContent, /Pezzo non trovato/);
});

test("timeout rete (errore di fetch): errore chiaro senza blocco", async () => {
  // il timeout reale (15 s) è coperto a livello API; qui: fetch che fallisce
  // come un abort deve produrre lo stesso messaggio di rete assente
  const ctx = carica(async () => { throw new TypeError("timeout artificiale"); });
  await assert.rejects(
    () => ctx.consultaBarcode("AB12"),
    (e) => e.message.includes("Connessione")
  );
});

test("401 nella consultazione: errore con codice 401, esci e reject", async () => {
  const ctx = carica(async () => risp(401, { detail: "Sessione scaduta" }));
  await assert.rejects(
    () => ctx.consultaBarcode("AB12"),
    (e) => e.message === "Sessione scaduta" && e.codice === 401
  );
  assert.match(ctx.document.getElementById("esito").textContent, /Sessione scaduta/);
  assert.strictEqual(ctx.STATO.token, null); // esci() ha azzerato lo stato
});

test("GET di consultazione: nessun corpo, metodo GET, Bearer se c'è il token", async () => {
  let chiamata = null;
  const ctx = carica(async (url, opz) => {
    chiamata = { url, opz };
    return risp(200, PEZZO_RESP);
  });
  ctx.STATO.token = "tok1";
  const corpo = await ctx.chiediGet("/api/pezzi/AB12");
  assert.strictEqual(chiamata.url, "/api/pezzi/AB12");
  assert.strictEqual(chiamata.opz.method, "GET");
  assert.strictEqual(chiamata.opz.body, undefined);
  assert.strictEqual(chiamata.opz.headers.Authorization, "Bearer tok1");
  assert.strictEqual(corpo.codice_profilo, "P001");
});

test("carico valido: POST /api/carico con payload e Bearer", async () => {
  let chiamata = null;
  const ctx = carica(async (url, opz) => {
    chiamata = { url, opz };
    return risp(200, PEZZO_RESP);
  });
  ctx.STATO.token = "tok1";
  ctx.STATO.modalita = "carico";
  ctx.document.getElementById("campo-quantita").value = "3";
  await ctx.inviaMovimento("AB12");
  assert.strictEqual(chiamata.url, "/api/carico");
  assert.strictEqual(chiamata.opz.method, "POST");
  assert.strictEqual(chiamata.opz.headers.Authorization, "Bearer tok1");
  const payload = JSON.parse(chiamata.opz.body);
  assert.strictEqual(payload.barcode, "AB12");
  assert.strictEqual(payload.quantita, 3);
});

test("carico con quantità nulla: nessuna richiesta inviata", async () => {
  let invii = 0;
  const ctx = carica(async () => { invii++; return risp(200, PEZZO_RESP); });
  ctx.STATO.modalita = "carico";
  ctx.document.getElementById("campo-quantita").value = "";
  await ctx.inviaMovimento("AB12");
  assert.strictEqual(invii, 0);
  assert.match(ctx.document.getElementById("esito").textContent, /quantità/);
});

test("consulta: dettaglio del pezzo mostrato sullo schermo", async () => {
  const ctx = carica(async () => risp(200, PEZZO_RESP));
  await ctx.consultaBarcode("AB12");
  const testo = ctx.document.getElementById("esito").textContent;
  assert.match(testo, /P001/);
  assert.match(testo, /Rosso/);
  assert.match(testo, /V-2/);
});
