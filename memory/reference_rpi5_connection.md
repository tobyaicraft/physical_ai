---
name: 라즈베리파이5 SSH 및 네트워크 접속 정보
description: RPi5 SSH 접속 방법, mDNS 호스트명, 서비스 포트 정보
type: reference
originSessionId: c9c717fe-e0f9-434c-98a0-66869ce3d6e6
---
## SSH 접속
```
ssh toby@toby.local
```
- 비밀번호 인증 사용
- 호스트명: toby (라즈베리파이 hostname)
- mDNS: toby.local (IP 변경되어도 자동 해석)

## 서비스 포트
| 서비스 | 포트 | 용도 |
|--------|------|------|
| 카메라 스트리밍 | 8000 | MJPEG over HTTP (브라우저 접속) |
| 명령 수신 | 9000 | PC → RPi5 → TC237 (1바이트 ASCII) |
| 센서 브로드캐스트 | 9001 | TC237 → RPi5 → PC (L:xx,R:xx,U:xx) |

## 라즈베리파이 프로젝트 경로
`/home/toby/project/` — camera_stream.py, uart_server.py, start.sh, rpi5_start.sh

## WiFi 변경 시
```
sudo nmcli dev wifi rescan && sudo nmcli dev wifi list
sudo nmcli dev wifi connect "WiFi이름" password "비밀번호"
```
주의: WiFi 변경 시 SSH 연결 끊김, PC도 같은 WiFi로 변경 후 재접속 필요
