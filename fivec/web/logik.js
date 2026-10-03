// Reine Funktionen der Übersicht, ohne DOM. Getestet mit `node --test tests/js`.

const MINUTE = 60 * 1000;
const STUNDE = 60 * MINUTE;
const TAG = 24 * STUNDE;

const zwei = (n) => String(n).padStart(2, "0");

export function zeitAbsolut(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "?";
  return `${zwei(d.getDate())}.${zwei(d.getMonth() + 1)}. ${zwei(d.getHours())}:${zwei(d.getMinutes())}`;
}

export function zeitRelativ(iso, jetzt = new Date()) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "?";
  const diff = jetzt.getTime() - d.getTime();
  if (diff < MINUTE) return "gerade eben";
  if (diff < STUNDE) return `vor ${Math.floor(diff / MINUTE)} Min.`;
  if (diff < TAG) return `vor ${Math.floor(diff / STUNDE)} Std.`;
  const gestern = new Date(jetzt);
  gestern.setDate(gestern.getDate() - 1);
  if (d.toDateString() === gestern.toDateString()) return "gestern";
  const tage = Math.round((startDesTages(jetzt) - startDesTages(d)) / TAG);
  if (tage < 7) return `vor ${tage} Tagen`;
  return zeitAbsolut(iso);
}

