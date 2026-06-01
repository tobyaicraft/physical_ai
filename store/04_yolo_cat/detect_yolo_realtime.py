import cv2
import numpy as np
import time
from threading import Condition, Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from picamera2 import Picamera2
from ultralytics import YOLO

FRAME_W = 640
FRAME_H = 480

model = YOLO("yolov8n.pt")


class FrameBuffer:
    def __init__(self):
        self.frame     = None
        self.condition = Condition()

    def set(self, data):
        with self.condition:
            self.frame = data
            self.condition.notify_all()


def capture_loop(picam, buf):
    interval   = 1.0 / 10
    last_time  = 0
    fps_time   = time.time()
    fps        = 0.0
    frame_count = 0

    while True:
        now = time.time()
        if now - last_time < interval:
            continue
        last_time = now

        frame   = picam.capture_array()
        results = model(frame, verbose=False)

        frame_count += 1
        elapsed = time.time() - fps_time
        if elapsed >= 1.0:
            fps        = frame_count / elapsed
            frame_count = 0
            fps_time   = time.time()

        found = False
        for r in results:
            for box in r.boxes:
                cls_name = model.names[int(box.cls[0])]
                if cls_name != "cat":
                    continue
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                print(f"[CAT] conf={conf:.2f}  center=({cx},{cy})")

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
                cv2.putText(frame, f"cat {conf:.2f}",
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                found = True

        if not found:
            print("[ ---- ] 고양이 없음")

        cv2.putText(frame, f"FPS: {fps:.1f}",
                    (10, FRAME_H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            buf.set(jpg.tobytes())


class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/stream.mjpg':
            self.send_response(200)
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
            except Exception:
                pass
        else:
            page = b'<html><body><img src="stream.mjpg" width="640" height="480"></body></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(page))
            self.end_headers()
            self.wfile.write(page)


class StreamServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads      = True


picam = Picamera2()
picam.configure(picam.create_video_configuration(
    main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}
))
picam.start()
time.sleep(1)

buffer = FrameBuffer()
Thread(target=capture_loop, args=(picam, buffer), daemon=True).start()

print("고양이 감지 시작")
print("스트림 : http://toby.local:8000")
print("Ctrl+C로 종료")

try:
    StreamServer(('0.0.0.0', 8000), StreamHandler).serve_forever()
except KeyboardInterrupt:
    print("\n종료")
finally:
    picam.stop()
