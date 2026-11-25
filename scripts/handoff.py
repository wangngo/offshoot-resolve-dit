#!/usr/bin/env python3
"""Cổng DIT → DaVinci Resolve (CHỈ ĐỌC): một roll đã offload có được phép import chưa.

ok=True chỉ khi ĐỦ:
  1. verify mode OffShoot HIỆN TẠI = SourceAndDestination (không đọc được mode lúc copy; ASC MHL ở bước 2
     mới là bằng chứng chính)
  2. ≥2 đích, mỗi đích có ASC MHL và mhl_verify.passed (không thiếu / sai / thừa file)
  3. các đích nằm trên ≥2 ổ VẬT LÝ khác nhau (2 volume APFS / 2 DMG chung 1 ổ không tính;
     NAS/SMB/Fusion không xác định được → FAIL, kiểm tay)
  4. MHL các đích giống hệt nhau (cùng tập path → hash)
Trả `media`: file media trong roll ở đích đầu (để ImportMedia — Resolve không nhận thư mục).

Dùng: scripts/handoff.py <roll trên đích 1> <roll trên đích 2> [...]     (cần gói xxhash)
"""
import json, os, plistlib, re, subprocess, sys
from pathlib import Path

import mhl_verify

MEDIA_EXT = {".mov", ".mp4", ".m4v", ".mxf", ".mts", ".m2ts", ".avi", ".braw", ".r3d", ".ari", ".arx", ".crm",
             ".nev", ".dng", ".exr", ".dpx", ".wav", ".bwf", ".aif", ".aiff", ".mp3", ".m4a"}
SIDECAR_EXT = {".xml", ".xmp", ".thm", ".bim", ".cpi", ".mpl", ".bdm", ".rtmd", ".ppn", ".smi", ".lrf", ".mhl"}


def mount_point(path):
    p = Path(path).resolve()
    while not os.path.ismount(p):
        p = p.parent
    return p


def whole_disk(dev):
    m = re.fullmatch(r"(disk\d+)(s\d+)*", dev or "")
    return m.group(1) if m else None


def _diskutil(mount):
    r = subprocess.run(["diskutil", "info", "-plist", str(mount)], capture_output=True)
    return plistlib.loads(r.stdout) if r.returncode == 0 else None


def _images():
    """{đường dẫn file ảnh đĩa: [dev-entry…]} của các DMG/sparsebundle đang attach."""
    r = subprocess.run(["hdiutil", "info", "-plist"], capture_output=True)
    if r.returncode != 0:
        return {}
    return {i["image-path"]: [e.get("dev-entry", "") for e in i.get("system-entities", [])]
            for i in plistlib.loads(r.stdout).get("images", [])}


def physical_disk(path, info=_diskutil, images=_images, mount=mount_point, _depth=0):
    """Ổ vật lý chứa path (APFS → physical store; khác → whole disk). None nếu không xác định được.
    - diskutil chỉ nhận mount point/thiết bị, KHÔNG nhận thư mục con → tìm mount point trước.
    - Disk image (DMG/sparsebundle) là đĩa ẢO: lần ra file ảnh rồi lấy ổ thật chứa file đó
      (2 DMG chung 1 ổ từng PASS sai trong lab 2026-11-14)."""
    d = info(mount(path))
    if not d or _depth > 3:
        return None
    devs = {whole_disk(x.get("APFSPhysicalStore")) for x in d.get("APFSPhysicalStores") or []}
    devs |= {whole_disk(d.get("ParentWholeDisk")), whole_disk(d.get("DeviceIdentifier"))}
    devs.discard(None)
    if d.get("BusProtocol") == "Disk Image":
        for img, entries in images().items():
            if devs & {whole_disk(e.replace("/dev/", "")) for e in entries}:
                return physical_disk(Path(img).parent, info, images, mount, _depth + 1)
        return None
    stores = d.get("APFSPhysicalStores") or []
    if len(stores) > 1:   # Fusion/nhiều store: không khẳng định được → fail closed
        return None
    if stores:
        return whole_disk(stores[0].get("APFSPhysicalStore"))
    return whole_disk(d.get("ParentWholeDisk") or d.get("DeviceIdentifier"))


def _files(root):
    root = Path(root)
    return [f for f in sorted(root.rglob("*")) if f.is_file()
            and "ascmhl" not in f.relative_to(root).parts
            and not any(p.startswith(".") for p in f.relative_to(root).parts)]


def skipped_files(root):
    """File không phải media cũng không phải sidecar quen → báo ra, không bỏ lặng lẽ."""
    return [str(f) for f in _files(root) if f.suffix.lower() not in MEDIA_EXT | SIDECAR_EXT]


def media_files(root):
    root = Path(root)
    return sorted(str(f) for f in root.rglob("*")
                  if f.is_file() and f.suffix.lower() in MEDIA_EXT
                  and "ascmhl" not in f.relative_to(root).parts
                  and not any(p.startswith(".") for p in f.relative_to(root).parts))


def check(roll_dirs, mode, dev=physical_disk):
    reasons, per = [], {}
    if mode != "SourceAndDestination":
        reasons.append(f"verify mode = {mode!r}, cần 'SourceAndDestination' (mới có ASC MHL, hash cả đích)")
    if len(roll_dirs) < 2:
        reasons.append("cần ≥2 đích (3-2-1) — mới có 1")
    hashsets = {}
    for d in roll_dirs:
        r = mhl_verify.verify(d)
        per[d] = {k: r[k] for k in ("format", "checked", "ok", "passed")} | {"problems": r["problems"][:20]}
        if r["format"] != "asc":
            reasons.append(f"{d}: không có ASC MHL (format={r['format']}) — trỏ đúng thư mục ROLL chứa ascmhl/?")
        elif not r["passed"]:
            kinds = sorted({p["kind"] for p in r["problems"]})
            reasons.append(f"{d}: verify FAIL {len(r['problems'])} file ({', '.join(kinds)})")
        if r["format"] == "asc":
            hashsets[d] = mhl_verify._asc_entries(Path(d))
    disks = {d: dev(d) for d in roll_dirs}
    unknown = [d for d, v in disks.items() if not v]
    if unknown:   # fail closed: không chứng minh được là ổ khác nhau thì không cho qua
        reasons.append(f"không xác định được ổ vật lý của: {', '.join(unknown)}")
    elif len(roll_dirs) >= 2 and len(set(disks.values())) < 2:
        reasons.append(f"các đích chung 1 ổ vật lý ({', '.join(sorted(set(map(str, disks.values()))))}) — không phải backup độc lập")
    if len(hashsets) >= 2:
        items = list(hashsets.items())
        base_d, base = items[0]
        for d, hs in items[1:]:
            diff = sorted(set(base.items()) ^ set(hs.items()))
            if diff:
                paths = sorted({p for p, _ in diff})
                reasons.append(f"MHL {d} khác {base_d}: {', '.join(paths[:10])}")
    return {"ok": not reasons, "reasons": reasons, "disks": disks, "dests": per,
            "media": media_files(roll_dirs[0]) if not reasons else [],
            "skipped": skipped_files(roll_dirs[0]) if roll_dirs else []}


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ingest
    res = check(sys.argv[1:], mode=ingest.read_pref("TransfersSettingsVerifyKey"))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
