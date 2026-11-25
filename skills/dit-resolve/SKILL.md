---
name: dit-resolve
description: >-
  End-to-end on-set DIT workflow: offload camera & sound cards via OffShoot Pro -> 3-2-1
  hardware & ASC MHL verification gate (handoff_check) -> DaVinci Resolve Studio import ->
  external BWF/waveform audio sync -> DAILIES timeline assembly.
---

# dit-resolve — Card → OffShoot Pro → Hardware/MHL Gate → DaVinci Resolve Dailies

> End-to-end verified on synthetic & production-layout rolls (`docs/10-e2e-resolve.md`):
> 0-sample sync drift across BWF timecode and waveform modes.

## Hard Safety Rules
- **The gate lives in CODE, not in prompts**: never import into DaVinci Resolve unless
  `handoff_check` (MCP) or `scripts/handoff.py` returns `ok=true`.
- **Import from the primary destination drive**, never from the camera card.
- **Never format a camera/sound card** until `handoff_check` returns `ok=true` across `>= 2`
  independent physical disks.

## Runbook (Per Card; Subsequent Cards Append to the Same Day Timeline)
1. `offshoot.status` → confirm verification mode is `SourceAndDestination` and `ASC MHL` is enabled.
   `list_volumes` → select source card + `>= 2` destination volumes on distinct physical drives.
2. `ingest_preflight` → review plan → `ingest_start(..., confirm=true)`.
   - If `started: false` ("OffShoot did not log Transfers Added"), OffShoot has not registered the source mount yet → remount card and retry.
3. `ingest_status(..., restore_preset=<previous_preset>)` until `done: true`. If `all_ok: false`, STOP.
4. **Hardware & MHL Gate**: `handoff_check([<dest1>/.../<ROLL>, <dest2>/.../<ROLL>])` — point to the **ROLL directory** (containing `ascmhl/`).
   - If `ok: false`, inspect `reasons` and STOP.
   - If `ok: true`, the roll is verified on `>= 2` distinct physical disks with identical ASC MHL hashes.
5. **DaVinci Resolve Dailies** (Resolve Studio open, no modal dialogs blocking UI):
   ```sh
   PYTHONUTF8=1 uv run --no-project -q --with xxhash python scripts/resolve_dailies.py \
     --project <SHOW> --day YYYYMMDD --fps <fps> \
     --cam <dest1>/<SHOW>/<DAY>/Camera_Media/A001 <dest2>/<SHOW>/<DAY>/Camera_Media/A001 \
     --sound <dest1>/<SHOW>/<DAY>/Sound_Media/S001 <dest2>/<SHOW>/<DAY>/Sound_Media/S001 \
     [--sync timecode|waveform] [--dry-run]
   ```
   - Automatically re-runs `handoff.check` (exit code `2` = gate failed before touching Resolve).
   - Exit code `0` only when `errors` is empty: all files imported into bins, project FPS matches, every video clip has `Synced Audio` populated (when `--sound` is provided), and all clips are placed on `DAILIES_<YYYYMMDD>`.
   - Idempotent: re-running skips already-imported clips and appends new rolls to the end of the existing day timeline.
6. End of day: `make_report` to generate HTML + PDF offload reports for post-production.
