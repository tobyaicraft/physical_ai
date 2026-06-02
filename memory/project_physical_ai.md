---
name: physical_ai 프로젝트 구조
description: physical_ai 레포 구성 - ai_rc_vehicle_mcu(TC23A) + ai_rc_vehicle_soc(RPi5) 통합 프로젝트
metadata:
  type: project
---
GitHub: github.com/tobyaicraft/physical_ai

## 폴더 구조
- `ai_rc_vehicle_mcu/` - Infineon TC23A MCU, 4WD 모터/센서 제어 (C언어)
- `ai_rc_vehicle_soc/rpi5/` - 라즈베리파이5 실행 스크립트 및 모델
- `ai_rc_vehicle_soc/pc/` - PC 컨트롤 패널 (Python/tkinter)

## RPi5 실행 방법 (2026-06-02 기준 최신)
1. SSH 접속 후:
```bash
source ~/virenv.sh      # 프로세스/포트/카메라 정리 + rccar-env 활성화 + cd ~/rccar
bash fstart.sh          # 최초 실행 (systemd 서비스 정지 포함)
bash start.sh           # 이후 재실행
```
- **실행 위치**: `~/rccar/` (구 `~/project/`는 systemd 서비스용)
- **가상환경**: `~/rccar-env/` (--system-site-packages)
- camera_stream.py (HTTP :8000) + uart_server.py (TCP :9000/:9001) 동시 실행

2. **PC**: `ai_rc_vehicle_soc/pc/run.bat` 더블클릭

## 하드웨어
- RPi5 4GB + 5MP CSI 카메라 (ov5647) + 서보 (GPIO 18)
- TC23A MCU: 4WD 모터, MPU-9250 IMU, 초음파(P02.6 TRIG / P02.7 ECHO) / IR 센서
- RPi5 ↔ TC237: UART /dev/ttyAMA2 @ 115200
- 모터드라이버 핀: FL(PWM:P33.4, IN1:P33.2, IN2:P33.3), FR(P33.5, P33.1, P33.12), RL(P02.4, P00.0, P00.1), RR(P02.5, P00.2, P00.3)

**Why:** MCU 전문 개발자가 SoC 레벨로 확장하는 과정을 YouTube 콘텐츠로 기록하는 프로젝트
**How to apply:** 실행 편의성(배치파일/스크립트 한방 실행)과 콘텐츠 제작 관점을 고려하여 작업
