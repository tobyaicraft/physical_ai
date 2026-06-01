# EP01: 하드웨어 배선 및 통합 패널 구축 (2026-05-28~29)

## 모터드라이버 (L298N x2) 연결

### X102 커넥터 (전방 모터 FL, FR)
| 신호 | TC23A 핀 | X102 핀 | L298N |
|------|----------|---------|-------|
| FL PWM | P33.4 | pin 14 | ENA |
| FL IN1 | P33.2 | pin 16 | IN1 |
| FL IN2 | P33.3 | pin 15 | IN2 |
| FR PWM | P33.5 | pin 13 | ENB |
| FR IN1 | P33.1 | pin 17 | IN3 |
| FR IN2 | P33.12 | pin 18 | IN4 |

### X103 커넥터 (후방 모터 RL, RR)
| 신호 | TC23A 핀 | X103 핀 | L298N |
|------|----------|---------|-------|
| RL PWM | P02.4 | pin 17 | ENA |
| RL IN1 | P00.0 | pin 22 | IN1 |
| RL IN2 | P00.1 | pin 23 | IN2 |
| RR PWM | P02.5 | pin 18 | ENB |
| RR IN1 | P00.2 | pin 24 | IN3 |
| RR IN2 | P00.3 | pin 25 | IN4 |

## UART (RPi5 ↔ TC23A 유선 직결)
| | TC23A | RPi5 |
|---|---|---|
| TX | P15.2 (X102 pin 31) | RX GPIO 5 (pin 29) |
| RX | P15.3 (X102 pin 32) | TX GPIO 4 (pin 7) |
| Baud | 115200 | 115200 |
| GND | X102 pin 3 | pin 6 |

## 적외선 센서 (IR, GP2Y0A21YK0F)
| 센서 | ADC 채널 | TC23A 핀 | 커넥터 |
|------|---------|----------|--------|
| IR 좌측 | AN1 | P40.1 | X102 pin 11 |
| IR 우측 | AN12 | P41.0 | X103 pin 40 |

## 초음파 센서 (HC-SR04)
| 신호 | TC23A 핀 | 커넥터 |
|------|----------|--------|
| TRIG | P02.6 | X103 pin 19 |
| ECHO | P02.7 | X103 pin 20 |
- ECHO 5V → 분압 저항 (1kΩ + 2kΩ) → 3.3V safe

## MPU-9250 자이로센서 (SPI, QSPI3)
| 신호 | TC23A 핀 | 커넥터 |
|------|----------|--------|
| SCLK | P22.3 | X102 pin 30 |
| MOSI | P22.0 | X102 pin 27 |
| MISO | P22.1 | X102 pin 28 |
| CS | P22.2 | X102 pin 29 |

## 서보모터 (RPi5)
- GPIO 18 (pin 12) → 서보 Signal
- 전원: 별도 레귤레이터 사용 (L298N 5V 출력은 노이즈 심함)
- RPi5 GND와 서보 GND 반드시 공유

## 배터리 전압 측정
| ADC 채널 | TC23A 핀 | 커넥터 |
|---------|----------|--------|
| AN0 | P40.0 | X102 pin 12 |

---

## 코드 변경 사항

### MCU (ai_rc_vehicle_mcu)
- DrvUart.c: baud rate 38400 → 115200
- DrvDio.c: FR 모터 방향 반전, RL 모터 방향 수정 (새 차량 배선)
- AppMotorTest.c: 테스트 듀티 50% → 100%

### RPi5 (uart_server.py)
- ASCII 명령(F/B/L/R/S) → TC237 패킷 프로토콜(AA LEN CMD PAYLOAD CHK 55) 변환
- MOVE 명령 100ms 주기 재전송 (MCU 200ms 타임아웃 대응)
- CMD_RESET(0x30) 지원 추가 (X 명령)

### PC (control_panel.py) — 신규 통합 패널
- 카메라 MJPEG 뷰 (640x480, Content-Length 파싱, 메인 스레드 렌더링)
- 방향키 조종 (tkinter KeyPress/KeyRelease)
- 센서 모니터 (IR Left/Right ADC→cm, Ultrasonic cm)
- 3D IMU 뷰 (Roll/Pitch/Yaw, matplotlib 3D car model)
- 서보 제어 (U/I 키)
- MCU 소프트 리셋 (R 키)
- AI Vision placeholder (향후 객체 인식용)
- 불필요한 개별 클라이언트 삭제 (keyboard_client, key, sensor_monitor, sensor)

## 조작 키
| 키 | 기능 |
|---|---|
| 방향키 | 차량 전진/후진/좌/우 |
| Space | 정지 |
| U / I | 서보 좌/우 |
| P | 자동 주차 모드 |
| R | MCU 소프트 리셋 |
| ESC | 종료 |

---

## 고양이 인식 (카메라 AI Detection) — 2026-05-29

### 검출 모드 전환 (control_panel Detect 드롭다운)
| 모드 | 방식 | 설명 |
|------|------|------|
| none | 없음 | 원본 스트리밍 |
| blue | HSV 색상 검출 | 파란색 물체 검출 (OpenCV) |
| cat | MobileNet SSD | 고양이 검출 (OpenCV DNN) |

