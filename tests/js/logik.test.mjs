import { test } from "node:test";
import assert from "node:assert/strict";
import {
  aktion, anzeigeName, gitText, gruppenInfo, gruppieren, passtZurSuche, projektTitel, verborgen, zeitRelativ,
  zusammenfassung, zustandDetail, zustandHinweis, zustandKlasse,
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
  const z = { name: "Kundenportal P9", beschreibung: "Auslieferung", cwd: "/Users/a/refold", sid: "53f41c24-x", erste_prompts: ["Zahlungsplan"] };
  assert.ok(passtZurSuche(z, "kundenportal"));
  assert.ok(passtZurSuche(z, "refold zahlungsplan"));
  assert.ok(passtZurSuche(z, "53f41c24"));
  assert.ok(!passtZurSuche(z, "kundenportal bioclip"));
  assert.ok(passtZurSuche(z, "   "));
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

test("aktiv vom Dienst hat Vorrang (startet ohne Statusdatei)", () => {
  const { gruppen } = gruppieren([
    { sid: "s", cwd: "/p", aktiv: true, lauf: null, zustand: "startet" },
    { sid: "t", cwd: "/q", aktiv: false, lauf: { zustand: "läuft" }, zustand: "ruht" },
  ]);
  assert.deepEqual(gruppen.map((g) => [g.cwd, g.laufend]), [["/p", 1], ["/q", 0]]);
});

const L = (sid, cwd, letzter, extra = {}) => ({ sid, cwd, cwd_kurz: cwd, letzter, aktiv: false, zustand: "ruht", ...extra });
const LAEUFT = { aktiv: true, zustand: "arbeitet" };

test("Gruppen: laufende zuerst, sonst nach letzter Aktivität, in der Gruppe ebenso", () => {
  const zeilen = [
    L("a1", "~/x/alt", "2026-10-01T10:00:00Z"),
    L("b1", "~/x/neu", "2026-10-03T09:00:00Z"),
    L("c1", "~/x/lebt", "2026-09-20T10:00:00Z"),
    L("c2", "~/x/lebt", "2026-09-01T10:00:00Z", LAEUFT),
    L("b2", "~/x/neu", "2026-10-03T10:00:00Z"),
  ];
  const { gruppen } = gruppieren(zeilen);
  assert.deepEqual(gruppen.map((g) => g.titel), ["lebt", "neu", "alt"]);
  assert.deepEqual(gruppen[0].zeilen.map((z) => z.sid), ["c2", "c1"], "laufend vor neuer");
  assert.deepEqual(gruppen[1].zeilen.map((z) => z.sid), ["b2", "b1"]);
  assert.equal(gruppen[1].letzter, "2026-10-03T10:00:00Z");
  assert.equal(gruppen[0].ort, "~/x");
});

test("Ausgeblendetes verschwindet, laufendes nie; der Zähler zählt nur Verborgenes", () => {
  const zeilen = [
    L("s1", "/p", "2026-10-03T10:00:00Z", { ausgeblendet: true }),
    L("s2", "/p", "2026-10-03T09:00:00Z"),
    L("q1", "/q", "2026-10-03T08:00:00Z", { projekt_ausgeblendet: true }),
    L("q2", "/q", "2026-10-03T07:00:00Z", { projekt_ausgeblendet: true, ...LAEUFT }),
  ];
  const { gruppen, ausgeblendet } = gruppieren(zeilen);
  assert.equal(ausgeblendet, 2);
  assert.deepEqual(gruppen.flatMap((g) => g.zeilen.map((z) => z.sid)), ["q2", "s2"]);
  assert.equal(gruppen[0].projektAusgeblendet, true);
  const alle = gruppieren(zeilen, { zeigeAusgeblendete: true });
  assert.equal(alle.gruppen.flatMap((g) => g.zeilen).length, 4);
  assert.equal(verborgen(zeilen[3]), false);
});

test("eingeklappte Gruppe zeigt nur laufende, zählt aber alle", () => {
  const zeilen = [L("a", "/p", "2026-10-03T10:00:00Z"), L("b", "/p", "2026-10-03T09:00:00Z", LAEUFT)];
  const [g] = gruppieren(zeilen, { eingeklappt: new Set(["/p"]) }).gruppen;
  assert.equal(g.eingeklappt, true);
  assert.deepEqual(g.zeilen.map((z) => z.sid), ["b"]);
  assert.equal(g.gesamt, 2);
});

test("Suche wirkt vor dem Gruppieren", () => {
  const zeilen = [L("a", "/p", "x", { name: "Stripe" }), L("b", "/q", "x", { name: "Kundenportal" })];
  assert.deepEqual(gruppieren(zeilen, { suche: "stripe" }).gruppen.map((g) => g.cwd), ["/p"]);
});

test("Projekttitel und Gruppeninfo", () => {
  assert.deepEqual(projektTitel("~/Desktop/coding/5c"), { titel: "5c", ort: "~/Desktop/coding" });
  assert.deepEqual(projektTitel("~"), { titel: "~", ort: "" });
  assert.deepEqual(projektTitel("/a/b/"), { titel: "b", ort: "/a" });
  const jetzt = new Date("2026-10-03T12:00:00Z");
  assert.equal(gruppenInfo({ laufend: 1, gesamt: 4, letzter: "2026-10-03T10:00:00Z" }, jetzt), "1 läuft · 4 Sessions · vor 2 Std.");
  assert.equal(gruppenInfo({ laufend: 0, gesamt: 1, letzter: "" }, jetzt), "1 Session");
});

test("zweite Zeile unter dem Zustand", () => {
  assert.equal(zustandDetail({ zustand: "hängt vielleicht", still_s: 845 }), "seit 14 Min. keine Ausgabe");
  assert.equal(zustandDetail({ zustand: "startet" }), "noch ohne Statusdatei");
  assert.equal(zustandDetail({ zustand: "arbeitet", prozess: { app: "iTerm", cpu: 2.6, speicher_mb: 348 } }), "iTerm, 3 % CPU, 348 MB");
  assert.equal(zustandDetail({ zustand: "ruht", prozess: null }), "");
  assert.equal(zustandHinweis({ prozess: { laufzeit: "06:32", caffeinate: true } }), "läuft seit 06:32, caffeinate aktiv");
});

test("unbekannter Zustand bekommt keine Warnfarbe", () => {
  assert.equal(zustandKlasse("arbeitet"), "arbeitet");
  assert.equal(zustandKlasse("wartet auf Dich"), "wartet");
  assert.equal(zustandKlasse("gibt es nicht"), "ruht");
});
