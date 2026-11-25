#!/usr/bin/env python3
"""DIT → DaVinci Resolve: import roll đã qua cổng handoff, sync audio rời, dựng timeline DAILIES.

Dùng (Resolve Studio đang mở, External scripting = Local):
  scripts/resolve_dailies.py --project PHIM --day 20261114 --fps 25 \\
      --cam  /Volumes/RAID/PHIM/20261114/Camera_Media/A001 /Volumes/SHUTTLE/PHIM/20261114/Camera_Media/A001 \\
      --sound /Volumes/RAID/PHIM/20261114/Sound_Media/S001 /Volumes/SHUTTLE/PHIM/20261114/Sound_Media/S001 \\
      [--sync timecode|waveform] [--dry-run]
Mỗi --cam/--sound = CÙNG 1 roll trên ≥2 đích (đích đầu là bản làm việc, import từ đây).
Lặp lại --cam/--sound cho nhiều roll. Exit 0 chỉ khi `errors` rỗng: mọi roll qua cổng, mọi file vào bin,
fps khớp, mọi clip video có Synced Audio (khi có --sound), mọi clip có trên timeline DAILIES_<ngày>.
Exit 2 = cổng FAIL (không đụng Resolve). Chạy lại an toàn: clip đã có trong bin (cùng File Path) bỏ qua;
timeline đã có thì NỐI clip mới (thẻ thứ 2 trong ngày) vào cuối.
"""
import argparse, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import handoff, ingest  # noqa: E402

MODULES = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"


def gate(groups, mode):
    """[[roll trên các đích]…] → (ok, {roll_dir_đầu: media list}, lý do)."""
    media, reasons = {}, []
    for dirs in groups:
        r = handoff.check(dirs, mode=mode)
        if r["ok"]:
            media[dirs[0]] = r["media"]
        else:
            reasons += [f"{Path(dirs[0]).name}: {x}" for x in r["reasons"]]
    return not reasons, media, reasons


def new_files(files, existing_paths):
    """Bỏ file đã có trong bin (so theo đường dẫn tuyệt đối đã chuẩn hoá)."""
    have = {os.path.realpath(p) for p in existing_paths}
    return [f for f in files if os.path.realpath(f) not in have]


def sort_by_tc(items, tc_of):
    """TC dạng HH:MM:SS:FF (hoặc ;FF drop-frame) sort được theo chuỗi sau khi chuẩn hoá dấu."""
    return sorted(items, key=lambda i: (tc_of(i) or "99:99:99:99").replace(";", ":"))


def unsynced(videos, synced_of):
    return [v for v in videos if not synced_of(v)]


def missing_after_import(files, imported_paths):
    """File đã qua cổng nhưng không có trong bin sau ImportMedia (import hỏng, codec lạ…)."""
    have = {os.path.realpath(x) for x in imported_paths}
    return [f for f in files if os.path.realpath(f) not in have]


def not_in(items, present):
    present = set(present)
    return [i for i in items if i not in present]


def clip_label(file_path, roll_names):
    """'<roll>/<tên file>' — tên clip có thể trùng giữa các roll (GoPro GX010001, máy reset bộ đếm)."""
    parts = Path(file_path).parts
    roll = next((x for x in reversed(parts[:-1]) if x in roll_names), Path(file_path).parent.name)
    return f"{roll}/{parts[-1]}"


def resolve():
    sys.path.insert(0, MODULES)
    import DaVinciResolveScript as d
    r = d.scriptapp("Resolve")
    if not r:
        sys.exit("Không kết nối được Resolve (chưa mở? External scripting chưa = Local?)")
    if not r.GetCurrentPage():
        sys.exit("Resolve đang có dialog mở (GetCurrentPage()=None) → mọi lệnh ghi sẽ im lặng thất bại. Đóng dialog rồi chạy lại.")
    return r


def subfolder(mp, parent, name):
    for f in parent.GetSubFolderList() or []:
        if f.GetName() == name:
            return f
    return mp.AddSubFolder(parent, name)


