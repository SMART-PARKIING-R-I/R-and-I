import os
import json
import cv2
import numpy as np
from shapely.geometry import Polygon, box

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "bac_park_empty.jpg")
SPOTS_FILE = os.path.join(BASE_DIR, "parking_spots.json")

# Virtual vehicle bounding box dimensions (width and height in pixels)
CAR_WIDTH = 60
CAR_HEIGHT = 100
OVERLAP_THRESHOLD = 0.3  # Occupied if car covers 30%+ of the spot area

# Global state
mouse_x, mouse_y = -1, -1

def mouse_move(event, x, y, flags, param):
    global mouse_x, mouse_y
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_x, mouse_y = x, y

def load_spots(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    spots = []
    for item in data:
        spots.append({
            "id": item["spot_id"],
            "polygon": Polygon(item["polygon"]),
            "raw_coords": item["polygon"]
        })
    return spots

if __name__ == "__main__":
    if not os.path.exists(IMAGE_PATH) or not os.path.exists(SPOTS_FILE):
        print("Error: Ensure 'bac_parking_empty.jpg' and 'parking_spots.json' exist in project park.")
        exit()

    spots = load_spots(SPOTS_FILE)
    base_image = cv2.imread(IMAGE_PATH)

    cv2.namedWindow("BAC Interactive Parking Test")
    cv2.setMouseCallback("BAC Interactive Parking Test", mouse_move)

    print("=== BAC CURSOR CAR SIMULATION ===")
    print("Move your mouse cursor over the mapped parking spaces.")
    print("Press 'q' in the image window to exit.")

    last_payload = []

    while True:
        display_frame = base_image.copy()
        current_payload = []

        # 1. Create a simulated vehicle box centered at the mouse cursor
        if mouse_x != -1 and mouse_y != -1:
            x1 = mouse_x - (CAR_WIDTH // 2)
            y1 = mouse_y - (CAR_HEIGHT // 2)
            x2 = mouse_x + (CAR_WIDTH // 2)
            y2 = mouse_y + (CAR_HEIGHT // 2)

            cursor_car_box = box(x1, y1, x2, y2)

            # Draw the 'Cursor Car' in Blue
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 100, 0), 2)
            cv2.putText(display_frame, "CAR CURSOR", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 100, 0), 1)
        else:
            cursor_car_box = None

        # 2. Check overlap against all drawn parking spots
        for spot in spots:
            spot_polygon = spot["polygon"]
            is_occupied = False

            if cursor_car_box and spot_polygon.intersects(cursor_car_box):
                intersection_area = spot_polygon.intersection(cursor_car_box).area
                overlap_ratio = intersection_area / spot_polygon.area

                if overlap_ratio >= OVERLAP_THRESHOLD:
                    is_occupied = True

            status_str = "occupied" if is_occupied else "vacant"
            current_payload.append({"spot_id": spot["id"], "status": status_str})

            # Draw status overlay (Red = Occupied, Green = Vacant)
            color = (0, 0, 255) if is_occupied else (0, 255, 0)
            pts_np = np.array(spot["raw_coords"], np.int32).reshape((-1, 1, 2))
            
            # Fill polygon lightly if occupied
            if is_occupied:
                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [pts_np], color)
                cv2.addWeighted(overlay, 0.3, display_frame, 0.7, 0, display_frame)

            cv2.polylines(display_frame, [pts_np], isClosed=True, color=color, thickness=2)
            cv2.putText(display_frame, f"{spot['id']}: {status_str}", 
                        (spot["raw_coords"][0][0], spot["raw_coords"][0][1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # 3. Print live state changes to the terminal console
        if current_payload != last_payload:
            print("[STATE UPDATE]:", json.dumps(current_payload, indent=2))
            last_payload = current_payload

        cv2.imshow("BAC Interactive Parking Test", display_frame)

        if cv2.waitKey(20) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()