# offshoot-resolve-dit

**On-Set DIT MCP Server, Read-Only ASC MHL Verifier & 3-2-1 Physical-Disk Handoff Gate for OffShoot Pro (Hedge) → DaVinci Resolve Studio Dailies.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 53 passed](https://img.shields.io/badge/tests-53%20passed-brightgreen.svg)](tests/)

> **Where this fits in the ecosystem:**
> While post-production MCP servers like [`samuelgursky/davinci-resolve-mcp`](https://github.com/samuelgursky/davinci-resolve-mcp) focus on **inside-Resolve** editorial, grading, and `.drp/.drt/.drx` manipulation, **`offshoot-resolve-dit` owns the upstream On-Set DIT boundary**: controlling **OffShoot Pro (Hedge)** card offloads, enforcing **industry-standard ASC MHL (`xxh64`) + physical-disk separation (`diskutil`/`hdiutil`)**, and driving a fail-closed handoff into **DaVinci Resolve Studio** for automated BWF timecode/waveform audio sync and `DAILIES_<YYYYMMDD>` timeline assembly.

---

## Key Capabilities

```
[Camera / Sound Card]
        │
        ▼  1. scripts/ingest.py  (or MCP: ingest_preflight → ingest_start → ingest_status)
[OffShoot Pro (Hedge)] ──► Destination 1 (Working RAID/SSD)  + ascmhl/*.mhl
                       ──► Destination 2 (Shuttle Drive)     + ascmhl/*.mhl
        │
        ▼  2. scripts/handoff.py (or MCP: handoff_check / verify_mhl)
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ 3-2-1 HARDWARE & ASC MHL GATE (Fail-Closed, Read-Only)                  │
   │  ✓ OffShoot Verify Mode == SourceAndDestination                         │
   │  ✓ >= 2 destinations with valid ASC MHL (xxh64) & 0 unlisted files      │
   │  ✓ >= 2 distinct PHYSICAL disks (traces APFS Physical Stores & DMGs)    │
   │  ✓ Identical MHL hash sets across all destinations                      │
   └─────────────────────────────────────────────────────────────────────────┘
        │
        ▼  3. scripts/resolve_dailies.py
[DaVinci Resolve Studio 21.x]
   ✓ Guards against silent write failures (GetCurrentPage() != None)
   ✓ Imports into <YYYYMMDD>/<ROLL> bins (file list, bypassing Resolve's directory bug)
   ✓ AutoSyncAudio (BWF timecode or waveform) + verifies "Synced Audio" per clip
   ✓ Creates or idempotently appends to DAILIES_<YYYYMMDD> timeline sorted by Start TC
```

### Why DITs & AI Agents Need This Gate

1. **True Industry-Standard ASC MHL (`urn:ASC:MHL:v2.0`) & Legacy MHL (`xxh64`) — 100% Read-Only:**
   Unlike the official `ascmhl` CLI (which writes a new generation into the destination drive when verifying) or ad-hoc JSON hash manifests, [`scripts/mhl_verify.py`](scripts/mhl_verify.py) is strictly **read-only**, normalizes NFC/NFD Unicode across exFAT and APFS, and catches **unlisted extra files** (such as `<name> 2.MP4` silently created when OffShoot encounters a filename collision).
2. **macOS Physical-Disk Provenance ([`scripts/handoff.py`](scripts/handoff.py)):**
   Two folders, two APFS volumes on the same SSD, or two mounted `.dmg`/`.sparsebundle` images stored on the same internal drive are **not** independent backups. `handoff.py` queries `diskutil info -plist` (`APFSPhysicalStores`, `ParentWholeDisk`) and `hdiutil info -plist` (tracing disk images back to their backing physical disk) and fails closed if destinations share a physical store.
3. **OffShoot Pro Silent-Failure Protection ([`scripts/ingest.py`](scripts/ingest.py)):**
   OffShoot's `offshoot://` URL-scheme API can write `success` to `urlSchemeResponseLog.txt` even when a source disk hasn't been registered yet (queuing 0 transfers). `ingest.py` tracks `OffShootEvents.log` by byte offset to confirm a matching `Transfers Added` event (`sourceLabel = <roll>`) and automatically restores the GUI preset on timeout or failure.
4. **Field-Tested DaVinci Resolve 21.2 Guards ([`scripts/resolve_dailies.py`](scripts/resolve_dailies.py) & [`docs/11-resolve-21-gotchas.md`](docs/11-resolve-21-gotchas.md)):**
   Protects against 12+ undocumented Resolve 21.2 scripting pitfalls (`GetCurrentPage() is None` modal dialog trap, `Resolve` returning `None` for unknown attributes instead of `AttributeError`, `ImportMedia([dir])` returning `[]` silently, etc.).

---

## Comparison & Synergy with `samuelgursky/davinci-resolve-mcp`

| Capability | `offshoot-resolve-dit` (This Repo) | `samuelgursky/davinci-resolve-mcp` |
|---|---|---|
| **Primary Stage** | **On-Set DIT Ingest → 3-2-1 Gate → Dailies Handoff** | **Post-Production Editorial, Color & Offline `.drp/.drt/.drx`** |
| **OffShoot Pro (Hedge) Control** | **10 MCP tools + CLI** (`offshoot://` API, Netflix presets, event scripts, 25.x/26.x log parser, HTML/PDF reports) | None |
| **Checksum / MHL Verification** | **Native ASC MHL v2.0 (`ascmhl/*.mhl`) & Legacy MHL (`xxh64`)**, recursive unlisted-file detection, NFC/NFD normalization | Custom SHA-256 JSON manifest (`ingest_verify` `"MHL-like"`) |
| **3-2-1 Physical Disk Gate** | **`diskutil` APFS Physical Store + `hdiutil` DMG backing-disk resolution** | None |
| **Resolve Dailies & BWF Sync** | Single-command guarded `resolve_dailies.py` (0-sample drift verified with synthetic BWF generator `scripts/lab/mkfoot.sh`) | General `media_pool` / `timeline` compound tools (see [`docs/upstream/`](docs/upstream/) for our upstream patch fixing 2 Resolve 21.2 bugs) |

Use **`offshoot-resolve-dit`** to offload cards, verify 3-2-1 ASC MHL integrity across physical drives, and build synced Dailies timelines; then use **`davinci-resolve-mcp`** for downstream editorial and color grading.

---

## Quickstart

### 1. Register the `offshoot` MCP Server (Claude Code / MCP Clients)

Requires [uv](https://docs.astral.sh/uv/) and macOS with OffShoot Pro and/or DaVinci Resolve Studio:

```bash
claude mcp add --scope user offshoot -- uv run --directory /path/to/offshoot-resolve-dit --no-project \
  --with "mcp<2" --with xxhash python -m tools.mcp_server
```

#### Available MCP Tools (10)
| Tool | Mode | Description |
|---|---|---|
| `status` | Read-only | Check if OffShoot is running, active verify mode, MHL type (Legacy vs ASC), current preset, iconik & move-on-same-volume flags |
| `list_volumes` | Read-only | List mounted volumes in `/Volumes` with total and free capacity (GB) |
| `scan_logs` | Read-only | Summarize OffShoot transfer logs across both 25.x and 26.x (`v1.1`) JSON schemas |
| `ingest_preflight` | Read-only | Validate card path, roll naming (`A001`, `S001`), preset existence, free space, duplicate roll collision, and volume independence |
| `ingest_start` | Mutating | Queue an offload across multiple destinations (defaults to `confirm=false` dry-run plan; requires `confirm=true` after human approval) |
| `ingest_status` | Mutating (light) | Poll per-destination transfer completion and automatically restore the GUI's previous preset |
| `verify_mhl` | Read-only | Re-hash a roll directory against its ASC MHL or Legacy MHL (`xxh64`) without writing to the drive; flags missing, corrupted, or unlisted files |
| `handoff_check` | Read-only | **3-2-1 Gate before Resolve**: enforces `SourceAndDestination`, `>= 2` physical disks, ASC MHL pass, and cross-destination MHL equality |
| `make_presets` | Mutating | Generate Netflix-standard `<PROJECT>_OCF.hedge` and `<PROJECT>_SOUND.hedge` presets and reload OffShoot |
| `make_report` | Mutating | Generate HTML + PDF offload reports via OffShoot's bundled `reports-cli` and headless Chrome |

---

### 2. CLI Usage

```bash
# 1. Generate Netflix-standard presets (<SHOW>_OCF and <SHOW>_SOUND)
python3 scripts/mkpreset.py "MY_SHOW" && scripts/os reload

# 2. Guarded multi-destination offload
python3 scripts/ingest.py /Volumes/A001 A001 MY_SHOW_OCF /Volumes/RAID01 /Volumes/SHUTTLE01

# 3. Read-only ASC/Legacy MHL verification on a roll directory
uv run --no-project --with xxhash python scripts/mhl_verify.py /Volumes/RAID01/MY_SHOW/20261114/Camera_Media/A001

# 4. 3-2-1 Physical-Disk & MHL Handoff Gate
uv run --no-project --with xxhash python scripts/handoff.py \
  /Volumes/RAID01/MY_SHOW/20261114/Camera_Media/A001 \
  /Volumes/SHUTTLE01/MY_SHOW/20261114/Camera_Media/A001

# 5. Import into DaVinci Resolve Studio, auto-sync BWF/waveform audio, and assemble DAILIES timeline
PYTHONUTF8=1 uv run --no-project --with xxhash python scripts/resolve_dailies.py \
  --project MY_SHOW --day 20261114 --fps 25 \
  --cam   /Volumes/RAID01/MY_SHOW/20261114/Camera_Media/A001 /Volumes/SHUTTLE01/MY_SHOW/20261114/Camera_Media/A001 \
  --sound /Volumes/RAID01/MY_SHOW/20261114/Sound_Media/S001  /Volumes/SHUTTLE01/MY_SHOW/20261114/Sound_Media/S001
```

---

### 3. Run Unit Tests & Synthetic E2E Lab

```bash
# Run all 53 unit tests
uv run --no-project --with xxhash python -m unittest discover tests -v

# Generate synthetic camera clips (with LTC/TC + scratch audio + clap pulse) and BWF sound WAVs (with bext time_reference)
scripts/lab/mkfoot.sh /tmp/lab_cam/PRIVATE/M4ROOT/CLIP /tmp/lab_sound
```

---

## Documentation & Agent Skills

- **Agent Skills** (`skills/`): Ready-to-use skills for Claude Code / AI agents:
  - [`skills/dit-resolve/SKILL.md`](skills/dit-resolve/SKILL.md) — End-to-end card → OffShoot → Gate → Resolve Dailies runbook
  - [`skills/offshoot-dit/SKILL.md`](skills/offshoot-dit/SKILL.md) — OffShoot Pro operation & gotchas
  - [`skills/davinci-resolve/SKILL.md`](skills/davinci-resolve/SKILL.md) — DaVinci Resolve Studio 21.x scripting gates
- **Technical Deep Dives** (`docs/`):
  - [`docs/11-resolve-21-gotchas.md`](docs/11-resolve-21-gotchas.md) — **12 Field-Tested DaVinci Resolve 21.2 Scripting API Gotchas** (English)
  - [`docs/01-concepts.md`](docs/01-concepts.md) — OffShoot verification modes, xxHash64, ASC MHL, filter & sidecar gotchas (Tiếng Việt)
  - [`docs/02-api.md`](docs/02-api.md) — `offshoot://` URL-scheme API reference & quirks (Tiếng Việt)
  - [`docs/03-scripting.md`](docs/03-scripting.md) — Event scripting & Telegram bot notifications (Tiếng Việt)
  - [`docs/04-dit-workflow.md`](docs/04-dit-workflow.md) — 3-2-1 on-set workflow & DMG lab exercises (Tiếng Việt)
  - [`docs/06-naming-standard.md`](docs/06-naming-standard.md) — Netflix folder & roll naming standard (Tiếng Việt)
  - [`docs/07-ascmhl-reports.md`](docs/07-ascmhl-reports.md) — ASC MHL cross-verification & HTML/PDF reports (Tiếng Việt)
  - [`docs/08-ecosystem-ai.md`](docs/08-ecosystem-ai.md) — Survey of AI/MCP tools around OffShoot (Tiếng Việt)
  - [`docs/09-mcp.md`](docs/09-mcp.md) — `offshoot` MCP server reference (Tiếng Việt)
  - [`docs/10-e2e-resolve.md`](docs/10-e2e-resolve.md) — E2E fault-injection & lab verification report (Tiếng Việt)
  - [`docs/upstream/davinci-resolve-mcp-audio-sync-import-dir.patch`](docs/upstream/davinci-resolve-mcp-audio-sync-import-dir.patch) — Patch for `samuelgursky/davinci-resolve-mcp`

## License

[MIT](LICENSE)
