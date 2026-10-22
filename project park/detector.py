import os
import json
import cv2
import threading
import time
import requests
import numpy as np
from ultralytics import YOLO
from shapely.geometry import Polygon, box
from shapely.validation import make_valid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
CAMERAS_CONFIG = os.path.join(BASE_DIR, "cameras.json")
BACKEND_URL = "http://127.0.0.1:5000/api/occupancy"

# Original reference image dimensions used during drawing
MAPPING_WIDTH = 2400.0
MAPPING_HEIGHT = 1480.0

# On-screen display height limit for desktop viewing
DISPLAY_HEIGHT = 720

OVERLAP_THRESHOLD = 0.30
REQUIRED_FRAMES = 10
DISPATCH_RETRY_SECONDS = 1.0
MAX_DISPATCH_RETRY_SECONDS = 30.0
IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"}

class SingleCameraWorker(threading.Thread):
    def __init__(self, cam_info, shared_model):
        super().__init__()
        self.cam_id = cam_info["camera_id"]
        self.lot_id = cam_info["lot_id"]
        self.source = cam_info["source"]
        self.spots_file = os.path.join(BASE_DIR, cam_info["spots_file"])
        self.model = shared_model
        
        self.vehicle_classes = [2, 3, 5, 7]  # Car, motorcycle, bus, truck
        self.spots = self.load_spots(self.spots_file)
        self.spot_buffers = {spot["id"]: 0 for spot in self.spots}
        self.spot_states = {spot["id"]: "vacant" for spot in self.spots}
        self.last_sent_payload = None
        self.last_attempted_payload = None
        self.next_dispatch_at = 0.0
        self.retry_delay_seconds = DISPATCH_RETRY_SECONDS
        self.running = True

    def load_spots(self, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        spots = []
        for item in data:
            poly = Polygon(item["polygon"])
            if not poly.is_valid:
                poly = make_valid(poly)  # Auto-repairs self-intersecting lines
            spots.append({
                "id": item["spot_id"],
                "polygon": poly,
                "raw_coords": item["polygon"]
            })
        return spots

    def process_frame(self, frame, smooth=True):
        frame_h, frame_w = frame.shape[:2]

        # Calculate dynamic resolution scaling ratios
        scale_x = frame_w / MAPPING_WIDTH
        scale_y = frame_h / MAPPING_HEIGHT

        # Detect vehicles in live frame
        results = self.model(frame, verbose=False)[0]
        detected_vehicles = [
            box(*result.xyxy[0].tolist())
            for result in results.boxes
            if int(result.cls[0]) in self.vehicle_classes
        ]

        spots_status = []
        for spot in self.spots:
            spot_id = spot["id"]
            
            # Dynamically scale polygon coordinates to match current frame resolution
            scaled_coords = [
                [int(pt[0] * scale_x), int(pt[1] * scale_y)] 
                for pt in spot["raw_coords"]
            ]
            scaled_polygon = Polygon(scaled_coords)
            if not scaled_polygon.is_valid:
                scaled_polygon = make_valid(scaled_polygon)

            # Check bounding box spatial overlap
            raw_occupied = any(
                scaled_polygon.intersection(vehicle).area / scaled_polygon.area
                >= OVERLAP_THRESHOLD
                for vehicle in detected_vehicles
            )

            # Frame buffer smoothing to reduce false toggles
            if smooth:
                self.spot_buffers[spot_id] = (
                    min(REQUIRED_FRAMES, self.spot_buffers[spot_id] + 1)
                    if raw_occupied
                    else max(0, self.spot_buffers[spot_id] - 1)
                )
                if self.spot_buffers[spot_id] >= REQUIRED_FRAMES:
                    self.spot_states[spot_id] = "occupied"
                elif self.spot_buffers[spot_id] == 0:
                    self.spot_states[spot_id] = "vacant"
            else:
                self.spot_states[spot_id] = (
                    "occupied" if raw_occupied else "vacant"
                )

            spots_status.append({
                "spot_id": spot_id,
                "status": self.spot_states[spot_id],
            })

            # Draw status bounding polygon (Red = Occupied, Green = Vacant)
            color = (
                (0, 0, 255)
                if self.spot_states[spot_id] == "occupied"
                else (0, 255, 0)
            )
            points = np.array(scaled_coords, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [points], isClosed=True, color=color, thickness=2)

        payload = {
            "camera_id": self.cam_id,
            "lot_id": self.lot_id,
            "spots": spots_status,
        }
        return frame, payload

    def run(self):
        window_name = f"Feed: {self.cam_id} ({self.lot_id})"
        cap = None
        window_displayed = False
        source_is_image = (
            isinstance(self.source, str)
            and os.path.splitext(self.source)[1].lower() in IMAGE_EXTENSIONS
        )
        source_is_local_file = (
            isinstance(self.source, str)
            and not self.source.lower().startswith(
                ("http://", "https://", "rtsp://", "rtmp://")
            )
        )

        print(f"[THREAD STARTED]: {self.cam_id} listening to {self.source}")
        try:
            if source_is_image:
                image_path = os.path.join(BASE_DIR, self.source)
                frame = cv2.imread(image_path)
                if frame is None:
                    print(f"[{self.cam_id} ERROR] Could not read image: {image_path}")
                    return

                frame, payload = self.process_frame(frame, smooth=False)
                self.dispatch_payload(payload)

                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                cv2.imshow(window_name, frame)
                window_displayed = True

                while self.running and cv2.waitKey(20) & 0xFF != ord("q"):
                    pass
                self.running = False
                return

            capture_source = (
                os.path.join(BASE_DIR, self.source)
                if source_is_local_file
                else self.source
            )
            cap = cv2.VideoCapture(capture_source)
            if not cap.isOpened():
                print(
                    f"[{self.cam_id} ERROR] Could not open video source: "
                    f"{capture_source}"
                )
                return

            has_read_frame = False
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    if source_is_local_file and has_read_frame:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    
                    # IP Camera dropped a frame: wait and reconnect instead of dying
                    print(f"[{self.cam_id} WARNING] Stream dropped. Reconnecting in 3s...")
                    time.sleep(3)
                    cap.release()
                    cap = cv2.VideoCapture(capture_source)
                    continue

                has_read_frame = True
                frame, payload = self.process_frame(frame)
                self.dispatch_payload(payload)

                if not window_displayed:
                    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                    window_displayed = True

                # Scale preview window down so it fits on monitor displays
                frame_h, frame_w = frame.shape[:2]
                disp_scale = frame_h / DISPLAY_HEIGHT
                disp_w = int(frame_w / disp_scale)
                display_frame = cv2.resize(frame, (disp_w, DISPLAY_HEIGHT))

                cv2.imshow(window_name, display_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.running = False
                    break
        finally:
            if cap is not None:
                cap.release()
            if window_displayed:
                cv2.destroyWindow(window_name)

    def dispatch_payload(self, payload):
        if payload == self.last_sent_payload:
            self.last_attempted_payload = None
            self.next_dispatch_at = 0.0
            self.retry_delay_seconds = DISPATCH_RETRY_SECONDS
            return

        if payload != self.last_attempted_payload:
            self.last_attempted_payload = payload
            self.next_dispatch_at = 0.0
            self.retry_delay_seconds = DISPATCH_RETRY_SECONDS
            print(
                f"[{self.cam_id} UPDATE] Occupancy changed for "
                f"{len(payload['spots'])} spots; sending to backend."
            )

        if time.monotonic() < self.next_dispatch_at:
            return

        try:
            response = requests.post(BACKEND_URL, json=payload, timeout=2.0)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(
                f"[{self.cam_id} ERROR] Occupancy update failed; "
                f"retrying in {self.retry_delay_seconds:g}s: {exc}"
            )
            self.next_dispatch_at = time.monotonic() + self.retry_delay_seconds
            self.retry_delay_seconds = min(
                self.retry_delay_seconds * 2,
                MAX_DISPATCH_RETRY_SECONDS,
            )
            return

        self.last_sent_payload = payload
        self.last_attempted_payload = None
        self.next_dispatch_at = 0.0
        self.retry_delay_seconds = DISPATCH_RETRY_SECONDS

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