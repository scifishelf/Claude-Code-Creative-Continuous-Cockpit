import subprocess
import tempfile
import unittest
from pathlib import Path

from fivec import gitstand


class GitstandTest(unittest.TestCase):
    def test_ordner_fehlt(self):
        self.assertEqual(gitstand.stand("/gibt/es/nicht"), {"art": "ordner_fehlt"})
        self.assertEqual(gitstand.stand(None), {"art": "ordner_fehlt"})

    def test_kein_repo(self):
        self.assertEqual(gitstand.stand(tempfile.mkdtemp()), {"art": "kein_repo"})

    def test_repo_mit_offener_datei(self):
        ordner = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(ordner)], check=True)
        (ordner / "a.txt").write_text("x")
        stand = gitstand.stand(str(ordner))
        self.assertEqual(stand["art"], "repo")
        self.assertEqual(stand["uncommittet"], 1)


if __name__ == "__main__":
    unittest.main()
