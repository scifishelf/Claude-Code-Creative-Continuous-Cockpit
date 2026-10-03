import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fivec import live


class StartzeitTest(unittest.TestCase):
    """Gemessen am 03.10.2026: procStart 08:32:51 (UTC) = ps lstart 10:32:51 (MESZ)."""

    def setUp(self):
        self.tz_alt = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        time.tzset()

    def tearDown(self):
        if self.tz_alt is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.tz_alt
        time.tzset()

    def test_utc_gegen_ortszeit(self):
        self.assertTrue(live.gleiche_startzeit("Sat Oct  3 08:32:51 2026", "Sat Oct  3 10:32:51 2026"))

    def test_naive_gleichheit_ist_falsch(self):
        self.assertFalse(live.gleiche_startzeit("Sat Oct  3 10:32:51 2026", "Sat Oct  3 10:32:51 2026"))

    def test_unlesbar(self):
        self.assertFalse(live.gleiche_startzeit("", "Sat Oct  3 10:32:51 2026"))


class LaufendeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "sessions").mkdir()

    def statusdatei(self, pid, sid, proc_start, **kw):
        (self.tmp / "sessions" / f"{pid}.json").write_text(
            json.dumps({"pid": pid, "sessionId": sid, "procStart": proc_start, "status": "idle", **kw})
        )

    def test_eigener_prozess_laeuft(self):
        pid = os.getpid()
        tty, lstart = live.prozess_info(pid)
        utc = time.strftime(live.PS_FORMAT, time.gmtime(time.mktime(time.strptime(lstart, live.PS_FORMAT))))
        self.statusdatei(pid, "a", utc)
        stand = live.laufende(self.tmp)["a"]
        self.assertEqual(stand["zustand"], "läuft")
        self.assertEqual(stand["tty"], tty)

    def test_toter_prozess_ist_verwaist(self):
        self.statusdatei(999999, "b", "Sat Oct  3 08:32:51 2026")
        self.assertEqual(live.laufende(self.tmp)["b"]["zustand"], "verwaist")

    def test_wiederverwendete_pid_ist_verwaist(self):
        # Prozess lebt, aber die Startzeit gehört zu einem anderen.
        self.statusdatei(os.getpid(), "c", "Mon Jan  1 00:00:00 2024")
        self.assertEqual(live.laufende(self.tmp)["c"]["zustand"], "verwaist")

    def test_key_dateien_werden_nicht_gelesen(self):
        (self.tmp / "sessions" / "123.abc.key").write_text("geheim")
        gelesen = []
        original = Path.read_text

        def mitschreiben(pfad, *a, **kw):
            gelesen.append(pfad.name)
            return original(pfad, *a, **kw)

        with mock.patch.object(Path, "read_text", mitschreiben):
            self.assertEqual(live.laufende(self.tmp), {})
        self.assertNotIn("123.abc.key", gelesen)

    def test_lebende_datei_gewinnt(self):
        pid = os.getpid()
        _, lstart = live.prozess_info(pid)
        utc = time.strftime(live.PS_FORMAT, time.gmtime(time.mktime(time.strptime(lstart, live.PS_FORMAT))))
        self.statusdatei(999999, "d", "Sat Oct  3 08:32:51 2026")
        self.statusdatei(pid, "d", utc)
        self.assertEqual(live.laufende(self.tmp)["d"]["zustand"], "läuft")


if __name__ == "__main__":
    unittest.main()
