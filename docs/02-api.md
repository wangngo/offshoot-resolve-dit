# 02 — URL-scheme API (Pro) — `offshoot://`

Gọi từ shell bằng `open '<url>'`. Kết quả ghi vào `~/Library/Logs/Hedge/urlSchemeResponseLog.txt`
(1 dòng `success`/`fail`, bị xoá trống sau mỗi lệnh). Wrapper: `scripts/os`.

| Action | Tham số | Ví dụ |
|---|---|---|
| open / quit / restart / update | — | `offshoot://open` |
| activate / deactivate | `key` | (không để key trong repo) |
| reset | `type=sources\|destinations` (bỏ trống = cả hai) | `offshoot://reset?type=sources` |
| setSource | `paths` (mảng JSON), `label` | `offshoot://setSource?paths=["/Volumes/UNTITLED"]&label=A001` |
| setDestination | `path` | `offshoot://setDestination?path=/Volumes/BACKUP` |
| addTransfers | — | tạo transfer cho mọi cặp Source–Destination mới (giống nút Add Transfers) |
| restartTransfer | `id` (lấy từ `FileCopyCompleted_id`) | |
| reloadPresets | — | |
| setPreferences | JSON (chỉ macOS) | `offshoot://setPreferences?preferences={"SFIDefaultsAutoSources":"0"}` |
| actions | `json=[{"<action>":{...}},...]` | gộp nhiều lệnh; nếu bị lỗi timing thì tách ra gọi riêng |

Gotcha: nên URL-encode tham số (đường dẫn có dấu cách hoặc tiếng Việt). `scripts/os` đã tự encode.

## Ví dụ: ingest 1 thẻ ra 2 đích
```sh
scripts/os reset
scripts/os src "/Volumes/A001" A001
scripts/os dst "/Volumes/RAID01/PROJECT/Media/D01"
scripts/os dst "/Volumes/SHUTTLE/PROJECT/Media/D01"
scripts/os add
```
Đã verify ở lab 2026-10-11: open, reset, setSource, setDestination, addTransfers, setPreferences đều chạy được.

## Gotcha
- File response **không đáng tin**: hay trả `success`, nhưng cũng có thể là tên action (`setSource`, `addTransfers`, `reset`) hoặc `mainview`
  mà lệnh vẫn chạy được. Phải kiểm tra bằng transfer log hoặc thư mục đích.
- addTransfers gặp đích thiếu chỗ thì transfer bị hủy `Canceled - Does not fit`, không có thông báo gì qua API.
- `setDestination` cần thư mục đã tồn tại. Thư mục con trên đích được đặt theo **label** của source.
- Lệnh `reset` không xoá các transfer đã xong trong danh sách GUI.
