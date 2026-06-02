---
name: AI 검출 모델 현황
description: RPi5 ~/rccar/models/ 사용 모델 - best.onnx 단일 모델로 단순화
metadata:
  type: project
---
## 현재 사용 모델 (`~/rccar/models/`)

2026-06-02 기준 **best.onnx 단일 모델**로 단순화 완료.
다중 모델 로드 시 OOM으로 카메라 프로세스가 SIGKILL로 종료되는 문제 해결.

| 모드 | 모델 | 설명 |
|------|------|------|
| `cat_custom` | best.onnx (12MB) | 커스텀 학습 고양이, mAP50=98.4% |
| `cat_track` | best.onnx (동일) | 검출 + RC카 자율 추적 |
| `blue` | 없음 (HSV) | 파란 물체 색상 검출 |
| `none` | 없음 | 원본 스트리밍 |

## 파인튜닝 결과 (russian_blue_v2-3)
- 학습: 55 epoch (patience=30 early stop), RTX 3060, 약 2분
- Best epoch 25: mAP50=98.4%, mAP50-95=91.2%
- 모델 경로: `store/06_fine_tune/runs/detect/russian_blue_v2-3/weights/best.onnx`

**Why:** 다중 모델(SSD+YOLO+TFLite+Custom) 동시 로드 시 RPi5 메모리 부족으로 프로세스 종료
**How to apply:** best.onnx 하나만 로드. 다른 모델 추가 제안 금지.
