import sys, os, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import resolve_dailies as rd

class T(unittest.TestCase):
    def test_new_files_skips_existing(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "A.MP4"), os.path.join(d, "B.MP4")
            open(a, "w").close(); open(b, "w").close()
            self.assertEqual(rd.new_files([a, b], [a]), [b])
            self.assertEqual(rd.new_files([a], [d + "/./A.MP4"]), [])

    def test_sort_by_tc_dropframe_and_missing_last(self):
        tcs = {"c": "10:00:40:00", "a": "09:59:59;29", "b": "10:00:00:00", "x": None}
        self.assertEqual(rd.sort_by_tc(list(tcs), tcs.get), ["a", "b", "c", "x"])

    def test_unsynced(self):
        s = {"v1": "S001T01.WAV", "v2": "", "v3": None}
        self.assertEqual(rd.unsynced(list(s), s.get), ["v2", "v3"])

    def test_clip_label_keeps_roll(self):
        rolls = {"A001", "A002"}
        a = rd.clip_label("/V/D1/P/20261114/Camera_Media/A001/PRIVATE/M4ROOT/CLIP/A001C001.MP4", rolls)
        b = rd.clip_label("/V/D1/P/20261114/Camera_Media/A002/PRIVATE/M4ROOT/CLIP/A001C001.MP4", rolls)
        self.assertEqual((a, b), ("A001/A001C001.MP4", "A002/A001C001.MP4"))

    def test_missing_after_import(self):
        self.assertEqual(rd.missing_after_import(["/a/X.MP4", "/a/Y.MP4"], ["/a/X.MP4"]), ["/a/Y.MP4"])

    def test_not_in_timeline(self):
        self.assertEqual(rd.not_in(["v1", "v2", "v3"], ["v1"]), ["v2", "v3"])

if __name__ == "__main__":
    unittest.main()
