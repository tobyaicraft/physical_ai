import cv2
import numpy as np

# 파란 공 이미지 직접 생성 (640x480 검정 배경에 파란 원)
img = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.circle(img, (320, 240), 100, (255, 50, 30), -1)  # BGR: 파란색 원
cv2.imwrite("ball.jpg", img)
print("ball.jpg 생성 완료")

# HSV 변환
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 파란색 범위
lower_blue = np.array([100, 80, 50])
upper_blue = np.array([130, 255, 255])

# 마스크 생성
mask = cv2.inRange(hsv, lower_blue, upper_blue)

# 결과
result = cv2.bitwise_and(img, img, mask=mask)

cv2.imwrite("mask.jpg", mask)
cv2.imwrite("result.jpg", result)
print("완료! mask.jpg, result.jpg 저장됨")
