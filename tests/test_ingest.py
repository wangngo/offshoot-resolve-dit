import json, sys, tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest

TZ = timezone(timedelta(hours=7))

def log(d, name, **kw):
    (Path(d) / name).write_text(json.dumps(kw))

class T(unittest.TestCase):
    def test_roll_names(self):
        for ok in ("A001", "B123", "S001"):
            self.assertTrue(ingest.valid_roll(ok))
        for bad in ("A1", "a001", "A001 ", "Untitled", "A0001"):
            self.assertFalse(ingest.valid_roll(bad))

    def test_space_check(self):
        self.assertEqual(ingest.short_dests(1000, {"/d1": 5000, "/d2": 900}), ["/d2"])

    def test_collect_results_only_new_matching(self):
        t0 = datetime(2026, 10, 12, 1, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as d:
            log(d, "old.json", sourceName="A001", destination="/Volumes/D1/X/A001",
                started="2026-10-12T00:59:00.000+07:00", status="Success")
            log(d, "new1.json", sourceName="A001", destination="/Volumes/D1/X/A001",
                started="2026-10-12T01:00:05.000+07:00", status="Success",
                failedFiles=[], failedVerificationFiles=[], missingFiles=[])
            log(d, "other.json", sourceName="B001", destination="/Volumes/D2/X/B001",
                started="2026-10-12T01:00:05.000+07:00", status="Success")
            log(d, "new2.json", sourceName="A001", destination="/Volumes/D2/X/A001",
                started="2026-10-12T01:00:06.000+07:00", status="Warnings",
                failedVerificationFiles=[{"x": 1}])
            r = ingest.collect(Path(d), "A001", ["/Volumes/D1", "/Volumes/D2"], t0)
            self.assertEqual({k: v["status"] for k, v in r.items()},
                             {"/Volumes/D1": "Success", "/Volumes/D2": "Warnings"})
            self.assertEqual(r["/Volumes/D2"]["problems"], 1)

class Roll(unittest.TestCase):
    def test_expand(self):
        now = datetime(2026, 10, 12, 1, 0, tzinfo=TZ)
        self.assertEqual(ingest.expand("P/{YYYY}{MM}{DD}/Camera_Media/{Source Name}", "A001", now),
                         "P/20261012/Camera_Media/A001")
        self.assertIsNone(ingest.expand("P/{Content YYYY}/{Source Name}", "A001", now))
        self.assertIsNone(ingest.expand("", "A001", now))

    def test_existing_roll_detected(self):
        now = datetime(2026, 10, 12, 1, 0, tzinfo=TZ)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "P/20261012/Camera_Media/A001").mkdir(parents=True)
            (Path(d) / "P/20261012/Camera_Media/A001/x.mp4").write_text("x")
            pat = "P/{YYYY}{MM}{DD}/Camera_Media/{Source Name}"
            self.assertEqual(ingest.existing_rolls(pat, "A001", [d], now), [d])
            self.assertEqual(ingest.existing_rolls(pat, "A002", [d], now), [])


class Preflight(unittest.TestCase):
    def _env(self, d):
        d = Path(d)
        (d / "card/CLIP").mkdir(parents=True); (d / "card/CLIP/a.mp4").write_bytes(b"x" * 1000)
        (d / "D1").mkdir(); (d / "D2").mkdir(); (d / "presets").mkdir()
        (d / "presets/P_OCF.hedge").write_text(json.dumps([{"folderPattern": "P/{YYYY}{MM}{DD}/Camera_Media/{Source Name}"}]))
        return d

    def test_ok(self):
        with tempfile.TemporaryDirectory() as d:
            d = self._env(d)
            r = ingest.preflight(str(d / "card"), "A001", "P_OCF", [str(d / "D1"), str(d / "D2")], presets_dir=d / "presets")
            self.assertEqual(r["errors"], [])
            self.assertEqual(r["need_bytes"], 1000)
            self.assertTrue(any("chung một volume" in w for w in r["warnings"]))  # tmp cùng ổ

    def test_errors_collected(self):
        with tempfile.TemporaryDirectory() as d:
            d = self._env(d)
            r = ingest.preflight(str(d / "nope"), "a1", "XX", [str(d / "D1"), str(d / "D1")], presets_dir=d / "presets")
            joined = " | ".join(r["errors"])
            for frag in ("không thấy thẻ", "sai chuẩn", "không có preset", "trùng"):
                self.assertIn(frag, joined)

    def test_existing_roll_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            d = self._env(d)
            day = datetime.now().strftime("%Y%m%d")
            roll = d / "D1/P" / day / "Camera_Media/A001"; roll.mkdir(parents=True); (roll / "x").write_text("x")
            r = ingest.preflight(str(d / "card"), "A001", "P_OCF", [str(d / "D1")], presets_dir=d / "presets")
            self.assertTrue(any("đã có" in e for e in r["errors"]))


