---
name: davinci-resolve
description: >-
  Control DaVinci Resolve Studio (21.x on macOS) via Python Scripting API and MCP —
  media pool ingest, BWF timecode & waveform audio sync, timeline assembly, proxy linking,
  frame/thumbnail extraction, Voice Isolation, and Deliver rendering with field-tested safety gates.
---

# davinci-resolve — DaVinci Resolve Studio 21.x Scripting & Safety Gates

## Direct Python API Quickstart (macOS)

```bash
export PYTHONPATH="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/"
python3 -c "import DaVinciResolveScript as d; r=d.scriptapp('Resolve'); print(r.GetVersionString(), r.GetCurrentPage())"
```
Check method signatures in `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/DaVinciResolveScript.pyi`.

## Mandatory Pre-Write Gates
1. **`r.GetCurrentPage() is not None`**: If `None`, a modal dialog/popup is open in Resolve and **every mutating API call will silently return `None`/`False`** (while read calls still work). Dismiss the dialog first.
2. **Validate `AUDIO_SYNC_*` constants against `None`**: Resolve objects return `None` for any unknown attribute name instead of raising `AttributeError`. Assert no key/value in `AutoSyncAudio` settings is `None`.
3. **Pass file paths (not directories) to `ImportMedia`**: `MediaPool.ImportMedia([directory])` silently returns `[]` on Resolve 21.2.
4. **Backup before `DeleteProject`**: `ProjectManager.DeleteProject` permanently deletes `~/Movies/Resolve Project Backups/<uuid>` without sending it to Trash. Always call `ExportProject` (`.drp`) first.

See `docs/11-resolve-21-gotchas.md` for the complete list of 12 field-tested DaVinci Resolve 21.2 API gotchas.
