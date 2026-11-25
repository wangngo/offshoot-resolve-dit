# 01 — Khái niệm OffShoot (nguồn: docs.hedge.video, tra 2026-10-11)

## Mô hình
**Source** (thẻ/ổ nguồn) × **Destination** (1..n ổ đích) → mỗi cặp là 1 **Transfer**, nằm trong 1 Transfer Group.
Copy song song nhiều đích, đọc nguồn một lần. Có Stop & Resume, incremental (bỏ qua file đã có), phát hiện trùng.

## Verification mode (quan trọng nhất)
| Mode | Làm gì | Khi nào dùng |
|---|---|---|
| **Transfer** (mặc định) | chỉ so **kích thước** nguồn/đích | nhanh nhất; **KHÔNG dùng nếu sẽ format thẻ** |
| **Source** | hash nguồn độc lập (đọc trước rồi đọc lại để copy), đích chỉ so size | khi format nguồn sau khi copy nhiều bản |
| **Source & Destination** | đọc lại + so hash cả nguồn lẫn đích | an toàn nhất, ~2× thời gian; dùng khi xuất ASC MHL |

Tên cũ (trước 24.3): Checkpoint OFF / ON (Backup) / ON (Archive).
Đặt ở pref **`nl.syncfactory.Hedge.Mac` → `TransfersSettingsVerifyKey`** = `Transfer` | `Source` | `SourceAndDestination`.
Đổi qua API:
`scripts/os raw 'offshoot://setPreferences?preferences=%7B%22TransfersSettingsVerifyKey%22%3A%22SourceAndDestination%22%7D'`.

## Checksum
- **XXH64BE** luôn được tính, ghi vào log và MHL.
- Legacy (tuỳ chọn, chậm hơn): **MD5, SHA1, C4**. Bật khi post-house/khách yêu cầu.

## MHL
- **Media Hash List**: danh sách hash đi kèm bản backup, dùng để verify lại về sau.
- **ASC MHL** (Pro): chuẩn ASC, Netflix yêu cầu. Có chain (`ascmhl/chain.xml`) theo dõi lịch sử copy.
- Nếu nguồn đã có ASC MHL khớp size và mtime, OffShoot dùng hash trong đó thay vì đọc lại.
- Verify tay: double-click file ASC MHL → Verify. Kết quả báo file thiếu và file sai hash.

## Lọc file mặc định (GOTCHA)
Pref `SFIDefaultsIndexFilterRules` (domain IngestPro) **lọc bỏ `.xml` và `.thumbs` cho mọi lần copy**.
Lab 2026-10-11: 12 file `A001C0xxM01.XML` (sidecar metadata của Sony) bị lọc, không được copy. Nên xem lại trước dự án thật.

## File sidecar `.json` (do tích hợp **iconik** đang bật — xem docs/06)
Mỗi file có thêm `<file>.json` (khoảng 140 byte, chứa `metadata_values` → Source Name) trên đích.
Khi **copy tiếp từ một đích cũ** (cascade thủ công, SSD → HDD), OffShoot ghi đè các file đó theo nhãn mới,
nên verify báo `Inconsistent file size detected on destination` cho **file .json**. Đây là cảnh báo vô hại, clip vẫn verify OK.
Đã tái hiện ở lab 2026-10-11. Cách tránh: copy tiếp với cùng nhãn, dùng Cascading chuẩn của Pro, hoặc lọc `.json` khi nguồn là bản backup.

## Preset (`~/Library/Preferences/Hedge/Presets/*.hedge`, JSON)
Các trường: `doNotCopyFiles` (lọc đuôi), `ignoreBundles`, `flattenFolders`, `folderPattern`
(vd `{File YYYY}{File MM}{File DD}`), `labelPattern` (`{Counter}`), `counter`, `renamePattern`, `ignoreEmptyFolders`.
Sửa file xong gọi `scripts/os reload`.

## Tính năng chỉ có ở Pro
S3 destination, API và scripting, ASC MHL, Cascading (copy tiếp từ đích nhanh sang đích chậm),
Ingest Browser, Codex copy engine (ARRI), Advanced Presets + Helper app, Connect Pro.

## Khác
- **Broken Media Detection**: cảnh báo file media 0 byte (hay gặp khi thẻ exFAT rút không eject).
- **Missing files detection**: hết transfer thì kiểm tra đích có đủ file không.
- Các pref tự động: `SFIDefaultsAutoEjectDisks`, `SFIDefaultsAutoSources`.

## GOTCHA: trùng tên ở đích → OffShoot âm thầm đổi tên, vẫn báo Success
Đích đã có `X.MP4` khác nội dung thì OffShoot ghi bản mới thành **`X 2.MP4`**, status **Success**, không có lỗi
(đã tái hiện ở lab 2026-10-12 với file bị khoá `uchg`). Khi đó roll không còn giống hệt thẻ, và dễ link nhầm file rác.
Cách chặn: `ingest.py` dừng ngay nếu thư mục roll đã tồn tại;
`tg_event.py` cảnh báo ⚠️ khi thấy file `<tên> N.ext`; `mhl_verify.py` báo lỗi `unlisted`.
