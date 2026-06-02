"""
RPi5 카메라 MJPEG 스트리머 + 검출 모드 전환
  - none      : 검출 없이 원본 스트리밍
  - blue      : 파란색 물체 HSV 검출
  - cat_custom: 커스텀 고양이 검출 (best.onnx)
  - cat_track : 고양이 자율 추적 RC카 제어 (best.onnx)

모드 전환: HTTP GET /mode/<name>  (예: /mode/cat_track, /mode/none)
스트리밍:  http://<RPi_IP>:8000/stream.mjpg
"""
import io
import os
import socket
import time
from threading import Condition, Thread, Lock
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import cv2
import numpy as np
from picamera2 import Picamera2

# --- 설정 ---
FRAME_W = 640
FRAME_H = 480
MODEL_DIR = "/home/toby/rccar/models"

# 커스텀 고양이 ONNX (best.onnx)
CAT_ONNX_PATH = f"{MODEL_DIR}/best.onnx"
CAT_ONNX_CONF = 0.2
YOLO_IMGSZ = 320

# 파랑색 HSV 범위
BLUE_LOW  = np.array([100, 80, 50])
BLUE_HIGH = np.array([130, 255, 255])
MIN_AREA  = 500

# --- Detection Mode ---
# "none", "blue", "cat_custom", "cat_track"
detect_mode = "none"
detect_lock = Lock()

# =====================================================================
# 7장 고양이 추적 모듈
# =====================================================================

# PD 제어 파라미터
_TRACK_KP         = 1.0    # 비례 게인
_TRACK_KD         = 0.2    # 미분 게인
_TRACK_DEAD_ZONE  = 0.15   # 이 범위 안이면 직진 (offset 절대값)
_TRACK_STOP_CM    = 25     # 초음파 장애물 정지 거리 (cm)

# 거리 추정 캘리브레이션 (실제 고양이로 측정 후 수정)
_REF_HEIGHT_PX = 120   # 1m 거리에서 박스 높이(px) — 캘리브레이션 필요
_REF_DIST_M    = 1.0
_STOP_DIST_M   = 0.45  # 이 거리 이내 → STOPPED


def _estimate_distance(box_h_px):
    """단일 카메라 거리 추정 (m). 신뢰 불가면 None."""
    if box_h_px < 20:
        return None
    return _REF_DIST_M * _REF_HEIGHT_PX / box_h_px


class _TrackingFSM:
    """고양이 추적 상태 머신 (7.4절)"""

    IDLE     = "IDLE"
    SEARCH   = "SEARCH"
    TRACKING = "TRACKING"
    LOST     = "LOST"
    STOPPED  = "STOPPED"

    def __init__(self):
        self.state = self.IDLE
        self._last_seen    = 0.0
        self._search_start = 0.0

    def start(self):
        self.state = self.SEARCH
        self._search_start = time.time()

    def stop(self):
        self.state = self.IDLE

    def update(self, cat_detected, distance_m, obstacle_near):
        """상태 전이 후 기본 명령 반환. None = PD 제어가 결정."""
        now = time.time()

        if obstacle_near:
            self.state = self.STOPPED
            return "S"

        if self.state == self.IDLE:
            return "S"

        if self.state == self.SEARCH:
            if cat_detected:
                self.state = self.TRACKING
                self._last_seen = now
                return None
            if now - self._search_start > 30:
                self.state = self.IDLE
                return "S"
            return "R"   # 오른쪽 회전하며 탐색

        if self.state == self.TRACKING:
            if not cat_detected:
                self.state = self.LOST
                return "F"
            if distance_m and distance_m < _STOP_DIST_M:
                self.state = self.STOPPED
                return "S"
            self._last_seen = now
            return None  # PD 제어

        if self.state == self.LOST:
            if cat_detected:
                self.state = self.TRACKING
                self._last_seen = now
                return None
            if now - self._last_seen > 2.0:
                self.state = self.SEARCH
                self._search_start = now
                return "R"
            return "F"   # 2초간 직진 대기

        if self.state == self.STOPPED:
            if not obstacle_near:
                if cat_detected and (not distance_m or distance_m >= _STOP_DIST_M):
                    self.state = self.TRACKING
                    return None
                if not cat_detected:
                    self.state = self.LOST
                    return "F"
            return "S"

        return "S"


