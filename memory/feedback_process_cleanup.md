---
name: RPi5 프로세스 정리 후 재시작
description: camera_stream.py / uart_server.py 재실행 전 프로세스/포트/카메라 강제 해제 필수
metadata:
  type: feedback
---
RPi5 재시작 전 반드시 기존 프로세스와 리소스를 정리해야 한다.

**Why:** 카메라 "Device or resource busy", UART "Address already in use", libcamera IPA 서브프로세스 좀비 등 복합 문제 발생.

**How to apply:** 항상 `source ~/virenv.sh` 먼저 실행:
```bash
source ~/virenv.sh   # 아래를 자동 처리:
# sudo pkill -f camera_stream / uart_server / libcamera / rpicam
# sudo fuser -k /dev/media0 /dev/media3   (카메라 디바이스)
# sudo fuser -k 9000/tcp 9001/tcp 8000/tcp  (포트)
# sleep 4
# source ~/rccar-env/bin/activate
# cd ~/rccar
```

최초 실행 또는 systemd 서비스가 살아있을 때: `bash fstart.sh`
이후 재실행: `bash start.sh`

**주의:** `bash start.sh`가 아닌 `source start.sh` 실행 금지 — venv 활성화/cd는 virenv.sh에서 처리됨.
