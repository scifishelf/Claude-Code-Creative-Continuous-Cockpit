// Übersicht: lädt /api/sessions alle 2 s, baut die Projektgruppen per DOM und textContent
// (nie als HTML, denn Namen, Prompts und Pfade sind fremder Text) und speichert Name,
// Beschreibung und „ausgeblendet“ per PATCH. Während einer Bearbeitung wird nicht neu gezeichnet.

import {
  aktion, anzeigeName, gitText, gruppenInfo, gruppieren, zeitAbsolut, zeitRelativ,
  verborgen, ZEITRAEUME, zusammenfassung, zustandDetail, zustandHinweis, zustandKlasse,
} from "./logik.js";

const TAKT_MS = 2000;
const MELDUNG_MS = 8000;
const TOKEN = document.querySelector('meta[name="fivec-token"]').content;
const SPEICHER_EINGEKLAPPT = "5c-eingeklappt";

// Eingeklappte Gruppen sind eine Bequemlichkeit je Browser; ohne Speicher geht es auch.
function eingeklapptLaden() {
  try {
    const liste = JSON.parse(localStorage.getItem(SPEICHER_EINGEKLAPPT) || "[]");
    return new Set(Array.isArray(liste) ? liste : []);
  } catch {
    return new Set();
  }
}

function eingeklapptSpeichern() {
  try {
    localStorage.setItem(SPEICHER_EINGEKLAPPT, JSON.stringify([...zustand.eingeklappt]));
  } catch { /* privater Modus: dann eben nur für diesen Besuch */ }
}

const zustand = {
  zeitraum: "48h",
  suche: "",
  zeilen: null,
  bearbeitet: null, // Session-ID der offenen Bearbeitung
  laedt: false,
  zeigeAusgeblendete: false,
  eingeklappt: eingeklapptLaden(),
  schreibStand: 0, // zählt Schreibvorgänge; eine Liste von davor ist veraltet
};

const $ = (id) => document.getElementById(id);

function el(tag, klasse, text) {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (text !== undefined) e.textContent = text;
  return e;
}

let meldungUhr = null;

// rueckgaengig: optionale Funktion, dann steht „Rückgängig“ daneben und die Meldung geht nach MELDUNG_MS.
function meldung(text, istFehler = false, rueckgaengig = null) {
  const m = $("meldung");
  clearTimeout(meldungUhr);
  m.hidden = !text;
  $("meldung-text").textContent = text || "";
  m.classList.toggle("fehler", istFehler);
  const knopf = $("meldung-knopf");
  knopf.hidden = !rueckgaengig;
  knopf.onclick = rueckgaengig ? () => { meldung(""); rueckgaengig(); } : null;
  if (rueckgaengig) meldungUhr = setTimeout(() => meldung(""), MELDUNG_MS);
}

// --- Laden --------------------------------------------------------------

async function laden() {
  if (zustand.laedt) return;
  zustand.laedt = true;
  const stand = zustand.schreibStand;
  try {
    const antwort = await fetch(`/api/sessions?${ZEITRAEUME[zustand.zeitraum].query}`, { cache: "no-store" });
    if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
    const zeilen = await antwort.json();
    // Während der Abfrage wurde geschrieben: Diese Liste kennt das noch nicht und würde es überzeichnen.
    if (stand !== zustand.schreibStand) return;
    zustand.zeilen = zeilen;
    if ($("meldung").classList.contains("fehler")) meldung("");
    if (!zustand.bearbeitet) zeichnen();
  } catch {
    meldung("Der 5C-Dienst antwortet nicht. Läuft „5c dienst“ noch?", true);
  } finally {
    zustand.laedt = false;
  }
}

// --- Zeichnen -----------------------------------------------------------

