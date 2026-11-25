# 10 — Test E2E: OffShoot → cổng → DaVinci Resolve (2026-11-14)

Lab giả (DMG, `scripts/lab/mkfoot.sh`): thẻ `A001` exFAT cấu trúc Sony (3 MP4 TC 25fps 10:00:00/20/40,
scratch 440 Hz + clap +3s, XML), thẻ `SOUND01` (WAV BWF 1000 Hz, `S001T01` sớm 2s, `S001T02` dài phủ C002+C003),
đích `DST1`/`DST2` APFS (2 disk image — vòng 1 code nhận nhầm là 2 ổ `disk8`/`disk10`; thật ra cùng `disk0`, xem lỗi #7). OffShoot 26.3.1, Resolve Studio 21.2.

## Kết quả happy path
ingest A001 + S001 → 2 đích Success, ASC MHL 6/6 → import DST1 → AutoSyncAudio TC 3/3 (WAV dài link cả 2 clip)
→ `DAILIES_20261114` (A1 scratch, A2 recorder) → render H264+LPCM: có cả 440/1000 Hz (−41 dB),
clap 1 đỉnh mỗi clip, độ rộng đúng 20.0 ms ⇒ A1/A2 lệch 0. Chạy lại theo skill `dit-resolve` (roll A003) OK.

## Lỗi tìm thấy (đã sửa, có regression test)
| # | Triệu chứng (dữ liệu thật) | Nguyên nhân | Sửa |
|---|---|---|---|
| 1 | `ingest_start` → `started:true` nhưng không copy gì; response API `success` | OffShoot chưa đăng ký ổ nguồn (A001 không có `Disk Added` trong Event Log; nghi do ổ đang bị ghi lúc app khởi động). URL API rơi im lặng | `ingest.start` chờ event `Transfers Added` sau offset byte của Event Log (không parse ngày theo locale); không thấy → `started:false` |
| 2 | Lần sau `previous_preset` = preset lab, preset gốc GENERAL mất | Lần hỏng không trả preset | Trả preset ngay khi không xác nhận; `ingest_status` có `give_up_after_s` → `timed_out` cũng trả preset |
| 3 | `verify_mhl(<thư mục ngày>)` → `problems: []` | Không có MHL vẫn không lỗi; không có cờ pass | Thêm `passed` (False khi không MHL); CLI exit theo `passed` |
| 4 | File thừa `A001C001 2.MP4` → verify 6/6 OK | Chỉ duyệt file trong MHL | Kind `unlisted` cho file trên đĩa không có trong MHL (bỏ `ascmhl/`, dotfile) |
| 5 | `ingest_status(started_at không múi giờ)` → crash naive vs aware | So datetime naive/aware | `ingest.aware()` |
| 6 | (code mới) `handoff` coi 2 thư mục con là 2 ổ khác nhau | `diskutil info` không nhận thư mục con → `unknown:<path>` khác nhau | Tìm mount point trước; không xác định được ⇒ FAIL (fail closed) |

Thêm: `scripts/handoff.py` + MCP `handoff_check` (cổng: mode S&D, ≥2 đích, ASC MHL `passed`, ≥2 ổ vật lý,
MHL các đích giống nhau, trả danh sách media), `scripts/resolve_dailies.py` (cổng + import file + sync + verify
`Synced Audio` + timeline, chạy lại an toàn).

## Review advisor (Fable) sau vòng 1 — đã sửa + verify lại trên lab (vòng 2)
| # | Lỗi | Sửa / bằng chứng |
|---|---|---|
| 7 | 2 DMG chung 1 ổ → cổng PASS (đĩa ảo diskN) | lần file ảnh qua `hdiutil info` → ổ thật; lab vòng 2: cả 2 = `disk0` → FAIL ✅ |
| 8 | `Transfers Added` của transfer khác xác nhận nhầm | khớp `sourceLabel = <roll>`; ingest vòng 2 OK ✅ |
| 9 | Event Log bị cắt (offset > size) → started:false sai | đọc lại từ đầu |
| 10 | NFD trên đĩa vs NFC trong MHL → `unlisted` sai; `ascmhl/` lồng | chuẩn hoá NFC; loại `ascmhl` mọi cấp |
| 11 | `resolve_dailies` exit 0 khi WAV không vào bin / file import thiếu / fps lệch | gom `errors`; fps lệch exit 1 ✅ |
| 12 | Timeline đã có → thẻ thứ 2 trong ngày không vào | nối clip mới; A002 nối 3 clip, V1 đủ 6 ✅ |
| 13 | Project load hỏng → tạo trùng tên | chỉ tạo khi không có trong danh sách |
| 14 | Đuôi media ngoài danh sách bị bỏ lặng | mở rộng đuôi + trả `skipped` |
Giữ nguyên (cố ý): NAS/SMB/Fusion → không xác định ổ → FAIL, không có cờ bỏ qua. Lab dùng wrapper monkeypatch trong scratchpad.

## Fault injection (DST1)
| Case | Kết quả |
|---|---|
| Lật 1 byte giữ size | hash_mismatch ✅ |
| Cắt cụt | size_mismatch ✅ |
| Xoá file | missing ✅ |
| File thừa `<tên> 2.ext` | trước: PASS ❌ → nay unlisted ✅ |
| Sửa XML | size_mismatch ✅ |
| Sửa hash trong `.mhl` | hash_mismatch ✅ (không phân biệt file hay MHL hỏng → đối chiếu đích 2, `handoff` báo "MHL khác") |
| Thư mục cha không MHL | trước: problems rỗng ❌ → nay `passed:false` ✅ |
| 2 bản chung 1 ổ | handoff FAIL ✅ |
| Roll trùng | preflight chặn ✅ |
| Đích có `/` cuối | OK ✅ |
| Path dấu cách + tiếng Việt (NFC/NFD) | Resolve import OK ✅ |
| Import lại lần 2 | 0 clip mới, không sync/timeline lại ✅ |
| Eject đích khi Resolve mở project | macOS từ chối (Resolve giữ file) — đóng project trước |

## Gotcha Resolve mới
- `ImportMedia([thư mục])` → `[]` im lặng; truyền danh sách file.
- Object Resolve trả `None` cho mọi tên thuộc tính sai (không AttributeError): `AUDIO_SYNC_WAVEFORM` (không S).

## Chưa test
- Nhánh âm "OffShoot không nhận ổ" chỉ có unit test (không tái hiện được theo ý muốn — phụ thuộc timing).
- Đích đầy GIỮA chừng; waveform sync với scratch khác mic; RAW (BRAW/R3D/ARRI); verify mode `Source` thật.
