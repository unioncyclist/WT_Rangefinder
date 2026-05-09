import argparse
import json
import math
import os
import socket
import subprocess
import threading
import sys
import time
import traceback
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

VENV_BOOTSTRAP_FLAG = "SHAPE_DISTANCE_VENV_BOOTSTRAPPED"
ROI_SIZE = 445


def relaunch_in_project_venv_if_needed() -> None:
    if os.environ.get(VENV_BOOTSTRAP_FLAG) == "1":
        return

    script_path = Path(__file__).resolve()
    venv_python = script_path.parent / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return

    try:
        current_python = Path(sys.executable).resolve()
        target_python = venv_python.resolve()
        if current_python == target_python:
            return
    except OSError:
        return

    env = os.environ.copy()
    env[VENV_BOOTSTRAP_FLAG] = "1"
    cmd = [str(target_python), str(script_path), *sys.argv[1:]]
    exit_code = subprocess.call(cmd, env=env)
    raise SystemExit(exit_code)


try:
    import cv2
    import numpy as np
except ModuleNotFoundError as import_exc:
    # If double-click used a non-venv Python, relaunch under project venv first.
    if (import_exc.name or "").split(".")[0] in {"cv2", "numpy"}:
        relaunch_in_project_venv_if_needed()
    raise

try:
    from pygrabber.dshow_graph import FilterGraph
except ImportError:
    FilterGraph = None


def find_free_port(host: str = "0.0.0.0") -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return int(s.getsockname()[1])


def get_local_lan_ip() -> str:
        try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.connect(("8.8.8.8", 80))
                        return str(s.getsockname()[0])
        except OSError:
                return "127.0.0.1"