function zeichnen() {
  if (!zustand.zeilen) return;
  const { gruppen, ausgeblendet } = gruppieren(zustand.zeilen, {
    suche: zustand.suche, zeigeAusgeblendete: zustand.zeigeAusgeblendete, eingeklappt: zustand.eingeklappt,
  });
  $("zusammenfassung").textContent = zusammenfassung(zustand.zeilen);
  const schalter = $("ausgeblendet-schalter");
  if (ausgeblendet === 0 && zustand.zeigeAusgeblendete) zustand.zeigeAusgeblendete = false;
  schalter.hidden = ausgeblendet === 0;
  schalter.textContent = `${ausgeblendet} ausgeblendet`;
  schalter.setAttribute("aria-pressed", String(zustand.zeigeAusgeblendete));
  schalter.title = zustand.zeigeAusgeblendete ? "Ausgeblendete wieder verbergen" : "Ausgeblendete anzeigen";

  // Der Takt baut die Zeilen neu; der Tastaturfokus soll dabei an seiner Stelle bleiben.
  const aktiv = document.activeElement;
  const fokusSid = aktiv?.closest?.(".zeile")?.dataset.sid;
  const fokusArt = aktiv?.classList?.contains("name") ? ".name"
    : aktiv?.classList?.contains("knopf-aus") ? ".knopf-aus" : ".knopf-haupt";
  const fokusGruppe = aktiv?.closest?.(".gruppe-kopf")?.dataset.cwd;
  const fokusKopfArt = aktiv?.classList?.contains("knopf-aus") ? ".knopf-aus" : ".gruppe-klappe";

  $("gruppen").replaceChildren(...gruppen.map(gruppe));

  if (fokusSid && !zustand.bearbeitet) {
    document.querySelector(`.zeile[data-sid="${CSS.escape(fokusSid)}"] ${fokusArt}`)?.focus();
  } else if (fokusGruppe) {
    document.querySelector(`.gruppe-kopf[data-cwd="${CSS.escape(fokusGruppe)}"] ${fokusKopfArt}`)?.focus();
  }

  const leer = gruppen.length === 0;
  $("leer").hidden = !leer;
  zustand.leerWeg = !leer ? null : zustand.suche ? "suche" : ausgeblendet ? "ausgeblendet" : "zeitraum";
  if (leer) {
    const texte = {
      suche: ["Keine Session passt zur Suche.", "Suche leeren"],
      ausgeblendet: ["Alle Sessions in diesem Zeitraum sind ausgeblendet.", "Ausgeblendete anzeigen"],
      zeitraum: [ZEITRAEUME[zustand.zeitraum].leer, "Zeitraum erweitern"],
    }[zustand.leerWeg];
    $("leer-text").textContent = texte[0];
    $("leer-erweitern").textContent = texte[1];
    $("leer-erweitern").hidden = zustand.leerWeg === "zeitraum" && zustand.zeitraum === "alle";
  }
}

function gruppe(g) {
  const abschnitt = el("section", "gruppe");
  const kopf = el("div", g.projektAusgeblendet ? "gruppe-kopf ausgeblendet" : "gruppe-kopf");
  kopf.dataset.cwd = g.cwd;
  const klappe = el("button", "gruppe-klappe");
  klappe.type = "button";
  klappe.setAttribute("aria-expanded", String(!g.eingeklappt));
  klappe.title = g.cwd;
  const titel = el("span", "gruppe-titel", g.titel);
  klappe.append(el("span", "pfeil"), titel);
  if (g.ort) klappe.append(el("span", "gruppe-ort", g.ort));
  if (g.projektAusgeblendet) klappe.append(el("span", "marke", "ausgeblendet"));
  klappe.append(el("span", "gruppe-info", gruppenInfo(g)));
  klappe.addEventListener("click", () => {
    if (zustand.eingeklappt.has(g.cwd)) zustand.eingeklappt.delete(g.cwd);
    else zustand.eingeklappt.add(g.cwd);
    eingeklapptSpeichern();
    zeichnen();
  });
  const aus = el("button", "knopf knopf-aus", g.projektAusgeblendet ? "Projekt einblenden" : "Projekt ausblenden");
  aus.type = "button";
  aus.addEventListener("click", () => projektAusblenden(g, !g.projektAusgeblendet));
  kopf.append(klappe, aus);
  abschnitt.append(kopf);
  const liste = el("div", "gruppe-zeilen");
  liste.append(...g.zeilen.map(zeile));
  abschnitt.append(liste);
  return abschnitt;
}

