import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import xxhash  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False
import mhl_verify

EMPTY, ABC = "ef46db3751d8e999", "44bc2cf5ad770999"   # xxh64 test vectors (seed 0)

LEGACY = """<?xml version="1.0" encoding="UTF-8"?><hashlist version="1.1">
<hash><file>CLIP/empty.mp4</file><size>0</size><xxhash64be>{e}</xxhash64be></hash>
<hash><file>CLIP/abc.mp4</file><size>3</size><xxhash64be>{a}</xxhash64be></hash>
<hash><file>CLIP/bad.mp4</file><size>3</size><xxhash64be>{e}</xxhash64be></hash>
<hash><file>CLIP/gone.mp4</file><size>3</size><xxhash64be>{a}</xxhash64be></hash>
</hashlist>"""

ASC = """<?xml version="1.0"?><hashlist xmlns="urn:ASC:MHL:v2.0" version="2.0"><hashes>
<hash><path size="3">CLIP/abc.mp4</path><xxh64 action="original">{a}</xxh64></hash>
<hash><path size="3">CLIP/bad.mp4</path><xxh64 action="original">{a}</xxh64></hash>
</hashes></hashlist>"""

def roll(d):
    c = Path(d) / "CLIP"; c.mkdir()
    (c / "empty.mp4").write_bytes(b""); (c / "abc.mp4").write_bytes(b"abc"); (c / "bad.mp4").write_bytes(b"abd")
    return Path(d)

@unittest.skipUnless(HAVE, "cần gói xxhash")
class T(unittest.TestCase):
    def test_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            r = roll(d); (r / "x.mhl").write_text(LEGACY.format(e=EMPTY, a=ABC))
            res = mhl_verify.verify(r)
            self.assertEqual(res["ok"], 2)
            self.assertEqual(sorted((p["path"], p["kind"]) for p in res["problems"]),
                             [("CLIP/bad.mp4", "hash_mismatch"), ("CLIP/gone.mp4", "missing")])

    def test_asc(self):
        with tempfile.TemporaryDirectory() as d:
            r = roll(d); (r / "ascmhl").mkdir()
            (r / "ascmhl/0001_A001.mhl").write_text(ASC.format(a=ABC))
            res = mhl_verify.verify(r)
            self.assertEqual(res["format"], "asc")
            self.assertEqual(res["ok"], 1)
            # empty.mp4 có trên đĩa nhưng không có trong MHL → unlisted
            self.assertEqual(sorted((p["path"], p["kind"]) for p in res["problems"]),
                             [("CLIP/bad.mp4", "hash_mismatch"), ("CLIP/empty.mp4", "unlisted")])
            self.assertFalse(res["passed"])

    def test_asc_clean_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); (r / "CLIP").mkdir(); (r / "CLIP/abc.mp4").write_bytes(b"abc")
            (r / "ascmhl").mkdir(); (r / "ascmhl/0001_A001.mhl").write_text(
                ASC.format(a=ABC).replace('<hash><path size="3">CLIP/bad.mp4</path><xxh64 action="original">%s</xxh64></hash>' % ABC, ""))
            (r / "ascmhl/ascmhl_chain.xml").write_text("<x/>"); (r / ".DS_Store").write_bytes(b"x")
            res = mhl_verify.verify(r)
            self.assertEqual((res["checked"], res["ok"], res["problems"], res["passed"]), (1, 1, [], True))

    def test_extra_duplicate_file_flagged(self):
        # OffShoot gặp tên trùng ghi "<tên> 2.ext" mà vẫn Success; MHL không liệt kê → phải bắt
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); (r / "CLIP").mkdir(); (r / "CLIP/abc.mp4").write_bytes(b"abc")
            (r / "CLIP/abc 2.mp4").write_bytes(b"abc")
            (r / "ascmhl").mkdir(); (r / "ascmhl/0001_A001.mhl").write_text(
                ASC.format(a=ABC).replace('<hash><path size="3">CLIP/bad.mp4</path><xxh64 action="original">%s</xxh64></hash>' % ABC, ""))
            res = mhl_verify.verify(r)
            self.assertEqual([(p["path"], p["kind"]) for p in res["problems"]], [("CLIP/abc 2.mp4", "unlisted")])
            self.assertFalse(res["passed"])

    def test_no_mhl(self):
        with tempfile.TemporaryDirectory() as d:
            res = mhl_verify.verify(Path(d))
            self.assertEqual(res["format"], None)
            self.assertFalse(res["passed"])   # không có MHL ≠ pass (trỏ nhầm thư mục cha)

    def test_nfd_on_disk_matches_nfc_in_mhl(self):
        import unicodedata, xxhash
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); (r / "CLIP").mkdir()
            name = "cảnh.mp4"
            (r / "CLIP" / unicodedata.normalize("NFD", name)).write_bytes(b"abc")
            (r / "CLIP/sub/ascmhl").mkdir(parents=True); (r / "CLIP/sub/ascmhl/x.mhl").write_text("<x/>")
            (r / "ascmhl").mkdir(); (r / "ascmhl/0001_A001.mhl").write_text(
                '<?xml version="1.0"?><hashlist xmlns="urn:ASC:MHL:v2.0" version="2.0"><hashes>'
                '<hash><path size="3">CLIP/%s</path><xxh64 action="original">%s</xxh64></hash></hashes></hashlist>'
                % (unicodedata.normalize("NFC", name), ABC))
            res = mhl_verify.verify(r)
            self.assertEqual(res["problems"], [])
            self.assertTrue(res["passed"])

if __name__ == "__main__":
    unittest.main()
