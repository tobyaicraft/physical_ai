from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolov8n.pt")  # COCO 사전학습 가중치로 처음부터

    model.train(
        data="my_cat/data.yaml",
        epochs=200,
        imgsz=320,
        batch=16,
        name="russian_blue_v2",
        freeze=10,      # 백본 고정, 헤드만 학습
        lr0=0.001,      # 낮은 학습률
        patience=30,
        device=0,
    )
