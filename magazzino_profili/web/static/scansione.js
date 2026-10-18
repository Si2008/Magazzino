/*
 * Scansione barcode da fotocamera — Magazzino Profili.
 *
 * Libreria client-side: html5-qrcode (https://github.com/mebjas/html5-qrcode),
 * caricata via CDN nella pagina HTML. Perché questa libreria:
 * - unico file, nessuna fase di build;
 * - API minimale (start/stop + callback di lettura);
 * - supporto nativo di Code 128 e lettura dalla fotocamera posteriore
 *   (facingMode: "environment").
 * L'alternativa principale (ZXing-js) offre un'API più complessa,
 * non necessaria per questo uso.
 *
 * Sicurezza: il token di autenticazione resta SOLO in memoria (variabile
 * di questo file), NON in localStorage — se il telefono viene perso o
 * rubato non c'è una sessione persistente da sfruttare; basta aprire o
 * chiudere la scheda del browser.
 */
"use strict";

const STATO = {
  token: null,      // token di sessione, solo in memoria
  utente: null,
  ruolo: null,
  modalita: null,   // "carico" | "scarico"
  scanner: null,    // istanza Html5Qrcode attiva (o null)
  in_corso: false,  // guardia contro doppi invii
};

const $ = (id) => document.getElementById(id);

let timerPing = null;

async function ping() {
  try {
    await chiedi("/api/telefono/ping", {});
  } catch (errore) {
    if (errore.codice === 401) {
      esci();
    }
    // altri errori di rete: si riprova al prossimo giro
  }
}

function avviaPing() {
  fermaPing();
  ping();
  timerPing = setInterval(ping, 10000);
}

function fermaPing() {
  if (timerPing) {
    clearInterval(timerPing);
    timerPing = null;
  }
}

/* ------------------------------------------------------------------ */
/* Chiamate all'API (JSON, token Bearer in memoria)                    */
/* ------------------------------------------------------------------ */
async function chiedi(url, payload) {
  const intestazioni = { "Content-Type": "application/json" };
  if (STATO.token) {
    intestazioni["Authorization"] = "Bearer " + STATO.token;
  }
  const risposta = await fetch(url, {
    method: "POST",
    headers: intestazioni,
    body: JSON.stringify(payload),
  });
  let corpo = {};
  try {
    corpo = await risposta.json();
  } catch (_) {
    // corpo non JSON: si usa il messaggio di riserva
  }
  if (!risposta.ok) {
    const errore = new Error(
      corpo.detail || "Errore non previsto (codice " + risposta.status + ")."
    );
    errore.codice = risposta.status;
    throw errore;
  }
  return corpo;
}

/* ------------------------------------------------------------------ */
/* Login / uscita                                                      */
/* ------------------------------------------------------------------ */
async function accedi(evento) {
  evento.preventDefault();
  const esito = $("esito-login");
  esito.textContent = "Accesso in corso…";
  esito.className = "esito";
  try {
    const corpo = await chiedi("/api/login", {
      utente: $("campo-utente").value.trim(),
      password: $("campo-password").value,
    });
    STATO.token = corpo.token;
    STATO.utente = corpo.utente;
    STATO.ruolo = corpo.ruolo;
    $("nome-utente").textContent = STATO.utente;
    $("ruolo-utente").textContent = STATO.ruolo;
    $("zona-login").hidden = true;
    $("zona-operazione").hidden = false;
    avviaPing();
  } catch (errore) {
    esito.textContent = errore.message;
    esito.className = "esito errore";
  }
}

function esci() {
  fermaPing(); fermiScanner(); STATO.modalita = null; STATO.in_corso = false;
  STATO.token = null;
  STATO.utente = null;
  STATO.ruolo = null;
  $("campo-password").value = "";
  $("zona-operazione").hidden = true;
  $("zona-login").hidden = false;
}

/* ------------------------------------------------------------------ */
/* Messaggi a schermo                                                  */
/* ------------------------------------------------------------------ */
function mostraMessaggio(testo, classe) {
  const esito = $("esito");
  esito.textContent = testo;
  esito.className = "esito" + (classe ? " " + classe : "");
}

