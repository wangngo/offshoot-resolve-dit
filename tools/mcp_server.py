"""MCP server `offshoot` — vỏ mỏng bọc các tool đã có test trong scripts/.

Chạy: uv run --directory /path/to/offshoot-resolve-dit --with "mcp<2" --with xxhash python -m tools.mcp_server
Nguyên tắc: tool đọc thì chạy thẳng; tool bắt đầu offload phải gọi với confirm=true
(mặc định chỉ trả về kế hoạch + preflight để người dùng duyệt).
"""
import shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import handoff, ingest, log_scan, mhl_verify, mkpreset  # noqa: E402

mcp = FastMCP("offshoot")
RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

PREF_KEYS = {
    "verify_mode": "TransfersSettingsVerifyKey",
    "mhl_type (0=legacy,1=ASC)": "SFIDefaultsHedgeProMHLType",
    "current_preset": "SFIDefaultsCurrentOrganizePreset",
    "iconik_enabled": "SFIIntegrationsIconikDefaultsEnableKey",
    "move_on_same_volume": "SFIDefaultsTransferShouldMoveEnabled",
    "script_file_copy_completed": "SFIDefaultsFileCopyCompletedScript",
    "script_verification_issue": "SFIDefaultsSourceVerifyIssueScript",
}


@mcp.tool(annotations=RO)
def status() -> dict:
    """Trạng thái OffShoot: app có chạy không, verify mode, loại MHL, preset đang chọn, iconik,
    move-on-same-volume, script event đang gắn, danh sách preset."""
    running = subprocess.run(["pgrep", "-x", "OffShoot"], capture_output=True).returncode == 0
    prefs = {k: ingest.read_pref(v) or None for k, v in PREF_KEYS.items()}
    presets = sorted(p.stem for p in ingest.PRESETS.glob("*.hedge"))
    return {"app_running": running, "prefs": prefs, "presets": presets}


@mcp.tool(annotations=RO)
def list_volumes() -> list[dict]:
    """Các ổ đang mount trong /Volumes (tên, dung lượng, còn trống) để chọn thẻ nguồn/đích."""
    out = []
    for v in sorted(Path("/Volumes").iterdir()):
        try:
            u = shutil.disk_usage(v)
        except OSError:
            continue
        out.append({"path": str(v), "total_gb": round(u.total / 1e9, 2), "free_gb": round(u.free / 1e9, 2)})
    return out


@mcp.tool(annotations=RO)
def scan_logs(since: str | None = None, show_problems: bool = False, limit: int = 50) -> dict:
    """Tóm tắt transfer log của OffShoot (cả schema 25.x và 26.x). since=YYYY-MM-DD.
    show_problems=true để liệt kê file lỗi (tối đa `limit`)."""
    rows = log_scan.load(log_scan.DEFAULT_DIR, since)
    probs = log_scan.problems(rows)
    res = {"summary": log_scan.summarize(rows), "problem_count": len(probs)}
    if show_problems:
        res["problems"] = probs[:limit]
    return res


@mcp.tool(annotations=RO)
def ingest_preflight(source: str, roll: str, preset: str, dests: list[str]) -> dict:
    """Kiểm tra trước offload (CHỈ ĐỌC): thẻ/đích tồn tại, roll đúng chuẩn A001/S001, preset có,
    đích trùng, roll đã tồn tại trên đích, đủ chỗ, đích chung volume, verify mode."""
    return ingest.preflight(source, roll, preset, dests)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                      idempotentHint=False, openWorldHint=False))
def ingest_start(source: str, roll: str, preset: str, dests: list[str], confirm: bool = False) -> dict:
    """Bắt đầu offload 1 thẻ ra nhiều đích trong OffShoot. Mặc định confirm=false: chỉ trả kế hoạch +
    preflight để người dùng duyệt. Gọi lại với confirm=true SAU KHI người dùng đồng ý. Không chạy nếu preflight có lỗi.
    Trả started_at + previous_preset để dùng với ingest_status."""
    pf = ingest.preflight(source, roll, preset, dests)
    plan = {"source": source, "roll": roll, "preset": preset, "dests": dests, "preflight": pf}
    if pf["errors"]:
        return {"started": False, "reason": "preflight có lỗi", **plan}
    if not confirm:
        return {"started": False, "reason": "chưa confirm — trình người dùng duyệt rồi gọi lại với confirm=true", **plan}
    t0, prev, confirmed = ingest.start(source, roll, preset, dests)
    if not confirmed:
        return {"started": False, "reason": "OffShoot không ghi 'Transfers Added' sau 30s — app chưa nhận ổ "
                "nguồn (tháo/gắn lại thẻ) hoặc đang khởi động. Preset đã trả về. Kiểm GUI/đích trước khi thử lại "
                "(app có thể add trễ → roll trùng).",
                "previous_preset": prev, **plan}
    return {"started": True, "started_at": t0.isoformat(), "previous_preset": prev, **plan}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                      idempotentHint=True, openWorldHint=False))
