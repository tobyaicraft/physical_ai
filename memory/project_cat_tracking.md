---
name: 7장 고양이 추적 RC카 구현
description: 7장 통합 - best.onnx 검출 + PC 판단 + TC237 실행 아키텍처, 주요 파라미터
metadata:
  type: project
---
## 아키텍처 (2026-06-02 구현)

```
카메라 → RPi5(best.onnx 검출) → PC(_cat_track_loop) → uart_server → TC237
```

- RPi5: 검출만 담당, `/detect` HTTP 엔드포인트로 결과 제공
- PC: 150ms마다 폴링 → 방향 판단 → F/L/R/S 명령 전송
- TC237: MANUAL 모드에서 명령 그대로 실행 (MOVE_TIMEOUT 200ms)

## 핵심 파라미터 (컨트롤 패널 슬라이더)
| 파라미터 | 기본값 | 역할 |
|---------|--------|------|
| Speed | 60% | 이동 속도 |
| Turn | 25% | 좌우 전환 임계값 (히스테리시스: 복귀=Turn×0.5) |
| Stop Size | 25% | 화면 점유율 초과 시 정지 |
| US Stop | 5cm | 초음파 정지 거리 |
| Resume Size | 15% | 정지 후 재출발 기준 |

## 상태 머신
- **FORWARD**: 고양이 감지 + Stop Size 미만 + 중앙 정렬
- **LEFT/RIGHT**: 고양이가 Turn% 이상 치우침 (히스테리시스 적용)
- **STOP**: 화면 점유율 > Stop Size
- **WAIT**: STOP 후 Resume Size 이하 되어야 재출발
- **LOST**: 2프레임 이상 미감지 → 정지

## TC237 모드 관련
- `VEHICLE_MODE_CAT_TRACK = 4` MCU 펌웨어에 추가됨 (아직 플래시 전)
- 구 펌웨어에서 mode=4 거부 → 현재 패널에서 'C' 명령 비활성화 상태
- TC237 새 펌웨어 플래시 후 'C' 명령 활성화 예정

## 알려진 이슈
- 초음파 센서: 4cm 허위 에코 (트리거 커플링), 127cm 고정 → 펌웨어 플래시로 해결 예정
- 후진 시 왼쪽 뒷바퀴 미동작 → 배선 재정비로 해결
- 좌우 채터링: 히스테리시스로 완화, Turn 슬라이더로 튜닝

**Why:** 직진 먼저 안정화 후 좌우 추가한 단계적 구현
**How to apply:** 파라미터 튜닝 시 Stop Size와 Resume Size 간격을 충분히 유지할 것 (최소 5% 이상 차이)