/* ------------------------------------------------------------------ */
/* Scansione e invio del movimento                                     */
/* ------------------------------------------------------------------ */
async function fermiScanner() {
  const scanner = STATO.scanner;
  STATO.scanner = null;
  if (scanner) {
    try {
      await scanner.stop();
    } catch (_) {
      // già fermato: nessun problema
    }
  }
}

async function avviaScansione(modalita) {
  if (STATO.in_corso) return;
  await fermiScanner();
  STATO.modalita = modalita;
  STATO.in_corso = true;
  mostraMessaggio("Punta la fotocamera sul barcode…", "successo");
  const scanner = new Html5Qrcode("lettore-barcode");
  STATO.scanner = scanner;
  try {
    await scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 260, height: 120 } },
      (testoLettura) => {
        onLettura(testoLettura); // non in attesa: callback asincrona
      },
      () => {
        // errore di singolo frame: si continua a scansionare
      }
    );
  } catch (errore) {
    STATO.in_corso = false;
    STATO.scanner = null;
    mostraMessaggio(
      "Impossibile avviare la fotocamera (" + errore + "). " +
      "Verificare che la pagina sia aperta con HTTPS e che il browser " +
      "abbia il permesso per la fotocamera.",
      "errore"
    );
  }
}

async function onLettura(testo) {
  if (!STATO.in_corso) return; // lettura in ritardo: la ignoro
  STATO.in_corso = false;
  await fermiScanner();
  await inviaMovimento(testo.trim());
}

async function inviaMovimento(barcode) {
  if (!barcode) {
    mostraMessaggio("Nessun barcode letto.", "errore");
    return;
  }

  if (STATO.modalita === "lettore") {
    mostraMessaggio("Invio al PC in corso…", "successo");
    try {
      const corpo = await chiedi("/api/scansione", { barcode: barcode });
      mostraMessaggio("Inviato al PC: " + corpo.barcode, "successo");
      // lettore continuo: dopo 1,2 s riparte la fotocamera
      setTimeout(() => {
        if (STATO.token && STATO.modalita === "lettore") avviaScansione("lettore");
      }, 1200);
    } catch (errore) {
      if (errore.codice === 401) {
        mostraMessaggio("Sessione scaduta: effettuare nuovamente il login.", "errore");
        esci();
        return;
      }
      mostraMessaggio(errore.message, "errore");
    }
    return;
  }
  const quantita = parseInt($("campo-quantita").value, 10);
  if (!Number.isInteger(quantita) || quantita <= 0) {
    mostraMessaggio("Inserire una quantità intera e maggiore di zero.", "errore");
    return;
  }
  const payload = { barcode: barcode, quantita: quantita };
  const causale = $("campo-causale").value.trim();
  if (causale) payload.causale = causale;

  mostraMessaggio("Invio del movimento in corso…", "successo");
  try {
    const corpo = await chiedi("/api/" + STATO.modalita, payload);
    mostraMessaggio(
      corpo.dettaglio +
      " Pezzo: " + corpo.codice_profilo + " — " + corpo.descrizione +
      " (" + corpo.colore + ", " + corpo.lunghezza_mm + " mm). " +
      "Giacenza attuale: " + corpo.quantita_giacenza + ".",
      "successo"
    );
  } catch (errore) {
    if (errore.codice === 401) {
      mostraMessaggio("Sessione scaduta: effettuare nuovamente il login.", "errore");
      esci();
      return;
    }
    mostraMessaggio(errore.message, "errore");
  }
}

/* ------------------------------------------------------------------ */
/* Avvio della pagina                                                  */
/* ------------------------------------------------------------------ */
document.addEventListener("DOMContentLoaded", () => {
  $("form-login").addEventListener("submit", accedi);
  $("btn-carico").addEventListener("click", () => avviaScansione("carico"));
  $("btn-scarico").addEventListener("click", () => avviaScansione("scarico"));
  $("btn-lettore").addEventListener("click", () => avviaScansione("lettore"));
  $("btn-esci").addEventListener("click", esci);
});
