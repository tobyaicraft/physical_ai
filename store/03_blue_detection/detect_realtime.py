import cv2
import numpy as np
import time
from threading import Condition, Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from picamera2 import Picamera2

FRAME_W = 640
FRAME_H = 480

BLUE_LOW  = np.array([100,  80,  50])
BLUE_HIGH = np.array([130, 255, 255])
MIN_AREA  = 500


def get_direction(cx, w):
    norm_x = (cx - FRAME_W / 2) / (FRAME_W / 2)
    if norm_x < -0.2:
        direction = "LEFT"
    elif norm_x > 0.2:
        direction = "RIGHT"
    else:
        direction = "CENTER"
    size_ratio = w / FRAME_W
    return norm_x, direction, size_ratio


class FrameBuffer:
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def set(self, data):
        with self.condition:
            self.frame = data
            self.condition.notify_all()


def capture_loop(picam, buf):
    interval = 1.0 / 10
    last_time = 0

    while True:
        now = time.time()
        if now - last_time < interval:
            continue
        last_time = now

        frame = picam.capture_array()

        # ── 파란색 검출 ──
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, BLUE_LOW, BLUE_HIGH)
        mask = cv2.erode(mask,  None, iterations=1)
        mask = cv2.dilate(mask, None, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            area    = cv2.contourArea(largest)
            if area > MIN_AREA:
                M = cv2.moments(largest)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    x, y, w, h = cv2.boundingRect(largest)
                    norm_x, direction, size_ratio = get_direction(cx, w)

                    print(f"[{direction:6s}] norm_x={norm_x:+.2f}  size={size_ratio:.2f}  center=({cx},{cy})")

                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
                    cv2.putText(frame, f"{direction} ({norm_x:+.2f})",
                                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            else:
                print("[ ---- ] 파란색 없음")
        else:
            print("[ ---- ] 파란색 없음")

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
            page = b'<html><body style="background:#111"><img src="stream.mjpg" width="640" height="480"></body></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(page))
            self.end_headers()
            self.wfile.write(page)


class StreamServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam = Picamera2()
picam.configure(picam.create_video_configuration(
    main={"size": (FRAME_W, FRAME_H), "format": "RGB888"}
))
picam.start()
time.sleep(1)

buffer = FrameBuffer()
Thread(target=capture_loop, args=(picam, buffer), daemon=True).start()

print("파란 공 감지 시작")
print("스트림 : http://toby.local:8000")
print("Ctrl+C로 종료")

try:
    StreamServer(('0.0.0.0', 8000), StreamHandler).serve_forever()
except KeyboardInterrupt:
    print("\n종료")
finally:
    picam.stop()
