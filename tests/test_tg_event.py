import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tg_event

class T(unittest.TestCase):
    def test_copy_ok(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "l.json"
            log.write_text(json.dumps({"version": "1.1", "status": "success",
                "source": {"name": "A001"}, "destination": {"path": "/Volumes/RAID/P/A001"},
                "started": "2026-10-12T00:00:00+07:00", "files": [],
                "clips": [{"assets": [{"status": "verified", "size": 2_000_000_000}]}]}))
            msg = tg_event.message({"FileCopyCompleted_state": "Success",
                "FileCopyCompleted_destinationPath": "/Volumes/RAID/P/A001",
                "FileCopyCompleted_presetName": "P_OCF", "FileCopyCompleted_verification_mode": "Source",
                "FileCopyCompleted_transferLogJSONPath": str(log)})
            self.assertTrue(msg.startswith("✅"))
            self.assertIn("A001", msg); self.assertIn("2.00 GB", msg); self.assertIn("lỗi 0", msg)

    def test_copy_with_problems_is_warning(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "l.json"
            log.write_text(json.dumps({"version": "1.1", "status": "warnings",
                "source": {"name": "A001"}, "destination": {"path": "/x"}, "started": "",
                "files": [], "clips": [{"assets": [{"status": "failed_verification",
                "source": {"path": "/s/c.mp4"}, "errorMessage": "bad"}]}]}))
            msg = tg_event.message({"FileCopyCompleted_state": "Warnings",
                "FileCopyCompleted_destinationPath": "/x", "FileCopyCompleted_transferLogJSONPath": str(log)})
            self.assertTrue(msg.startswith("⚠️"))
            self.assertIn("/s/c.mp4", msg); self.assertIn("KHÔNG format", msg)

    def test_copy_log_missing_still_reports(self):
        msg = tg_event.message({"FileCopyCompleted_state": "Failed",
                                "FileCopyCompleted_destinationPath": "/x",
                                "FileCopyCompleted_transferLogJSONPath": "/nope.json"})
        self.assertTrue(msg.startswith("❌"))

    def test_silent_rename_duplicates_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "CLIP").mkdir()
            for n in ("A001C004.MP4", "A001C004 2.MP4", "A001C005.MP4"):
                (Path(d) / "CLIP" / n).write_text("x")
            log = Path(d) / "l.json"
            log.write_text(json.dumps({"version": "1.1", "status": "success", "source": {"name": "C001"},
                "destination": {"path": d}, "started": "", "files": [], "clips": []}))
            msg = tg_event.message({"FileCopyCompleted_state": "Success",
                "FileCopyCompleted_destinationPath": d, "FileCopyCompleted_transferLogJSONPath": str(log)})
            self.assertTrue(msg.startswith("⚠️"))
            self.assertIn("A001C004 2.MP4", msg)

    def test_verification_issue(self):
        msg = tg_event.message({"VerificationIssue_description": "Inconsistent read",
                                "VerificationIssue_filePath": "/Volumes/A001/C1.mov"})
        self.assertTrue(msg.startswith("🚨")); self.assertIn("/Volumes/A001/C1.mov", msg)

    def test_unknown_event_ignored(self):
        self.assertIsNone(tg_event.message({"DiskAdded_title": "X"}))

if __name__ == "__main__":
    unittest.main()
