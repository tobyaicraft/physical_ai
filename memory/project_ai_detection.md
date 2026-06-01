---
name: AI 검출 모델 현황
description: RPi5에서 사용 가능한 AI 검출 모델 목록, 성능 비교, 전력 이슈
type: project
originSessionId: 3c4fd13c-0225-4dee-981c-40fe07870cf3
---
## RPi5 검출 모델 (`~/project/models/`)

| 모드 | 모델 파일 | 성능 | 평가 |
|------|----------|------|------|
| ssd | MobileNetSSD (Caffe) | 20~30 FPS | 가볍고 빠름 |
| cat_custom | best_int8.onnx | ~10.9 FPS, mAP50=0.99 | 커스텀 고양이 정확 |
| yolo_onnx | yolov8n_int8.onnx | ~10 FPS | **인식 최고**, 전력 주의 |
| yolo_tflite | yolov8n_int8.tflite | - | 인식 불량, 비추 |

**Why:** YOLO ONNX 추론 시 RPi5 CPU 풀로드 → 배터리 소모, 빨간불 가능
**How to apply:** 평소 none/blue, 필요시만 yolo_onnx/cat_custom 전환. 전원 어댑터 5V/5A 권장.