class CatTracker:
    """카메라 검출 결과를 받아 uart_server(9000)로 RC카 명령을 보내는 추적기."""

    def __init__(self, uart_port=9000, sensor_port=9001):
        self._uart_port   = uart_port
        self._sensor_port = sensor_port
        self._fsm         = _TrackingFSM()
        self._sock        = None
        self._prev_offset = 0.0
        self._obstacle_near = False
        self._running     = False
        self._lock        = Lock()

    # ── 시작 / 정지 ──────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._connect_uart()
        Thread(target=self._sensor_loop, daemon=True).start()
        self._fsm.start()
        print("[TRACKER] 시작 → SEARCH")

    def stop(self):
        self._running = False
        self._fsm.stop()
        self._send("S")
        self._close_uart()
        print("[TRACKER] 정지")

    # ── UART 연결 ─────────────────────────────────────────────────

    def _connect_uart(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("localhost", self._uart_port))
            self._sock = s
            print(f"[TRACKER] uart_server:{self._uart_port} 연결")
        except OSError as e:
            print(f"[TRACKER] uart_server 연결 실패: {e}")
            self._sock = None

    def _close_uart(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _send(self, cmd):
        if not self._sock:
            return
        try:
            self._sock.sendall(cmd.encode("ascii"))
        except OSError:
            self._sock = None

    # ── 센서 수신 (9001 → obstacle_near) ─────────────────────────

    def _sensor_loop(self):
        while self._running:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("localhost", self._sensor_port))
                buf = ""
                while self._running:
                    chunk = s.recv(128).decode("ascii", errors="ignore")
                    if not chunk:
                        break
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if "U:" in line:
                            try:
                                u_val = int([p for p in line.split(",")
                                             if p.startswith("U:")][0][2:])
                                with self._lock:
                                    self._obstacle_near = u_val < _TRACK_STOP_CM
                            except (ValueError, IndexError):
                                pass
                s.close()
            except OSError:
                pass
            if self._running:
                time.sleep(1)

    # ── 프레임 처리 (capture_loop에서 호출) ──────────────────────

    def process(self, frame, best_box, best_conf):
        h, w = frame.shape[:2]
        cat_detected = best_box is not None
        distance_m   = None
        offset       = 0.0

        if cat_detected:
            x1, y1, x2, y2 = best_box
            cx       = (x1 + x2) / 2
            offset   = (cx - w / 2) / (w / 2)  # -1.0 ~ +1.0
            distance_m = _estimate_distance(y2 - y1)

        with self._lock:
            obstacle_near = self._obstacle_near

        fsm_cmd = self._fsm.update(cat_detected, distance_m, obstacle_near)

        if fsm_cmd is not None:
            self._send(fsm_cmd)
            self._prev_offset = 0.0
        elif cat_detected:
            # PD 제어 → L / F / R
            pd = _TRACK_KP * offset + _TRACK_KD * (offset - self._prev_offset)
            self._prev_offset = offset
            if abs(offset) < _TRACK_DEAD_ZONE:
                self._send("F")
            elif pd < 0:
                self._send("L")
            else:
                self._send("R")

        self._draw_overlay(frame, best_box, best_conf, distance_m,
                           obstacle_near, offset)
        return frame

    def _draw_overlay(self, frame, best_box, best_conf,
                      distance_m, obstacle_near, offset):
        h, w = frame.shape[:2]
        state = self._fsm.state

        if best_box:
            x1, y1, x2, y2 = best_box
            color = (0, 255, 0) if state == "TRACKING" else (0, 165, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            cv2.circle(frame, (cx, cy), 6, color, -1)
            # 조향 방향 화살표
            arr_x = int(w // 2 + offset * w // 2 * 0.8)
            cv2.arrowedLine(frame, (w // 2, h - 30),
                            (arr_x, h - 30), (0, 255, 255), 3)
            label = f"CAT {best_conf:.2f}"
            if distance_m:
                label += f"  {distance_m:.2f}m"
            cv2.putText(frame, label, (x1, max(y1 - 10, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        else:
            cv2.putText(frame, "Searching...", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        state_color = {
            "TRACKING": (0, 255, 0), "SEARCH":  (0, 165, 255),
            "LOST":     (0, 255, 255), "STOPPED": (0, 0, 255),
            "IDLE":     (128, 128, 128),
        }.get(state, (255, 255, 255))
        cv2.putText(frame, f"[TRACK:{state}]", (w - 230, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, state_color, 2)

        if obstacle_near:
            cv2.putText(frame, "!! OBSTACLE !!", (w // 2 - 90, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

        cv2.line(frame, (w // 2, 0), (w // 2, h), (255, 255, 255), 1)

    @property
    def fsm_state(self):
        return self._fsm.state


# 전역 tracker 인스턴스
cat_tracker = CatTracker()

# =====================================================================

# --- 최신 검출 결과 (PC 폴링용) ---
last_detection = {"box": None, "conf": 0.0, "timestamp": 0.0}

# --- 모델 인스턴스 ---
cat_onnx_session = None
cat_onnx_input   = None


def load_models():
    global cat_onnx_session, cat_onnx_input

    if os.path.exists(CAT_ONNX_PATH):
        try:
            import onnxruntime as ort
            cat_onnx_session = ort.InferenceSession(
                CAT_ONNX_PATH, providers=["CPUExecutionProvider"])
            cat_onnx_input = cat_onnx_session.get_inputs()[0].name
            print(f"[MODEL] Custom Cat ONNX loaded: {CAT_ONNX_PATH}")
        except Exception as e:
            print(f"[MODEL] Custom Cat ONNX failed: {e}")
    else:
        print(f"[MODEL] 파일 없음: {CAT_ONNX_PATH}")


def _run_cat_custom_inference(frame):
    """커스텀 고양이 ONNX 추론만 수행. (best_box, best_conf) 반환."""
    if cat_onnx_session is None:
        return None, 0.0

    h, w = frame.shape[:2]
    img = cv2.resize(frame, (YOLO_IMGSZ, YOLO_IMGSZ))
    img = img[:, :, ::-1].astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, 0)

    outputs = cat_onnx_session.run(None, {cat_onnx_input: img})
    preds = outputs[0][0]
    if preds.shape[0] == 5:
        preds = preds.T

    sx = w / YOLO_IMGSZ
    sy = h / YOLO_IMGSZ
    best_conf = 0.0
    best_box  = None

    for det in preds:
        cx, cy, bw, bh = det[0], det[1], det[2], det[3]
        conf = float(det[4]) if preds.shape[1] == 5 else float(det[4:].max())
        if conf < CAT_ONNX_CONF:
            continue
        if conf > best_conf:
            best_conf = conf
            best_box  = (int((cx - bw/2)*sx), int((cy - bh/2)*sy),
                         int((cx + bw/2)*sx), int((cy + bh/2)*sy))

    # 전역 검출 결과 갱신 (PC 폴링용)
    with detect_lock:
        last_detection["box"]       = list(best_box) if best_box else None
        last_detection["conf"]      = best_conf
        last_detection["timestamp"] = time.time()

    return best_box, best_conf


def detect_cat_custom(frame):
    """커스텀 고양이 ONNX INT8 검출 (87장 학습 모델)"""
    if cat_onnx_session is None:
        cv2.putText(frame, "Cat model not loaded", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    h, w = frame.shape[:2]
    best_box, best_conf = _run_cat_custom_inference(frame)

    if best_box:
        x1, y1, x2, y2 = best_box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, ((x1+x2)//2, (y1+y2)//2), 6, (0, 255, 0), -1)
        cv2.putText(frame, f"CAT {best_conf:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "No cat", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.line(frame, (w//2, 0), (w//2, h), (255, 255, 255), 1)
    cv2.putText(frame, "[CAT CUSTOM]", (w - 190, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
    return frame


def detect_cat_track(frame):
    """고양이 추적 모드 — 검출 후 CatTracker로 RC카 제어."""
    if cat_onnx_session is None:
        cv2.putText(frame, "Cat model not loaded", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    best_box, best_conf = _run_cat_custom_inference(frame)
    return cat_tracker.process(frame, best_box, best_conf)


def detect_blue(frame):
    """파랑 물체 검출 + 오버레이 그리기."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BLUE_LOW, BLUE_HIGH)
    mask = cv2.erode(mask, None, iterations=1)
    mask = cv2.dilate(mask, None, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area > MIN_AREA:
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                x, y, w, h = cv2.boundingRect(largest)

                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 6, (0, 255, 0), -1)
                cv2.putText(frame, f"BLUE area={int(area)}", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "No blue", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    else:
        cv2.putText(frame, "No blue", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.line(frame, (FRAME_W // 2, 0), (FRAME_W // 2, FRAME_H), (255, 255, 255), 1)

    cv2.putText(frame, "[BLUE]", (FRAME_W - 90, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 2)
    return frame


# --- Frame Buffer ---
class FrameBuffer:
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def set(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


def capture_loop(picam, buffer):
    while True:
        frame = picam.capture_array()

        with detect_lock:
            mode = detect_mode

        if mode == "cat_track":
            frame = detect_cat_track(frame)
        elif mode == "cat_custom":
            frame = detect_cat_custom(frame)
        elif mode == "blue":
            frame = detect_blue(frame)
        # "none" → 원본 그대로

        ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            buffer.set(jpg.tobytes())


PAGE = """\
<!DOCTYPE html>
<html>
<head><title>RPi5 Camera</title></head>
<body style="background:#111;color:#eee;font-family:sans-serif;text-align:center;">
<h2>RPi5 Camera Stream</h2>
<img src="stream.mjpg" width="640" height="480" /><br><br>
<a href="/mode/none" style="color:#888;margin:10px;font-size:15px;">None</a>
<a href="/mode/blue" style="color:#44f;margin:10px;font-size:15px;">Blue</a>
<a href="/mode/cat_custom" style="color:#f0f;margin:10px;font-size:15px;">Cat Custom</a>
<br><br>
<a href="/mode/cat_track" style="color:#fff;background:#e55;padding:8px 20px;border-radius:6px;font-weight:bold;text-decoration:none;font-size:16px;">Cat Track (RC카 추적)</a>
&nbsp;&nbsp;
<a href="/mode/none" style="color:#fff;background:#555;padding:8px 20px;border-radius:6px;font-weight:bold;text-decoration:none;font-size:16px;">정지</a>
</body>
</html>
"""


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global detect_mode

        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path.startswith('/mode/'):
            new_mode = self.path.split('/mode/')[-1].strip('/')
            valid = ("none", "blue", "cat_custom", "cat_track")
            if new_mode in valid:
                with detect_lock:
                    prev = detect_mode
                    detect_mode = new_mode
                # tracker 시작/정지
                if new_mode == "cat_track" and prev != "cat_track":
                    cat_tracker.start()
                elif prev == "cat_track" and new_mode != "cat_track":
                    cat_tracker.stop()
                msg = f"Mode changed to: {new_mode}"
                print(f"[MODE] {new_mode}")
            else:
                msg = f"Unknown mode: {new_mode}"
            content = msg.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/detect':
            import json
            with detect_lock:
                data = {
                    "box": last_detection["box"],
                    "conf": last_detection["conf"],
                    "frame_w": FRAME_W,
                    "frame_h": FRAME_H,
                    "timestamp": last_detection["timestamp"],
                }
            content = json.dumps(data).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with buffer.condition:
                        buffer.condition.wait()
                        frame = buffer.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                print(f'[WARN] client disconnected: {e}')
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


# --- 시작 ---
load_models()

picam = Picamera2()
picam.configure(picam.create_video_configuration(
    main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}
))
picam.start()
time.sleep(1)

buffer = FrameBuffer()
worker = Thread(target=capture_loop, args=(picam, buffer), daemon=True)
worker.start()

try:
    addr = ('0.0.0.0', 8000)
    server = StreamingServer(addr, StreamingHandler)
    print("=" * 40)
    print("  RPi5 Camera + Detection")
    print("=" * 40)
    print(f"  Stream : http://0.0.0.0:8000/stream.mjpg")
    print(f"  Mode   : none | blue | ssd | yolo_onnx | yolo_tflite")
    print(f"  Current: {detect_mode}")
    print("=" * 40)
    server.serve_forever()
finally:
    picam.stop()
