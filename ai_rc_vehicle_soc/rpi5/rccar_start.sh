#!/bin/bash
# ================================================================
#  RC Car 런처 (rccar-env 기준)
#  사용법: source ~/virenv.sh  →  bash start.sh
# ================================================================

# sudo 아니면 자동으로 sudo 재실행
if [ "$(id -u)" -ne 0 ]; then
    exec sudo -E bash "$0" "$@"
fi

# sudo 시 HOME 경로 보정
if [ -n "$SUDO_USER" ]; then
    USER_HOME="/home/$SUDO_USER"
else
    USER_HOME="$HOME"
fi

PYTHON="$USER_HOME/rccar-env/bin/python3"
PROJECT_DIR="$USER_HOME/rccar"
CAM_SCRIPT="$PROJECT_DIR/camera_stream.py"
UART_SCRIPT="$PROJECT_DIR/uart_server.py"
LOG_CAM="/tmp/rccar_cam.log"
LOG_UART="/tmp/rccar_uart.log"

# 파일 확인
for f in "$CAM_SCRIPT" "$UART_SCRIPT"; do
    if [ ! -f "$f" ]; then
        echo "[Error] 파일 없음: $f"
        exit 1
    fi
done

# 기존 프로세스 정리
pkill -f camera_stream 2>/dev/null
pkill -f uart_server   2>/dev/null
pkill -f libcamera     2>/dev/null
pkill -f rpicam        2>/dev/null
fuser -k /dev/media0 /dev/media3 2>/dev/null
fuser -k 9000/tcp 9001/tcp 8000/tcp 2>/dev/null
sleep 4

# 로그 초기화
> "$LOG_CAM"
> "$LOG_UART"

# 종료 시 정리
cleanup() {
    echo ""
    echo "[Exit] 종료 중..."
    kill "$CAM_PID" "$UART_PID" "$TAIL_CAM_PID" "$TAIL_UART_PID" 2>/dev/null
    sleep 0.3
    kill -9 "$CAM_PID" "$UART_PID" 2>/dev/null
    echo "[Exit] 완료"
    exit 0
}
trap cleanup INT TERM

RPI_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================"
echo "  RC Car Launcher (rccar-env)"
echo "========================================"
echo "  Python : $PYTHON"
echo "  Dir    : $PROJECT_DIR"
echo "  Log    : $LOG_CAM"
echo "           $LOG_UART"
echo ""

# 1) 카메라 스트리밍 + 검출 — 일반 유저로 실행 (picamera2는 root 불필요)
if [ -n "$SUDO_USER" ]; then
    sudo -u "$SUDO_USER" "$PYTHON" -u "$CAM_SCRIPT" >> "$LOG_CAM" 2>&1 &
else
    "$PYTHON" -u "$CAM_SCRIPT" >> "$LOG_CAM" 2>&1 &
fi
CAM_PID=$!
echo "  [1/2] camera_stream.py  (PID $CAM_PID)"

# 실시간 로그 출력
tail -f "$LOG_CAM" | sed 's/^/[CAM ] /' &
TAIL_CAM_PID=$!

sleep 2

# 2) UART 서버 (로그 파일로)
"$PYTHON" -u "$UART_SCRIPT" >> "$LOG_UART" 2>&1 &
UART_PID=$!
echo "  [2/2] uart_server.py    (PID $UART_PID)"

# 실시간 로그 출력
tail -f "$LOG_UART" | sed 's/^/[UART] /' &
TAIL_UART_PID=$!

echo ""
echo "========================================"
echo "  카메라:  http://${RPI_IP}:8000"
echo "  키보드:  PC에서 run.bat 실행"
echo "  센서:    TCP :9001"
echo "========================================"
echo "  종료: Ctrl+C"
echo "========================================"
echo ""

# 프로세스 감시 루프 — 한쪽이 죽으면 원인 출력 후 종료
while true; do
    sleep 3
    if ! kill -0 "$CAM_PID" 2>/dev/null; then
        echo ""
        echo "[!!] camera_stream.py 종료됨 (PID $CAM_PID)"
        echo "--- 마지막 로그 ---"
        tail -20 "$LOG_CAM"
        echo "-------------------"
        cleanup
    fi
    if ! kill -0 "$UART_PID" 2>/dev/null; then
        echo ""
        echo "[!!] uart_server.py 종료됨 (PID $UART_PID)"
        echo "--- 마지막 로그 ---"
        tail -20 "$LOG_UART"
        echo "-------------------"
        cleanup
    fi
done