def start_web_dashboard(
    host: str,
    port: int,
    state: Dict[str, Any],
    roi_stream: Dict[str, Optional[bytes]],
    lock: threading.Lock,
    trigger_state: Dict[str, Any],
) -> ThreadingHTTPServer:
        dashboard_path = Path(__file__).resolve().parent / "dashboard.html"
        if not dashboard_path.exists():
                raise FileNotFoundError(f"网页文件不存在: {dashboard_path}")
        dashboard_html = dashboard_path.read_text(encoding="utf-8")

        class Handler(BaseHTTPRequestHandler):
                def do_POST(self) -> None:
                        if self.path == "/api/trigger-apoint":
                                with lock:
                                        if not trigger_state.get("apoint_available", False):
                                                payload = json.dumps({"ok": False, "message": "apoint template unavailable"}, ensure_ascii=False).encode("utf-8")
                                                self.send_response(409)
                                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                                self.send_header("Content-Length", str(len(payload)))
                                                self.end_headers()
                                                self.wfile.write(payload)
                                                return
                                        trigger_state["apoint_trigger_until"] = time.time() + 1.0
                                        payload = json.dumps({"ok": True, "active_for": 1.0}, ensure_ascii=False).encode("utf-8")
                                self.send_response(200)
                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                self.send_header("Content-Length", str(len(payload)))
                                self.end_headers()
                                self.wfile.write(payload)
                                return

                        if self.path == "/api/set-apoint-template":
                                try:
                                        length = int(self.headers.get("Content-Length", "0"))
                                except ValueError:
                                        length = 0
                                raw = self.rfile.read(length) if length > 0 else b""
                                try:
                                        data = json.loads(raw.decode("utf-8") or "{}")
                                except json.JSONDecodeError:
                                        data = {}

                                template_key = data.get("template_key")
                                with lock:
                                        available_keys = state.get("apoint_available_template_keys", [])
                                        if not isinstance(available_keys, list):
                                                available_keys = []
                                        if template_key not in available_keys:
                                                payload = json.dumps({"ok": False, "message": "template unavailable"}, ensure_ascii=False).encode("utf-8")
                                                self.send_response(409)
                                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                                self.send_header("Content-Length", str(len(payload)))
                                                self.end_headers()
                                                self.wfile.write(payload)
                                                return
                                        trigger_state["apoint_template_key"] = template_key
                                        state["apoint_template_key"] = template_key
                                        payload = json.dumps({"ok": True, "template_key": template_key}, ensure_ascii=False).encode("utf-8")
                                self.send_response(200)
                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                self.send_header("Content-Length", str(len(payload)))
                                self.end_headers()
                                self.wfile.write(payload)
                                return

                        if self.path == "/api/set-apoint-input":
                                try:
                                        length = int(self.headers.get("Content-Length", "0"))
                                except ValueError:
                                        length = 0
                                raw = self.rfile.read(length) if length > 0 else b""
                                try:
                                        data = json.loads(raw.decode("utf-8") or "{}")
                                except json.JSONDecodeError:
                                        data = {}

                                value = data.get("value")
                                if not isinstance(value, int) or value <= 0:
                                        payload = json.dumps({"ok": False, "message": "value must be positive integer"}, ensure_ascii=False).encode("utf-8")
                                        self.send_response(400)
                                        self.send_header("Content-Type", "application/json; charset=utf-8")
                                        self.send_header("Content-Length", str(len(payload)))
                                        self.end_headers()
                                        self.wfile.write(payload)
                                        return

                                with lock:
                                        trigger_state["apoint_input_value"] = value
                                payload = json.dumps({"ok": True, "value": value}, ensure_ascii=False).encode("utf-8")
                                self.send_response(200)
                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                self.send_header("Content-Length", str(len(payload)))
                                self.end_headers()
                                self.wfile.write(payload)
                                return

                        self.send_response(404)
                        self.end_headers()

                def do_GET(self) -> None:
                        if self.path in ("/", "/index.html"):
                                body = dashboard_html.encode("utf-8")
                                self.send_response(200)
                                self.send_header("Content-Type", "text/html; charset=utf-8")
                                self.send_header("Content-Length", str(len(body)))
                                self.end_headers()
                                self.wfile.write(body)
                                return

                        if self.path == "/api/status":
                                with lock:
                                        payload = json.dumps(state, ensure_ascii=False).encode("utf-8")
                                self.send_response(200)
                                self.send_header("Content-Type", "application/json; charset=utf-8")
                                self.send_header("Cache-Control", "no-store")
                                self.send_header("Content-Length", str(len(payload)))
                                self.end_headers()
                                self.wfile.write(payload)
                                return

                        if self.path == "/api/status-stream":
                                self.send_response(200)
                                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                                self.send_header("Cache-Control", "no-cache")
                                self.send_header("Connection", "keep-alive")
                                self.send_header("Access-Control-Allow-Origin", "*")
                                self.end_headers()
                                try:
                                        last_update_ts = 0.0
                                        while True:
                                                with lock:
                                                        current_update_ts = state.get("updated_at", 0.0)
                                                        if current_update_ts > last_update_ts:
                                                                payload = json.dumps(state, ensure_ascii=False)
                                                                msg = f"data: {payload}\n\n"
                                                                self.wfile.write(msg.encode("utf-8"))
                                                                self.wfile.flush()
                                                                last_update_ts = current_update_ts
                                                time.sleep(0.01)
                                except (BrokenPipeError, ConnectionResetError, Exception):
                                        pass
                                return

                        if self.path.startswith("/api/roi.jpg"):
                                with lock:
                                        jpg = roi_stream.get("jpg")
                                if not jpg:
                                        self.send_response(204)
                                        self.end_headers()
                                        return
                                self.send_response(200)
                                self.send_header("Content-Type", "image/jpeg")
                                self.send_header("Cache-Control", "no-store")
                                self.send_header("Content-Length", str(len(jpg)))
                                self.end_headers()
                                self.wfile.write(jpg)
                                return

                        self.send_response(404)
                        self.end_headers()

                def log_message(self, format: str, *args: object) -> None:
                        return

        server = ThreadingHTTPServer((host, port), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server


@dataclass
class MatchResult:
    center: Tuple[int, int]
    score: float
    top_left: Tuple[int, int]
    size: Tuple[int, int]


def load_image(path: Path) -> np.ndarray:
    # Use imdecode+fromfile for better Unicode path support on Windows.
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        raise FileNotFoundError(f"无法读取图片: {path}")
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {path}")
    return img


def load_optional_image(path: Path) -> Optional[np.ndarray]:
    if not path.exists():
        return None
    return load_image(path)


def save_image(path: Path, img: np.ndarray) -> None:
    ext = path.suffix.lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise RuntimeError(f"图片编码失败: {path}")
    buf.tofile(str(path))


def split_template(template: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    if template.ndim == 3 and template.shape[2] == 4:
        bgr = template[:, :, :3]
        alpha = template[:, :, 3]
        mask = np.where(alpha > 0, 255, 0).astype(np.uint8)
        return bgr, mask
    if template.ndim == 3 and template.shape[2] == 3:
        return template, None
    raise ValueError("模板图像必须是 BGR 或 BGRA 格式")


def match_template_single(
    roi_bgr: np.ndarray,
    template_bgr: np.ndarray,
    template_mask: Optional[np.ndarray],
) -> MatchResult:
    roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)

    if tpl_gray.shape[0] > roi_gray.shape[0] or tpl_gray.shape[1] > roi_gray.shape[1]:
        return MatchResult(center=(0, 0), score=-1.0, top_left=(0, 0), size=(0, 0))

    if template_mask is not None:
        result = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCORR_NORMED, mask=template_mask)
    else:
        result = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)

    # Prevent numerical anomalies from masked matching (NaN/Inf) from corrupting ranking.
    result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)

    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    th, tw = tpl_gray.shape[:2]
    cx = max_loc[0] + tw // 2
    cy = max_loc[1] + th // 2

    return MatchResult(
        center=(cx, cy),
        score=float(max_val),
        top_left=max_loc,
        size=(tw, th),
    )