if __name__ == "__main__":
    unittest.main()


class StartConfirm(unittest.TestCase):
    # E2E 2026-11-14: OffShoot chưa nhận ổ nguồn → setSource rơi im lặng, API vẫn 'success'
    EV = "14/11/26, 00:13:31 - Source Added: {\n}\n"
    def test_transfers_added_only_after_offset(self):
        with tempfile.TemporaryDirectory() as d:
            ev = Path(d) / "OffShootEvents.log"
            ev.write_text("12/10/26, 00:47:42 - Transfers Added: {\n}\n")   # cũ, trước offset
            off = ev.stat().st_size
            with ev.open("a") as f: f.write(self.EV)
            self.assertFalse(ingest.transfers_added(ev, off))
            with ev.open("a") as f: f.write("14/11/26, 00:14:42 - Transfers Added: {\n}\n")
            self.assertTrue(ingest.transfers_added(ev, off))

    def test_transfers_added_must_match_roll(self):
        with tempfile.TemporaryDirectory() as d:
            ev = Path(d) / "e.log"; ev.write_text("")
            with ev.open("a") as f:
                f.write('14/11/26, 00:14:42 - Transfers Added: {\n  sourceLabel = B007;\n}\n')
            self.assertFalse(ingest.transfers_added(ev, 0, "A001"))   # transfer khác chen vào
            with ev.open("a") as f:
                f.write('14/11/26, 00:14:43 - Transfers Added: {\n        sourceLabel = A001;\n}\n')
            self.assertTrue(ingest.transfers_added(ev, 0, "A001"))
            self.assertFalse(ingest.transfers_added(ev, 0, "A00"))

    def test_log_truncated_reads_from_start(self):
        with tempfile.TemporaryDirectory() as d:
            ev = Path(d) / "e.log"; ev.write_text("x - Transfers Added: {\n sourceLabel = A001;\n}\n")
            self.assertTrue(ingest.transfers_added(ev, 10**9, "A001"))

    def test_missing_event_log_is_false(self):
        self.assertFalse(ingest.transfers_added(Path("/nonexistent/x.log"), 0))


class NaiveTime(unittest.TestCase):
    def test_collect_accepts_naive_t0(self):
        # started_at không có múi giờ từng làm ingest_status crash (naive vs aware)
        with tempfile.TemporaryDirectory() as d:
            log(d, "a.json", sourceName="A001", destination="/Volumes/D1/X/A001",
                started="2026-10-12T01:00:05.000+07:00", status="Success")
            t0 = datetime(2026, 10, 12, 1, 0).replace(tzinfo=None)
            r = ingest.collect(Path(d), "A001", ["/Volumes/D1"], ingest.aware(t0, TZ))
            self.assertEqual(list(r), ["/Volumes/D1"])

    def test_aware_keeps_offset(self):
        t = datetime(2026, 1, 1, 0, 0, tzinfo=TZ)
        self.assertEqual(ingest.aware(t), t)
        self.assertEqual(ingest.aware(datetime(2026, 1, 1, 0, 0), TZ).utcoffset(), timedelta(hours=7))
