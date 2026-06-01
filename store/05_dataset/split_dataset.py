import shutil
from pathlib import Path

src_img = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/images")
src_lbl = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/labels")
dst     = Path("D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/my_cat")

# 폴더 생성
for split in ["train", "val"]:
    (dst / "images" / split).mkdir(parents=True, exist_ok=True)
    (dst / "labels" / split).mkdir(parents=True, exist_ok=True)

# cat1~8 → train (frame_0000 ~ frame_0221)
# cat9~10 → val  (frame_0222 ~ frame_0335)
train_count = 0
val_count   = 0

for img_path in sorted(src_img.glob("*.jpg")):
    idx      = int(img_path.stem.split("_")[1])
    lbl_path = src_lbl / (img_path.stem + ".txt")
    split    = "train" if idx <= 221 else "val"

    shutil.copy(img_path, dst / "images" / split / img_path.name)
    if lbl_path.exists():
        shutil.copy(lbl_path, dst / "labels" / split / lbl_path.name)

    if split == "train":
        train_count += 1
    else:
        val_count += 1

# data.yaml 생성
yaml_content = f"""path: {dst.as_posix()}
train: images/train
val:   images/val
nc: 1
names:
  0: russian_blue
"""
(dst / "data.yaml").write_text(yaml_content)

print(f"train : {train_count}장")
print(f"val   : {val_count}장")
print(f"data.yaml 생성 완료")
print(f"저장 위치 : {dst}")
