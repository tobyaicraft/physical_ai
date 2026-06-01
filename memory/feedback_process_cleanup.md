---
name: RPi5 프로세스 정리 후 재시작
description: camera_stream.py / uart_server.py 재실행 전 기존 프로세스 kill 필요
type: feedback
originSessionId: c9c717fe-e0f9-434c-98a0-66869ce3d6e6
---
start.sh 재실행 전에 기존 프로세스를 먼저 정리해야 한다.

**Why:** 카메라는 "Device or resource busy", UART 서버는 "Address already in use" 에러 발생. 2026-05-27 세션에서 두 번 겪음.

**How to apply:** start.sh 재실행 안내 시 항상 먼저 정리 명령을 안내:
```
sudo pkill -f camera_stream.py
sudo pkill -f uart_server.py
bash start.sh
```
또는 start.sh 자체에 시작 전 기존 프로세스 kill 로직 추가 권장.
