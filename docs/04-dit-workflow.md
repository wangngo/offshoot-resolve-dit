# 04 — Quy trình offload trên set + lộ trình tự học

## Nguyên tắc 3-2-1 cho footage
- **3 bản**: thẻ gốc + 2 bản backup.
- **2 loại/ổ vật lý khác nhau**: vd RAID hoặc SSD làm việc + HDD shuttle.
- **1 bản rời khỏi set** (shuttle mang về post/văn phòng, hoặc S3/NAS).
- **Chỉ format thẻ khi**: 2 đích đều có status Success, mode là **Source** hoặc **Source & Destination**, và đã kiểm tra lại log.

## Quy trình mỗi thẻ
1. Cắm thẻ, khoá write-protect nếu thẻ hỗ trợ. Kiểm tra tên volume và roll name (A001, B002, SOUND_D01…).
2. Chọn preset dự án. Preset quy định cấu trúc thư mục `PROJECT/Dxx_YYYYMMDD/Cam|Sound/Roll`.
3. Verification: **Source** (format thẻ ngay sau đó) hoặc **Source & Destination** (khi cần giao ASC MHL).
4. Add 2 đích → Add Transfers → chờ Success trên **cả 2** đích.
5. Đọc log: `scripts/log_scan.py --since <hôm nay> --problems`.
6. Ghi camera report và sổ thẻ: roll, số clip, dung lượng, trạng thái, người format.
7. Cuối ngày: report PDF (reports-cli/Ingest Browser), cascade sang shuttle, eject đúng cách.

## Lộ trình làm quen (dùng dữ liệu giả)
- [ ] B1 — Tạo thẻ giả: folder hoặc USB có cấu trúc giống thẻ (DCIM/CLIP, file `.MOV` giả bằng `mkfile`).
- [ ] B2 — Chạy 1 transfer với mỗi verify mode, so thời gian và đọc log txt/json.
- [ ] B3 — Cố tình làm hỏng 1 file ở đích, thử verify bằng MHL để xem OffShoot báo lỗi thế nào.
- [ ] B4 — Tạo preset dự án mẫu (folderPattern, filter), sửa JSON rồi `scripts/os reload`.
- [ ] B5 — Lái bằng API: `scripts/os src/dst/add`.
- [ ] B6 — Script event: File Copy Completed → Telegram.
- [ ] B7 — ASC MHL + reports-cli xuất report cho post.

## Kết quả lab B1–B2 (2026-10-11, `~/offshoot-lab`, ngoài git — DMG đã xoá 2026-10-12, dựng lại bằng lệnh dưới)
- B1: `A001.dmg` (exFAT, cấu trúc Sony `PRIVATE/M4ROOT/CLIP`, 12 MP4 ngẫu nhiên 80 MB + 12 XML), đích `DST1/DST2/DST3.dmg` (APFS 1.5 GB).
  Dựng lại:
  ```sh
  cd ~/offshoot-lab && hdiutil create -size 1500m -fs ExFAT -volname A001 A001.dmg && hdiutil attach A001.dmg
  for d in DST1 DST2; do hdiutil create -size 3g -fs APFS -volname $d $d.dmg && hdiutil attach $d.dmg; done
  C=/Volumes/A001/PRIVATE/M4ROOT/CLIP; mkdir -p $C
  for i in $(seq -w 1 12); do head -c 80000000 /dev/urandom > $C/A001C0$i.MP4; echo "<xml>$i</xml>" > $C/A001C0${i}M01.XML; done
  ```
  Dùng xong: `hdiutil detach /Volumes/<tên>` rồi xoá file `.dmg`. Đích nên ≥ 2× dung lượng thẻ (bài học "Does not fit").
- B2: 960 MB với Transfer 0.9 s, Source 1.7 s, Source & Destination 1.3 s.
  ⚠️ **Thời gian không phản ánh thực tế** vì DMG nằm trên SSD trong và đã được cache trong RAM. Muốn so tốc độ phải dùng thẻ/ổ thật.
- Đọc từ log: chế độ Transfer không có dòng `Hash:` cho từng file ở đích. Source & Destination có hash cho mọi file.
- Phát hiện thêm: XML bị lọc mặc định, sidecar `.json`, response API thất thường, đích đầy thì transfer bị hủy "Does not fit".

## Kết quả lab B3 (2026-10-12) — làm hỏng dữ liệu ở đích rồi verify lại bằng MHL
- Trên DST1: **lật 1 byte** trong `A001C003.MP4` (giữ nguyên size và mtime) và **xoá** `A001C005.MP4`.
- Cách verify lại: `open -a OffShoot "<thư mục>/OffShoot Media Hash List - ….mhl"` → hộp thoại hỏi "verify all files in …" → bấm **Verify**.
  Chạy được với **MHL kiểu cũ** (`hashlist 1.1`), không cần ASC MHL.
- Kết quả: `Verification Failed: 1` (C003), `Missing Files: 1` (C005), 10 file OK, status *Completed with warnings*.
  Log nằm ở `Transfer Logs/<ngày>/OffShoot Log - OffShoot Media Hash List - ….txt`.
- **Bài học:** lỗi lật bit giữ nguyên kích thước nên **chế độ Transfer (chỉ so size) không thể phát hiện**. Chỉ hash (MHL hoặc Source & Destination) mới bắt được.
  MHL chỉ chứa clip media, không chứa sidecar `.json`.
- Đã khôi phục dữ liệu lab về như cũ.

## Kết quả lab B5 (2026-10-12) — offload bằng 1 lệnh: `scripts/ingest.py`
```sh
scripts/ingest.py /Volumes/A001 A001 PHIM_OCF /Volumes/RAID01 /Volumes/SHUTTLE01
```
- **Preflight** chặn trước khi chạy: thẻ hoặc đích không tồn tại, roll sai chuẩn (`^[A-Z]\d{3}$`), preset không có,
  đích trùng, **đích không đủ chỗ** (tránh bị hủy "Does not fit" mà không có log). Cảnh báo khi 2 đích chung volume
  hoặc verify mode là Transfer.
- Chạy: đặt preset → reset → setSource(label=roll) → setDestination×n → addTransfers, sau đó chờ log JSON của từng đích.
- Exit 0 **chỉ khi mọi đích Success và 0 file lỗi**. Chạy xong trả preset của GUI về như cũ.
- Lab đã thử: roll `a1` → PREFLIGHT FAIL; DST1 thiếu chỗ → PREFLIGHT FAIL; A001 → DST2+DST3 → ✓✓ rc=0, 24 file có XML, 0 sidecar.
- **GOTCHA: OffShoot 26.x đổi schema log JSON** (`version: "1.1"`): `source{}`, `destination{path}`, `preset{name}`,
  `status` viết thường, lỗi nằm trong `status` của từng mục `files[]` và `clips[].assets[]`
  (`verified|filtered|skipped|hidden` = OK; `failed|failed_verification|missing|not_transferred` = lỗi).
  `scripts/oslog.py` chuẩn hoá cả 2 schema; `log_scan.py` và `ingest.py` đều dùng module này.
