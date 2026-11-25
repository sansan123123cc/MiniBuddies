"""윈도우 8.3 짧은 경로처럼 '실제 경로와 다른 이름'으로 팩 폴더가 들어와도 팩을 읽을 수 있어야 함."""

import os
import tempfile
import unittest
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from minibuddies.plugins.packs import pack_file


class AliasedFolderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_pack_file_through_alias(self):
        with tempfile.TemporaryDirectory() as real:
            alias = Path(real).parent / (Path(real).name + "-alias")
            os.symlink(real, alias)
            try:
                (Path(real) / "plugin.json").write_text("{}", encoding="utf-8")
                self.assertEqual(pack_file(alias, "plugin.json"), (Path(real) / "plugin.json").resolve())
                with self.assertRaises(ValueError):
                    pack_file(alias, "../outside.json")
            finally:
                alias.unlink()


if __name__ == "__main__":
    unittest.main()
