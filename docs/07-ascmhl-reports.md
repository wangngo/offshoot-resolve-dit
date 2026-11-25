# 07 — ASC MHL & Report cho hậu kỳ (lab B7, 2026-10-12)

## Bật ASC MHL
Settings > Transfers > **Paper Trail**: `legacy MHLs` ↔ `ASC MHLS`.
- **ASC MHL chỉ dùng được với verify Source & Destination**. Chọn S&D thì GUI tự chuyển sang ASC MHLS.
- Pref: `nl.syncfactory.Hedge.Mac` → `SFIDefaultsHedgeProMHLType` (`0` = legacy, `1` = ASC) + `TransfersSettingsVerifyKey=SourceAndDestination`.
  Đổi qua API: `setPreferences {"TransfersSettingsVerifyKey":"SourceAndDestination","SFIDefaultsHedgeProMHLType":"1"}`.
- Kết quả trên đích, trong thư mục roll:
  ```
  A001/ascmhl/0001_A001_<UTC>.mhl      ← urn:ASC:MHL:v2.0, xxh64 cho MỌI file (kể cả XML), process=transfer
  A001/ascmhl/ascmhl_chain.xml          ← chuỗi generation, mỗi mục có c4 của file .mhl
  ```
  Ngày trong tên file là **giờ UTC**. Thư mục `ascmhl/` nằm **trong** roll, đúng chuẩn ASC.

## Kiểm tra chéo bằng công cụ chính thức `ascmhl` (ASC, open-source)
```sh
python3 -m venv ~/offshoot-lab/ascmhl-venv && ~/offshoot-lab/ascmhl-venv/bin/pip install ascmhl   # v1.2 (đã xoá 2026-10-12, cài lại khi cần)
ascmhl info   <roll>             # xem các generation
ascmhl create -h xxh64 <roll>    # đọc lại TẤT CẢ file, so với lịch sử, thêm 1 generation (GHI vào ascmhl/)
ascmhl diff   <roll>             # chỉ so có/thiếu file, không hash
```
Lab: roll nguyên vẹn → rc=0 (thêm Generation 2). Lật 1 bit ở `A001C009.MP4` →
`ERROR: hash mismatch … xxh64 (old) … (new)`, rc=11. **MHL của OffShoot tương thích với tool chuẩn.**
⚠️ `ascmhl create` ghi thêm vào ổ đích. Chỉ chạy trên ổ được phép ghi; còn bàn giao thì để post house tự chạy.

## Report
- GUI: Window > Transfer Logs (⌘L) → chọn ngày → **Create Report** → ra HTML + PDF (Window > Reports để mở thư mục).
  Tiêu đề, logo, ghi chú, Clip Awareness (thumbnail + metadata) đặt ở Settings > Reports.
- CLI: `scripts/report <YYYY-MM-DD | file.json…> -o <thư mục> -t "Tiêu đề" -n "Ghi chú"`
  dùng `reports-cli` trong app (chỉ ra HTML), rồi in PDF bằng Chrome headless.
- Report có: Summary, Sources (verify mode, checksum type, status), Destinations, từng roll gồm preset/elements,
  đường dẫn đích và **từng clip kèm checksum + Verified theo từng đích**.
- Report lấy MỌI log trong ngày. Muốn loại transfer nào thì dùng `-f` chọn file, hoặc chuyển file .json của transfer đó ra chỗ khác.

## Khuyến nghị cho dự án phim
- Dự án cần bàn giao chuẩn (Netflix/post house): **Source & Destination + ASC MHL**. Chậm hơn khoảng 2×, nhưng có ASC MHL và đọc lại cả đích.
- Dự án nhỏ, cần nhanh: Source + legacy MHL.
