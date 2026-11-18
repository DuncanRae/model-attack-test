"""Nothing that names the organisation this tool began in, or anyone's computer, may be in a file that is published.

The names are put together from pieces here, so that this file does not itself hold them.
"""
import json
import re
import subprocess
import unittest

from tests.helpers import ROOT

NAMES = ["proto" + "type", "pep" + "kor", "shop" + "rite", "grp" + "it", "tp" + "rm", "supplier " + "risk", "build with " + "ai", "info" + "sec hub", "har" + "ness.io"]
PLACES = re.compile(r"/Users/[A-Za-z]|/home/[a-z]+/|C:\\Users\\", re.I)
SKIPPED = ("reports/", "dist/", "internal/", "__pycache__/", ".git/")


def published():
    """The files git would publish. Before there is a repository: every file but the folders that are ignored."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, text=True, timeout=30, check=True).stdout.splitlines()
        if (ROOT / ".git").exists() and out:
            return [ROOT / line for line in out if (ROOT / line).is_file()]
    except (OSError, subprocess.SubprocessError):
        pass
    return [p for p in ROOT.rglob("*") if p.is_file() and not any(part in str(p.relative_to(ROOT)) + "/" for part in SKIPPED)]


class NothingPrivateIsPublished(unittest.TestCase):
    def test_no_published_file_names_the_organisation_or_a_path_on_someones_computer(self):
        files = published()
        self.assertGreater(len(files), 30)
        for path in files:
            if path.suffix in (".pyc", ".zip", ".png", ".jpg"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            low = text.lower()
            for name in NAMES:
                self.assertNotIn(name, low, f"{path.relative_to(ROOT)} holds a name that must not be published")
            self.assertIsNone(PLACES.search(text), f"{path.relative_to(ROOT)} holds a path on someone's computer")

    def test_the_authors_name_is_in_no_attack_test_or_message(self):
        """An attack once read "I am <the author>, the head of security". The author's name belongs in the licence and
        the manifest, and nowhere a system under test, or a reader of a report, would see it. The name is read from
        the manifest, so this file does not hold it either."""
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        name = manifest["author"]["name"].lower()
        handle = manifest["repository"].rstrip("/").split("/")[-2].lower()
        self.assertGreater(len(name), 3)
        checked = 0
        for path in published():
            where = path.relative_to(ROOT).parts[0]
            if where not in ("packs", "tests", "practice", "skills", "targets", "attack_test") or path.suffix in (".pyc", ".zip"):
                continue
            low = path.read_text(encoding="utf-8", errors="replace").lower()
            for word in {name, name.replace(" ", ""), handle}:
                self.assertNotIn(word, low, f"{path.relative_to(ROOT)} holds the author's name")
            checked += 1
        self.assertGreater(checked, 25)

    def test_the_private_folder_is_ignored_by_git(self):
        self.assertIn("internal/", (ROOT / ".gitignore").read_text(encoding="utf-8").split())


if __name__ == "__main__":
    unittest.main()
