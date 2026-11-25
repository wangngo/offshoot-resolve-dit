# 09 — MCP server `offshoot` (2026-10-12)

Vỏ mỏng FastMCP (`mcp<2`) bọc các tool đã có test trong `scripts/`. Code: `tools/mcp_server.py`.
Đăng ký (user scope, `~/.claude.json`):
```sh
claude mcp add --scope user offshoot -- uv run --directory /path/to/offshoot-resolve-dit --no-project \
  --with "mcp<2" --with xxhash python -m tools.mcp_server
```
Cần restart Claude Code để thấy tool.

| Tool | Loại | Việc |
|---|---|---|
| `status` | đọc | app chạy?, verify mode, loại MHL, preset, iconik, move-on-same-volume, script event, danh sách preset |
| `list_volumes` | đọc | ổ trong /Volumes + dung lượng trống |
| `scan_logs(since, show_problems, limit)` | đọc | tóm tắt transfer log (schema 25.x + 26.x) |
| `ingest_preflight(source, roll, preset, dests)` | đọc | kiểm tra trước offload |
| `ingest_start(..., confirm=false)` | ghi | **mặc định chỉ trả kế hoạch**; `confirm=true` (sau khi người dùng duyệt) mới đưa vào OffShoot. Preflight lỗi → từ chối |
| `ingest_status(roll, dests, started_at, restore_preset)` | ghi nhẹ | kết quả từng đích, `all_ok`; xong thì trả preset GUI về cũ |
| `verify_mhl(path)` | đọc | verify **chỉ đọc** theo ASC/legacy MHL (xxh64), không ghi lên ổ; chỉ tin `passed` (file thừa = `unlisted`) |
| `handoff_check(roll_dirs)` | đọc | **cổng trước Resolve**: S&D, ASC MHL passed mọi đích, ≥2 ổ vật lý, MHL khớp; trả `media` (docs/10) |
| `make_presets(project)` | ghi | tạo preset chuẩn Netflix (không ghi đè) + reload |
| `make_report(day_or_files, out_dir, title, note)` | ghi | report HTML + PDF |

## Kiểm thử e2e (lab DMG)
không confirm → chỉ trả kế hoạch · roll đã tồn tại → bị chặn · confirm → 2 đích Success, preset trả về GENERAL ·
verify_mhl ASC 6/6 OK · lật 1 bit → `hash_mismatch` đúng file.

## Gotcha
- **Không được in ra stdout trong MCP stdio** (stdout là kênh JSON-RPC). `ingest.api()` bắt output của `scripts/os`.
- Offload dài → tách `ingest_start` / `ingest_status` để không treo cuộc gọi.
- Mỗi lần offload thật vẫn bắn event → Telegram báo như thường.
