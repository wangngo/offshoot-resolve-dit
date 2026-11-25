#!/usr/bin/env python3
"""Verify CHỈ ĐỌC một roll/thư mục đích theo MHL của OffShoot (không ghi gì vào ổ).

- ASC MHL: <roll>/ascmhl/*.mhl (urn:ASC:MHL:v2.0, xxh64) — lấy hash mới nhất theo từng path qua các generation.
- MHL kiểu cũ: <thư mục>/*.mhl (hashlist 1.1, xxhash64be), path tương đối với thư mục chứa file .mhl.

Dùng: scripts/mhl_verify.py <roll hoặc thư mục> [--problems]   (cần gói `xxhash`)
Exit 0 khi không có file lỗi/thiếu/thừa (unlisted). Kết quả `passed` = cổng duy nhất nên dùng.
"""
import argparse, json, sys, unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

CHUNK = 8 * 1024 * 1024


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _asc_entries(root):
    entries = {}
    for mhl in sorted((root / "ascmhl").glob("*.mhl")):  # tên file có số thứ tự generation → sort = thứ tự
        for h in ET.parse(mhl).getroot().iter():
            if _local(h.tag) != "hash":
                continue
            path = digest = size = None
            for c in h:
                if _local(c.tag) == "path":
                    path, size = c.text, c.get("size")
                elif _local(c.tag) == "xxh64":
                    digest = c.text
            if path and digest:
                entries[path] = (int(size) if size else None, digest.lower())
    return entries


def _legacy_entries(root):
    entries = {}
    for mhl in sorted(root.glob("*.mhl")):
        for h in ET.parse(mhl).getroot().iter("hash"):
            f, d, s = h.findtext("file"), h.findtext("xxhash64be"), h.findtext("size")
            if f and d:
                entries[f] = (int(s) if s else None, d.lower())
    return entries


def xxh64_file(path):
    import xxhash
    h = xxhash.xxh64()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(root):
    root = Path(root)
    if (root / "ascmhl").is_dir() and any((root / "ascmhl").glob("*.mhl")):
        fmt, entries = "asc", _asc_entries(root)
    elif any(root.glob("*.mhl")):
        fmt, entries = "legacy", _legacy_entries(root)
    else:
        # Không có MHL (vd trỏ nhầm thư mục cha) KHÔNG phải pass
        return {"format": None, "root": str(root), "checked": 0, "ok": 0, "problems": [], "passed": False}
    ok, problems = 0, []
    for rel, (size, digest) in sorted(entries.items()):
        p = root / rel
        if not p.is_file():
            problems.append({"path": rel, "kind": "missing"})
        elif size is not None and p.stat().st_size != size:
            problems.append({"path": rel, "kind": "size_mismatch", "expected": size, "actual": p.stat().st_size})
        else:
            got = xxh64_file(p)
            if got == digest:
                ok += 1
            else:
                problems.append({"path": rel, "kind": "hash_mismatch", "expected": digest, "actual": got})
    # File có trên đĩa mà MHL không liệt kê: OffShoot gặp tên trùng ghi "<tên> 2.ext" vẫn báo Success
    nfc = lambda x: unicodedata.normalize("NFC", x)   # HFS+/exFAT có thể trả NFD, MHL ghi NFC
    listed = {nfc(k) for k in entries}
    for f in sorted(root.rglob("*")):
        rel = f.relative_to(root)
        if (f.is_file() and not any(part.startswith(".") for part in rel.parts)
                and "ascmhl" not in rel.parts and not (fmt == "legacy" and f.suffix == ".mhl" and len(rel.parts) == 1)
                and nfc(rel.as_posix()) not in listed):
            problems.append({"path": rel.as_posix(), "kind": "unlisted"})
    return {"format": fmt, "root": str(root), "checked": len(entries), "ok": ok, "problems": problems,
            "passed": not problems and ok == len(entries) > 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = verify(a.root)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"{r['root']}: MHL={r['format']}, {r['checked']} file, OK {r['ok']}, lỗi {len(r['problems'])}")
        for p in r["problems"]:
            print(f"  ✗ {p['kind']}: {p['path']}")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
