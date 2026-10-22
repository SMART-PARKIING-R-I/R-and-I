import os
import cv2
import json
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "bac_park_empty.jpg")
OUTPUT_JSON = os.path.join(BASE_DIR, "configs", "parking_spots.json")

current_polygon = []
all_spots = []
spot_counter = 1
img = None
img_copy = None


def redraw_overlay():
    global img_copy

    img_copy = img.copy()
    for spot in all_spots:
        points = spot["polygon"]
        points_np = np.array(points, dtype="int32").reshape((-1, 1, 2))
        cv2.polylines(img_copy, [points_np], isClosed=True, color=(255, 0, 0), thickness=2)
        cv2.putText(
            img_copy,
            spot["spot_id"],
            (points[0][0], points[0][1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    for index, point in enumerate(current_polygon):
        cv2.circle(img_copy, tuple(point), 5, (0, 255, 0), -1)
        if index:
            cv2.line(
                img_copy,
                tuple(current_polygon[index - 1]),
                tuple(point),
                (255, 0, 0),
                2,
            )


def click_event(event, x, y, flags, params):
    global current_polygon, spot_counter
    
    if event == cv2.EVENT_LBUTTONDOWN:
        current_polygon.append([x, y])
        if len(current_polygon) == 4:
            spot_id = f"A-{spot_counter:03d}"
            all_spots.append({
                "spot_id": spot_id,
                "polygon": current_polygon.copy()
            })
            print(f"[SAVED]: {spot_id} -> {current_polygon}")
            spot_counter += 1
            current_polygon = []

        redraw_overlay()
        cv2.imshow("Draw BAC Parking Spots", img_copy)


def undo_last_corner():
    if not current_polygon:
        return False

    removed_point = current_polygon.pop()
    print(f"[UNDO CORNER]: removed {removed_point}")
    redraw_overlay()
    cv2.imshow("Draw BAC Parking Spots", img_copy)
    return True


def undo_last_spot():
    global spot_counter

    if not all_spots:
        return False

    removed_spot = all_spots.pop()
    existing_numbers = [
        int(spot["spot_id"].rsplit("-", 1)[-1])
        for spot in all_spots
        if isinstance(spot.get("spot_id"), str)
        and spot["spot_id"].rsplit("-", 1)[-1].isdigit()
    ]
    spot_counter = max(existing_numbers, default=0) + 1
    print(f"[UNDO BAY]: removed {removed_spot['spot_id']}; redraw its corners.")
    redraw_overlay()
    cv2.imshow("Draw BAC Parking Spots", img_copy)
    return True

if __name__ == "__main__":
    if not os.path.exists(IMAGE_PATH):
        raise FileNotFoundError(f"Parking-lot image not found: {IMAGE_PATH}")

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        raise ValueError(f"Could not read parking-lot image: {IMAGE_PATH}")

    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            existing_spots = json.load(f)
        if not isinstance(existing_spots, list):
            raise ValueError(f"Expected a list of parking spaces in {OUTPUT_JSON}")
        all_spots.extend(existing_spots)
        existing_numbers = [
            int(spot["spot_id"].rsplit("-", 1)[-1])
            for spot in all_spots
            if isinstance(spot.get("spot_id"), str)
            and spot["spot_id"].rsplit("-", 1)[-1].isdigit()
        ]
        spot_counter = max(existing_numbers, default=0) + 1

    cv2.namedWindow("Draw BAC Parking Spots", cv2.WINDOW_AUTOSIZE)
    redraw_overlay()
    cv2.imshow("Draw BAC Parking Spots", img_copy)
    cv2.setMouseCallback("Draw BAC Parking Spots", click_event)

    print("--- PARKING SPOT MAPPING TOOL ---")
    print(f"Image: {IMAGE_PATH} ({img.shape[1]}x{img.shape[0]})")
    print("Click the four corners of each marked parking bay, going around its boundary.")
    print("Map only actual parking bays, not the drive lanes or road markings.")
    print("Backspace: undo the last corner of the bay being drawn.")
    print("U: undo the last completed bay; redraw it with corrected corners.")
    print("Press 's' to save all bays to configs/parking_spots.json.")
    print("Press 'q' to exit without saving.")

    while True:
        key = cv2.waitKey(1) & 0xFF
        if key in (8, 127):
            if not undo_last_corner():
                print("No unfinished bay corner to undo.")
        elif key in (ord('u'), ord('U')):
            if not undo_last_spot():
                print("No completed bay to undo.")
        elif key == ord('s'):
            if current_polygon:
                print(
                    f"Finish this parking bay by clicking "
                    f"{4 - len(current_polygon)} more corner(s) before saving."
                )
                continue
            if not all_spots:
                print("No parking bays mapped; nothing was saved.")
                continue
            with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
                json.dump(all_spots, f, indent=2)
            print(f"Saved {len(all_spots)} parking spaces to {OUTPUT_JSON}.")
            break
        elif key == ord('q'):
            break

    cv2.destroyAllWindows()