function zeile(z) {
  const bearbeiten = zustand.bearbeitet === z.sid;
  const verdeckt = verborgen(z);
  const reihe = el("div", ["zeile", bearbeiten && "bearbeiten", verdeckt && "ausgeblendet"].filter(Boolean).join(" "));
  reihe.dataset.sid = z.sid;

  const zelle = el("div", "zustand-zelle");
  const zk = el("div", `zustand z-${zustandKlasse(z.zustand)}`);
  zk.append(el("span", "marker"), el("span", "", z.zustand));
  zelle.append(zk);
  const detail = zustandDetail(z);
  if (detail) zelle.append(el("div", "zustand-detail", detail));
  const hinweis = zustandHinweis(z);
  if (hinweis) zelle.title = hinweis;
  reihe.append(zelle);

  reihe.append(bearbeiten ? formular(z) : nameZelle(z));

  const projekt = el("div", "projekt");
  const sid = el("span", "sid", z.sid.slice(0, 8));
  sid.title = z.sid;
  projekt.append(sid);
  reihe.append(projekt);

  const zeit = el("div", "zeit");
  zeit.append(el("div", "zeit-rel", zeitRelativ(z.letzter)), el("div", "zeit-abs", zeitAbsolut(z.letzter)));
  reihe.append(zeit);

  reihe.append(el("div", "nachr", String(z.nachrichten)));

  const gt = gitText(z.git);
  const gitKlasse = z.git?.art === "ordner_fehlt" ? "git fehlt" : (gt === "sauber" || gt === "kein Repo" ? "git leise" : "git");
  const git = el("div", gitKlasse, gt);
  if (z.git?.letzter_commit) git.title = z.git.letzter_commit;
  reihe.append(git);

  if (bearbeiten) {
    reihe.append(el("div"));
  } else {
    const aktionen = el("div", "aktionen");
    const aus = el("button", "knopf knopf-aus", z.ausgeblendet ? "Einblenden" : "Ausblenden");
    aus.type = "button";
    aus.addEventListener("click", () => sessionAusblenden(z, !z.ausgeblendet));
    const a = aktion(z);
    const knopf = el("button", `knopf knopf-haupt knopf-${a.art}`, a.text);
    knopf.type = "button";
    knopf.disabled = a.gesperrt;
    if (a.gesperrt) knopf.title = "Der Ordner dieser Session existiert nicht mehr";
    knopf.addEventListener("click", () => oeffnen(z, knopf));
    aktionen.append(aus, knopf);
    reihe.append(aktionen);
  }
  return reihe;
}

function nameZelle(z) {
  const { name, ohneName, unterzeile } = anzeigeName(z);
  const zelle = el("div", "name-zelle");
  const knopf = el("button", ohneName ? "name ohne-name" : "name", name);
  knopf.type = "button";
  knopf.title = "Name und Beschreibung bearbeiten";
  knopf.addEventListener("click", () => bearbeitungStarten(z.sid));
  zelle.append(knopf, el("div", "unterzeile", unterzeile));
  return zelle;
}

function formular(z) {
  const f = el("form", "formular");
  const idName = `name-${z.sid}`;
  const idBeschr = `beschreibung-${z.sid}`;
  const lName = el("label", "", "Name");
  lName.htmlFor = idName;
  const iName = el("input");
  iName.id = idName;
  iName.type = "text";
  iName.maxLength = 60;
  iName.value = z.name || "";
  iName.placeholder = "";
  const lBeschr = el("label", "", "Beschreibung");
  lBeschr.htmlFor = idBeschr;
  const iBeschr = el("textarea");
  iBeschr.id = idBeschr;
  iBeschr.rows = 2;
  iBeschr.maxLength = 2000;
  iBeschr.value = z.beschreibung || "";
  const fehler = el("p", "fehler");
  fehler.hidden = true;
  fehler.setAttribute("role", "alert");

  const knoepfe = el("div", "knoepfe");
  const speichern = el("button", "knopf knopf-hell", "Speichern");
  speichern.type = "submit";
  const abbrechen = el("button", "knopf knopf-leer", "Abbrechen");
  abbrechen.type = "button";
  abbrechen.addEventListener("click", bearbeitungBeenden);
  knoepfe.append(speichern, abbrechen);

  f.append(lName, iName, lBeschr, iBeschr, el("p", "hinweis", "Enter speichert, Esc bricht ab"), fehler, knoepfe);

  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    speichern.disabled = true;
    const ok = await speichernAnDienst(z.sid, { name: iName.value, beschreibung: iBeschr.value }, fehler);
    speichern.disabled = false;
    if (ok) bearbeitungBeenden();
  });
  f.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); bearbeitungBeenden(); }
    if (e.key === "Enter" && e.target === iBeschr && (e.metaKey || e.ctrlKey)) { e.preventDefault(); f.requestSubmit(); }
  });
  queueMicrotask(() => { iName.focus(); iName.select(); });
  return f;
}

// --- Aktionen -----------------------------------------------------------

function bearbeitungStarten(sid) {
  zustand.bearbeitet = sid;
  zeichnen();
}

function bearbeitungBeenden() {
  const sid = zustand.bearbeitet;
  zustand.bearbeitet = null;
  zeichnen();
  const knopf = sid && document.querySelector(`.zeile[data-sid="${CSS.escape(sid)}"] .name`);
  if (knopf) knopf.focus();
}

