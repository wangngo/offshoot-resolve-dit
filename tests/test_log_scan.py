import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import log_scan

def write(d, name, **kw):
    base = {"status": "Success", "presetName": "OCF", "sourceName": "A001",
            "destination": "/Volumes/HDD/SHOW/A001", "started": "2025-12-21T18:24:12.699+07:00",
            "transferredFileCount": 10, "totalNumberOfBytesTransferred": 1000,
            "hashTypes": ["XXH64BE"], "failedFiles": [], "failedVerificationFiles": [],
            "missingFiles": []}
    base.update(kw)
    (Path(d) / name).write_text(json.dumps(base))

class T(unittest.TestCase):
    def test_summary_counts_and_problems(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "a.json")
            write(d, "b.json", status="Warnings", failedVerificationFiles=[
                {"source": {"path": "/s/T18.json"}, "errorMessage": "Inconsistent file size detected on destination"}])
            write(d, "c.json", status="Failed", failedFiles=[
                {"source": {"path": "/s/x.mov"}, "errorMessage": "Input/output error"}])
            rows = log_scan.load(Path(d))
            self.assertEqual(len(rows), 3)
            s = log_scan.summarize(rows)
            self.assertEqual(s["status"], {"Success": 1, "Warnings": 1, "Failed": 1})
            self.assertEqual(s["bytes"], 3000)
            probs = log_scan.problems(rows)
            self.assertEqual(len(probs), 2)
            self.assertIn(("verify", "/s/T18.json", "Inconsistent file size detected on destination"),
                          [(p["kind"], p["path"], p["error"]) for p in probs])

    def test_bad_json_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.json").write_text("{not json")
            write(d, "ok.json")
            self.assertEqual(len(log_scan.load(Path(d))), 1)

if __name__ == "__main__":
    unittest.main()
