#!/usr/bin/env python3
"""Tóm tắt transfer log JSON của OffShoot: đếm status, dung lượng, liệt kê file lỗi.

Dùng:
  scripts/log_scan.py                         # mặc định đọc thư mục log của OffShoot
  scripts/log_scan.py <dir> --since 2025-12-01 --problems
"""
import argparse, sys
from collections import Counter
from pathlib import Path

import oslog

DEFAULT_DIR = Path.home() / "Library/Application Support/OffShoot/Transfer Logs"


def load(root, since=None):
    return [r for r in oslog.load(root) if not since or r["started"][:10] >= since]


def summarize(rows):
    return {
        "transfers": len(rows),
        "status": dict(Counter(r["status"] for r in rows)),
        "files": sum(r["files"] for r in rows),
        "bytes": sum(r["bytes"] for r in rows),
        "presets": dict(Counter(r["preset"] or "(none)" for r in rows)),
        "hash": dict(Counter(h for r in rows for h in r["hash"])),
    }


def problems(rows):
    return [dict(p, started=r["started"], dest=r["dest"]) for r in rows for p in r["problems"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?", default=DEFAULT_DIR)
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--problems", action="store_true", help="liệt kê file lỗi")
    a = ap.parse_args()
    rows = load(a.dir, a.since)
    s = summarize(rows)
    print(f"Transfers: {s['transfers']}  Files: {s['files']}  Size: {s['bytes']/1e9:.2f} GB")
    for k in ("status", "presets", "hash"):
        print(f"{k:8}: " + ", ".join(f"{n}={c}" for n, c in sorted(s[k].items(), key=lambda x: -x[1])))
    probs = problems(rows)
    print(f"Problems: {len(probs)} " + str(dict(Counter(p['error'] for p in probs).most_common(8))))
    if a.problems:
        for p in probs:
            print(f"{p['started'][:16]}  {p['kind']:7} {p['path']}  ->  {p['error']}")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
