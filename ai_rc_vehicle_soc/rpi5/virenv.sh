#!/bin/bash
sudo pkill -f camera_stream
sudo pkill -f uart_server
sudo pkill -f libcamera
sudo pkill -f rpicam
sudo fuser -k /dev/media0 /dev/media3 2>/dev/null
sudo fuser -k 9000/tcp 9001/tcp 8000/tcp 2>/dev/null
sleep 4
source ~/rccar-env/bin/activate
cd ~/rccar
