import os
import json
import cv2
import threading
import time
import requests
import numpy as np
from ultralytics import YOLO
from shapely.geometry import Polygon, box

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
CAMERAS_CONFIG = os.path.join(BASE_DIR, "cameras.json")
BACKEND_URL = "http://127.0.0.1:5000/api/occupancy"

OVERLAP_THRESHOLD = 0.30
REQUIRED_FRAMES = 10
DISPATCH_RETRY_SECONDS = 1.0
MAX_DISPATCH_RETRY_SECONDS = 30.0
IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"}
PREVIEW_WIDTH = 1920
PREVIEW_HEIGHT = 1080

class SingleCameraWorker(threading.Thread):
    def __init__(self, cam_info, shared_model):
        super().__init__()
        self.cam_id = cam_info["camera_id"]
        self.lot_id = cam_info["lot_id"]
        self.source = cam_info["source"]
        self.spots_file = os.path.join(BASE_DIR, cam_info["spots_file"])
        coordinate_reference = cam_info.get("coordinate_reference")
        self.coordinate_reference_size = None
        if coordinate_reference:
            # Spot polygons are drawn in this image's pixel coordinates.
            reference_path = os.path.join(BASE_DIR, coordinate_reference)
            reference_image = cv2.imread(reference_path)
            if reference_image is None:
                raise ValueError(f"Could not read coordinate reference: {reference_path}")
            self.coordinate_reference_size = (
                reference_image.shape[1],
                reference_image.shape[0],
            )
        self.model = shared_model
        
        self.vehicle_classes = [2, 3, 5, 7]
        self.spots = self.load_spots(self.spots_file)
        # The buffer filters brief detection flicker before a spot changes state.
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
        return [{"id": item["spot_id"], "polygon": Polygon(item["polygon"]), "raw_coords": item["polygon"]} for item in data]

    def process_frame(self, frame, smooth=True):
        results = self.model(frame, verbose=False)[0]
        frame_height, frame_width = frame.shape[:2]
        if self.coordinate_reference_size is None:
            scale_x = scale_y = 1.0
        else:
            # Convert reference-image coordinates into this frame's pixel coordinates.
            reference_width, reference_height = self.coordinate_reference_size
            scale_x = frame_width / reference_width
            scale_y = frame_height / reference_height

        detected_vehicles = [
            box(*result.xyxy[0].tolist())
            for result in results.boxes
            if int(result.cls[0]) in self.vehicle_classes
        ]

        spots_status = []
        for spot in self.spots:
            spot_id = spot["id"]
            frame_coords = [
                [round(x * scale_x), round(y * scale_y)]
                for x, y in spot["raw_coords"]
            ]
            frame_polygon = Polygon(frame_coords)
            raw_occupied = any(
                # A vehicle counts only when it covers at least the configured spot-area fraction.
                frame_polygon.intersection(vehicle).area / frame_polygon.area
                >= OVERLAP_THRESHOLD
                for vehicle in detected_vehicles
            )

            if smooth:
                # Require repeated evidence to fill or clear the buffer before changing status.
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

            color = (
                (0, 0, 255)
                if self.spot_states[spot_id] == "occupied"
                else (0, 255, 0)
            )
            points = np.array(frame_coords, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [points], isClosed=True, color=color, thickness=2)

        payload = {
            "camera_id": self.cam_id,
            "lot_id": self.lot_id,
            "spots": spots_status,
        }
        return frame, payload

    @staticmethod
    def show_preview(window_name, frame, create_window):
        if create_window:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, PREVIEW_WIDTH, PREVIEW_HEIGHT)
        cv2.imshow(window_name, frame)

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
                # A still-image demo is processed once; it is not looped as a camera/video feed.
                image_path = os.path.join(BASE_DIR, self.source)
                frame = cv2.imread(image_path)
                if frame is None:
                    print(f"[{self.cam_id} ERROR] Could not read image: {image_path}")
                    return

                frame, payload = self.process_frame(frame, smooth=False)
                self.dispatch_payload(payload)
                self.show_preview(window_name, frame, create_window=True)
                window_displayed = True
                # Keep the still-image preview open until the user quits.
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
                    print(f"[{self.cam_id} ERROR] Could not read a frame from source.")
                    break

                has_read_frame = True
                frame, payload = self.process_frame(frame)
                self.dispatch_payload(payload)
                self.show_preview(
                    window_name,
                    frame,
                    create_window=not window_displayed,
                )
                window_displayed = True
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.running = False
                    break
        finally:
            if cap is not None:
                cap.release()
            # Some camera-open/read failures happen before OpenCV creates a preview window.
            if window_displayed:
                cv2.destroyWindow(window_name)

    def dispatch_payload(self, payload):
        # Avoid resending an unchanged state after the API has acknowledged it.
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
            # Keep the latest state and retry later rather than blocking the camera worker.
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

    # Camera settings and their spot/reference-image paths are defined in cameras.json.
    with open(CAMERAS_CONFIG, 'r') as f:
        camera_list = json.load(f)

    threads = []
    for cam_info in camera_list:
        worker = SingleCameraWorker(cam_info, shared_yolo)
        worker.start()
        threads.append(worker)

    for t in threads:
        t.join()