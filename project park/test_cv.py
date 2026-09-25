import cv2
import shapely
import ultralytics
from ultralytics import YOLO

print("=== Person 2 Environment Ready ===")
print(f"OpenCV: {cv2.__version__}")
print(f"Ultralytics: {ultralytics.__version__}")
print(f"Shapely: {shapely.__version__}")

# Downloads and verifies the lightweight YOLOv8 Nano weights
model = YOLO("yolov8n.pt")
print("YOLOv8 Nano model initialized successfully!")