from ultralytics import YOLO
from pathlib import Path
import cv2

model   = YOLO("yolov8n.pt")
img_dir = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/images")
lbl_dir = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/labels")
lbl_dir.mkdir(exist_ok=True)

CAT_CLASS_ID = 15  # COCO cat

labeled = 0
skipped = 0

for img_path in sorted(img_dir.glob("*.jpg")):
    img    = cv2.imread(str(img_path))
    h, w   = img.shape[:2]
    results = model(img, verbose=False)[0]

    lines = []
    for box in results.boxes:
        if int(box.cls[0]) == CAT_CLASS_ID and float(box.conf[0]) > 0.5:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            xc = (x1 + x2) / 2 / w
            yc = (y1 + y2) / 2 / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            lines.append(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

    out_path = lbl_dir / (img_path.stem + ".txt")
    out_path.write_text("\n".join(lines))

    if lines:
        labeled += 1
    else:
        skipped += 1

print(f"총 {labeled + skipped}장 처리")
print(f"  라벨 있음 : {labeled}장")
print(f"  고양이 없음: {skipped}장 (빈 txt 생성)")
print(f"라벨 저장 위치 : {lbl_dir}")
