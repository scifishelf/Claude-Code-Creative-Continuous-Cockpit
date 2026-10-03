"""Statische Prüfungen der Oberfläche."""

import re
import unittest
from pathlib import Path
from unittest import mock

from fivec import dienst, uebersicht

WEB = Path(dienst.__file__).resolve().parent / "web"


class WebTest(unittest.TestCase):
    def test_keine_externen_quellen(self):
        """Alles kommt aus 'self': keine CDN, keine Google Fonts (CSP default-src 'self')."""
        for datei in WEB.rglob("*"):
            if datei.suffix not in (".html", ".css", ".js", ".svg"):
                continue
            text = datei.read_text()
            treffer = re.findall(r"(?:src|href|url\()\s*=?\s*[\"']?(https?:)?//", text)
            self.assertEqual(treffer, [], f"externe Quelle in {datei.name}")

    def test_kein_innerhtml(self):
        """Namen, Prompts und Pfade sind fremder Text und dürfen nie als HTML laufen."""
        for datei in WEB.glob("*.js"):
            treffer = re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", datei.read_text())
            self.assertIsNone(treffer, f"{datei.name}: {treffer and treffer.group(0)}")

    def test_keine_inline_styles_oder_skripte(self):
        """Die CSP verbietet beides; ein Rückfall würde still nicht greifen."""
        html = (WEB / "index.html").read_text()
        self.assertNotIn("style=", html)
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)")
        self.assertNotRegex(html, r"\son[a-z]+=")

    def test_jede_statische_datei_existiert(self):
        for datei, _ in dienst.STATISCH.values():
            self.assertTrue((WEB / datei).is_file(), datei)

    def test_keine_gedankenstriche(self):
        for datei in WEB.rglob("*"):
            if datei.suffix in (".html", ".css", ".js", ".svg"):
                self.assertNotRegex(datei.read_text(), "[–—]", datei.name)


class KurzPfadTest(unittest.TestCase):
    def test_heim_wird_tilde(self):
        with mock.patch("fivec.uebersicht.Path.home", return_value=Path("/Users/nutzer")):
            self.assertEqual(uebersicht.kurz_pfad("/Users/nutzer/Desktop/x"), "~/Desktop/x")
            self.assertEqual(uebersicht.kurz_pfad("/Users/nutzer"), "~")
            # Nur ganze Pfadteile: ein Nachbarordner mit gleichem Anfang bleibt, wie er ist.
            self.assertEqual(uebersicht.kurz_pfad("/Users/nutzer2/x"), "/Users/nutzer2/x")
            self.assertEqual(uebersicht.kurz_pfad(None), "?")


if __name__ == "__main__":
    unittest.main()
