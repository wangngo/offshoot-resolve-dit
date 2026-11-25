import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import oslog

OLD = {"status": "Warnings", "sourceName": "A001", "destination": "/Volumes/D1/A001",
       "started": "2025-12-21T18:24:12.699+07:00", "presetName": "OCF", "transferredFileCount": 3,
       "totalNumberOfBytesTransferred": 300, "hashTypes": ["XXH64BE"],
       "failedVerificationFiles": [{"source": {"path": "/s/a.json"}, "errorMessage": "Inconsistent"}],
       "missingFiles": [{"source": {"path": "/s/b.mov"}}]}

NEW = {"version": "1.1", "status": "warnings", "verificationMode": "source",
       "source": {"name": "A001", "paths": ["/Volumes/A001"]},
       "destination": {"name": "D1", "path": "/Volumes/D1/P/20261012/Camera_Media/A001"},
       "preset": {"name": "P_OCF", "elements": []}, "started": "2026-10-12T00:11:35.845+07:00",
       "hashTypes": ["XXH64BE"],
       "files": [{"status": "filtered", "size": 5, "source": {"path": "/s/x.xml"}},
                 {"status": "failed_verification", "size": 7, "source": {"path": "/s/y.json"},
                  "errorMessage": "Inconsistent file size detected on destination"}],
       "clips": [{"assets": [{"status": "verified", "size": 100, "source": {"path": "/s/c1.mp4"}},
                             {"status": "missing", "size": 50, "source": {"path": "/s/c2.mp4"}}]}]}

class T(unittest.TestCase):
    def test_old_schema(self):
        n = oslog.normalize(OLD)
        self.assertEqual((n["status"], n["source"], n["dest"], n["preset"]),
                         ("Warnings", "A001", "/Volumes/D1/A001", "OCF"))
        self.assertEqual((n["files"], n["bytes"]), (3, 300))
        self.assertEqual([(p["kind"], p["path"]) for p in n["problems"]],
                         [("verify", "/s/a.json"), ("missing", "/s/b.mov")])

    def test_new_schema(self):
        n = oslog.normalize(NEW)
        self.assertEqual((n["status"], n["source"], n["dest"], n["preset"], n["mode"]),
                         ("Warnings", "A001", "/Volumes/D1/P/20261012/Camera_Media/A001", "P_OCF", "source"))
        self.assertEqual(n["files"], 3)          # filtered không tính là đã copy
        self.assertEqual(n["bytes"], 157)
        self.assertEqual(sorted((p["kind"], p["path"]) for p in n["problems"]),
                         [("missing", "/s/c2.mp4"), ("verify", "/s/y.json")])

    def test_not_a_transfer_log(self):
        self.assertIsNone(oslog.normalize({"foo": 1}))

if __name__ == "__main__":
    unittest.main()
