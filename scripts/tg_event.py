#!/usr/bin/env python3
"""Script gắn event OffShoot (Settings > Scripting, Python) → báo Telegram Bot.

Gắn cho 2 event: File Copy Completed, Verification Issue.
OffShoot gọi: python3 tg_event.py '<JSON tham số event>'.
Token + chat id đọc từ file .env qua OFFSHOOT_TG_ENV (mặc định ~/.config/offshoot-dit/telegram.env,
chứa TELEGRAM_BOT_TOKEN và ALLOWED_USER_IDS).
Chỉ dùng stdlib, chạy được trên /usr/bin/python3 3.9. Không bao giờ raise (để không làm phiền OffShoot).
Debug: ~/Library/Logs/offshoot-dit/tg_event.log. Đặt TG_DRY_RUN=1 thì chỉ ghi log, không gửi.
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oslog  # noqa: E402

BOT_ENV = Path(os.environ.get("OFFSHOOT_TG_ENV", Path.home() / ".config/offshoot-dit/telegram.env"))
LOG = Path.home() / "Library/Logs/offshoot-dit/tg_event.log"
ICON = {"Success": "✅", "Warnings": "⚠️", "Failed": "❌", "Canceled": "⏹", "Stopped": "⏸"}
MAX_LIST = 5


def message(p):
    if "FileCopyCompleted_state" in p:
        return _copy_message(p)
    if "VerificationIssue_filePath" in p:
        return ("🚨 OffShoot: lỗi đọc NGUỒN (Verification Issue)\n"
                f"{p.get('VerificationIssue_filePath', '')}\n{p.get('VerificationIssue_description', '')}\n"
                "→ Kiểm tra thẻ/đầu đọc. KHÔNG format thẻ.")
    return None


def _copy_message(p):
    state = str(p.get("FileCopyCompleted_state", "")).capitalize()
    dest = p.get("FileCopyCompleted_destinationPath", "")
    n = None
    try:
        n = oslog.normalize(json.loads(Path(p.get("FileCopyCompleted_transferLogJSONPath", "")).read_text()))
    except (OSError, ValueError):
        pass
    probs = n["problems"] if n else []
    dupes = _renamed_dupes(dest)
    if state == "Success" and (probs or dupes):
        state = "Warnings"
    lines = [f"{ICON.get(state, '❔')} OffShoot {state}: {n['source'] if n else ''} → {dest}"]
    if n:
        lines.append(f"{n['files']} file, {n['bytes']/1e9:.2f} GB, lỗi {len(probs)}"
                     f" · preset {p.get('FileCopyCompleted_presetName') or n['preset']}"
                     f" · verify {p.get('FileCopyCompleted_verification_mode') or n['mode']}")
    else:
        lines.append("(không có transfer log — thường do bị hủy: đích không đủ chỗ 'Does not fit', hoặc bị dừng tay)")
    for x in probs[:MAX_LIST]:
        lines.append(f"• {x['kind']}: {x['path']} — {x['error']}")
    if len(probs) > MAX_LIST:
        lines.append(f"… +{len(probs) - MAX_LIST} file nữa")
    if dupes:
        lines.append(f"⚠️ {len(dupes)} file bị đổi tên do trùng tên ở đích (đích có sẵn file khác nội dung):")
        lines += [f"• {x}" for x in dupes[:MAX_LIST]]
    if state != "Success":
        lines.append("→ KHÔNG format thẻ cho tới khi xử lý xong.")
    return "\n".join(lines)


def _renamed_dupes(dest):
    """File '<tên> 2.ext' mà OffShoot âm thầm tạo khi đích có sẵn file trùng tên khác nội dung."""
    out = []
    try:
        for f in Path(dest).rglob("*"):
            m = re.fullmatch(r"(.+) \d+(\.[^.]+)", f.name)
            if m and f.is_file() and (f.parent / (m.group(1) + m.group(2))).exists():
                out.append(str(f.relative_to(dest)))
    except OSError:
        pass
    return sorted(out)


def _creds():
    token = chat = None
    for line in BOT_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip()
        elif line.startswith("ALLOWED_USER_IDS="):
            chat = line.split("=", 1)[1].split(",")[0].strip()
    return token, chat


def send(text):
    # Dùng curl của macOS (kho CA hệ thống): python3 mà OffShoot gọi có thể là bản python.org
    # với kho CA hỏng (lỗi CERTIFICATE_VERIFY_FAILED). Token đi qua stdin (-K -), không lộ trên ps.
    token, chat = _creds()
    cfg = (f'url = "https://api.telegram.org/bot{token}/sendMessage"\n'
           f'data-urlencode = "chat_id={chat}"\n')
    r = subprocess.run(["/usr/bin/curl", "-sS", "--fail", "--max-time", "15", "-K", "-",
                        "--data-urlencode", f"text={text}"],
                       input=cfg, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"curl rc={r.returncode} {r.stderr.strip()[:200]}")


def _log(s):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        params = json.loads(raw)
        msg = message(params)
        _log(f"event keys={sorted(params)[:4]} msg={'none' if msg is None else 'yes'}")
        if msg and os.environ.get("TG_DRY_RUN") != "1":
            send(msg)
            _log("sent")
        elif msg:
            _log("DRY_RUN:\n" + msg)
    except Exception as e:  # noqa: BLE001 — không bao giờ làm vỡ OffShoot
        _log(f"ERROR {type(e).__name__}: {e} raw={raw[:300]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
