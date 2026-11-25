import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mkpreset

class T(unittest.TestCase):
    def test_sanitize(self):
        self.assertEqual(mkpreset.sanitize("Chef's Table"), "CHEFS_TABLE")
        self.assertEqual(mkpreset.sanitize("Phim Đà Nẵng 2"), "PHIM_DA_NANG_2")
        with self.assertRaises(ValueError):
            mkpreset.sanitize("!!!")

    def test_presets_follow_netflix_layout(self):
        with tempfile.TemporaryDirectory() as d:
            paths = mkpreset.write("Demo Show", Path(d))
            names = sorted(p.name for p in paths)
            self.assertEqual(names, ["DEMO_SHOW_OCF.hedge", "DEMO_SHOW_SOUND.hedge"])
            ocf = json.loads((Path(d) / "DEMO_SHOW_OCF.hedge").read_text())[0]
            self.assertEqual(ocf["folderPattern"], "DEMO_SHOW/{YYYY}{MM}{DD}/Camera_Media/{Source Name}")
            self.assertFalse(ocf["flattenFolders"])           # giữ nguyên cấu trúc thẻ
            self.assertEqual(ocf["doNotCopyFiles"], [""])     # không lọc gì
            self.assertEqual(ocf["renamePattern"], "")        # không đổi tên OCF
            snd = json.loads((Path(d) / "DEMO_SHOW_SOUND.hedge").read_text())[0]
            self.assertIn("/Sound_Media/", snd["folderPattern"])

    def test_no_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            mkpreset.write("X1", Path(d))
            with self.assertRaises(FileExistsError):
                mkpreset.write("X1", Path(d))

if __name__ == "__main__":
    unittest.main()
