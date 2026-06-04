"""
RPi5 카메라 MJPEG 스트리머 + 검출 + 자율 고양이 추적
  - none       : 검출 없이 원본 스트리밍
  - blue       : 파란색 물체 HSV 검출
  - cat_custom : 커스텀 고양이 ONNX 검출 (best.onnx)

Drive 모드:
  - MANUAL    : PC 키보드 조종 (기본 동작 없음)
  - CAT_TRACK : 자율 고양이 추적 (검출 결과로 직접 조향)

모드 전환: HTTP GET /drive/<mode>  (예: /drive/cat_track, /drive/manual)
검출 전환: HTTP GET /mode/<name>   (예: /mode/cat_custom, /mode/blue, /mode/none)
검출 결과: HTTP GET /detect        (JSON: box, conf, frame_w, frame_h)
상태 조회: HTTP GET /status        (JSON: drive_mode, detect_mode, track_action)
스트리밍:  http://<RPi_IP>:8000/stream.mjpg
"""
import io
import json
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
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

# 커스텀 고양이 ONNX (best.onnx)
CAT_ONNX_PATH = os.path.join(MODEL_DIR, "best.onnx")
CAT_ONNX_CONF = 0.5
IMGSZ = 320
CAT_CLASS = 0  # fine-tuned: russian_blue = class 0

# 파랑색 HSV 범위
BLUE_LOW = np.array([100, 80, 50])
BLUE_HIGH = np.array([130, 255, 255])
MIN_AREA = 500

# --- Detection Mode ---
# "none", "blue", "cat_custom"
detect_mode = "cat_custom"
detect_lock = Lock()

# --- Drive Mode ---
# "MANUAL", "CAT_TRACK"
drive_mode = "CAT_TRACK"
drive_mode_lock = Lock()

# --- 추적 상태 (영상 오버레이용) ---
track_action = ""
track_action_lock = Lock()

# --- 최신 검출 결과 ---
last_detection = {"box": None, "conf": 0.0, "timestamp": 0.0}

# --- 모델 인스턴스 (best.onnx 단일) ---
cat_session = None
cat_input = None

# --- uart_server TCP 연결 (localhost:9000) ---
UART_CMD_HOST = "127.0.0.1"
UART_CMD_PORT = 9000
uart_cmd_sock = None
uart_cmd_lock = Lock()


def load_model():
    global cat_session, cat_input
    if os.path.exists(CAT_ONNX_PATH):
        try:
            import onnxruntime as ort
            cat_session = ort.InferenceSession(
                CAT_ONNX_PATH, providers=["CPUExecutionProvider"])
            cat_input = cat_session.get_inputs()[0].name
            print(f"[MODEL] Cat ONNX loaded: {CAT_ONNX_PATH}")
        except Exception as e:
            print(f"[MODEL] Cat ONNX failed: {e}")
    else:
        print(f"[MODEL] 파일 없음: {CAT_ONNX_PATH}")


# --- uart_server TCP 명령 전송 ---

def send_uart_cmd(cmd_char):
    """uart_server.py에 ASCII 1바이트 명령 전송 (TCP localhost:9000)"""
    global uart_cmd_sock
    with uart_cmd_lock:
        # 연결 시도
        if uart_cmd_sock is None:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect((UART_CMD_HOST, UART_CMD_PORT))
                uart_cmd_sock = s
                print(f"[TRACK] uart_server 연결 성공 ({UART_CMD_HOST}:{UART_CMD_PORT})")
            except Exception:
                return
        # 전송
        try:
            uart_cmd_sock.sendall(cmd_char.encode('ascii'))
        except Exception:
            try:
                uart_cmd_sock.close()
            except Exception:
                pass
            uart_cmd_sock = None


def disconnect_uart_cmd():
    """uart_server TCP 연결 해제"""
    global uart_cmd_sock
    with uart_cmd_lock:
        if uart_cmd_sock:
            try:
                uart_cmd_sock.close()
            except Exception:
                pass
            uart_cmd_sock = None


# --- 고양이 추적 스레드 ---

