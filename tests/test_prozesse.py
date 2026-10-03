import unittest

from fivec import prozesse

SID = "64acb6d7-79e6-43a0-8bb0-5d676ddf5ead"

# Gekürzt nach echter `ps -axww -o pid=,ppid=,pcpu=,rss=,etime=,tty=,lstart=,command=`-Ausgabe vom 03.10.2026.
PS = f"""\
  900     1   1.0 100000 05:00:00 ??       Sat Oct  3 07:00:00 2026     /Applications/iTerm.app/Contents/MacOS/iTerm2
  950   900   0.0   2000 04:00:00 ??       Sat Oct  3 08:00:00 2026     /Applications/iTerm.app/Contents/MacOS/iTermServer-3.7.3 /x
 6015   950   0.0   1000 01:00:00 ttys017  Sat Oct  3 10:32:51 2026     /usr/bin/login -fpl nutzer /Applications/iTerm.app/Contents/MacOS/ShellLauncher --launch_shell
 6022  6015   0.0   3000 01:00:00 ttys017  Sat Oct  3 10:32:51 2026     -zsh
 9549  6022   2,5 356352 06:32 ttys017  Sat Oct  3 10:35:18 2026     claude --resume {SID}
 9551  9549   0.0    900 06:32 ttys017  Sat Oct  3 10:35:18 2026     caffeinate -dims claude --resume {SID}
 1207     1   3.0 500000 09:00:00 ??       Sat Oct  3 01:00:00 2026     /Applications/Cursor.app/Contents/MacOS/Cursor
 1930  1207   0.0  40000 08:00:00 ??       Sat Oct  3 02:00:00 2026     Cursor Helper: terminal pty-host
72228  1930   0.0   3000 02:10:00 ttys003  Sat Oct  3 09:55:30 2026     /bin/zsh -i
72366 72228   6.1 663472 02:10:58 ttys003  Sat Oct  3 09:55:37 2026     claude
 1511  1209   0.0  95520 11:37:03 ??       Sat Oct  3 00:29:32 2026     /Applications/Claude.app/Contents/Frameworks/Claude Helper (Renderer).app/Contents/MacOS/Claude Helper (Renderer) --type=renderer
kaputte zeile
"""


class ProzesseTest(unittest.TestCase):
    def setUp(self):
        self.tab = prozesse.parsen(PS)

    def test_parsen(self):
        p = self.tab[9549]
        self.assertEqual(p["ppid"], 6022)
        self.assertEqual(p["cpu"], 2.5, "Komma als Dezimaltrenner")
        self.assertEqual(p["tty"], "ttys017")
        self.assertEqual(p["lstart"], "Sat Oct  3 10:35:18 2026".replace("  ", " "))
        self.assertEqual(p["command"], f"claude --resume {SID}")
        self.assertIn("Claude Helper (Renderer).app", self.tab[1511]["command"])
        self.assertNotIn("kaputte", str(self.tab))

    def test_info_fuer_lebendpruefung(self):
        tty, lstart = prozesse.info_von(self.tab)(72366)
        self.assertEqual(tty, "ttys003")
        self.assertEqual(lstart.split(), "Sat Oct 3 09:55:37 2026".split())
        self.assertIsNone(prozesse.info_von(self.tab)(424242))

    def test_app_iterm_nicht_ueber_login_argument(self):
        self.assertEqual(prozesse.app_fuer(9549, self.tab), "/Applications/iTerm.app")

    def test_app_cursor_ueber_pty_host(self):
        self.assertEqual(prozesse.app_fuer(72366, self.tab), "/Applications/Cursor.app")

    def test_app_mit_leerzeichen_im_pfad(self):
        self.assertEqual(prozesse.app_fuer(1511, self.tab), "/Applications/Claude.app")

    def test_startende_nur_claude_nicht_caffeinate(self):
        self.assertEqual(prozesse.startende(self.tab), {SID: 9549})

    def test_kennzahlen(self):
        k = prozesse.kennzahlen(9549, self.tab)
        self.assertEqual(k["app"], "iTerm")
        self.assertEqual(k["speicher_mb"], 348)
        self.assertEqual(k["laufzeit"], "06:32")
        self.assertTrue(k["caffeinate"])
        self.assertFalse(prozesse.kennzahlen(72366, self.tab)["caffeinate"])
        self.assertIsNone(prozesse.kennzahlen(1, self.tab))


if __name__ == "__main__":
    unittest.main()
