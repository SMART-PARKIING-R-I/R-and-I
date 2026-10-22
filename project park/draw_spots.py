import os
import cv2
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "bac_parkA_empty.jpg")
OUTPUT_JSON = os.path.join(BASE_DIR, "parking_spots.json")

# Target display height so the window fits on standard monitor displays
DISPLAY_HEIGHT = 720

current_polygon = []
all_spots = []
spot_counter = 1
scale_factor = 1.0

def click_event(event, x, y, flags, params):
    global current_polygon, spot_counter, img_display, scale_factor, lot_id, camera_id
    
    if event == cv2.EVENT_LBUTTONDOWN:
        # Scale display coordinates back to original image resolution (2560x1179)
        orig_x = int(x * scale_factor)
        orig_y = int(y * scale_factor)
        
        current_polygon.append([orig_x, orig_y])
        cv2.circle(img_display, (x, y), 4, (0, 255, 0), -1)
        
        # Draw line between consecutive points on display
        if len(current_polygon) > 1:
            prev_display_x = int(current_polygon[-2][0] / scale_factor)
            prev_display_y = int(current_polygon[-2][1] / scale_factor)
            cv2.line(img_display, (prev_display_x, prev_display_y), (x, y), (255, 0, 0), 2)
            
        # Complete a 4-point polygon space
        if len(current_polygon) == 4:
            first_display_x = int(current_polygon[0][0] / scale_factor)
            first_display_y = int(current_polygon[0][1] / scale_factor)
            cv2.line(img_display, (x, y), (first_display_x, first_display_y), (255, 0, 0), 2)
            
            spot_id = f"A-{spot_counter:03d}"
            
            # Formatted exactly to match backend & init_db.py schema
            all_spots.append({
                "spot_id": spot_id,
                "camera_id": camera_id,
                "lot_id": lot_id,
                "polygon": current_polygon.copy()
            })
            
            print(f"[SAVED]: {spot_id} ({lot_id} / {camera_id}) -> {current_polygon}")
            cv2.putText(img_display, spot_id, (first_display_x, first_display_y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            spot_counter += 1
            current_polygon = []

        cv2.imshow("Draw BAC Parking Spots", img_display)

if __name__ == "__main__":
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: {IMAGE_PATH} not found.")
        exit()

    print("=== PARKING SPOT CONFIGURATION ===")
    lot_id = input("Enter Lot ID (e.g., BAC_PARKING or LOT_A) [Default: BAC_PARKING]: ").strip() or "BAC_PARKING"
    camera_id = input("Enter Camera ID (e.g., CAM_BAC_MAIN or CAM_01) [Default: CAM_BAC_MAIN]: ").strip() or "CAM_BAC_MAIN"
    print(f"\nConfiguring spots for Lot: '{lot_id}' | Camera: '{camera_id}'\n")

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print(f"Error: Unable to load image from {IMAGE_PATH}.")
        exit()

    orig_h, orig_w = img.shape[:2]

    # Calculate scale factor to shrink window for display while saving full resolution
    scale_factor = orig_h / DISPLAY_HEIGHT
    display_w = int(orig_w / scale_factor)
    
    img_display = cv2.resize(img, (display_w, DISPLAY_HEIGHT))

    # Configure resizable window
    cv2.namedWindow("Draw BAC Parking Spots", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Draw BAC Parking Spots", display_w, DISPLAY_HEIGHT)
    
    cv2.imshow("Draw BAC Parking Spots", img_display)
    cv2.setMouseCallback("Draw BAC Parking Spots", click_event)

    print("--- INSTRUCTIONS ---")
    print("1. Click 4 corners of each parking space in order.")
    print("2. Press 's' to export all spots directly to parking_spots.json and exit.")
    print("3. Press 'q' to quit without saving.")

    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            with open(OUTPUT_JSON, 'w') as f:
                json.dump(all_spots, f, indent=2)
            print(f"\nSuccessfully exported {len(all_spots)} spots to {OUTPUT_JSON}!")
            break
        elif key == ord('q'):
            print("\nCancelled without saving.")
            break

    cv2.destroyAllWindows()