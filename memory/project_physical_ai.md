---
name: physical_ai 프로젝트 구조
description: physical_ai 레포 구성 - ai_rc_vehicle_mcu(TC23A) + ai_rc_vehicle_soc(RPi5) 통합 프로젝트
type: project
originSessionId: c9c717fe-e0f9-434c-98a0-66869ce3d6e6
---
GitHub: github.com/tobyaicraft/physical_ai

## 폴더 구조
- `ai_rc_vehicle_mcu/` - Infineon TC23A MCU, 4WD 모터/센서 제어 (C언어)
- `ai_rc_vehicle_soc/` - 라즈베리파이5, 카메라 스트리밍 + UART 브릿지 + PC 제어 (Python)

## 실행 방법
1. **라즈베리파이**: SSH 접속 후 `cd ~/project && bash start.sh`
   - camera_stream.py (HTTP :8000) + uart_server.py (TCP :9000/:9001) 동시 실행
2. **PC**: `ai_rc_vehicle_soc/pc/run.bat` 더블클릭
   - keyboard_client.py + sensor_monitor.py 동시 실행

## 하드웨어
- RPi5 4GB + 5MP CSI 카메라 (ov5647) + 서보 (GPIO 18)
- TC23A MCU: 4WD 모터, MPU-9250 IMU, 초음파/IR 센서
- RPi5 ↔ TC237: UART /dev/ttyAMA2 @ 115200

**Why:** MCU 전문 개발자가 SoC 레벨로 확장하는 과정을 YouTube 콘텐츠로 기록하는 프로젝트
**How to apply:** 실행 편의성(배치파일 한방 실행)과 콘텐츠 제작 관점을 고려하여 작업