def cat_track_thread():
    """CAT_TRACK: 검출 결과 직접 읽기 → uart_server로 조향 명령"""
    global track_action
    no_detect_count = 0
    TURN_THRESHOLD = 0.25
    CLOSE_THRESHOLD = 0.25

    while True:
        # 모드 확인
        with drive_mode_lock:
            mode = drive_mode
        if mode != "CAT_TRACK":
            with track_action_lock:
                track_action = ""
            no_detect_count = 0
            time.sleep(0.5)
            continue

        # 검출 모드가 cat_custom이 아니면 자동 전환
        with detect_lock:
            if detect_mode != "cat_custom":
                pass  # capture_loop에서 detect_mode에 따라 검출

        # 검출 결과 읽기 (HTTP 폴링 없이 직접)
        with detect_lock:
            box = last_detection["box"]

        if box is None:
            no_detect_count += 1
            if no_detect_count > 5:
                send_uart_cmd('S')
                with track_action_lock:
                    track_action = "LOST"
            time.sleep(0.15)
            continue

        no_detect_count = 0
        x1, y1, x2, y2 = box
        box_cx = (x1 + x2) / 2.0
        box_area = (x2 - x1) * (y2 - y1)
        frame_area = FRAME_W * FRAME_H

        offset_x = (box_cx - FRAME_W / 2.0) / (FRAME_W / 2.0)
        area_ratio = box_area / frame_area

        if area_ratio > CLOSE_THRESHOLD:
            send_uart_cmd('S')
            action = "CLOSE"
        elif offset_x < -TURN_THRESHOLD:
            send_uart_cmd('L')
            action = "LEFT"
        elif offset_x > TURN_THRESHOLD:
            send_uart_cmd('R')
            action = "RIGHT"
        else:
            send_uart_cmd('F')
            action = "FORWARD"

        with track_action_lock:
            track_action = action

        time.sleep(0.15)


# --- 검출 함수 ---

