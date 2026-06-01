import cv2
import os

video_dir  = "D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset"
output_dir = "D:/01_WorkPlace/202_Pysical_AI/physical_ai/store/05_dataset/images"
os.makedirs(output_dir, exist_ok=True)

total = 159  # 기존 추출분 이어서
new_files = ["cat6.mp4", "cat7.mp4", "cat8.mp4", "cat9.mp4", "cat10.mp4"]
for filename in new_files:

    cap      = cv2.VideoCapture(os.path.join(video_dir, filename))
    fps      = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, int(fps * 0.5))  # 0.5초 간격

    i = 0
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if i % interval == 0:
            cv2.imwrite(f"{output_dir}/frame_{total:04d}.jpg", frame)
            total += 1
            count += 1
        i += 1
    cap.release()
    print(f"{filename}: {count}장 추출")

print(f"\n총 {total}장 추출 완료 → {output_dir}")