### MobileNet SSD 모델
- 모델: MobileNetSSD_deploy.caffemodel (22MB) + .prototxt
- 경로: `/home/toby/project/models/`
- 추론: OpenCV DNN (`cv2.dnn.readNetFromCaffe`)
- 입력: 300x300, 20클래스 (cat 포함)
- 신뢰도 임계값: 0.5

### 모드 전환 구조
- PC control_panel → HTTP GET `/mode/<name>` → RPi5 camera_stream.py
- camera_stream.py 내부에서 `detect_mode` 변수로 분기

### 시도한 모델들
1. **YOLOv8n ONNX INT8** (12MB) — RPi5 전력 부족 (빨간불), onnxruntime 무거움
2. **YOLOv8n TFLite INT8** (3.4MB, Colab에서 변환) — 인식 안 됨 (score 낮음)
3. **MobileNet SSD Caffe** (22MB) — OpenCV DNN으로 가벼움, 인식 잘 됨, 채택

### RPi5 패키지 설치 이력
```
sudo pip3 install onnxruntime --break-system-packages    # ONNX용 (YOLO)
sudo pip3 install ai-edge-litert --break-system-packages # TFLite용
# MobileNet SSD는 OpenCV만 있으면 됨 (추가 설치 불필요)
```

### 모델 다운로드 (RPi5에서)
```bash
mkdir -p ~/project/models && cd ~/project/models
wget https://github.com/djmv/MobilNet_SSD_opencv/raw/master/MobileNetSSD_deploy.prototxt
wget https://github.com/djmv/MobilNet_SSD_opencv/raw/master/MobileNetSSD_deploy.caffemodel
```

### control_panel.py 레이아웃 최종
```
┌──────────────────────┬─────────────────┬──────────┐
│                      │  AI Vision      │  IMU 3D  │
│  카메라 MJPEG 뷰     │  (인식 결과용)   │  R P Y   │
│  (640x480)           │                 │  [3D뷰]  │
├──────────────────────┤──────┬─────┬────┴──────────┤
│  [↑][←][↓][→]       │ IR L │ Car │ IR R          │
│  [U][I][SPC][P][R]  │      │ 2D뷰│               │
│  Servo / Detect 선택 │      │     │               │
└──────────────────────┴──────┴─────┴───────────────┘
  상단 바: IP, Connect, Detect(none/blue/ssd/cat_custom/yolo_onnx/yolo_tflite)
```

---

## 멀티 검출 모델 통합 — 2026-05-29

### RPi5 모델 폴더 (`~/project/models/`)
| 파일 | 모델 | 크기 | 추론 방식 | 성능 |
|------|------|------|----------|------|
| MobileNetSSD_deploy.caffemodel + .prototxt | MobileNet SSD | 22MB | OpenCV DNN | 20~30 FPS, 20클래스 |
| best_int8.onnx | 커스텀 고양이 YOLOv8s | 10.8MB | onnxruntime | ~10.9 FPS, mAP50=0.99 |
| yolov8n_int8.onnx | YOLOv8n COCO INT8 | 3.4MB | onnxruntime | **인식 잘 됨 (최고)** |
| yolov8n_int8.tflite | YOLOv8n COCO TFLite | 3.4MB | ai-edge-litert | 인식 안 됨 (양자화 손실) |

### 패널 검출 모드 (Detect 드롭다운)
| 모드 | 설명 | 평가 |
|------|------|------|
| none | 원본 스트리밍 | 전력 최소 |
| blue | HSV 파란색 검출 | 가벼움 |
| ssd | MobileNet SSD 20클래스 | 빠르고 가벼움 |
| cat_custom | 커스텀 고양이 (best_int8.onnx) | 정확도 최고 |
| **yolo_onnx** | **YOLOv8n COCO (yolov8n_int8.onnx)** | **인식 최고, 전력 주의** |
| yolo_tflite | YOLOv8n TFLite | 인식 불량 |

### 모델 변환 이력
- PC에서 `ultralytics`로 YOLOv8n.pt → ONNX → ONNX INT8 양자화
- Google Colab에서 YOLOv8n.pt → TFLite INT8 변환 (PC Python 3.14는 TF 미지원)
- 커스텀 고양이 모델 (best_int8.onnx): 이전 프로젝트에서 학습 완료, cat_tracker_tflite_rev1/ 폴더에 보관

### RPi5 필수 패키지
```bash
sudo pip3 install onnxruntime --break-system-packages     # YOLO ONNX용
sudo pip3 install ai-edge-litert --break-system-packages   # TFLite용
# MobileNet SSD는 OpenCV만 있으면 됨
```

### 모드 전환 구조
- PC control_panel Detect 드롭다운 → HTTP GET `http://<IP>:8000/mode/<name>`
- RPi5 camera_stream.py `detect_mode` 변수 분기
- 드롭다운 선택 후 `root.focus_set()` 으로 키보드 포커스 복귀

---

