# 11 — DaVinci Resolve Studio 21.2 Scripting API Gotchas (Field-Tested)

Empirical findings measured on **DaVinci Resolve Studio 21.2** (macOS Apple Silicon) with External Scripting set to `Local`. None of these behaviors are documented in Blackmagic Design's official `README.txt` or `DaVinciResolveScript.pyi` stub.

---

## 1. Silent Write Failures When a Modal Dialog is Open (`GetCurrentPage() is None`)
- **Symptom:** Every mutating API call (`ImportMedia`, `CreateTimelineFromClips`, `SetSetting`, etc.) silently returns `None` or `False`, while read calls (`GetVersionString()`, `GetProjectName()`) continue to succeed.
- **Root Cause:** A modal dialog or popup (e.g., *Extras Download Manager*, missing font prompt, or project recovery dialog) is blocking the UI thread.
- **Guard:** Always assert `resolve.GetCurrentPage() is not None` before executing any write operation. If it returns `None`, dismiss the modal dialog in the UI first.

## 2. `Resolve` Object Returns `None` for ANY Unknown Attribute (No `AttributeError`)
- **Symptom:** Passing a slightly misspelled constant such as `resolve.AUDIO_SYNC_WAVEFORMS` (with a trailing `S`) into `MediaPool.AutoSyncAudio(items, settings)` does **not** raise `AttributeError`. Instead, the attribute evaluates to `None`, producing `{1: None}` in the settings dictionary and causing `AutoSyncAudio` to silently return `False`.
- **Guard:** Explicitly assert that no key or value in your settings dictionary is `None` before calling `AutoSyncAudio`:
  ```python
  settings = {
      resolve.AUDIO_SYNC_MODE: resolve.AUDIO_SYNC_TIMECODE,
      resolve.AUDIO_SYNC_RETAIN_EMBEDDED_AUDIO: True,
  }
  assert not any(x is None for kv in settings.items() for x in kv), f"Resolved to None: {settings}"
  ```

## 3. `MediaPool.ImportMedia([directory_path])` Silently Returns `[]`
- **Symptom:** Passing a folder path in a list to `mp.ImportMedia(["/Volumes/RAID/ROLL_A001"])` returns `[]` without any error on Resolve 21.2.
- **Fix:** Enumerate and pass explicit media file paths (filtering out `ascmhl/` and sidecar XMLs), or guard against `os.path.isdir()` before calling `ImportMedia`.

## 4. `AutoSyncAudio` Return Value is Not Sufficient — Verify `Synced Audio` Property
- **Symptom:** `mp.AutoSyncAudio(items, settings)` can return `True` even if only a subset of video clips matched an external WAV recorder file.
- **Fix:** After calling `AutoSyncAudio`, inspect `clip.GetClipProperty("Synced Audio")` on every target video clip. Unsynced clips will have an empty string `""`.
- **Note on BWF Timecode:** Resolve reads external WAV timecode from the Broadcast Wave (`bext`) `time_reference` field (samples since midnight). A standard WAV without `bext` defaults to `00:00:00:00` and can only sync via `AUDIO_SYNC_WAVEFORM`.

## 5. `ProjectManager.DeleteProject` Deletes Auto-Backups Without Trash
- **Symptom:** Calling `pm.DeleteProject(name)` permanently deletes the project's auto-backup folder under `~/Movies/Resolve Project Backups/<project-uuid>` immediately, bypassing the macOS Trash.
- **Guard:** Always call `pm.ExportProject(name, backup_drp_path, False)` to create a `.drp` snapshot before deleting any project, and `pm.CloseProject(project)` if it is currently open.

## 6. `ExportFrame` vs. `ExportThumbnails` Signature & Failure Modes
- `Timeline.ExportFrame(frameOffset, {"outputType": "file", "filePath": "/tmp/out.jpg", "maxDimension": 1280})`: The first argument is the **frame offset**, NOT a file path. Returns a dict `{"success": True, "error": "", "width": ..., "height": ...}`.
- `MediaPoolItem.ExportFrame(...)` consistently fails with `"Failed to render frame"` on 21.2. To inspect source clips without placing them on a timeline, use `MediaPoolItem.ExportThumbnails([0, n//3, 2*n//3, n-1], {"outputType": "file", "filePath": "/tmp/grid.jpg", "maxDimension": 800})`, which exports a labeled contact sheet grid.

## 7. `SetClipColor` Only Accepts 16 Exact Resolve Color Names
- Valid names: `Orange`, `Apricot`, `Yellow`, `Lime`, `Olive`, `Green`, `Teal`, `Navy`, `Blue`, `Purple`, `Violet`, `Pink`, `Tan`, `Beige`, `Brown`, `Chocolate`.
- Passing `"Red"` or `"Gray"` silently returns `False`. To clear a color, call `clip.ClearClipColor()`.

## 8. `SetClipProperty("Clip Name", new_name)` Returns `False` Even When It Succeeds
- **Fix:** Ignore the boolean return value of `SetClipProperty("Clip Name", ...)` and verify by reading back `clip.GetClipProperty("Clip Name")`.

## 9. `timelineFrameRate` Must Be Set Before the First Timeline Exists
- Once a project has `project.GetTimelineCount() > 0`, project-level `project.SetSetting("timelineFrameRate", ...)` can no longer alter the project base frame rate. Set it immediately after `CreateProject()` while timeline count is `0`.
- For vertical timelines (e.g., 1080×1920): create the timeline first, then set `tl.SetSetting("useCustomSettings", "1")` followed by `tl.SetSetting("timelineResolutionWidth", "1080")` and `tl.SetSetting("timelineResolutionHeight", "1920")`.

## 10. `TranscribeAudio` Must Be Called on a `Folder`, Not Per-Clip in a Loop
- Calling `clip.TranscribeAudio()` in a loop only runs the first job; subsequent calls return `None`.
- **Fix:** Call `folder.TranscribeAudio()` on the Media Pool bin, and poll `project.GetTranscribeAudioStatus()` (located on `Project`, NOT `MediaPool`) until it reaches `'Complete'`.

## 11. Render Job Polling & Audio-Only `.mp4` Trap
- `project.IsRenderingInProgress()` can return `False` immediately right after `StartRendering([job_id])`. Always poll `project.GetRenderJobStatus(job_id)["JobStatus"]` until `'Complete'` (or `'Failed'` / `'Cancelled'`).
- Resolve persists `ExportVideo` / `ExportAudio` flags from previous render jobs. If a prior job had `ExportVideo: False`, a subsequent H.264/MP4 render job can finish `'Complete'` with an audio-only `.mp4`. Always explicitly call `project.SetRenderSettings({"ExportVideo": True, "ExportAudio": True})`, verify `IsExportVideo` and `IsExportAudio` in `project.GetRenderJobList()`, and run `ffprobe` on the output file after rendering.

## 12. `Timeline.SetTrackEnable` is Unreliable for Track-Isolated Renders
- `tl.SetTrackEnable(track_type, idx, bool)` and `tl.GetIsTrackEnabled(...)` can desynchronize from actual Deliver page output. Do not rely on `SetTrackEnable` to stem-render individual tracks via the scripting API.
