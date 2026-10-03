import { test } from "node:test";
import assert from "node:assert/strict";
import {
  aktion, anzeigeName, aufteilen, gitText, passtZurSuche, zeitRelativ, zusammenfassung, zustandKlasse,
} from "../../fivec/web/logik.js";

const jetzt = new Date(2026, 9, 3, 10, 50, 0); // 03.10.2026 10:50 Ortszeit
const vor = (ms) => new Date(jetzt.getTime() - ms).toISOString();
const MIN = 60 * 1000;

test("relative Zeit", () => {
  assert.equal(zeitRelativ(vor(20 * 1000), jetzt), "gerade eben");
  assert.equal(zeitRelativ(vor(6 * MIN), jetzt), "vor 6 Min.");
  assert.equal(zeitRelativ(vor(3 * 60 * MIN), jetzt), "vor 3 Std.");
  assert.equal(zeitRelativ(new Date(2026, 9, 2, 8, 15).toISOString(), jetzt), "gestern");
  assert.equal(zeitRelativ(new Date(2026, 9, 2, 23, 0).toISOString(), jetzt), "vor 11 Std.");
  assert.equal(zeitRelativ(new Date(2026, 9, 1, 16, 32).toISOString(), jetzt), "vor 2 Tagen");
  assert.equal(zeitRelativ(new Date(2026, 8, 20, 9, 0).toISOString(), jetzt), "20.09. 09:00");
  assert.equal(zeitRelativ("kaputt", jetzt), "?");
});

test("gestern nur, wenn älter als 24 Stunden und am Vortag", () => {
  const abends = new Date(2026, 9, 3, 23, 0);
  assert.equal(zeitRelativ(new Date(2026, 9, 2, 8, 0).toISOString(), abends), "gestern");
});

test("Git-Text", () => {
  assert.equal(gitText({ art: "ordner_fehlt" }), "Ordner fehlt");
  assert.equal(gitText({ art: "kein_repo" }), "kein Repo");
  assert.equal(gitText({ art: "repo", uncommittet: 0 }), "sauber");
  assert.equal(gitText({ art: "repo", uncommittet: 28 }), "28 offen");
});

test("Name fällt auf den ersten Prompt zurück", () => {
  assert.deepEqual(anzeigeName({ name: "X", beschreibung: "Y" }), { name: "X", ohneName: false, unterzeile: "Y" });
  assert.deepEqual(anzeigeName({ name: "", erste_prompts: ["Bitte orientiere dich."] }),
    { name: "Ohne Namen", ohneName: true, unterzeile: "Bitte orientiere dich." });
});

test("Suche über Name, Beschreibung, Pfad, ID und Prompts, alle Wörter müssen passen", () => {
  const z = { name: "Kundenportal P9", beschreibung: "Rollout", cwd: "/Users/a/refold", sid: "53f41c24-x", erste_prompts: ["Stripe-Plan"] };
  assert.ok(passtZurSuche(z, "telekom"));
  assert.ok(passtZurSuche(z, "refold stripe"));
  assert.ok(passtZurSuche(z, "53f41c24"));
  assert.ok(!passtZurSuche(z, "telekom bioclip"));
  assert.ok(passtZurSuche(z, "   "));
});

test("Aufteilen nach läuft und Rest", () => {
  const a = { sid: "a", lauf: { zustand: "läuft" }, zustand: "arbeitet" };
  const b = { sid: "b", lauf: { zustand: "verwaist" }, zustand: "verwaist" };
  const c = { sid: "c", lauf: null, zustand: "ruht" };
  const { laufend, zuletzt } = aufteilen([a, b, c]);
  assert.deepEqual(laufend.map((z) => z.sid), ["a"]);
  assert.deepEqual(zuletzt.map((z) => z.sid), ["b", "c"]);
});

test("Zusammenfassung zählt nur laufende", () => {
  const z = [
    { lauf: { zustand: "läuft" }, zustand: "arbeitet" },
    { lauf: { zustand: "läuft" }, zustand: "wartet auf Dich" },
    { lauf: { zustand: "läuft" }, zustand: "wartet auf Dich" },
    { lauf: null, zustand: "ruht" },
  ];
  assert.equal(zusammenfassung(z), "1 arbeitet, 2 wartet auf Dich");
  assert.equal(zusammenfassung([]), "Gerade läuft keine Session");
});

test("Aktion je Zustand", () => {
  assert.equal(aktion({ lauf: { zustand: "läuft" } }).text, "Nach vorn");
  assert.equal(aktion({ lauf: null, git: { art: "repo", uncommittet: 0 } }).text, "Fortsetzen");
  const fehlt = aktion({ lauf: null, git: { art: "ordner_fehlt" } });
  assert.equal(fehlt.text, "Ordner fehlt");
  assert.equal(fehlt.gesperrt, true);
});

test("unbekannter Zustand bekommt keine Warnfarbe", () => {
  assert.equal(zustandKlasse("arbeitet"), "arbeitet");
  assert.equal(zustandKlasse("wartet auf Dich"), "wartet");
  assert.equal(zustandKlasse("gibt es nicht"), "ruht");
});
