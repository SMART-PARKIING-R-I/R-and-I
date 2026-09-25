import os
import json
import cv2
import threading
import requests
import numpy as np
from ultralytics import YOLO
from shapely.geometry import Polygon, box

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
CAMERAS_CONFIG = os.path.join(BASE_DIR, "cameras.json")
BACKEND_URL = "http://localhost:5000/api/occupancy"

OVERLAP_THRESHOLD = 0.30
REQUIRED_FRAMES = 10

class SingleCameraWorker(threading.Thread):
    def __init__(self, cam_info, shared_model):
        super().__init__()
        self.cam_id = cam_info["camera_id"]
        self.lot_id = cam_info["lot_id"]
        self.source = cam_info["source"]
        self.spots_file = os.path.join(BASE_DIR, cam_info["spots_file"])
        self.model = shared_model
        
        self.vehicle_classes = [2, 3, 5, 7]
        self.spots = self.load_spots(self.spots_file)
        self.spot_buffers = {spot["id"]: 0 for spot in self.spots}
        self.spot_states = {spot["id"]: "vacant" for spot in self.spots}
        self.last_sent_payload = None
        self.running = True

    def load_spots(self, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
        return [{"id": item["spot_id"], "polygon": Polygon(item["polygon"]), "raw_coords": item["polygon"]} for item in data]

    def run(self):
        cap = cv2.VideoCapture(self.source)
        print(f"[THREAD STARTED]: {self.cam_id} listening to {self.source}")

        while self.running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                if isinstance(self.source, str) and not self.source.startswith("http"):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break

            # YOLO inference
            results = self.model(frame, verbose=False)[0]
            detected_vehicles = [box(*r.xyxy[0].tolist()) for r in results.boxes if int(r.cls[0]) in self.vehicle_classes]

            current_spots_status = []
            for spot in self.spots:
                s_id = spot["id"]
                raw_occupied = any((spot["polygon"].intersection(v).area / spot["polygon"].area) >= OVERLAP_THRESHOLD for v in detected_vehicles)

                # Buffer smoothing
                self.spot_buffers[s_id] = min(REQUIRED_FRAMES, self.spot_buffers[s_id] + 1) if raw_occupied else max(0, self.spot_buffers[s_id] - 1)
                
                if self.spot_buffers[s_id] >= REQUIRED_FRAMES:
                    self.spot_states[s_id] = "occupied"
                elif self.spot_buffers[s_id] == 0:
                    self.spot_states[s_id] = "vacant"

                current_spots_status.append({"spot_id": s_id, "status": self.spot_states[s_id]})

                # Render overlay
                color = (0, 0, 255) if self.spot_states[s_id] == "occupied" else (0, 255, 0)
                pts_np = np.array(spot["raw_coords"], np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts_np], isClosed=True, color=color, thickness=2)

            payload = {
                "camera_id": self.cam_id,
                "lot_id": self.lot_id,
                "spots": current_spots_status
            }

            self.dispatch_payload(payload)

            # Display feed window for this specific camera
            cv2.imshow(f"Feed: {self.cam_id} ({self.lot_id})", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.running = False
                break

        cap.release()
        cv2.destroyWindow(f"Feed: {self.cam_id} ({self.lot_id})")

    def dispatch_payload(self, payload):
        if payload != self.last_sent_payload:
            print(f"[{self.cam_id} UPDATE]:", json.dumps(payload, indent=2))
            try:
                requests.post(BACKEND_URL, json=payload, timeout=0.2)
            except Exception:
                pass
            self.last_sent_payload = payload

if __name__ == "__main__":
    print("[INIT]: Loading shared YOLOv8 Model...")
    shared_yolo = YOLO(MODEL_PATH)

    with open(CAMERAS_CONFIG, 'r') as f:
        camera_list = json.load(f)

    threads = []
    for cam_info in camera_list:
        worker = SingleCameraWorker(cam_info, shared_yolo)
        worker.start()
        threads.append(worker)

    for t in threads:
        t.join()