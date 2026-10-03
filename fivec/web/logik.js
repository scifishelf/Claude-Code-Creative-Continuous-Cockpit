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

export function aufteilen(zeilen, suche = "") {
  const sichtbar = zeilen.filter((z) => passtZurSuche(z, suche));
  return {
    laufend: sichtbar.filter(laeuft),
    zuletzt: sichtbar.filter((z) => !laeuft(z)),
  };
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
