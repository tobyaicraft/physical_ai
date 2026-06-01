import cv2
from pathlib import Path

img_dir = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/images")
lbl_dir = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/labels")
out_dir = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/preview")
out_dir.mkdir(exist_ok=True)

for img_path in sorted(img_dir.glob("*.jpg")):
    lbl_path = lbl_dir / (img_path.stem + ".txt")
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]

    if lbl_path.exists() and lbl_path.stat().st_size > 0:
        with open(lbl_path) as f:
            for line in f:
                parts = line.strip().split()
                xc, yc, bw, bh = map(float, parts[1:])
                x1 = int((xc - bw/2) * w)
                y1 = int((yc - bh/2) * h)
                x2 = int((xc + bw/2) * w)
                y2 = int((yc + bh/2) * h)
                cv2.rectangle(img, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(img, "cat", (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    cv2.imwrite(str(out_dir / img_path.name), img)

total = len(list(img_dir.glob("*.jpg")))
print(f"{total}장 preview 저장 완료 → {out_dir}")
