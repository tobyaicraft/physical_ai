# Physical AI RC Car 프로젝트 작업 요약

## 프로젝트 개요
- RC카에 RPi5 + 카메라 탑재
- 러시안블루 고양이 실시간 감지 (파인튜닝 YOLOv8n → ONNX → RPi5 배포)
- 책 집필 목적

---

## 환경

### PC (Windows 11, RTX 3060)
- Python 3.12 venv (`store/06_fine_tune/venv_train`)
- torch 2.5.1+cu121, ultralytics 8.4.59

### RPi5
- Python 3.13, rccar-env
- picamera2, onnxruntime, opencv-python, ultralytics

---

## 작업 흐름

### 1단계. 저장소 클론
```bash
git clone --recurse-submodules https://github.com/tobyaicraft/physical_ai
```
- `ai_rc_vehicle_soc`는 phantom submodule (내용 없음)

---

### 2단계. 파란색 물체 감지 (HSV)
**파일:** `test/detect_realtime.py`, `store/03_blue_detection/detect_realtime.py`

**핵심 코드:**
```python
picam.configure(picam.create_video_configuration(
    main={"size": (640, 480), "format": "RGB888"}
))
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)  # RGB888 = BGR 데이터
lower = np.array([100, 80, 50])
upper = np.array([130, 255, 255])
```
- RGB888 포맷이지만 실제 데이터는 BGR → COLOR_BGR2HSV 사용
- MJPEG 스트리밍: `http://toby.local:8000`

---

### 3단계. YOLO ONNX 추론 비교
**파일:** `store/04_yolo_cat/`, `test/detect_onnx_realtime.py`, `test/detect_int8_realtime.py`

| 모델 | FPS | 좌표계 |
|---|---|---|
| yolov8n.onnx | 10.0 | 정규화 (0~1) → `* fw/fh` |
| yolov8n_int8.onnx | 9.3 | 픽셀 (imgsz) → `* fw/IMGSZ` |

**NMS 주의:** 키워드 인자 불가 → 위치 인자만
```python
indices = cv2.dnn.NMSBoxes(boxes, confs, CONF_THR, 0.45)
```

---

### 4단계. 러시안블루 데이터셋 구축
**파일:** `store/05_dataset/`

```
extract_frames.py   # 영상 10개 → 336장 (0.5초 간격)
auto_label.py       # YOLOv8n COCO class15(cat) → YOLO txt
preview_labels.py   # 바운딩박스 시각화 검수
split_dataset.py    # train(222장) / val(114장) 분할
```

- train: cat1~8 (frame_0000~0221)
- val: cat9~10 (frame_0222~0335) — 영상 단위 분할로 데이터 누수 방지

---

### 5단계. 파인튜닝

#### 1차 실패
```python
model.train(data="my_cat/data.yaml", epochs=100, imgsz=320, batch=16,
            name="russian_blue", patience=20, device=0)
```
- 원인: nc=80→1 분류 헤드 재초기화 → confidence 최대 0.03

#### 2차 성공 (`store/06_fine_tune/train_v2.py`)
```python
if __name__ == "__main__":
    model = YOLO("yolov8n.pt")
    model.train(
        data="my_cat/data.yaml",
        epochs=200, imgsz=320, batch=16,
        name="russian_blue_v2",
        freeze=10,    # 백본 고정 (핵심!)
        lr0=0.001,    # 낮은 학습률
        patience=30,
        device=0,
    )
```
- 결과: **mAP50=0.984, P=0.973, R=1.0** (epoch 25에서 조기 종료)
- 저장: `runs/detect/russian_blue_v2-3/weights/best.pt`

---

### 6단계. ONNX 변환
```python
model = YOLO("runs/detect/russian_blue_v2-3/weights/best.pt")
model.export(format="onnx", imgsz=320, simplify=True)
# → best.onnx (11.6MB), shape: (1, 5, 2100)
```

---

### 7단계. RPi5 배포
```bash
scp best.onnx toby@toby.local:~/rccar/models/
scp detect_mycat_realtime.py toby@toby.local:~/rccar/
```

**최종 스크립트:** `test/detect_mycat_realtime.py`
```python
IMGSZ     = 320
CONF_THR  = 0.5
CAT_CLASS = 0   # russian_blue

# 파인튜닝 ONNX는 imgsz 픽셀 좌표 출력
sx, sy = fw / IMGSZ, fh / IMGSZ
x1 = int((cx - bw / 2) * sx)

# shape transpose: nc=1이라 shape[0]=5
if preds.shape[0] < preds.shape[1]:
    preds = preds.T
```

---

## 최종 성능

| 방식 | FPS | confidence | 비고 |
|---|---|---|---|
| ONNX (best.onnx) | **10.1** | 0.91 | 배포 권장 |
| PT (best.pt) | 10.0 | 0.87 | ultralytics 필요 |

---

## 모델 위치

**PC:**
```
store/06_fine_tune/runs/detect/russian_blue_v2-3/weights/
├── best.pt    (6.2MB)
└── best.onnx  (11.6MB)
```

**RPi5:**
```
~/rccar/models/
├── best.pt
└── best.onnx
```

---

## 주요 트러블슈팅

| 문제 | 원인 | 해결 |
|---|---|---|
| camera 읽기 실패 | cv2.VideoCapture(0) RPi5 미지원 | Picamera2 사용 |
| 색상 이상 (파란→노랑) | RGB888 포맷이 BGR 데이터 전달 | COLOR_BGR2HSV 사용 |
| ONNX bbox center=(0,0) | 정규화 좌표에 sx/sy 스케일링 적용 | fw/fh 직접 곱하기 |
| INT8 bbox 좌표 이상 | IMGSZ 픽셀 좌표인데 fw/fh 곱함 | fw/IMGSZ 스케일링 |
| NMSBoxes TypeError | keyword arg 사용 | 위치 인자만 사용 |
| 1차 학습 confidence 0.03 | nc 변경으로 헤드 재초기화 | freeze=10, lr0=0.001 |
| ONNX shape transpose 실패 | nc=1 → shape[0]=5 (84 체크 실패) | shape[0] < shape[1] 조건 |
| Windows 멀티프로세싱 오류 | train.py에 guard 없음 | if __name__ == "__main__": |

---

## 파일 구조
```
physical_ai/
├── test/
│   ├── detect_realtime.py          # HSV 파란색 감지
│   ├── detect_onnx_realtime.py     # COCO ONNX 고양이 감지
│   ├── detect_int8_realtime.py     # INT8 ONNX 고양이 감지
│   ├── detect_yolo_realtime.py     # COCO PT 고양이 감지
│   ├── detect_mycat_realtime.py    # 파인튜닝 ONNX (최종)
│   └── detect_mycat_pt_realtime.py # 파인튜닝 PT
├── store/
│   ├── 03_blue_detection/
│   ├── 04_yolo_cat/
│   ├── 05_dataset/
│   │   ├── extract_frames.py
│   │   ├── auto_label.py
│   │   ├── preview_labels.py
│   │   ├── split_dataset.py
│   │   └── labels/                 # YOLO 라벨 txt
│   └── 06_fine_tune/
│       ├── train_v2.py
│       ├── my_cat/                 # 학습 데이터셋
│       │   ├── data.yaml
│       │   └── labels/
│       └── runs/detect/russian_blue_v2-3/weights/
│           ├── best.pt
│           └── best.onnx
└── memory/
    └── project_summary.md          # 이 파일
```