def build_yellow_mask(roi_bgr: np.ndarray) -> np.ndarray:
    # Warning yellow match with +/-10 tolerance: RGB(206,206,15) -> BGR(15,206,206) 184 188 37
    lower = np.array([27, 178, 178], dtype=np.uint8)
    upper = np.array([47, 198, 198], dtype=np.uint8)
    return cv2.inRange(roi_bgr, lower, upper)


def match_warning_with_yellow_prefilter(
    roi_bgr: np.ndarray,
    template_bgr: np.ndarray,
    template_mask: Optional[np.ndarray],
) -> MatchResult:
    yellow_mask = build_yellow_mask(roi_bgr)
    if cv2.countNonZero(yellow_mask) == 0:
        return MatchResult(center=(0, 0), score=-1.0, top_left=(0, 0), size=(0, 0))

    prefiltered = cv2.bitwise_and(roi_bgr, roi_bgr, mask=yellow_mask)
    result = match_template_single(prefiltered, template_bgr, template_mask)
    if result.score < 0:
        return result

    return result


def rotate_template_keep_all(
    template_bgr: np.ndarray,
    template_mask: Optional[np.ndarray],
    angle_deg: float,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    h, w = template_bgr.shape[:2]
    cx, cy = w / 2.0, h / 2.0

    mat = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
    cos_v = abs(mat[0, 0])
    sin_v = abs(mat[0, 1])

    new_w = max(1, int((h * sin_v) + (w * cos_v)))
    new_h = max(1, int((h * cos_v) + (w * sin_v)))

    mat[0, 2] += (new_w / 2.0) - cx
    mat[1, 2] += (new_h / 2.0) - cy

    rot_bgr = cv2.warpAffine(
        template_bgr,
        mat,
        (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    if template_mask is None:
        return rot_bgr, None

    rot_mask = cv2.warpAffine(
        template_mask,
        mat,
        (new_w, new_h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    rot_mask = np.where(rot_mask > 0, 255, 0).astype(np.uint8)
    return rot_bgr, rot_mask


def match_template_rotating(
    roi_bgr: np.ndarray,
    template_bgr: np.ndarray,
    template_mask: Optional[np.ndarray],
    angles: np.ndarray,
) -> MatchResult:
    best = MatchResult(center=(0, 0), score=-1.0, top_left=(0, 0), size=(0, 0))

    for angle in angles:
        rot_tpl, rot_mask = rotate_template_keep_all(template_bgr, template_mask, float(angle))
        cur = match_template_single(roi_bgr, rot_tpl, rot_mask)
        if cur.score > best.score:
            best = cur

    return best


def match_best_apoint_template(
    roi_bgr: np.ndarray,
    templates: list[tuple[str, np.ndarray, Optional[np.ndarray]]],
) -> tuple[str, MatchResult]:
    best_name = "apoint"
    best_result = MatchResult(center=(0, 0), score=-1.0, top_left=(0, 0), size=(0, 0))

    for template_name, template_bgr, template_mask in templates:
        cur = match_template_single(roi_bgr, template_bgr, template_mask)
        if cur.score > best_result.score:
            best_name = template_name
            best_result = cur

    return best_name, best_result


def apoint_template_key_from_name(template_name: str) -> str:
    if template_name == "apointRed.png":
        return "Red"
    return "A"


def get_nine_grid_roi(img: np.ndarray, row: int, col: int) -> Tuple[np.ndarray, Tuple[int, int]]:
    if row not in (0, 1, 2) or col not in (0, 1, 2):
        raise ValueError("九宫格位置 row/col 必须是 0,1,2")

    h, w = img.shape[:2]
    x_edges = [0, w // 3, (2 * w) // 3, w]
    y_edges = [0, h // 3, (2 * h) // 3, h]

    x1, x2 = x_edges[col], x_edges[col + 1]
    y1, y2 = y_edges[row], y_edges[row + 1]

    roi = img[y1:y2, x1:x2]
    return roi, (x1, y1)


def open_video_source(camera_index: Optional[int]) -> tuple[cv2.VideoCapture, str, Tuple[int, int]]:
    candidates: list[tuple[Any, int, str]] = []
    if camera_index is None:
        candidates.extend([
            ("video=OBS Virtual Camera", cv2.CAP_DSHOW, "OBS Virtual Camera (DirectShow)"),
            ("video=OBS Virtual Camera", cv2.CAP_FFMPEG, "OBS Virtual Camera (FFmpeg)"),
        ])
    else:
        candidates.extend([
            (int(camera_index), cv2.CAP_DSHOW, f"camera index {camera_index} (DirectShow)"),
            (int(camera_index), cv2.CAP_ANY, f"camera index {camera_index} (Auto)"),
        ])

    last_error = ""
    for source, backend, source_name in candidates:
        cap = cv2.VideoCapture(source, backend)
        if not cap.isOpened():
            cap.release()
            continue

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            last_error = f"打开成功但无法读取帧: {source_name}"
            continue

        height, width = frame.shape[:2]
        return cap, source_name, (width, height)

    if camera_index is None:
        if FilterGraph is not None:
            try:
                devices = FilterGraph().get_input_devices()
                obs_indices = [i for i, name in enumerate(devices) if "obs virtual camera" in name.lower()]
                for idx in obs_indices:
                    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        cap.release()
                        cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
                    if not cap.isOpened():
                        cap.release()
                        continue
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        height, width = frame.shape[:2]
                        return cap, f"OBS Virtual Camera (index {idx} via device list)", (width, height)
                    cap.release()
            except Exception as exc:
                last_error = f"{last_error}; 设备枚举失败: {exc}" if last_error else f"设备枚举失败: {exc}"

        raise RuntimeError(
            "无法打开 OBS Virtual Camera。"
            + (f" 最后错误: {last_error}" if last_error else "")
            + " 请确认 OBS 已启动 Virtual Camera。"
        )

    raise RuntimeError(
        f"无法打开 camera-index={camera_index}。"
        + (f" 最后错误: {last_error}" if last_error else "")
        + " 请确认该索引对应摄像头可用。"
    )


def get_bottom_right_roi(img: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
    h, w = img.shape[:2]
    roi_w = min(ROI_SIZE, w)
    roi_h = min(ROI_SIZE, h)

    x2, y2 = w, h
    x1 = max(0, x2 - roi_w)
    y1 = max(0, y2 - roi_h)

    roi = img[y1:y2, x1:x2]
    return roi, (x1, y1)


def draw_result(
    full_img: np.ndarray,
    roi_offset: Tuple[int, int],
    a: MatchResult,
    b: MatchResult,
    label_a: str,
    label_b: str,
    out_path: Optional[Path] = None,
) -> np.ndarray:
    x0, y0 = roi_offset

    a_center = (a.center[0] + x0, a.center[1] + y0)
    b_center = (b.center[0] + x0, b.center[1] + y0)

    vis = full_img.copy()

    cv2.rectangle(vis, (x0 + a.top_left[0], y0 + a.top_left[1]),
                  (x0 + a.top_left[0] + a.size[0], y0 + a.top_left[1] + a.size[1]), (0, 255, 255), 2)
    cv2.rectangle(vis, (x0 + b.top_left[0], y0 + b.top_left[1]),
                  (x0 + b.top_left[0] + b.size[0], y0 + b.top_left[1] + b.size[1]), (255, 255, 0), 2)

    cv2.circle(vis, a_center, 5, (0, 255, 255), -1)
    cv2.circle(vis, b_center, 5, (255, 255, 0), -1)
    cv2.line(vis, a_center, b_center, (0, 200, 255), 2)

    dist = math.hypot(a_center[0] - b_center[0], a_center[1] - b_center[1])
    text = f"{label_a} <-> {label_b}: {dist:.2f}px"
    cv2.putText(vis, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 220, 255), 2, cv2.LINE_AA)

    if out_path is not None:
        save_image(out_path, vis)
    return vis


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent
    default_tpl_a = base_dir / "templates" / "warning.png"
    default_tpl_b = base_dir / "templates" / "arrow.png"

    p = argparse.ArgumentParser(description="实时检测视频源右下区域内两目标中心距离")
    p.add_argument("--template-a", type=str, default=str(default_tpl_a), help="目标A模板图")
    p.add_argument("--template-b", type=str, default=str(default_tpl_b), help="目标B模板图")
    p.add_argument("--apoint-template", type=str, default=str(base_dir / "templates" / "apoint.png"), help="临时目标apoint模板图")
    p.add_argument("--label-a", type=str, default="A")
    p.add_argument("--label-b", type=str, default="B")
    p.add_argument("--arrow-angle-min", type=float, default=-180.0, help="箭头旋转最小角度")
    p.add_argument("--arrow-angle-max", type=float, default=180.0, help="箭头旋转最大角度")
    p.add_argument("--arrow-angle-step", type=float, default=10.0, help="箭头旋转步长")
    p.add_argument("--warning-min-score", type=float, default=0.114, help="warning最低匹配阈值")
    p.add_argument("--arrow-min-score", type=float, default=0.9, help="arrow最低匹配阈值")
    p.add_argument("--apoint-min-score", type=float, default=0.9, help="apoint最低匹配阈值")
    p.add_argument("--interval-ms", type=int, default=50, help="每帧检测间隔毫秒")
    p.add_argument("--report-ms", type=int, default=50, help="终端输出间隔毫秒")
    p.add_argument("--web-host", type=str, default="0.0.0.0", help="网页服务监听地址")
    p.add_argument("--web-port", type=int, default=9973, help="网页服务端口，默认9973；冲突时自动切换")
    p.add_argument("--camera-index", type=int, default=None, help="视频源索引（OBS Virtual Camera 打不开时可手动指定）")
    p.add_argument("--debug", action="store_true", help="打印调试信息")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    templates_dir = Path(__file__).resolve().parent / "templates"
    template_a_path = Path(args.template_a)
    template_b_path = Path(args.template_b)
    apoint_template_path = Path(args.apoint_template)
    apoint_template_paths = [apoint_template_path]
    if apoint_template_path.parent == templates_dir:
        for builtin_name in ("apoint.png", "apointRed.png"):
            builtin_path = templates_dir / builtin_name
            if builtin_path not in apoint_template_paths:
                apoint_template_paths.append(builtin_path)

    if not template_a_path.exists():
        raise FileNotFoundError(f"模板A不存在: {template_a_path}")
    if not template_b_path.exists():
        raise FileNotFoundError(f"模板B不存在: {template_b_path}")

    tpl_a_raw = load_image(template_a_path)
    tpl_b_raw = load_image(template_b_path)
    tpl_a_bgr, tpl_a_mask = split_template(tpl_a_raw)
    tpl_b_bgr, tpl_b_mask = split_template(tpl_b_raw)
    apoint_templates: list[tuple[str, np.ndarray, Optional[np.ndarray]]] = []
    for apoint_path in apoint_template_paths:
        if not apoint_path.exists():
            continue
        tpl_apoint_raw = load_image(apoint_path)
        tpl_apoint_bgr, tpl_apoint_mask = split_template(tpl_apoint_raw)
        apoint_templates.append((apoint_path.name, tpl_apoint_bgr, tpl_apoint_mask))
    apoint_templates_by_key: dict[str, tuple[str, np.ndarray, Optional[np.ndarray]]] = {}
    for apoint_name, apoint_bgr, apoint_mask in apoint_templates:
        apoint_templates_by_key[apoint_template_key_from_name(apoint_name)] = (apoint_name, apoint_bgr, apoint_mask)
    default_apoint_key = "Red" if "Red" in apoint_templates_by_key else "A"
    if default_apoint_key not in apoint_templates_by_key and apoint_templates_by_key:
        default_apoint_key = next(iter(apoint_templates_by_key))
    default_apoint_name = apoint_templates_by_key.get(default_apoint_key, (apoint_template_path.name, None, None))[0]

    if args.arrow_angle_step <= 0:
        raise ValueError("arrow-angle-step 必须大于 0")
    if args.arrow_angle_min > args.arrow_angle_max:
        raise ValueError("arrow-angle-min 不能大于 arrow-angle-max")
    if not (0.0 <= args.warning_min_score <= 1.0):
        raise ValueError("warning-min-score 必须在 0~1")
    if not (0.0 <= args.arrow_min_score <= 1.0):
        raise ValueError("arrow-min-score 必须在 0~1")
    if not (0.0 <= args.apoint_min_score <= 1.0):
        raise ValueError("apoint-min-score 必须在 0~1")
    if args.interval_ms < 0:
        raise ValueError("interval-ms 不能小于 0")
    if args.report_ms <= 0:
        raise ValueError("report-ms 必须大于 0")
    if not (0 <= args.web_port <= 65535):
        raise ValueError("web-port 必须在 0~65535")

    angles = np.arange(args.arrow_angle_min, args.arrow_angle_max + 1e-6, args.arrow_angle_step)
    sleep_sec = args.interval_ms / 1000.0
    report_sec = args.report_ms / 1000.0
    last_report_ts = 0.0

    state_lock = threading.Lock()
    roi_stream: Dict[str, Optional[bytes]] = {"jpg": None}
    trigger_state: Dict[str, Any] = {
        "apoint_trigger_until": 0.0,
        "apoint_available": bool(apoint_templates),
        "apoint_input_value": None,
        "last_apoint_distance_px": None,
        "apoint_template_key": default_apoint_key,
    }
    status: Dict[str, Any] = {
        "distance_px": None,
        "score_a": -1.0,
        "score_b": -1.0,
        "warning_valid": False,
        "arrow_valid": False,
        "apoint_valid": False,
        "template_a_name": template_a_path.name,
        "template_b_name": template_b_path.name,
        "apoint_name": default_apoint_name,
        "apoint_template_key": default_apoint_key,
        "apoint_available_template_keys": list(apoint_templates_by_key.keys()),
        "apoint_available": bool(apoint_templates),
        "apoint_active": False,
        "apoint_remaining": 0.0,
        "apoint_score": -1.0,
        "apoint_input_value": None,
        "last_apoint_distance_px": None,
        "a_xy": None,
        "b_xy": None,
        "roi_xyxy": None,
        "updated_at": time.time(),
    }

    cap, source_name, source_resolution = open_video_source(args.camera_index)
    print(f"视频源: {source_name}")
    print(f"摄像头分辨率: {source_resolution[0]}x{source_resolution[1]}")

    preferred_port = args.web_port if args.web_port != 0 else 9973
    web_port = preferred_port
    try:
        web_server = start_web_dashboard(args.web_host, web_port, status, roi_stream, state_lock, trigger_state)
    except OSError:
        web_port = find_free_port(args.web_host)
        web_server = start_web_dashboard(args.web_host, web_port, status, roi_stream, state_lock, trigger_state)
        print(f"端口 {preferred_port} 已占用，已切换到空闲端口 {web_port}")
    lan_ip = get_local_lan_ip()
    print(f"网页面板: http://127.0.0.1:{web_port}")
    print(f"局域网访问: http://{lan_ip}:{web_port}")

    print(f"实时检测已启动（视频输入源右下角 {ROI_SIZE}x{ROI_SIZE} ROI），按 Ctrl+C 退出")
    live_line_len = 0

    try:
        while True:
            ok, full_img = cap.read()
            if not ok or full_img is None:
                raise RuntimeError("视频源读取失败，请检查 OBS Virtual Camera 是否仍在运行")
            roi, offset = get_bottom_right_roi(full_img)

            # warning: yellow prefilter + translation match (no rotation / no scaling)
            a = match_warning_with_yellow_prefilter(
                roi,
                tpl_a_bgr,
                tpl_a_mask,
            )
            # arrow: translation + rotation (no scaling)
            b = match_template_rotating(roi, tpl_b_bgr, tpl_b_mask, angles)

            now = time.time()
            a_valid = a.score >= args.warning_min_score
            b_valid = b.score >= args.arrow_min_score
            apoint_active = bool(apoint_templates and now < trigger_state["apoint_trigger_until"])
            with state_lock:
                selected_apoint_key = trigger_state.get("apoint_template_key", default_apoint_key)
            selected_apoint = apoint_templates_by_key.get(selected_apoint_key)
            if selected_apoint is None and apoint_templates_by_key:
                selected_apoint_key, selected_apoint = next(iter(apoint_templates_by_key.items()))
            if apoint_active:
                if selected_apoint is not None:
                    c_name, c_tpl_bgr, c_tpl_mask = selected_apoint
                    c = match_template_single(roi, c_tpl_bgr, c_tpl_mask)
                else:
                    c_name = "apoint"
                    c = MatchResult(center=(0, 0), score=-1.0, top_left=(0, 0), size=(0, 0))
            else:
                c_name = selected_apoint[0] if selected_apoint is not None else "apoint"
                c = MatchResult(center=(0, 0), score=-1.0, top_left=(0, 0), size=(0, 0))
            c_valid = apoint_active and c.score >= args.apoint_min_score

            if b_valid and c_valid:
                bx_global = b.center[0] + offset[0]
                by_global = b.center[1] + offset[1]
                cx_global = c.center[0] + offset[0]
                cy_global = c.center[1] + offset[1]
                apoint_dist = math.hypot(bx_global - cx_global, by_global - cy_global)
                with state_lock:
                    trigger_state["last_apoint_distance_px"] = float(apoint_dist)

            warning_dist = None
            if a_valid and b_valid:
                ax_global = a.center[0] + offset[0]
                ay_global = a.center[1] + offset[1]
                bx_global = b.center[0] + offset[0]
                by_global = b.center[1] + offset[1]
                warning_dist = math.hypot(ax_global - bx_global, ay_global - by_global)

            with state_lock:
                apoint_input_value = trigger_state.get("apoint_input_value")
                last_apoint_distance_px = trigger_state.get("last_apoint_distance_px")

            display_dist = None
            if (
                warning_dist is not None
                and isinstance(apoint_input_value, int)
                and apoint_input_value > 0
                and isinstance(last_apoint_distance_px, (int, float))
                and float(last_apoint_distance_px) > 0.0
            ):
                display_dist = (float(apoint_input_value) / float(last_apoint_distance_px)) * float(warning_dist)

            roi_vis = roi.copy()
            warning_color = (255, 89, 155)
            arrow_color = (216, 79, 255)
            apoint_color = (57, 255, 105)
            if a_valid:
                x, y = a.top_left
                w, h = a.size
                cv2.rectangle(roi_vis, (x, y), (x + w, y + h), warning_color, 2)
            if b_valid:
                x, y = b.top_left
                w, h = b.size
                cv2.rectangle(roi_vis, (x, y), (x + w, y + h), arrow_color, 2)
            if c_valid:
                x, y = c.top_left
                w, h = c.size
                cv2.rectangle(roi_vis, (x, y), (x + w, y + h), apoint_color, 2)

            ok, buf = cv2.imencode('.jpg', roi_vis, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ok:
                with state_lock:
                    roi_stream["jpg"] = buf.tobytes()

            if now - last_report_ts >= report_sec:
                roi_x1, roi_y1 = offset
                roi_x2 = roi_x1 + roi.shape[1]
                roi_y2 = roi_y1 + roi.shape[0]
                roi_text = f"roi=({roi_x1},{roi_y1})-({roi_x2},{roi_y2})"
                if a_valid and b_valid:
                    ax, ay = a.center[0] + offset[0], a.center[1] + offset[1]
                    bx, by = b.center[0] + offset[0], b.center[1] + offset[1]
                    dist = math.hypot(ax - bx, ay - by)
                    with state_lock:
                        status["distance_px"] = float(display_dist) if display_dist is not None else None
                        status["score_a"] = float(a.score)
                        status["score_b"] = float(b.score)
                        status["warning_valid"] = bool(a_valid)
                        status["arrow_valid"] = bool(b_valid)
                        status["apoint_valid"] = bool(c_valid)
                        status["apoint_available"] = bool(apoint_templates)
                        status["apoint_template_key"] = trigger_state.get("apoint_template_key", default_apoint_key)
                        status["apoint_available_template_keys"] = list(apoint_templates_by_key.keys())
                        status["apoint_active"] = apoint_active
                        status["apoint_remaining"] = max(0.0, trigger_state["apoint_trigger_until"] - now) if apoint_templates else 0.0
                        status["apoint_score"] = float(c.score) if apoint_active else -1.0
                        status["apoint_name"] = c_name
                        status["apoint_input_value"] = apoint_input_value
                        status["last_apoint_distance_px"] = last_apoint_distance_px
                        status["a_xy"] = [int(ax), int(ay)]
                        status["b_xy"] = [int(bx), int(by)]
                        status["roi_xyxy"] = [int(roi_x1), int(roi_y1), int(roi_x2), int(roi_y2)]
                        status["updated_at"] = time.time()
                    if args.debug:
                        live_text = (
                            f"{roi_text} | "
                            f"distance={dist:.2f}px | "
                            f"warning={a.score:.3f}@({ax},{ay}) | "
                            f"arrow={b.score:.3f}@({bx},{by}) | "
                            f"apoint={c.score:.3f} active={int(apoint_active)} valid={int(c_valid)} name={c_name}"
                        )
                    else:
                        live_text = f"distance={dist:.2f}px"
                else:
                    with state_lock:
                        status["distance_px"] = None
                        status["score_a"] = float(a.score)
                        status["score_b"] = float(b.score)
                        status["warning_valid"] = bool(a_valid)
                        status["arrow_valid"] = bool(b_valid)
                        status["apoint_valid"] = bool(c_valid)
                        status["apoint_available"] = bool(apoint_templates)
                        status["apoint_template_key"] = trigger_state.get("apoint_template_key", default_apoint_key)
                        status["apoint_available_template_keys"] = list(apoint_templates_by_key.keys())
                        status["apoint_active"] = apoint_active
                        status["apoint_remaining"] = max(0.0, trigger_state["apoint_trigger_until"] - now) if apoint_templates else 0.0
                        status["apoint_score"] = float(c.score) if apoint_active else -1.0
                        status["apoint_name"] = c_name
                        status["apoint_input_value"] = apoint_input_value
                        status["last_apoint_distance_px"] = last_apoint_distance_px
                        status["a_xy"] = None
                        status["b_xy"] = None
                        status["roi_xyxy"] = [int(roi_x1), int(roi_y1), int(roi_x2), int(roi_y2)]
                        status["updated_at"] = time.time()
                    if args.debug:
                        live_text = (
                            f"{roi_text} | "
                            f"distance=nan | "
                            f"warning={a.score:.3f} valid={int(a_valid)} | "
                            f"arrow={b.score:.3f} valid={int(b_valid)} | "
                            f"apoint={c.score:.3f} active={int(apoint_active)} valid={int(c_valid)} name={c_name}"
                        )
                    else:
                        live_text = "distance=nan"

                padding = " " * max(0, live_line_len - len(live_text))
                print(f"\r{live_text}{padding}", end="", flush=True)
                live_line_len = len(live_text)

                last_report_ts = now

            if sleep_sec > 0:
                time.sleep(sleep_sec)
    except KeyboardInterrupt:
        if live_line_len > 0:
            print()
        print("检测已停止")
    finally:
        cap.release()
        web_server.shutdown()
        web_server.server_close()


if __name__ == "__main__":
    try:
        relaunch_in_project_venv_if_needed()
        main()
    except Exception:
        print("\n程序启动失败，详细错误如下：")
        traceback.print_exc()
        try:
            input("\n按回车键退出...")
        except EOFError:
            pass
