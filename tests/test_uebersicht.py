import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from fivec import prozesse, uebersicht

STARTET = "11111111-2222-3333-4444-555555555555"
HAENGT = "22222222-2222-3333-4444-555555555555"
ALT = "33333333-2222-3333-4444-555555555555"


def iso_vor(minuten):
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten)).isoformat().replace("+00:00", "Z")


class UebersichtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        projekt = self.tmp / "claude" / "projects" / "-p"
        projekt.mkdir(parents=True)
        (self.tmp / "claude" / "sessions").mkdir()
        for sid, minuten in ((STARTET, 60 * 24 * 30), (HAENGT, 15), (ALT, 60 * 24 * 30)):
            (projekt / f"{sid}.jsonl").write_text(json.dumps({
                "type": "user", "timestamp": iso_vor(minuten), "cwd": "/gibt/es/nicht", "message": {"content": "x"},
            }) + "\n")
        # HAENGT: lebender Prozess (dieser Testlauf), seit 15 Min. busy
        pid = os.getpid()
        lstart = prozesse.tabelle().get(pid, {}).get("lstart") or time.strftime("%a %b %d %H:%M:%S %Y")
        proc_start_utc = time.strftime("%a %b %d %H:%M:%S %Y",
                                       time.gmtime(time.mktime(time.strptime(lstart, "%a %b %d %H:%M:%S %Y"))))
        (self.tmp / "claude" / "sessions" / f"{pid}.json").write_text(json.dumps({
            "pid": pid, "sessionId": HAENGT, "procStart": proc_start_utc, "status": "busy",
            "statusUpdatedAt": (time.time() - 15 * 60) * 1000,
        }))
        self.tab = {
            **prozesse.tabelle(),
            999001: {"pid": 999001, "ppid": 1, "cpu": 1.0, "rss_kb": 2048, "etime": "00:05", "tty": "ttys099",
                     "lstart": "Sat Oct 3 12:00:00 2026", "command": f"claude --resume {STARTET}"},
        }
        self.env = mock.patch.dict(os.environ, {"CLAUDE_HOME": str(self.tmp / "claude"), "FIVEC_HOME": str(self.tmp / "5c")})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_startet_und_haengt_sind_aktiv_und_immer_sichtbar(self):
        zeilen = {z["sid"]: z for z in uebersicht.sessions(1, tab=self.tab)}
        self.assertNotIn(ALT, zeilen, "alt und ruhend: außerhalb des Zeitraums")

        s = zeilen[STARTET]
        self.assertEqual(s["zustand"], "startet")
        self.assertTrue(s["aktiv"], "startet zählt zu „Läuft gerade“, obwohl außerhalb des Zeitraums")
        self.assertEqual(s["prozess"]["speicher_mb"], 2)

        h = zeilen[HAENGT]
        self.assertEqual(h["zustand"], "hängt vielleicht")
        self.assertTrue(h["aktiv"])
        self.assertGreaterEqual(h["still_s"], 14 * 60)


if __name__ == "__main__":
    unittest.main()