async function speichernAnDienst(sid, daten, fehlerFeld) {
  try {
    const antwort = await fetch(`/api/sessions/${encodeURIComponent(sid)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-5C-Token": TOKEN },
      body: JSON.stringify(daten),
    });
    const inhalt = await antwort.json().catch(() => ({}));
    if (!antwort.ok) {
      fehlerFeld.textContent = inhalt.fehler || `Speichern fehlgeschlagen (HTTP ${antwort.status})`;
      fehlerFeld.hidden = false;
      return false;
    }
    const z = zustand.zeilen.find((x) => x.sid === sid);
    if (z) { z.name = inhalt.name || ""; z.beschreibung = inhalt.beschreibung || ""; }
    return true;
  } catch {
    fehlerFeld.textContent = "Der 5C-Dienst antwortet nicht.";
    fehlerFeld.hidden = false;
    return false;
  }
}

// Ausblenden (E8): sofort zeichnen, dann speichern; scheitert das Speichern, zurück und Fehler zeigen.
async function ausblendenSpeichern(pfad, koerper, anwenden, text, rueckgaengig) {
  zustand.schreibStand += 1;
  anwenden(koerper.ausgeblendet);
  zeichnen();
  try {
    const antwort = await fetch(pfad, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-5C-Token": TOKEN },
      body: JSON.stringify(koerper),
    });
    const inhalt = await antwort.json().catch(() => ({}));
    if (!antwort.ok) throw new Error(inhalt.fehler || `HTTP ${antwort.status}`);
    zustand.schreibStand += 1; // auch Abfragen, die während des Speicherns liefen, sind veraltet
    meldung(text, false, rueckgaengig);
  } catch (e) {
    anwenden(!koerper.ausgeblendet);
    zeichnen();
    meldung(`Nicht gespeichert: ${e.message === "Failed to fetch" ? "Der 5C-Dienst antwortet nicht." : e.message}`, true);
  }
}

function sessionAusblenden(z, aus) {
  const name = anzeigeName(z).ohneName ? z.sid.slice(0, 8) : z.name;
  ausblendenSpeichern(
    `/api/sessions/${encodeURIComponent(z.sid)}`,
    { ausgeblendet: aus },
    (wert) => { for (const x of zustand.zeilen) if (x.sid === z.sid) x.ausgeblendet = wert; },
    aus ? `Ausgeblendet: ${name}.` : `Eingeblendet: ${name}.`,
    () => sessionAusblenden(z, !aus),
  );
}

function projektAusblenden(g, aus) {
  ausblendenSpeichern(
    "/api/projekte",
    { cwd: g.cwd, ausgeblendet: aus },
    (wert) => { for (const x of zustand.zeilen) if ((x.cwd || "?") === g.cwd) x.projekt_ausgeblendet = wert; },
    aus ? `Ausgeblendet: ${g.titel}.` : `Eingeblendet: ${g.titel}.`,
    () => projektAusblenden(g, !aus),
  );
}

async function oeffnen(z, knopf) {
  knopf.disabled = true;
  try {
    const antwort = await fetch(`/api/sessions/${encodeURIComponent(z.sid)}/open`, {
      method: "POST",
      headers: { "X-5C-Token": TOKEN },
    });
    const inhalt = await antwort.json().catch(() => ({}));
    meldung(antwort.ok ? inhalt.text : (inhalt.fehler || `Fehlgeschlagen (HTTP ${antwort.status})`), !antwort.ok);
  } catch {
    meldung("Der 5C-Dienst antwortet nicht.", true);
  } finally {
    knopf.disabled = false;
    laden();
  }
}

// --- Bedienung ----------------------------------------------------------

function zeitraumSetzen(schluessel) {
  zustand.zeitraum = schluessel;
  for (const b of document.querySelectorAll("[data-zeitraum]")) {
    b.setAttribute("aria-pressed", String(b.dataset.zeitraum === schluessel));
  }
  laden();
}

for (const b of document.querySelectorAll("[data-zeitraum]")) {
  b.addEventListener("click", () => zeitraumSetzen(b.dataset.zeitraum));
}
$("suche").addEventListener("input", (e) => { zustand.suche = e.target.value; zeichnen(); });
$("ausgeblendet-schalter").addEventListener("click", () => {
  zustand.zeigeAusgeblendete = !zustand.zeigeAusgeblendete;
  zeichnen();
});
$("leer-erweitern").addEventListener("click", () => {
  if (zustand.leerWeg === "suche") { $("suche").value = ""; zustand.suche = ""; zeichnen(); return; }
  if (zustand.leerWeg === "ausgeblendet") { zustand.zeigeAusgeblendete = true; zeichnen(); return; }
  zeitraumSetzen(zustand.zeitraum === "48h" ? "7t" : "alle");
});

laden();
setInterval(() => { if (!document.hidden) laden(); }, TAKT_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) laden(); });
