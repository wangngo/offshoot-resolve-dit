---
name: offshoot-dit
description: >-
  Operate OffShoot Pro (Hedge) on macOS for film/commercial DIT offloading — URL-scheme API
  (offshoot://), preflight checks, Netflix-standard presets, read-only ASC/Legacy MHL verification
  (xxh64), transfer log scanning, HTML/PDF reports, and Telegram event alerts.
---

# offshoot-dit — OffShoot Pro (Hedge) Operations & Verification

## Tools
- **MCP server `offshoot`** (`tools/mcp_server.py`, 10 tools):
  - Read-only: `status`, `list_volumes`, `scan_logs`, `ingest_preflight`, `verify_mhl`, `handoff_check`
  - Action: `ingest_start` (defaults to `confirm=false` dry-run plan), `ingest_status`, `make_presets`, `make_report`
- **Read-only MHL verifier**: `scripts/mhl_verify.py <roll_dir>` (verifies ASC MHL `ascmhl/*.mhl` and legacy `*.mhl` via `xxh64` without writing new generations to the destination drive; flags unlisted extra files).
- **URL-scheme CLI wrapper**: `scripts/os open|reset|src <path> [label]|dst <path>|add|reload|raw <url>`.
- **Single-command guarded ingest**: `scripts/ingest.py <card> <roll> <preset> <dest1> <dest2>...`.

## Field-Tested Gotchas (OffShoot Pro 25.x / 26.x)
- **Verify mode preference key** lives in domain `nl.syncfactory.Hedge.Mac` → `TransfersSettingsVerifyKey` (`Transfer` | `Source` | `SourceAndDestination`), NOT `video.hedge.IngestPro.Mac`.
- **URL-scheme API returns `success` even when nothing was queued** (e.g., if OffShoot has not registered the source volume yet). The only reliable proof that a transfer started is a new `Transfers Added` block matching `sourceLabel = <roll>` in `~/Library/Application Support/OffShoot/Event Log/OffShootEvents.log` (`ingest.py` verifies this by byte offset).
- **Silent duplicate rename (`<name> 2.ext`)**: If a destination already contains a file with the same name but different content, OffShoot silently writes `<name> 2.ext` and still reports `Success`. `ingest.py` blocks existing roll folders during preflight, and `mhl_verify.py` catches extra files as `unlisted`.
- **Default global filter drops `.xml`**: `SFIDefaultsIndexFilterRules` filters out `.xml` by default when no preset is active, dropping Sony `M01.XML` camera metadata sidecars. Active presets override global filters when `doNotCopyFiles: [""]`.
- **iconik integration sidecars**: When `SFIIntegrationsIconikDefaultsEnableKey=1`, OffShoot injects `<clip>.json` sidecars into the roll folder, violating verbatim card-clone rules and causing `Inconsistent file size` warnings on cascaded copies. Disable iconik for verbatim OCF offloads.
- **OffShoot 26.x JSON log schema change (`version: "1.1"`)**: Uses nested `source{}`, `destination{path}`, and per-asset statuses under `files[]` and `clips[].assets[]`. `scripts/oslog.py` normalizes both 25.x and 26.x schemas.