function startDesTages(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function gitText(git) {
  if (!git || git.art === "kein_repo") return "kein Repo";
  if (git.art === "ordner_fehlt") return "Ordner fehlt";
  return git.uncommittet === 0 ? "sauber" : `${git.uncommittet} offen`;
}

export function laeuft(zeile) {
  if (typeof zeile.aktiv === "boolean") return zeile.aktiv;
  return Boolean(zeile.lauf && zeile.lauf.zustand === "läuft");
}

// Zweite Zeile unter dem Zustand: bei "hängt vielleicht" die stille Zeit, sonst App, CPU, Speicher.
export function zustandDetail(zeile) {
  if (zeile.zustand === "hängt vielleicht" && zeile.still_s != null) {
    return `seit ${Math.floor(zeile.still_s / 60)} Min. keine Ausgabe`;
  }
  if (zeile.zustand === "startet") return "noch ohne Statusdatei";
  const p = zeile.prozess;
  if (!p) return "";
  const cpu = `${Math.round(p.cpu)} % CPU`;
  return [p.app, cpu, `${p.speicher_mb} MB`].filter(Boolean).join(", ");
}

export function zustandHinweis(zeile) {
  const p = zeile.prozess;
  if (!p) return "";
  return `läuft seit ${p.laufzeit}, caffeinate ${p.caffeinate ? "aktiv" : "nicht aktiv"}`;
}

// CSS-Klasse je Zustand. Unbekanntes fällt auf "ruht" zurück, nie auf eine Warnfarbe.
const KLASSEN = {
  "arbeitet": "arbeitet",
  "wartet auf Dich": "wartet",
  "hängt vielleicht": "haengt",
  "startet": "startet",
  "läuft": "startet",
  "verwaist": "verwaist",
  "ruht": "ruht",
};

export function zustandKlasse(zustand) {
  return KLASSEN[zustand] ?? "ruht";
}

export function anzeigeName(zeile) {
  if (zeile.name) return { name: zeile.name, ohneName: false, unterzeile: zeile.beschreibung || "" };
  const prompt = (zeile.erste_prompts && zeile.erste_prompts[0]) || "";
  return { name: "Ohne Namen", ohneName: true, unterzeile: prompt };
}

export function passtZurSuche(zeile, suche) {
  const q = suche.trim().toLowerCase();
  if (!q) return true;
  const heu = [zeile.name, zeile.beschreibung, zeile.cwd, zeile.sid, ...(zeile.erste_prompts || [])]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
  return q.split(/\s+/).every((wort) => heu.includes(wort));
}

// Ausgeblendet (E8): die Session selbst oder ihr Projekt. Laufende bleiben immer sichtbar,
// damit keine übersehen wird, die auf Dich wartet.
export function verborgen(zeile) {
  return Boolean(zeile.ausgeblendet || zeile.projekt_ausgeblendet) && !laeuft(zeile);
}

function neuer(a, b) {
  return (b.letzter || "").localeCompare(a.letzter || "");
}

// Gruppen nach Projekt (cwd). Laufende zuerst, in der Gruppe wie zwischen den Gruppen,
// sonst nach letzter Aktivität. Eine eingeklappte Gruppe zeigt nur ihre laufenden Sessions.
export function gruppieren(zeilen, { suche = "", zeigeAusgeblendete = false, eingeklappt = new Set() } = {}) {
  const passend = zeilen.filter((z) => passtZurSuche(z, suche));
  const ausgeblendet = passend.filter(verborgen).length;
  const karte = new Map();
  for (const z of passend) {
    if (verborgen(z) && !zeigeAusgeblendete) continue;
    const schluessel = z.cwd || "?";
    if (!karte.has(schluessel)) karte.set(schluessel, []);
    karte.get(schluessel).push(z);
  }
  const gruppen = [...karte.entries()].map(([cwd, liste]) => {
    liste.sort((a, b) => Number(laeuft(b)) - Number(laeuft(a)) || neuer(a, b));
    const zu = eingeklappt.has(cwd);
    return {
      cwd,
      ...projektTitel(liste[0].cwd_kurz || cwd),
      laufend: liste.filter(laeuft).length,
      gesamt: liste.length,
      letzter: liste.reduce((m, z) => ((z.letzter || "") > m ? z.letzter : m), ""),
      projektAusgeblendet: liste.some((z) => z.projekt_ausgeblendet),
      eingeklappt: zu,
      zeilen: zu ? liste.filter(laeuft) : liste,
    };
  });
  gruppen.sort((a, b) => Number(b.laufend > 0) - Number(a.laufend > 0) || neuer(a, b));
  return { gruppen, ausgeblendet };
}

// "~/Desktop/coding/5c" -> { titel: "5c", ort: "~/Desktop/coding" }
export function projektTitel(pfad) {
  const teile = String(pfad || "?").replace(/\/+$/, "").split("/");
  const titel = teile.pop() || pfad || "?";
  return { titel, ort: teile.join("/") };
}

export function gruppenInfo(g, jetzt = new Date()) {
  const teile = [];
  if (g.laufend) teile.push(`${g.laufend} läuft`);
  teile.push(g.gesamt === 1 ? "1 Session" : `${g.gesamt} Sessions`);
  if (g.letzter) teile.push(zeitRelativ(g.letzter, jetzt));
  return teile.join(" · ");
}

export function zusammenfassung(zeilen) {
  const zaehler = new Map();
  for (const z of zeilen.filter(laeuft)) zaehler.set(z.zustand, (zaehler.get(z.zustand) || 0) + 1);
  const reihenfolge = ["arbeitet", "wartet auf Dich", "hängt vielleicht", "startet"];
  const teile = reihenfolge.filter((k) => zaehler.has(k)).map((k) => `${zaehler.get(k)} ${k}`);
  return teile.length ? teile.join(", ") : "Gerade läuft keine Session";
}

export function aktion(zeile) {
  if (laeuft(zeile)) return { text: "Nach vorn", art: "vorn", gesperrt: false };
  if (zeile.git && zeile.git.art === "ordner_fehlt") return { text: "Ordner fehlt", art: "fehlt", gesperrt: true };
  return { text: "Fortsetzen", art: "fortsetzen", gesperrt: false };
}

export const ZEITRAEUME = {
  "48h": { text: "48 Stunden", query: "stunden=48", leer: "Keine Session in den letzten 48 Stunden." },
  "7t": { text: "7 Tage", query: "stunden=168", leer: "Keine Session in den letzten 7 Tagen." },
  "alle": { text: "Alle", query: "alle=1", leer: "Keine Session gefunden." },
};
