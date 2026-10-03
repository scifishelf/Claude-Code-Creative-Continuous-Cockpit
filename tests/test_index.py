import json
import tempfile
import unittest
from pathlib import Path

from fivec import index

SID = "11111111-2222-3333-4444-555555555555"


def zeile(**kw) -> str:
    return json.dumps(kw) + "\n"


def user(text, ts, **kw):
    return zeile(type="user", timestamp=ts, cwd="/p", message={"role": "user", "content": text}, **kw)


def antwort(text, ts):
    return zeile(type="assistant", timestamp=ts, message={"content": [{"type": "text", "text": text}]})


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "projects" / "-p").mkdir(parents=True)
        self.datei = self.tmp / "projects" / "-p" / f"{SID}.jsonl"
        self.cache = self.tmp / "5c" / "index.json"

    def schreiben(self, text: str, modus="a"):
        with open(self.datei, modus) as f:
            f.write(text)

    def lauf(self) -> dict:
        return index.aktualisieren(self.tmp, self.cache)[SID]

    def test_liest_nur_angehaengtes_und_keine_halbe_zeile(self):
        self.schreiben(user("eins", "2026-10-01T10:00:00Z") + antwort("a1", "2026-10-01T10:01:00Z"))
        e = self.lauf()
        self.assertEqual(e["nachrichten"], 2)
        offset = e["offset"]

        halb = user("zwei", "2026-10-02T10:00:00Z")
        self.schreiben(halb[:20])
        e = self.lauf()
        self.assertEqual(e["nachrichten"], 2, "halbe Zeile darf nicht zählen")
        self.assertEqual(e["offset"], offset)

        self.schreiben(halb[20:])
        e = self.lauf()
        self.assertEqual(e["nachrichten"], 3)
        self.assertEqual(e["letzter"], "2026-10-02T10:00:00Z")
        self.assertEqual(e["erster"], "2026-10-01T10:00:00Z")
        self.assertEqual(e["letzte_prompts"], ["eins", "zwei"])

    def test_cache_wird_genutzt(self):
        self.schreiben(user("eins", "2026-10-01T10:00:00Z"))
        self.lauf()
        # Steht im Cache ein abweichender Wert, beweist sein Überleben, dass nicht neu gelesen wurde.
        daten = json.loads(self.cache.read_text())
        daten["sessions"][SID]["erste_prompts"] = ["aus dem cache"]
        self.cache.write_text(json.dumps(daten))
        self.assertEqual(self.lauf()["erste_prompts"], ["aus dem cache"])

    def test_gekuerzte_datei_wird_neu_gelesen(self):
        self.schreiben(user("eins", "2026-10-01T10:00:00Z") + user("zwei", "2026-10-01T11:00:00Z"))
        self.lauf()
        self.schreiben(user("neu", "2026-10-03T10:00:00Z"), modus="w")
        e = self.lauf()
        self.assertEqual(e["nachrichten"], 1)
        self.assertEqual(e["erste_prompts"], ["neu"])

    def test_filtert_meta_toolresult_und_spitze_klammer(self):
        self.schreiben(
            user("<command-name>/clear</command-name>", "2026-10-01T10:00:00Z")
            + user("meta", "2026-10-01T10:00:01Z", isMeta=True)
            + zeile(type="user", timestamp="2026-10-01T10:00:02Z",
                    message={"content": [{"type": "tool_result", "content": "x"}]})
            + user("zusammenfassung", "2026-10-01T10:00:03Z", isCompactSummary=True)
            + user("nebenlauf", "2026-10-01T10:00:04Z", isSidechain=True)
            + user("echt", "2026-10-01T10:00:05Z")
        )
        e = self.lauf()
        self.assertEqual(e["erste_prompts"], ["echt"])
        self.assertEqual(e["nachrichten"], 6, "gezählt werden alle user/assistant-Zeilen")

    def test_letzte_drei_und_kuerzen(self):
        text = "".join(antwort(f"a{i}", f"2026-10-01T10:0{i}:00Z") for i in range(5))
        self.schreiben(text + user("x" * 1000, "2026-10-01T11:00:00Z"))
        e = self.lauf()
        self.assertEqual(e["letzte_antworten"], ["a2", "a3", "a4"])
        self.assertEqual(len(e["letzte_prompts"][0]), index.KURZ + 1)


if __name__ == "__main__":
    unittest.main()
