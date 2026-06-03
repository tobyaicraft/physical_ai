#!/bin/bash
# ================================================================
#  RC Car 강제 런처 (fstart)
#  systemd 서비스 정지/비활성화 후 start.sh 실행
#  사용법: source ~/virenv.sh → bash fstart.sh
# ================================================================

if [ "$(id -u)" -ne 0 ]; then
    exec sudo -E bash "$0" "$@"
fi

echo "[fstart] rc-car 서비스 정지 및 비활성화..."
systemctl stop rc-car    2>/dev/null && echo "  stopped"
systemctl disable rc-car 2>/dev/null && echo "  disabled"

# 서비스가 쓰던 프로세스/포트/카메라 강제 정리
pkill -f camera_stream 2>/dev/null
pkill -f uart_server   2>/dev/null
pkill -f libcamera     2>/dev/null
pkill -f rpicam        2>/dev/null
fuser -k /dev/media0 /dev/media3 2>/dev/null
fuser -k 9000/tcp 9001/tcp 8000/tcp 2>/dev/null
sleep 4

echo "[fstart] start.sh 실행..."

# sudo 시 HOME 경로 보정
if [ -n "$SUDO_USER" ]; then
    USER_HOME="/home/$SUDO_USER"
else
    USER_HOME="$HOME"
fi

exec bash "$USER_HOME/rccar/rccar_start.sh"
