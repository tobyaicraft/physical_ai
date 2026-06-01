from ultralytics import YOLO

model = YOLO("yolov8n.pt")
results = model("cat.png")

for r in results:
    cats = [box for box in r.boxes if model.names[int(box.cls[0])] == "cat"]

    if cats:
        for box in cats:
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            print(f"고양이 발견!")
            print(f"  정확도 : {conf:.2%}")
            print(f"  위치   : ({x1:.0f},{y1:.0f}) ~ ({x2:.0f},{y2:.0f})")
    else:
        print("고양이 없음")

results[0].save("detected.jpg")
print("detected.jpg 저장 완료")