def ingest_status(roll: str, dests: list[str], started_at: str, restore_preset: str | None = None,
                  give_up_after_s: int = 6 * 3600) -> dict:
    """Kết quả offload đã bắt đầu bằng ingest_start: từng đích Success/lỗi. done=true khi mọi đích có log.
    all_ok=true chỉ khi mọi đích Success và 0 file lỗi; ngược lại KHÔNG format thẻ.
    Khi done (hoặc timed_out: quá give_up_after_s mà còn đích thiếu log — bị hủy/đầy giữa chừng),
    nếu truyền restore_preset (= previous_preset) thì trả preset của GUI về như cũ."""
    t0 = ingest.aware(datetime.fromisoformat(started_at))
    res = ingest.results(roll, dests, t0)
    done = len(res) == len(dests)
    timed_out = not done and (datetime.now().astimezone() - t0).total_seconds() > give_up_after_s
    restored = False
    if (done or timed_out) and restore_preset and ingest.read_pref("SFIDefaultsCurrentOrganizePreset") != restore_preset:
        ingest.set_pref("SFIDefaultsCurrentOrganizePreset", restore_preset)
        restored = True
    return {"done": done, "timed_out": timed_out, "all_ok": done and all(r["ok"] for r in res.values()),
            "results": res, "missing": [d for d in dests if d not in res], "preset_restored": restored}


@mcp.tool(annotations=RO)
def verify_mhl(path: str) -> dict:
    """Verify CHỈ ĐỌC một roll/thư mục đích theo MHL (ASC hoặc kiểu cũ): hash lại từng file bằng xxh64,
    báo file thiếu / sai size / sai hash / thừa (unlisted). Không ghi gì vào ổ. Thư mục lớn thì chạy lâu.
    Chỉ `passed`=true mới là pass (không có MHL ⇒ passed=false). path phải là thư mục ROLL (chứa ascmhl/)."""
    return mhl_verify.verify(path)


@mcp.tool(annotations=RO)
def handoff_check(roll_dirs: list[str]) -> dict:
    """CỔNG trước khi import vào DaVinci Resolve (CHỈ ĐỌC). roll_dirs = cùng 1 roll trên ≥2 đích
    (vd .../Camera_Media/A001 trên RAID và SHUTTLE). ok=true chỉ khi: verify mode SourceAndDestination,
    mọi đích có ASC MHL và verify_mhl passed (không thiếu/sai/thừa file), ≥2 ổ vật lý khác nhau,
    MHL các đích giống hệt nhau. Trả `media` = danh sách file media (từ đích đầu) để ImportMedia —
    KHÔNG truyền thư mục (Resolve ImportMedia([thư mục]) trả [] im lặng)."""
    return handoff.check(roll_dirs, mode=ingest.read_pref("TransfersSettingsVerifyKey"))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                      idempotentHint=False, openWorldHint=False))
def make_presets(project: str) -> dict:
    """Tạo cặp preset <PROJECT>_OCF / <PROJECT>_SOUND theo chuẩn Netflix
    (PROJECT/YYYYMMDD/Camera_Media|Sound_Media/<roll>) rồi reload trong OffShoot. Không ghi đè preset có sẵn."""
    try:
        paths = mkpreset.write(project)
    except FileExistsError as e:
        return {"created": [], "error": f"đã có: {e}"}
    ingest.api("reload")
    return {"created": [p.name for p in paths]}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                      idempotentHint=False, openWorldHint=False))
def make_report(day_or_files: list[str], out_dir: str, title: str = "Offload Report", note: str = "") -> dict:
    """Report HTML + PDF từ transfer log (ngày YYYY-MM-DD và/hoặc đường dẫn file .json) vào out_dir."""
    r = subprocess.run([str(REPO / "scripts/report"), *day_or_files, "-o", out_dir, "-t", title, "-n", note],
                       capture_output=True, text=True, timeout=300)
    files = [l for l in r.stdout.splitlines() if l.endswith((".html", ".pdf")) and not l.startswith("Report generated")]
    return {"ok": r.returncode == 0, "files": files, "stderr": r.stderr[-500:]}


if __name__ == "__main__":
    mcp.run()