## 알려진 이슈
- toby.local mDNS가 TCP 연결에서 타임아웃 (SSH는 됨) → IP 직접 사용 (192.168.0.23)
- 서보모터 외부전원 사용 시 L298N 5V 레귤레이터 노이즈 → 별도 UBEC/레귤레이터 필요
- RPi5 서보 구동 시 전압 부족 경고 (빨간불) → 레귤레이터 분리로 완화
- YOLO ONNX 추론 시 CPU 풀로드 → 배터리 소모 큼, 필요할 때만 cat/yolo 모드 사용
- sudo 환경에서 `~` → `/root/` 됨 → 모델 경로 절대경로 필수 (`/home/toby/project/models/`)
- Detect 드롭다운 선택 후 키보드 포커스 빠짐 → `root.focus_set()` 으로 해결
- yolo_tflite 모드: COCO pretrained INT8 양자화 후 인식 정확도 심각하게 저하 → 사용 비추
- load_models()에서 global 선언 누락 시 모델 로딩 안 됨 → 반드시 전체 변수 global 선언

## GPS (NEO-6M) 연결 — 2026-05-30

### 배선 (RPi5)
| NEO-6M | RPi5 | 비고 |
|--------|------|------|
| VCC | pin 2 (5V) | 3.3V로는 동작 안 함 |
| GND | pin 6 (GND) | |
| TX | pin 10 (GPIO 15, RX) | TX↔RX 크로스 |
| RX | pin 8 (GPIO 14, TX) | |

### RPi5 UART 설정
- `/boot/firmware/config.txt`에 `dtoverlay=uart0-pi5` 추가 필요
- GPS 포트: `/dev/ttyAMA0` (9600 baud)
- TC23A 통신: `/dev/ttyAMA2` (115200 baud) — 별도 포트

### 데이터 흐름
```
NEO-6M (ttyAMA0, 9600)
  → uart_server.py (NMEA $GPRMC/$GPGGA 파싱)
  → "G:lat,lon,speed,sats" TCP 9001 브로드캐스트
  → control_panel.py (GPS 표시 + 경로 + 귀환)
```

### NMEA 파싱 (수동, pynmea2 불필요)
- `$GPRMC` → 위도, 경도, 속도 (knots→km/h)
- `$GPGGA` → 위성 수

### 패널 GPS 기능
| 기능 | 키 | 설명 |
|------|-----|------|
| 위치 표시 | - | LAT/LON/속도/위성 수 실시간 |
| 경로 기록 | - | 이동 궤적 2D 캔버스에 표시 |
| Home 저장 | H | 현재 GPS 좌표를 출발점으로 저장 |
| 귀환 | G | Home까지 GPS+IMU Yaw로 자동 이동 (3m 이내 도착 시 정지) |

### IP 공통 설정
- `pc/config.py`에 `RPI5_HOST` 한 곳에서 관리
- IP 변경 시 config.py만 수정하면 control_panel, voice_client 모두 적용

### 알려진 제한
- NEO-6M 정확도: ±2~3m
- 1Hz 업데이트 (1초 1회)
- 실외에서만 동작 (위성 신호 필요)
- Cold Start 시 위성 잡기까지 30초~2분

---

## RPi5 WiFi 변경 (nmcli)

### WiFi 목록 확인
```bash
sudo nmcli dev wifi list
```

### WiFi 연결 (새 네트워크)
```bash
sudo nmcli connection add type wifi con-name "이름" ssid "SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "비밀번호"
sudo nmcli connection up "이름"
```

### 기존 연결로 전환
```bash
sudo nmcli connection up "이름"
```

### 주의
- 연결 성공하면 SSH 끊어짐 → PC도 같은 WiFi로 변경 후 새 IP로 재접속
- RPi5 새 IP 확인: 핫스팟 앱에서 연결된 기기 목록 또는 `hostname -I`
- IP 변경 시 `pc/config.py`의 `RPI5_HOST`만 수정

---

## RPi5 자동 실행 (systemd)

### 서비스 등록
```bash
sudo cp ~/project/rc-car.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rc-car.service
```

### 동작
- RPi5 전원 ON → 자동으로 camera_stream.py + uart_server.py 실행
- 1~2분 대기 후 PC에서 control_panel Connect

### 수동 제어
```bash
sudo systemctl stop rc-car      # 정지
sudo systemctl start rc-car     # 시작
sudo systemctl restart rc-car   # 재시작
sudo systemctl status rc-car    # 상태 확인
```

### 서비스 파일: `/etc/systemd/system/rc-car.service`
- User=root (PWM/UART 접근 필요)
- ExecStart=/bin/bash /home/toby/project/rpi5_start.sh
- Restart=on-failure, RestartSec=5

---

## 다음에 할 것
- 캘리브레이션 / TEST 모드 / 자율주행 수동모드 UI (panel.py 참고)
- 고양이 추적 (서보 자동 추적) 구현
- AI Vision 패널에 인식 결과 텍스트 표시
- RPi5 전원 문제 근본 해결 (공식 27W 어댑터)
- best.pt → TFLite 변환 (Colab에서) 후 cat_custom_tflite 모드 추가
