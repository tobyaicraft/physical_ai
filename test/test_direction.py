import cv2
import numpy as np


def get_direction(cx, w):
    norm_x = (cx - W/2) / (W/2)

    if norm_x < -0.2:
        direction = "LEFT"
    elif norm_x > 0.2:
        direction = "RIGHT"
    else:
        direction = "CENTER"

    size_ratio = w / W

    return norm_x, direction, size_ratio


img = cv2.imread("left_ball.png")
H, W = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

lower_blue = np.array([100, 80, 50])
upper_blue = np.array([130, 255, 255])
mask = cv2.inRange(hsv, lower_blue, upper_blue)
mask = cv2.erode(mask, None, iterations=1)
mask = cv2.dilate(mask, None, iterations=1)

contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
if contours:
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) > 500:
        x, y, w, h = cv2.boundingRect(largest)
        cx = x + w // 2
        cy = y + h // 2

        norm_x, direction, size_ratio = get_direction(cx, w)

        print(f"중심 좌표  : ({cx}, {cy})")
        print(f"norm_x     : {norm_x:.2f}")
        print(f"direction  : {direction}")
        print(f"size_ratio : {size_ratio:.2f} {'(가까움!)' if size_ratio > 0.5 else ''}")

        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.circle(img, (cx, cy), 5, (0, 0, 255), -1)
        cv2.putText(img, f"{direction} ({norm_x:.2f})",
                    (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        cv2.imwrite("direction_result.jpg", img)
        print("direction_result.jpg 저장 완료")
else:
    print("파란색 없음")
