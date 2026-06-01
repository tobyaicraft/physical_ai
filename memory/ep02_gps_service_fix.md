# EP02: GPS 연결 확인 및 서비스 자동시작 수정 (2026-05-30)

## GPS 모듈 (NEO-6M) 상태
- 시리얼 포트: `/dev/ttyAMA0` @ 9600 baud
- RPi5에서 정상 동작 확인 (위성 4개, 좌표 수신 성공)
- 수신 좌표 예시: LAT:37.241040, LON:127.067649

## 문제 1: rc-car 서비스 즉시 종료
- **증상**: `systemctl start rc-car` 실행 시 58ms만에 종료
- **원인**: `rpi5_start.sh` 안에 `systemctl stop rc-car 2>/dev/null` 코드가 있어서 서비스로 실행하면 자기 자신을 죽임
- **해결**: `rpi5_start.sh`에서 해당 줄 제거
  - 로컬 파일 수정 후 scp로 전송했으나 반영 안 됨
  - RPi5에서 직접 `sudo sed -i '/systemctl stop rc-car/d' ~/project/rpi5_start.sh`로 해결

## 문제 2: 서비스 자동시작 비활성화
- 디버깅 중 `sudo systemctl disable rc-car` 실행하여 자동시작 해제됨
- `sudo systemctl enable rc-car`로 재활성화
- 서비스 정상 동작 확인: camera_stream.py + uart_server.py + GPS 모두 실행됨

## 문제 3: 서비스 모드에서 GPS fix 안 잡힘
- **증상**: 수동 실행(`sudo bash ~/project/rpi5_start.sh`)하면 GPS 좌표 정상 수신, 서비스로 실행하면 SAT:0, LAT/LON:0
- **원인 추정**: 부팅 직후 서비스가 너무 빨리 시작되어 GPS 모듈 준비 시간 부족
- **상태**: 미해결 — 추후 서비스 시작 지연(ExecStartPre=sleep) 추가 검토 필요

## GPS 동작 특성
- NMEA 파싱: `$GPRMC`에서 `A`(valid fix)일 때만 좌표 업데이트, `$GPGGA`에서 위성 수 파싱
- GPS drift: 위성 4개 이하일 때 가만히 있어도 좌표가 흔들리고 가짜 속도(~18km/h) 발생 (NEO-6M 한계)
- DOP 값 25~27로 높으면 위치 정밀도 낮음 (낮을수록 좋음)

## GPS Home 복귀 한계
- NEO-6M 오차 5~15m → 도착 판정(3m) 불가, 가만히 있어도 좌표가 10m씩 튀어서 방향 계산 무의미
- 현재 복귀 알고리즘(`control_panel.py:930`): 방위각 vs IMU Yaw 비교 → 회전/직진 반복 → GPS 오차로 계속 회전만 함
- **결론**: GPS만으로 정확한 Home 복귀 불가능
  - 원거리(50m+): GPS로 대략적 방향 이동 가능
  - 중/근거리(10~15m 이내): 카메라(마커/표지판 인식)로 정밀 접근 필요
- 향후 개선: 속도 필터링(정지 시 좌표 고정) + 카메라 비전 융합

## GPS 복귀 로직 개선 방향 (미구현)
- 현재 문제: 매 0.3초 GPS 방위각 재계산 → 오차로 회전만 반복
- **개선안 (직선 복귀)**: Home GPS + Yaw 저장 → 복귀 시 방위각 한 번 계산 → IMU Yaw로 방향 유지하며 직진 → 5m마다 방위각 재계산
- GPS는 거리 판단용, 방향 유지는 IMU Yaw 기반
- 테스트 장소: 운동장 (하늘 트인 곳, DOP 낮아짐)

## 관련 파일
- `ai_rc_vehicle_soc/rpi5/rpi5_start.sh` — 통합 런처 (수정됨)
- `ai_rc_vehicle_soc/rpi5/uart_server.py` — GPS NMEA 파싱 + 브로드캐스트
- `ai_rc_vehicle_soc/rpi5/rc-car.service` — systemd 서비스 파일
- `ai_rc_vehicle_soc/pc/control_panel.py` — PC 제어 패널 (GPS 표시)
