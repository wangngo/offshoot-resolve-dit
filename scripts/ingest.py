#!/usr/bin/env python3
"""Offload 1 thẻ ra nhiều đích bằng 1 lệnh qua API OffShoot, chờ xong rồi đọc log từng đích.

Dùng: scripts/ingest.py <thẻ> <roll> <preset> <đích1> [đích2 ...] [--timeout giây]
  vd: scripts/ingest.py /Volumes/A001 A001 PHIM_OCF /Volumes/RAID01 /Volumes/SHUTTLE01

Exit 0 chỉ khi MỌI đích Success và không có file lỗi. Có lỗi thì exit khác 0, và KHÔNG được format thẻ.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from datetime import datetime
from pathlib import Path

import oslog

HERE = Path(__file__).resolve().parent
LOGS = Path.home() / "Library/Application Support/OffShoot/Transfer Logs"
PRESETS = Path.home() / "Library/Preferences/Hedge/Presets"
PREF_DOMAIN = "nl.syncfactory.Hedge.Mac"
EVENT_LOG = Path.home() / "Library/Application Support/OffShoot/Event Log/OffShootEvents.log"


def aware(t, tz=None):
    """datetime không múi giờ → gắn múi giờ máy (hoặc tz). So naive với aware sẽ TypeError."""
    return t if t.tzinfo else (t.replace(tzinfo=tz) if tz else t.astimezone())


def event_offset(ev=EVENT_LOG):
    try:
        return Path(ev).stat().st_size
    except OSError:
        return 0


def transfers_added(ev, offset, roll=None):
    """OffShoot có ghi 'Transfers Added' cho roll này SAU offset không. Dựa vào offset byte, không parse
    ngày (định dạng ngày theo locale). Response API 'success' KHÔNG chứng minh đã add.
    Khớp `sourceLabel = <roll>;` trong body để transfer khác chen vào không xác nhận nhầm.
    Log bị cắt/xoay (offset > size) → đọc từ đầu."""
    try:
        with open(ev, "rb") as f:
            size = f.seek(0, 2)
            f.seek(offset if offset <= size else 0)
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return False
    for block in text.split(" - Transfers Added:")[1:]:
        body = re.split(r"\n\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}, ", block, maxsplit=1)[0]
        if roll is None or re.search(r"sourceLabel = \"?" + re.escape(roll) + r"\"?;", body):
            return True
    return False


def valid_roll(roll):
    return re.fullmatch(r"[A-Z]\d{3}", roll) is not None


def short_dests(need, free):
    """Các đích không đủ chỗ (bytes cần, {đích: bytes trống})."""
    return [d for d, f in free.items() if f < need]


def tree_size(path):
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file() and not f.is_symlink())


def expand(pattern, roll, now):
    """Đường dẫn roll trên đích theo folderPattern; None nếu pattern rỗng/có token không tự tính được."""
    if not pattern:
        return None
    out = (pattern.replace("{YYYY}", f"{now:%Y}").replace("{YY}", f"{now:%y}")
           .replace("{MM}", f"{now:%m}").replace("{DD}", f"{now:%d}").replace("{Source Name}", roll))
    return None if "{" in out else out


def existing_rolls(pattern, roll, dests, now):
    """Các đích đã có thư mục roll không rỗng. OffShoot gặp file trùng tên khác nội dung sẽ âm thầm
    ghi '<tên> 2.ext' mà vẫn báo Success, nên phải chặn từ preflight."""
    rel = expand(pattern, roll, now)
    if rel is None:
        return []
    return [d for d in dests if (Path(d) / rel).is_dir() and any((Path(d) / rel).iterdir())]


def collect(log_dir, roll, dests, t0):
    """Kết quả mới nhất (bắt đầu sau t0) cho từng đích, khớp theo tên source + tiền tố đường dẫn đích."""
    out = {}
    for r in oslog.load(log_dir):
        try:
            started = aware(datetime.fromisoformat(r["started"]))
        except ValueError:
            continue
        if r["source"] != roll or started < aware(t0):
            continue
        for dest in dests:
            if r["dest"].startswith(dest.rstrip("/") + "/"):
                out[dest] = {"status": r["status"], "file": r["_file"], "files": r["files"],
                             "bytes": r["bytes"], "problems": len(r["problems"])}
    return out


def api(*args):
    # capture: không in ra stdout (stdout của MCP server là kênh JSON-RPC)
    subprocess.run([str(HERE / "os"), *args], check=False, capture_output=True)
    time.sleep(1)  # docs: action dồn dập dễ lỗi timing


def set_pref(key, value):
    import urllib.parse
    api("raw", "offshoot://setPreferences?preferences=" + urllib.parse.quote(json.dumps({key: value})))


def read_pref(key):
    r = subprocess.run(["defaults", "read", PREF_DOMAIN, key], capture_output=True, text=True)
    return r.stdout.strip()


def preflight(source, roll, preset, dests, presets_dir=PRESETS):
    """Chỉ đọc. Trả {errors, warnings, need_bytes, mode}. errors rỗng mới được chạy."""
    errs, warns, need = [], [], 0
    preset_file = Path(presets_dir) / f"{preset}.hedge"
    if not Path(source).is_dir():
        errs.append(f"không thấy thẻ: {source}")
    if not valid_roll(roll):
        errs.append(f"roll '{roll}' sai chuẩn (A001, B002, S001…)")
    if not preset_file.is_file():
        errs.append(f"không có preset {preset} trong {presets_dir}")
    for d in dests:
        if not Path(d).is_dir():
            errs.append(f"không thấy đích: {d}")
    if len({Path(d).resolve() for d in dests}) != len(dests):
        errs.append("đích bị trùng")
    if errs:
        return {"errors": errs, "warnings": warns, "need_bytes": 0, "mode": ""}
    now = datetime.now().astimezone()
    pattern = json.loads(preset_file.read_text())[0].get("folderPattern", "")
    dup = existing_rolls(pattern, roll, dests, now)
    if dup:
        errs.append(f"roll {roll} đã có trên: {', '.join(dup)} — roll phải là duy nhất "
                    "(OffShoot sẽ âm thầm ghi '<file> 2.ext'). Kiểm tra lại hoặc dùng roll mới.")
    if expand(pattern, roll, now) is None:
        warns.append("Không tính được đường dẫn roll từ preset → bỏ qua kiểm tra roll trùng.")
    need = tree_size(source)
    short = short_dests(need, {d: shutil.disk_usage(d).free for d in dests})
    if short:
        errs.append(f"không đủ chỗ ({need/1e9:.2f} GB) trên: {', '.join(short)}")
    if len(dests) > 1 and len({os.stat(d).st_dev for d in dests}) < len(dests):
        warns.append("Có đích nằm chung một volume, không phải bản backup độc lập.")
    mode = read_pref("TransfersSettingsVerifyKey")
    if mode == "Transfer":
        warns.append("Verify=Transfer chỉ so size. KHÔNG format thẻ dựa trên lần copy này.")
    return {"errors": errs, "warnings": warns, "need_bytes": need, "mode": mode}


def start(source, roll, preset, dests, confirm_wait=30, ev=EVENT_LOG):
    """Đưa transfer vào OffShoot. Trả (t0, preset trước đó, confirmed). Gọi SAU khi preflight không lỗi.
    confirmed=False khi OffShoot không ghi 'Transfers Added' cho roll trong confirm_wait giây (vd app chưa
    nhận ổ nguồn) → đã trả preset GUI về như cũ. Thường là không có gì được copy, nhưng app có thể add
    TRỄ → luôn kiểm GUI/đích trước khi thử lại (tránh roll trùng)."""
    t0 = datetime.now().astimezone()
    off = event_offset(ev)
    prev = read_pref("SFIDefaultsCurrentOrganizePreset")
    set_pref("SFIDefaultsCurrentOrganizePreset", preset)
    api("reset")
    api("src", source, roll)
    for d in dests:
        api("dst", d)
    api("add")
    deadline = time.time() + confirm_wait
    while time.time() < deadline:
        if transfers_added(ev, off, roll):
            return t0, prev, True
        time.sleep(1)
    if prev and prev != preset:
        set_pref("SFIDefaultsCurrentOrganizePreset", prev)  # đừng để GUI kẹt preset (lỗi dây chuyền prev)
    return t0, prev, False


def results(roll, dests, t0):
    """{đích: {status, files, bytes, problems, ok}}; đích chưa có log thì vắng mặt."""
    res = collect(LOGS, roll, dests, t0)
    for r in res.values():
        r["ok"] = r["status"] == "Success" and r["problems"] == 0
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("roll")
    ap.add_argument("preset")
    ap.add_argument("dests", nargs="+")
    ap.add_argument("--timeout", type=int, default=6 * 3600)
    a = ap.parse_args()

    pf = preflight(a.source, a.roll, a.preset, a.dests)
    if pf["errors"]:
        sys.exit("PREFLIGHT FAIL:\n  " + "\n  ".join(pf["errors"]))
    for w in pf["warnings"]:
        print("⚠️ ", w)
    print(f"Thẻ {a.source} → roll {a.roll}, preset {a.preset}, {pf['need_bytes']/1e9:.2f} GB, "
          f"verify={pf['mode']}, {len(a.dests)} đích")

    t0, prev_preset, confirmed = start(a.source, a.roll, a.preset, a.dests)
    if not confirmed:
        sys.exit("KHÔNG BẮT ĐẦU: OffShoot không ghi 'Transfers Added' (app chưa nhận ổ nguồn? "
                 "tháo/gắn lại thẻ hoặc mở app trước) — đã trả preset về cũ")
    deadline = time.time() + a.timeout
    res = {}
    while time.time() < deadline:
        res = results(a.roll, a.dests, t0)
        if len(res) == len(a.dests):
            break
        time.sleep(5)

    ok = True
    for d in a.dests:
        r = res.get(d)
        if not r:
            ok = False
            print(f"  ✗ {d}: KHÔNG có log (bị hủy? 'Does not fit'? hết thời gian chờ) — xem GUI")
            continue
        ok &= r["ok"]
        print(f"  {'✓' if r['ok'] else '✗'} {d}: {r['status']}, {r['files']} file, "
              f"{r['bytes']/1e9:.2f} GB, lỗi={r['problems']}")
    if prev_preset and prev_preset != a.preset:
        set_pref("SFIDefaultsCurrentOrganizePreset", prev_preset)  # trả GUI về preset cũ
    print("KẾT QUẢ:", "OK — mọi đích Success" if ok else "CÓ LỖI — KHÔNG format thẻ")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