def detect_cat_custom(frame):
    """커스텀 고양이 ONNX 검출 (best.onnx)"""
    if cat_session is None:
        cv2.putText(frame, "Cat model not loaded", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    h, w = frame.shape[:2]
    img = cv2.resize(frame, (IMGSZ, IMGSZ))
    img = img[:, :, ::-1].astype(np.float32) / 255.0  # BGR→RGB
    img = np.transpose(img, (2, 0, 1))                 # HWC→CHW
    img = np.expand_dims(img, 0)                       # NCHW

    outputs = cat_session.run(None, {cat_input: img})
    preds = outputs[0][0]
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T

    sx, sy = w / IMGSZ, h / IMGSZ
    boxes, confs = [], []
    for det in preds:
        scores = det[4:]
        class_id = int(np.argmax(scores))
        conf = float(scores[class_id])
        if class_id != CAT_CLASS or conf < CAT_ONNX_CONF:
            continue
        cx, cy, bw, bh = det[0], det[1], det[2], det[3]
        x1 = int((cx - bw / 2) * sx)
        y1 = int((cy - bh / 2) * sy)
        x2 = int((cx + bw / 2) * sx)
        y2 = int((cy + bh / 2) * sy)
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confs.append(conf)

    # NMS
    best_box = None
    best_conf = 0.0
    if boxes:
        indices = cv2.dnn.NMSBoxes(boxes, confs, CAT_ONNX_CONF, 0.45)
        for i in indices:
            x, y, bw, bh = boxes[i]
            if confs[i] > best_conf:
                best_conf = confs[i]
                best_box = (x, y, x + bw, y + bh)

    # 검출 결과 전역 저장
    with detect_lock:
        if best_box:
            last_detection["box"] = list(best_box)
            last_detection["conf"] = best_conf
        else:
            last_detection["box"] = None
            last_detection["conf"] = 0.0
        last_detection["timestamp"] = time.time()

    if best_box:
        x1, y1, x2, y2 = best_box
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
        cv2.putText(frame, f"russian_blue {best_conf:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "No cat", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    cv2.line(frame, (w // 2, 0), (w // 2, h), (255, 255, 255), 1)
    cv2.putText(frame, "[CAT CUSTOM]", (w - 220, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

    # 추적 상태 오버레이
    with drive_mode_lock:
        mode = drive_mode
    if mode == "CAT_TRACK":
        with track_action_lock:
            action = track_action
        if action:
            color = (0, 255, 0) if action == "FORWARD" else \
                    (0, 255, 255) if action in ("LEFT", "RIGHT") else \
                    (0, 0, 255)
            cv2.putText(frame, f"TRACK: {action}", (10, h - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    return frame


def detect_blue(frame):
    """파란색 물체 HSV 검출"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, BLUE_LOW, BLUE_HIGH)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area > MIN_AREA:
            x, y, w, h = cv2.boundingRect(largest)
            cx, cy = x + w // 2, y + h // 2
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
    fps_time = time.time()
    fps = 0.0
    frame_count = 0

    while True:
        frame = picam.capture_array()

        with detect_lock:
            mode = detect_mode

        if mode == "cat_custom":
            frame = detect_cat_custom(frame)
        elif mode == "blue":
            frame = detect_blue(frame)
        # "none" → 원본 그대로

        # Drive 모드 표시
        with drive_mode_lock:
            dmode = drive_mode
        cv2.putText(frame, dmode, (FRAME_W - 120, FRAME_H - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

        # FPS 계산
        frame_count += 1
        elapsed = time.time() - fps_time
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            frame_count = 0
            fps_time = time.time()

        cv2.putText(frame, f"FPS: {fps:.1f}", (10, FRAME_H - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            buffer.set(jpg.tobytes())


PAGE = """\
<!DOCTYPE html>
<html>
<head><title>RPi5 Camera</title></head>
<body style="background:#111;color:#eee;font-family:sans-serif;text-align:center;">
<h2>RPi5 Camera Stream</h2>
<img src="stream.mjpg" width="640" height="480" /><br>
<a href="/drive/manual" style="color:#888;margin:10px;">MANUAL</a>
<a href="/drive/cat_track" style="color:#f0f;margin:10px;">CAT_TRACK</a>
<br>
<a href="/mode/none" style="color:#888;margin:10px;">None</a>
<a href="/mode/blue" style="color:#44f;margin:10px;">Blue</a>
<a href="/mode/cat_custom" style="color:#f0f;margin:10px;">Cat Custom</a>
</body>
</html>
"""


class StreamingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global detect_mode, drive_mode

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
        elif self.path.startswith('/drive/'):
            new_drive = self.path.split('/drive/')[-1].strip('/').upper()
            if new_drive in ("MANUAL", "CAT_TRACK"):
                with drive_mode_lock:
                    old = drive_mode
                    drive_mode = new_drive
                # CAT_TRACK 진입 시 검출 모드 자동 전환
                if new_drive == "CAT_TRACK":
                    with detect_lock:
                        detect_mode = "cat_custom"
                elif new_drive == "MANUAL":
                    send_uart_cmd('S')  # 정지
                msg = f"Drive mode: {new_drive}"
                print(f"[DRIVE] {old} → {new_drive}")
            else:
                msg = f"Unknown drive mode: {new_drive}"
            content = msg.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path.startswith('/mode/'):
            new_mode = self.path.split('/mode/')[-1].strip('/')
            if new_mode in ("none", "blue", "cat_custom"):
                with detect_lock:
                    detect_mode = new_mode
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
        elif self.path == '/status':
            with drive_mode_lock:
                dm = drive_mode
            with detect_lock:
                dtm = detect_mode
            with track_action_lock:
                ta = track_action
            data = {"drive_mode": dm, "detect_mode": dtm, "track_action": ta}
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
load_model()

picam = Picamera2()
picam.configure(picam.create_video_configuration(
    main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}
))
picam.start()
time.sleep(1)

buffer = FrameBuffer()
worker = Thread(target=capture_loop, args=(picam, buffer), daemon=True)
worker.start()

# 고양이 추적 스레드 (drive_mode에 따라 동작/대기)
tracker = Thread(target=cat_track_thread, daemon=True)
tracker.start()

try:
    addr = ('0.0.0.0', 8000)
    server = StreamingServer(addr, StreamingHandler)
    print("=" * 40)
    print("  RPi5 Camera + Detection + Tracking")
    print("=" * 40)
    print(f"  Stream : http://0.0.0.0:8000/stream.mjpg")
    print(f"  Detect : {detect_mode}")
    print(f"  Drive  : {drive_mode}")
    print(f"  /drive/manual | /drive/cat_track")
    print(f"  /status  → JSON 상태 조회")
    print("=" * 40)
    server.serve_forever()
except KeyboardInterrupt:
    print("\n종료")
finally:
    disconnect_uart_cmd()
    picam.stop()
