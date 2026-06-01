import cv2
import numpy as np

# ball.jpg 불러오기
img = cv2.imread("ball.jpg")

# BGR → HSV 변환
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# 파란색 마스크 생성
lower_blue = np.array([100, 80, 50])
upper_blue = np.array([130, 255, 255])
mask = cv2.inRange(hsv, lower_blue, upper_blue)

# 노이즈 제거
mask_clean = cv2.erode(mask, None, iterations=1)
mask_clean = cv2.dilate(mask_clean, None, iterations=1)

# 컨투어 찾기
contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL,
                                cv2.CHAIN_APPROX_SIMPLE)
if contours:
    # 가장 큰 파란 영역 선택
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)

    if area > 500:
        x, y, w, h = cv2.boundingRect(largest)
        cx = x + w // 2   # 중심 X
        cy = y + h // 2   # 중심 Y

        print(f"파란공 발견!")
        print(f"  바운딩 박스: x={x}, y={y}, w={w}, h={h}")
        print(f"  중심 좌표:  cx={cx}, cy={cy}")
        print(f"  면적:       {int(area)}")

        # 시각화: 박스 + 중심점 그리기
        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.circle(img, (cx, cy), 5, (0, 0, 255), -1)
        cv2.putText(img, f"({cx},{cy})", (cx+10, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imwrite("bbox_result.jpg", img)
        print("  bbox_result.jpg 저장 완료")
else:
    print("파란색 없음")
