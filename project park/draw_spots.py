import os
import cv2
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "Lot_2_empty.png")
OUTPUT_JSON = os.path.join(BASE_DIR, "configs","lot_B.json")

current_polygon = []
all_spots = []
spot_counter = 1

def click_event(event, x, y, flags, params):
    global current_polygon, spot_counter, img_copy
    
    if event == cv2.EVENT_LBUTTONDOWN:
        # Record clicked point
        current_polygon.append([x, y])
        cv2.circle(img_copy, (x, y), 5, (0, 255, 0), -1)
        
        # Draw line between consecutive points
        if len(current_polygon) > 1:
            cv2.line(img_copy, tuple(current_polygon[-2]), tuple(current_polygon[-1]), (255, 0, 0), 2)
            
        # Complete a 4-point polygon space
        if len(current_polygon) == 4:
            cv2.line(img_copy, tuple(current_polygon[3]), tuple(current_polygon[0]), (255, 0, 0), 2)
            spot_id = f"A-{spot_counter:03d}"
            
            all_spots.append({
                "spot_id": spot_id,
                "polygon": current_polygon.copy()
            })
            
            print(f"[SAVED]: {spot_id} -> {current_polygon}")
            cv2.putText(img_copy, spot_id, (current_polygon[0][0], current_polygon[0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            spot_counter += 1
            current_polygon = [] # Reset for next spot

        cv2.imshow("Draw BAC Parking Spots", img_copy)

if __name__ == "__main__":
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: {IMAGE_PATH} not found. Save your image as 'bac_parking_empty.jpg' in project park.")
        exit()

    img = cv2.imread(IMAGE_PATH)
    img_copy = img.copy()

    cv2.imshow("Draw BAC Parking Spots", img_copy)
    cv2.setMouseCallback("Draw BAC Parking Spots", click_event)

    print("--- PARKING SPOT MAPPING TOOL ---")
    print("1. Click the 4 corners of a parking bay in order (Top-Left -> Top-Right -> Bottom-Right -> Bottom-Left).")
    print("2. Repeat for all available spaces on the land.")
    print("3. Press 's' to save all drawn spots to parking_spots.json and exit.")

    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            with open(OUTPUT_JSON, 'w') as f:
                json.dump(all_spots, f, indent=2)
            print(f"Successfully exported {len(all_spots)} spots to {OUTPUT_JSON}!")
            break
        elif key == ord('q'):
            break

    cv2.destroyAllWindows()