def import_into(mp, folder, files):
    mp.SetCurrentFolder(folder)
    existing = [c.GetClipProperty("File Path") for c in folder.GetClipList() or []]
    todo = new_files(files, existing)
    if todo:
        mp.ImportMedia(todo)   # truyền FILE, không truyền thư mục (thư mục → [] im lặng)
    byname = {os.path.realpath(c.GetClipProperty("File Path")): c for c in folder.GetClipList() or []}
    items = [byname[os.path.realpath(f)] for f in files if os.path.realpath(f) in byname]
    return items, len(todo), missing_after_import(files, byname)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--day", required=True, help="YYYYMMDD — tên bin + timeline")
    ap.add_argument("--fps", default="25")
    ap.add_argument("--cam", nargs="+", action="append", default=[])
    ap.add_argument("--sound", nargs="+", action="append", default=[])
    ap.add_argument("--sync", choices=["timecode", "waveform"], default="timecode")
    ap.add_argument("--dry-run", action="store_true", help="chỉ chạy cổng, không đụng Resolve")
    a = ap.parse_args()
    if not a.cam:
        sys.exit("cần ít nhất 1 --cam")

    mode = ingest.read_pref("TransfersSettingsVerifyKey")
    ok, cam_media, reasons = gate(a.cam, mode)
    ok2, snd_media, reasons2 = gate(a.sound, mode)
    if not (ok and ok2):
        print(json.dumps({"gate": "FAIL", "reasons": reasons + reasons2}, ensure_ascii=False, indent=2))
        return 2
    out = {"gate": "OK", "cam": {Path(k).name: len(v) for k, v in cam_media.items()},
           "sound": {Path(k).name: len(v) for k, v in snd_media.items()}}
    if a.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    r = resolve()
    pm = r.GetProjectManager()
    errors = []
    if a.project in (pm.GetProjectListInCurrentFolder() or []):
        p = pm.LoadProject(a.project)   # đã có mà load hỏng → DỪNG, không tạo trùng tên
    else:
        p = pm.CreateProject(a.project)
    if not p:
        sys.exit(f"Không mở/tạo được project {a.project} (đang mở ở máy khác? sai thư mục project?)")
    if p.GetTimelineCount() == 0:   # fps chỉ đổi được khi chưa có timeline
        p.SetSetting("timelineFrameRate", str(a.fps))
    out["project_fps"] = p.GetSetting("timelineFrameRate")
    if float(out["project_fps"]) != float(a.fps):
        errors.append(f"project fps {out['project_fps']} ≠ --fps {a.fps} (đã có timeline, không đổi được)")
    mp = p.GetMediaPool()
    day = subfolder(mp, mp.GetRootFolder(), a.day)
    vids, wavs, imported, missing = [], [], 0, []
    for src, dst in ((cam_media, vids), (snd_media, wavs)):
        for roll, files in src.items():
            items, n, miss = import_into(mp, subfolder(mp, day, Path(roll).name), files)
            dst += items; imported += n; missing += miss
    out["imported_new"], out["videos"], out["wavs"] = imported, len(vids), len(wavs)
    if missing:
        errors.append(f"{len(missing)} file qua cổng nhưng không vào được bin: {[Path(x).name for x in missing[:10]]}")
    rolls = {Path(k).name for k in cam_media}
    label = lambda v: clip_label(v.GetClipProperty("File Path"), rolls)

    if a.sound:
        if not wavs:
            errors.append("có --sound nhưng không clip audio nào vào bin (đuôi lạ? import hỏng?)")
        else:
            m = r.AUDIO_SYNC_TIMECODE if a.sync == "timecode" else r.AUDIO_SYNC_WAVEFORM
            settings = {r.AUDIO_SYNC_MODE: m, r.AUDIO_SYNC_RETAIN_EMBEDDED_AUDIO: True}   # key/value PHẢI là hằng r.*
            # object Resolve trả None cho MỌI tên sai (không AttributeError) → gõ nhầm hằng = sync im lặng False
            if any(x is None for kv in settings.items() for x in kv):
                sys.exit(f"Hằng AUDIO_SYNC_* ra None (sai tên?): {settings}")
            need = unsynced(vids, lambda v: v.GetClipProperty("Synced Audio"))
            out["autosync_return"] = bool(mp.AutoSyncAudio(need + wavs, settings)) if need else "đã sync từ trước"
            out["synced"] = {label(v): v.GetClipProperty("Synced Audio") for v in vids}
            out["unsynced"] = [label(v) for v in unsynced(vids, lambda v: v.GetClipProperty("Synced Audio"))]
            if out["unsynced"]:
                errors.append(f"{len(out['unsynced'])} clip chưa sync audio")

    name = f"DAILIES_{a.day}"
    ordered = sort_by_tc(vids, lambda v: v.GetClipProperty("Start TC"))
    tl = next((p.GetTimelineByIndex(i) for i in range(1, p.GetTimelineCount() + 1)
               if p.GetTimelineByIndex(i).GetName() == name), None)
    if tl is None:
        mp.SetCurrentFolder(day)
        tl = mp.CreateTimelineFromClips(name, ordered)
        out["timeline"] = "tạo mới" if tl else None
    else:   # thẻ thứ 2+ trong ngày: nối clip chưa có vào cuối timeline
        p.SetCurrentTimeline(tl)
        in_tl = lambda: {i.GetMediaPoolItem().GetUniqueId() for i in tl.GetItemListInTrack("video", 1) or []
                         if i.GetMediaPoolItem()}
        todo = [v for v in ordered if v.GetUniqueId() in not_in([x.GetUniqueId() for x in ordered], in_tl())]
        if todo:
            mp.AppendToTimeline(todo)
        out["timeline"] = f"đã có — nối thêm {len(todo)} clip"
    if not tl:
        errors.append("không tạo được timeline")
    else:
        lacking = not_in([v.GetUniqueId() for v in vids],
                         {i.GetMediaPoolItem().GetUniqueId() for i in tl.GetItemListInTrack("video", 1) or [] if i.GetMediaPoolItem()})
        if lacking:
            errors.append(f"{len(lacking)} clip không có trên timeline {name}")
    pm.SaveProject()
    out["errors"] = errors
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
