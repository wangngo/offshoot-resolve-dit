# 08 — Hệ sinh thái MCP/AI quanh OffShoot (khảo sát 2026-10-12)

## Kết luận nhanh
- **Hedge (hãng) KHÔNG có MCP và không có tính năng AI chính thức** trong OffShoot. Tài liệu docs.hedge.video không nhắc AI/LLM/MCP.
  Thứ gần AI nhất là **Clip Awareness** (thumbnail + metadata JSON, Pro, dùng để đẩy sang MAM) và tích hợp **iconik** (MAM bên thứ 3 có AI tagging).
- Không có MCP OffShoot nào trên các kho MCP lớn (glama…). Cũng không có skill Claude nào.
- Trên GitHub có **2 dự án cộng đồng (rất mới, ít sao)** đúng hướng tích hợp AI:

| Dự án | Là gì | Trạng thái | Liên quan tới repo mình |
|---|---|---|---|
| [shakedex/hedgebuddy](https://github.com/shakedex/hedgebuddy) | Tool cho DIT quản lý script Python của bộ Hedge (OffShoot/FoolCat/EditReady/Canister): biến + profile, gắn script vào event, **MCP server** (`hedgebuddy mcp`) cho Claude. Lệnh nguy hiểm (`addTransfers/reset/quit/restart/restartTransfer`) bắt `confirmed: true`, thay đổi có `dry_run`. Rust + Tauri + gói Python. MIT | ★2, đang **viết lại từ đầu** (nhánh 0.11, release gần nhất v0.10 tháng 5/2026, commit 4/10/2026) | Trùng với `scripts/os` + gắn `tg_event.py`. Mạnh hơn ở quản lý profile/biến và GUI. Không có preflight/parse log/chuẩn đặt tên |
| [statik/majestical](https://github.com/statik/majestical) | Catalog media local-first (CLI `maj`), ingest có verify, tìm kiếm ngữ nghĩa bằng AI chạy offline, **MCP 36 tool** (mutating mặc định dry-run). Rust, Apache-2.0 | ★1, cập nhật 2/10/2026 | Không điều khiển OffShoot. Là **đối thủ/bổ trợ**: lấp chỗ OffShoot không có (search, catalog, tag). Có bài research OffShoot rất chi tiết |
| [itn-ltd/hedge-cli](https://github.com/itn-ltd/hedge-cli) | CLI điều khiển Hedge cũ | bỏ dở từ 2021 | bỏ qua |

## Kiểm chéo với phát hiện trong lab (từ research của majestical)
Bài `docs/research/offshoot.md` của majestical **khớp** với lab: hậu tố " 2" khi trùng tên, chế độ mặc định yếu nhất (chỉ so size),
resume tạo log/MHL mới chỉ cho phần copy thêm, auto-ingest phải tự viết script. Có thêm 2 điều mình chưa có:
- `SFIDefaultsSkipDuplicateDetectModificationDateCheck` (26.1.2+): phát hiện trùng **theo tên + size + mtime**, không theo hash.
- Dung lượng **purgeable của APFS** có thể gây báo "Does not fit" giả.

## Kiến trúc tích hợp AI
1. **MCP mỏng cho chính repo này** (~150 dòng Python, stdio): bọc `ingest` (preflight + confirm), `log_scan`, `report`,
   `os` (đọc trạng thái), verify MHL, cổng handoff sang DaVinci Resolve. Tận dụng code đã có test. Hợp với quy tắc an toàn (dry-run → người dùng duyệt).
2. **Thử HedgeBuddy trong sandbox**: chỉ dùng phần MCP `call list_apps`/đọc, không cho ghi vào OffShoot thật cho tới khi bản 0.11 ổn định.
   Rủi ro: đang viết lại, nó cũng gắn script vào event, dễ đè lên `tg_event.py` đang chạy.
3. **majestical** cho catalog/tìm kiếm footage sau khi offload (bài toán khác với offload).
