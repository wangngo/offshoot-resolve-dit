#!/usr/bin/env python3
"""Sinh cặp preset OffShoot theo chuẩn Netflix cho một dự án phim:
  <PROJECT>_OCF.hedge   -> PROJECT/YYYYMMDD/Camera_Media/<roll>
  <PROJECT>_SOUND.hedge -> PROJECT/YYYYMMDD/Sound_Media/<roll>
Roll = {Source Name} = label của source (A001, B002, S001…) hoặc tên volume.

Dùng: scripts/mkpreset.py "Tên dự án" [--out ~/Library/Preferences/Hedge/Presets]
Sau đó chạy: scripts/os reload
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path

DEFAULT_OUT = Path.home() / "Library/Preferences/Hedge/Presets"
MEDIA = {"OCF": "Camera_Media", "SOUND": "Sound_Media"}


def sanitize(name):
    s = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s.replace("'", "")).strip("_").upper()
    if not s:
        raise ValueError(f"tên dự án không hợp lệ: {name!r}")
    return s


def preset(project, media):
    return [{
        "folderPattern": f"{project}/{{YYYY}}{{MM}}{{DD}}/{media}/{{Source Name}}",
        "labelPattern": "",
        "renamePattern": "",
        "counter": "001",
        "doNotCopyFiles": [""],
        "ignoreBundles": [""],
        "flattenFolders": False,
        "ignoreEmptyFolders": False,
    }]


def write(name, out=DEFAULT_OUT):
    project = sanitize(name)
    paths = [Path(out) / f"{project}_{kind}.hedge" for kind in MEDIA]
    for p in paths:
        if p.exists():
            raise FileExistsError(p)
    for p, media in zip(paths, MEDIA.values()):
        p.write_text(json.dumps(preset(project, media), indent=2) + "\n")
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    for p in write(a.name, a.out):
        print(p)


if __name__ == "__main__":
    sys.exit(main())
