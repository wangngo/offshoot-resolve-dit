import os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import xxhash  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False
import handoff

ABC, ABD = "44bc2cf5ad770999", None
MHL = """<?xml version="1.0"?><hashlist xmlns="urn:ASC:MHL:v2.0" version="2.0"><hashes>{}</hashes></hashlist>"""
H = '<hash><path size="{s}">{p}</path><xxh64 action="original">{h}</xxh64></hash>'

def mkroll(d, files):
    """files: {relpath: bytes}; ghi ASC MHL đúng bằng xxhash thật."""
    import xxhash
    r = Path(d); (r / "ascmhl").mkdir(parents=True)
    entries = ""
    for rel, data in files.items():
        f = r / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(data)
        entries += H.format(s=len(data), p=rel, h=xxhash.xxh64(data).hexdigest())
    (r / "ascmhl/0001_A001.mhl").write_text(MHL.format(entries))
    return r

CARD = {"CLIP/A001C001.MP4": b"video1", "CLIP/A001C001M01.XML": b"<x/>", "CLIP/A001C002.MP4": b"video2"}

@unittest.skipUnless(HAVE, "cần gói xxhash")
class T(unittest.TestCase):
    def run_check(self, a_files, b_files, mode="SourceAndDestination", devs=None):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a, b = mkroll(d1, a_files), mkroll(d2, b_files)
            return handoff.check([str(a), str(b)], mode=mode, dev=devs or {str(a): 1, str(b): 2}.get)

    def test_ok_lists_media_only(self):
        res = self.run_check(CARD, CARD)
        self.assertTrue(res["ok"], res["reasons"])
        self.assertEqual([Path(m).name for m in res["media"]], ["A001C001.MP4", "A001C002.MP4"])

    def test_mode_must_be_s_and_d(self):
        res = self.run_check(CARD, CARD, mode="Source")
        self.assertFalse(res["ok"])
        self.assertTrue(any("SourceAndDestination" in x for x in res["reasons"]))

    def test_needs_two_physical_volumes(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a, b = mkroll(d1, CARD), mkroll(d2, CARD)
            res = handoff.check([str(a), str(b)], mode="SourceAndDestination", dev=lambda p: 7)
            self.assertFalse(res["ok"])

    def test_single_dest_rejected(self):
        with tempfile.TemporaryDirectory() as d1:
            res = handoff.check([str(mkroll(d1, CARD))], mode="SourceAndDestination", dev=lambda p: 1)
            self.assertFalse(res["ok"])

    def test_dests_differ(self):
        other = dict(CARD); other["CLIP/A001C002.MP4"] = b"videoX"   # MHL mỗi bên tự khớp nhưng 2 bản khác nhau
        res = self.run_check(CARD, other)
        self.assertFalse(res["ok"])
        self.assertTrue(any("A001C002.MP4" in x for x in res["reasons"]))

    def test_problem_on_one_dest_blocks(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a, b = mkroll(d1, CARD), mkroll(d2, CARD)
            (a / "CLIP/A001C002.MP4").write_bytes(b"videoZ")   # lật nội dung, giữ size
            res = handoff.check([str(a), str(b)], mode="SourceAndDestination", dev={str(a): 1, str(b): 2}.get)
            self.assertFalse(res["ok"])

    def test_parent_folder_without_mhl_rejected(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            mkroll(Path(d1) / "A001", CARD); mkroll(Path(d2) / "A001", CARD)
            res = handoff.check([d1, d2], mode="SourceAndDestination", dev={d1: 1, d2: 2}.get)
            self.assertFalse(res["ok"])

class Disk(unittest.TestCase):
    def test_disk_image_resolves_to_backing_disk(self):
        # E2E 2026-11-14: 2 DMG chung Macintosh HD từng ra disk8/disk10 (đĩa ảo) → PASS sai
        info = {"/Volumes/D1": {"BusProtocol": "Disk Image", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk6s1"}], "ParentWholeDisk": "disk7"},
                "/Volumes/D2": {"BusProtocol": "Disk Image", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk8s1"}], "ParentWholeDisk": "disk9"},
                "/": {"BusProtocol": "Apple Fabric", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}]}}
        images = {"/Users/w/lab/d1.dmg": ["/dev/disk6", "/dev/disk6s1", "/dev/disk7", "/dev/disk7s1"],
                  "/Users/w/lab/d2.dmg": ["/dev/disk8", "/dev/disk8s1", "/dev/disk9"]}
        mp = lambda p: "/Volumes/D1" if str(p).startswith("/Volumes/D1") else "/Volumes/D2" if str(p).startswith("/Volumes/D2") else "/"
        f = lambda p: handoff.physical_disk(p, info=lambda m: info[str(m)], images=lambda: images, mount=mp)
        self.assertEqual(f("/Volumes/D1/X/A001"), "disk0")
        self.assertEqual(f("/Volumes/D2/X/A001"), "disk0")

    def test_unknown_image_fails_closed(self):
        info = {"/Volumes/D1": {"BusProtocol": "Disk Image", "ParentWholeDisk": "disk7"}}
        self.assertIsNone(handoff.physical_disk("/Volumes/D1/x", info=lambda m: info[str(m)], images=lambda: {}, mount=lambda p: "/Volumes/D1"))

    def test_other_files_reported(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("A.MP4", "B.MTS", "C.xyz", "C.XML"):
                (Path(d) / n).write_bytes(b"x")
            media, skipped = handoff.media_files(d), handoff.skipped_files(d)
            self.assertEqual([Path(m).name for m in media], ["A.MP4", "B.MTS"])
            self.assertEqual([Path(m).name for m in skipped], ["C.xyz"])
    def test_unknown_disk_fails_closed(self):
        # E2E 2026-11-14: diskutil không nhận thư mục con → mỗi đích 'unknown:<path>' khác nhau → từng PASS sai
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            if not HAVE:
                self.skipTest("cần xxhash")
            a, b = mkroll(d1, CARD), mkroll(d2, CARD)
            res = handoff.check([str(a), str(b)], mode="SourceAndDestination", dev=lambda p: None)
            self.assertFalse(res["ok"])

    def test_mount_point_is_ancestor_mount(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "x/y"; sub.mkdir(parents=True)
            m = handoff.mount_point(sub)
            self.assertTrue(os.path.ismount(m))
            self.assertTrue(str(sub.resolve()).startswith(str(m)))

    def test_store_to_whole_disk(self):
        self.assertEqual(handoff.whole_disk("disk8s1"), "disk8")
        self.assertEqual(handoff.whole_disk("disk10s2"), "disk10")
        self.assertEqual(handoff.whole_disk("disk4"), "disk4")

if __name__ == "__main__":
    unittest.main()
