# 06 — Chuẩn đặt tên & cấu trúc thư mục (theo Netflix, Hedge khuyến nghị)

Nguồn: Netflix Partner Help "Production Assets: Folder & File Naming" (tóm tắt qua Hedge blog và Pomfort),
docs.hedge.video (Organization, Labels, Elements). Tra ngày 2026-10-12.

## Cấu trúc tối thiểu
```
<SHOW_TITLE>/<YYYYMMDD>/Camera_Media/<ROLL>/   ← nguyên cây thư mục của thẻ (PRIVATE/M4ROOT/CLIP…)
<SHOW_TITLE>/<YYYYMMDD>/Sound_Media/<ROLL>/
```
- **Show title**: chỉ dùng `A-Z a-z 0-9 . _ -`, không dấu cách, không dấu tiếng Việt (`Chef's Table` → `CHEFS_TABLE`).
- **Ngày quay** `YYYYMMDD`, mỗi ngày quay một thư mục. Thư mục Season/Episode/Unit/Shoot Day là tuỳ chọn.
- **Roll**: camera = chữ cái máy + số thẻ, 3 chữ số (`A001`, `B002`); âm thanh = `S001`… Không tái dùng số roll trong cùng dự án.
- **Thư mục roll phải giống hệt thẻ**: **không** Flatten Folders, **không** đổi tên clip (đổi tên làm hỏng relink và metadata), **không** lọc sidecar (XML, BIM, SMI…).
- Mỗi bản copy là một bản lưu trữ độc lập, có MHL. Áp dụng 3-2-1.

## Cách làm trong OffShoot
`scripts/mkpreset.py "Tên dự án"` sinh 2 preset vào `~/Library/Preferences/Hedge/Presets/`, sau đó chạy `scripts/os reload`:

| Preset | folderPattern |
|---|---|
| `<PROJECT>_OCF` | `PROJECT/{YYYY}{MM}{DD}/Camera_Media/{Source Name}` |
| `<PROJECT>_SOUND` | `PROJECT/{YYYY}{MM}{DD}/Sound_Media/{Source Name}` |

Cả hai: không lọc, không flatten, không rename.
- **Roll = label của source.** Máy quay chuyên nghiệp thường đặt sẵn tên volume là roll (`A001`). Thẻ `Untitled` hoặc `NO NAME`
  thì phải **đặt label** (click tên đĩa → gõ `A001` → Enter) hoặc `scripts/os src /Volumes/X A001`.
- **Ngày** `{YYYY}{MM}{DD}` là ngày "hôm nay" theo OffShoot. Nếu offload qua nửa đêm, chỉnh ở **Settings > General > Date**
  (chọn ngày quay, giờ bắt đầu ngày mới). `{Content YYYY}…` lấy ngày file cũ nhất trên thẻ, sai nếu đồng hồ máy quay lệch.
- Chọn preset: dropdown Preset trong GUI, hoặc qua API `setPreferences {"SFIDefaultsCurrentOrganizePreset":"<tên>"}`.

## Lab 2026-10-12 (dự án giả `TEST_FILM`)
- `A001` → `DST2/TEST_FILM/20261012/Camera_Media/A001/PRIVATE/M4ROOT/CLIP/…`, Success, 24 file (**có cả XML**).
- `S001` (thư mục giả có WAV) → `…/Sound_Media/S001/…`, Success.
- **Quy tắc lọc của preset thay cho quy tắc lọc chung** (`.xml`) khi preset đang bật, nên XML không còn bị bỏ.
- **GOTCHA: file `<clip>.json` thừa trong roll là do tích hợp iconik.**
  `SFIIntegrationsIconikDefaultsEnableKey=1` với danh sách đuôi rỗng → mỗi file có thêm một `.json`.
  Tắt iconik thì không còn sidecar nào (đã kiểm chứng). Với dự án Netflix, roll phải giống hệt thẻ, nên **tắt iconik**
  (Settings > Integrations) nếu không dùng iconik.
