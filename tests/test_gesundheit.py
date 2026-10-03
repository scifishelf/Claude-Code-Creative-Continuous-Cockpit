import unittest
from datetime import datetime, timedelta, timezone

from fivec import gesundheit

JETZT = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
GRENZE = gesundheit.HAENGT_NACH_S


def ms_vor(s):
    return (JETZT - timedelta(seconds=s)).timestamp() * 1000


def iso_vor(s):
    return (JETZT - timedelta(seconds=s)).isoformat().replace("+00:00", "Z")


def lauf(status, seit_s=5, **kw):
    return {"zustand": "läuft", "status": status, "statusUpdatedAt": ms_vor(seit_s), **kw}


def z(l, startend=False, still_s=5):
    return gesundheit.bewerten(l, startend, iso_vor(still_s), JETZT)["zustand"]


class GesundheitTest(unittest.TestCase):
    def test_grundzustaende(self):
        self.assertEqual(z(lauf("busy")), "arbeitet")
        self.assertEqual(z(lauf("idle")), "wartet auf Dich")
        self.assertEqual(z(lauf("busy", waitingFor="permission")), "wartet auf Dich")
        self.assertEqual(z(None), "ruht")
        self.assertEqual(z({"zustand": "verwaist"}), "verwaist")
        self.assertEqual(z(lauf("irgendwas")), "läuft")

    def test_startet(self):
        self.assertEqual(z(None, startend=True), "startet")
        self.assertEqual(z({"zustand": "verwaist"}, startend=True), "startet")

    def test_haengt_nur_wenn_beides_still(self):
        self.assertEqual(z(lauf("busy", seit_s=GRENZE + 1), still_s=GRENZE + 1), "hängt vielleicht")
        self.assertEqual(z(lauf("busy", seit_s=GRENZE + 1), still_s=30), "arbeitet", "Verlauf wächst noch")
        self.assertEqual(z(lauf("busy", seit_s=30), still_s=GRENZE + 1), "arbeitet", "gerade erst busy")
        self.assertEqual(z(lauf("busy", seit_s=GRENZE - 1), still_s=GRENZE - 1), "arbeitet", "Grenze")
        self.assertEqual(z(lauf("idle", seit_s=GRENZE * 9), still_s=GRENZE * 9), "wartet auf Dich",
                         "lange idle ist normal, kein Hängen")

    def test_stille_zeit(self):
        g = gesundheit.bewerten(lauf("busy", seit_s=900), False, iso_vor(840), JETZT)
        self.assertEqual(g["still_s"], 840)

    def test_fehlende_zeiten_nie_haengt(self):
        self.assertEqual(gesundheit.bewerten({"zustand": "läuft", "status": "busy"}, False, None, JETZT)["zustand"],
                         "arbeitet")

    def test_emoji_fuer_jeden_aktiven_zustand(self):
        for zustand in ("arbeitet", "wartet auf Dich", "hängt vielleicht", "startet"):
            self.assertIn(zustand, gesundheit.EMOJI)


if __name__ == "__main__":
    unittest.main()
