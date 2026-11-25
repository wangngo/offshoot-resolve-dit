"""Đọc transfer log JSON của OffShoot, chuẩn hoá 2 schema về một dạng:
- schema cũ (≤25.x): sourceName, destination=str, failedFiles/failedVerificationFiles/missingFiles
- schema 1.1 (26.x): version="1.1", source{}, destination{}, files[] + clips[].assets[] mỗi mục có status
"""
import json
from pathlib import Path

OLD_LISTS = {"failedFiles": "copy", "failedVerificationFiles": "verify", "missingFiles": "missing"}
NEW_PROBLEM = {"failed": "copy", "failed_verification": "verify", "missing": "missing",
               "not_transferred": "copy"}
NEW_NOT_COPIED = {"filtered", "skipped", "hidden"}


def _problem(kind, entry):
    return {"kind": kind, "path": (entry.get("source") or {}).get("path", ""),
            "error": entry.get("errorMessage") or f"({kind})"}


def normalize(d):
    if not isinstance(d, dict) or "status" not in d:
        return None
    if isinstance(d.get("destination"), dict):  # schema 1.1
        entries = list(d.get("files") or [])
        for c in d.get("clips") or []:
            entries += c.get("assets") or []
        copied = [e for e in entries if e.get("status") not in NEW_NOT_COPIED]
        return {
            "status": str(d["status"]).capitalize(),
            "source": (d.get("source") or {}).get("name", ""),
            "dest": d["destination"].get("path", ""),
            "preset": (d.get("preset") or {}).get("name") or "",
            "mode": d.get("verificationMode", ""),
            "started": d.get("started", ""),
            "hash": d.get("hashTypes") or [],
            "files": len(copied),
            "bytes": sum(e.get("size", 0) for e in copied),
            "problems": [_problem(NEW_PROBLEM[e["status"]], e)
                         for e in entries if e.get("status") in NEW_PROBLEM],
        }
    return {
        "status": d["status"],
        "source": d.get("sourceName", ""),
        "dest": d.get("destination", ""),
        "preset": d.get("presetName") or "",
        "mode": d.get("verificationMode", ""),
        "started": d.get("started", ""),
        "hash": d.get("hashTypes") or [],
        "files": d.get("transferredFileCount", 0),
        "bytes": d.get("totalNumberOfBytesTransferred", 0),
        "problems": [_problem(kind, e) for key, kind in OLD_LISTS.items() for e in d.get(key) or []],
    }


def load(root):
    """[(file, normalized)] cho mọi log JSON hợp lệ dưới root."""
    out = []
    for f in sorted(Path(root).rglob("*.json")):
        try:
            n = normalize(json.loads(f.read_text()))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if n:
            n["_file"] = str(f)
            out.append(n)
    return out
