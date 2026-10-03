// Übersicht: lädt /api/sessions alle 2 s, baut die Zeilen per DOM und textContent
// (nie als HTML, denn Namen, Prompts und Pfade sind fremder Text) und speichert Name und
// Beschreibung per PATCH. Während einer Bearbeitung wird nicht neu gezeichnet.

import {
  aktion, anzeigeName, aufteilen, gitText, zeitAbsolut, zeitRelativ,
  ZEITRAEUME, zusammenfassung, zustandDetail, zustandHinweis, zustandKlasse,
} from "./logik.js";

const TAKT_MS = 2000;
const TOKEN = document.querySelector('meta[name="fivec-token"]').content;

const zustand = {
  zeitraum: "48h",
  suche: "",
  zeilen: null,
  bearbeitet: null, // Session-ID der offenen Bearbeitung
  laedt: false,
};

const $ = (id) => document.getElementById(id);

function el(tag, klasse, text) {
  const e = document.createElement(tag);
  if (klasse) e.className = klasse;
  if (text !== undefined) e.textContent = text;
  return e;
}

function meldung(text, istFehler = false) {
  const m = $("meldung");
  m.hidden = !text;
  m.textContent = text || "";
  m.classList.toggle("fehler", istFehler);
}

// --- Laden --------------------------------------------------------------

async function laden() {
  if (zustand.laedt) return;
  zustand.laedt = true;
  try {
    const antwort = await fetch(`/api/sessions?${ZEITRAEUME[zustand.zeitraum].query}`, { cache: "no-store" });
    if (!antwort.ok) throw new Error(`HTTP ${antwort.status}`);
    zustand.zeilen = await antwort.json();
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
  const { laufend, zuletzt } = aufteilen(zustand.zeilen, zustand.suche);
  $("zusammenfassung").textContent = zusammenfassung(zustand.zeilen);

  // Der Takt baut die Zeilen neu; der Tastaturfokus soll dabei an seiner Stelle bleiben.
  const aktiv = document.activeElement;
  const fokusSid = aktiv?.closest?.(".zeile")?.dataset.sid;
  const fokusArt = aktiv?.classList?.contains("name") ? ".name" : ".knopf";

  $("gruppe-laufend").hidden = laufend.length === 0;
  $("liste-laufend").replaceChildren(...laufend.map(zeile));
  $("gruppe-zuletzt").hidden = zuletzt.length === 0;
  $("liste-zuletzt").replaceChildren(...zuletzt.map(zeile));

  if (fokusSid && !zustand.bearbeitet) {
    document.querySelector(`.zeile[data-sid="${CSS.escape(fokusSid)}"] ${fokusArt}`)?.focus();
  }

  const leer = laufend.length === 0 && zuletzt.length === 0;
  $("leer").hidden = !leer;
  if (leer) {
    $("leer-text").textContent = zustand.suche ? "Keine Session passt zur Suche." : ZEITRAEUME[zustand.zeitraum].leer;
    $("leer-erweitern").hidden = zustand.zeitraum === "alle" && !zustand.suche;
    $("leer-erweitern").textContent = zustand.suche ? "Suche leeren" : "Zeitraum erweitern";
  }
}

function zeile(z) {
  const bearbeiten = zustand.bearbeitet === z.sid;
  const reihe = el("div", bearbeiten ? "zeile bearbeiten" : "zeile");
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
  const pfad = el("span", "", z.cwd_kurz || z.cwd || "?");
  pfad.title = z.cwd || "";
  projekt.append(pfad, el("span", "sid", z.sid.slice(0, 8)));
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
    const a = aktion(z);
    const knopf = el("button", `knopf knopf-${a.art}`, a.text);
    knopf.type = "button";
    knopf.disabled = a.gesperrt;
    if (a.gesperrt) knopf.title = "Der Ordner dieser Session existiert nicht mehr";
    knopf.addEventListener("click", () => oeffnen(z, knopf));
    reihe.append(knopf);
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
$("leer-erweitern").addEventListener("click", () => {
  if (zustand.suche) { $("suche").value = ""; zustand.suche = ""; zeichnen(); return; }
  zeitraumSetzen(zustand.zeitraum === "48h" ? "7t" : "alle");
});

laden();
setInterval(() => { if (!document.hidden) laden(); }, TAKT_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) laden(); });
