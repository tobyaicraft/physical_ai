import cv2
import numpy as np
import time
import onnxruntime as ort
from threading import Condition, Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from picamera2 import Picamera2

FRAME_W   = 640
FRAME_H   = 480
IMGSZ     = 320
CONF_THR  = 0.5
CAT_CLASS = 0   # fine-tuned: russian_blue = class 0

session  = ort.InferenceSession("models/best.onnx", providers=["CPUExecutionProvider"])
inp_name = session.get_inputs()[0].name


def preprocess(frame):
    img = cv2.resize(frame, (IMGSZ, IMGSZ))
    img = img[:, :, ::-1].astype(np.float32) / 255.0  # BGR→RGB
    img = np.transpose(img, (2, 0, 1))                 # HWC→CHW
    return np.expand_dims(img, 0)                       # NCHW


def postprocess(preds, fw, fh):
    if preds.shape[0] < preds.shape[1]:   # [features, anchors] → [anchors, features]
        preds = preds.T
    boxes, confs = [], []
    for det in preds:
        scores   = det[4:]
        class_id = int(np.argmax(scores))
        conf     = float(scores[class_id])
        if class_id != CAT_CLASS or conf < CONF_THR:
            continue
        cx, cy, bw, bh = det[0], det[1], det[2], det[3]
        sx, sy = fw / IMGSZ, fh / IMGSZ
        x1 = int((cx - bw / 2) * sx)
        y1 = int((cy - bh / 2) * sy)
        x2 = int((cx + bw / 2) * sx)
        y2 = int((cy + bh / 2) * sy)
        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confs.append(conf)

    if not boxes:
        return []

    indices = cv2.dnn.NMSBoxes(boxes, confs, CONF_THR, 0.45)
    results = []
    for i in indices:
        x, y, w, h = boxes[i]
        results.append((x, y, x + w, y + h, confs[i]))
    return results


class FrameBuffer:
    def __init__(self):
        self.frame     = None
        self.condition = Condition()

    def set(self, data):
        with self.condition:
            self.frame = data
            self.condition.notify_all()


def capture_loop(picam, buf):
    fps_time    = time.time()
    fps         = 0.0
    frame_count = 0

    while True:
        frame   = picam.capture_array()
        inp     = preprocess(frame)
        outputs = session.run(None, {inp_name: inp})
        preds   = outputs[0][0]
        if preds.shape[0] < preds.shape[1]:
            preds = preds.T
        top_conf = float(preds[:, 4:].max())
        dets     = postprocess(outputs[0][0], FRAME_W, FRAME_H)

        frame_count += 1
        elapsed = time.time() - fps_time
        if elapsed >= 1.0:
            fps         = frame_count / elapsed
            frame_count = 0
            fps_time    = time.time()

        if dets:
            for x1, y1, x2, y2, conf in dets:
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                print(f"[CAT] conf={conf:.2f}  center=({cx},{cy})")
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
                cv2.putText(frame, f"russian_blue {conf:.2f}",
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        else:
            print(f"[ ---- ] 러시안블루 없음  (max_conf={top_conf:.3f})")

        cv2.putText(frame, f"FPS: {fps:.1f}  [MyCAT-ONNX]",
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

print("러시안블루 감지 시작 (fine-tuned ONNX)")
print("스트림 : http://toby.local:8000")
print("Ctrl+C로 종료")

try:
    StreamServer(('0.0.0.0', 8000), StreamHandler).serve_forever()
except KeyboardInterrupt:
    print("\n종료")
finally:
    picam.stop()
