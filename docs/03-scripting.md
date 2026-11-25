# 03 — Scripting theo event (Pro)

Gắn script ở **Settings > Scripting**. macOS hỗ trợ AppleScript và Python 3 (từ 25.2, `python3` phải có trong PATH).
- Python: nhận tham số event dưới dạng **chuỗi JSON ở argv[1]**.
- AppleScript: chèn placeholder, vd `set p to "{FileCopyCompleted_destinationPath}"`. `return x` ghi vào Event Log.
- Kết quả ghi ở `~/Library/Application Support/OffShoot/Event Log/OffShootEvents.log`.

## Event và tham số (docs.hedge.video, file `.md`)
| Event | Tham số chính |
|---|---|
| OffShoot Started | — |
| Disk Added | `DiskAdded_rootFilePath`, `_title`, `_volumeKind` (exfat…), `_diskSize`, `_availableDiskSpace`, `_protocolName`, `_modelName`, `_deviceName` |
| Disk Removed / Disk Busy / Disk Idle / Disks Idle | (xem docs) |
| Transfers Added | `transferGroups` (id, sourceLabel, sourcePaths, transfers[destinationPath,id]) |
| **File Copy Completed** | `_state` (Success/Failed/Warnings/Canceled/Stopped), `_destinationPath`, `_sourcePaths`, `_presetName`, `_bytesCopied`, `_duration`, `_verification_mode`, `_id`, **`_transferLogJSONPath`** |
| **Verification Issue** | `VerificationIssue_description`, `VerificationIssue_filePath` |

Lưu ý: File Copy Completed bắn ra với **mọi** trạng thái kết thúc, nên script phải kiểm tra `_state`.

## Cài đặt `scripts/tg_event.py` → Telegram Bot
Gắn cho **File Copy Completed** và **Verification Issue**. Cài qua API vì hộp thoại Browse là tiến trình riêng:
```sh
S=/path/to/offshoot-resolve-dit/scripts/tg_event.py
scripts/os raw "offshoot://setPreferences?preferences=$(python3 -c 'import sys,json,urllib.parse;print(urllib.parse.quote(json.dumps({"SFIDefaultsFileCopyCompletedScript":sys.argv[1],"SFIDefaultsSourceVerifyIssueScript":sys.argv[1]})))' $S)"
```
Pref key theo từng event: `SFIDefaults{HedgeStarted,DiskAdded,DiskRemoved,DiskBusy,DiskNoLongerBusy,AllDisksIdle,SourceAdded,TransferAdded,FileCopyCompleted,SourceVerifyIssue}Script`
(giá trị là đường dẫn tuyệt đối). Gỡ: nút **Clear** trong Settings > Scripting.

Nội dung tin: ✅/⚠️/❌/⏹ + roll → đích, số file, GB, số lỗi, preset, verify mode, tối đa 5 file lỗi,
cảnh báo file bị đổi tên `<tên> 2.ext`, và dòng "KHÔNG format thẻ" khi không Success. Debug: `~/Library/Logs/offshoot-dit/tg_event.log`.

### Gotcha
- OffShoot gọi `python3` theo PATH GUI, trên macOS có thể ra **`/usr/local/bin/python3` = python.org 3.12 với kho CA chưa cài**
  → urllib lỗi `CERTIFICATE_VERIFY_FAILED`. Script gửi bằng `/usr/bin/curl` (kho CA hệ thống), token qua stdin.
- Script phải chạy được trên Python 3.9 (`/usr/bin/python3`) và 3.12. Test: `python3 -m unittest discover tests` và `/usr/bin/python3 -m unittest discover tests`.
- Transfer bị **Canceled** (vd đích thiếu chỗ) vẫn bắn File Copy Completed, nhưng **không có transfer log JSON**.
- Event Log ghi `Succeeded executing Python script` kèm Output, dùng để kiểm tra script có chạy.

## Ý tưởng tự động hoá (chưa làm)
- Disk Added (exfat, tên khớp mẫu thẻ) → `setSource` + 2 `setDestination` + `addTransfers`.
