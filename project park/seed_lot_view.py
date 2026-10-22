"""
Registers the lot used by static/lot_view.html (lot BAC_PARK_A, camera
CAM_BAC_MAIN and its 20 bays) in the MySQL database.

The bays are read straight from lot_view.html, so the page and the database
always agree. Safe to run any number of times: existing spot status and
history are kept.
"""
import json
import os
import re

from db import BASE_DIR, get_connection

PAGE = os.path.join(BASE_DIR, "static", "lot_view.html")


def read_page_settings():
    html = open(PAGE, encoding="utf-8").read()
    lot_id = re.search(r'const LOT_ID = "([^"]+)"', html).group(1)
    camera_id = re.search(r'const CAMERA_ID = "([^"]+)"', html).group(1)
    bays = json.loads(re.search(r"const BAYS = (\[.*?\]);", html, re.S).group(1))
    return lot_id, camera_id, bays


def main():
    lot_id, camera_id, bays = read_page_settings()
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO parking_lots (lot_id, name) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE name = VALUES(name)",
            (lot_id, lot_id),
        )
        cursor.execute(
            "INSERT INTO cameras (camera_id, lot_id) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE lot_id = VALUES(lot_id)",
            (camera_id, lot_id),
        )
        for bay in bays:
            cursor.execute(
                "INSERT INTO parking_spots (lot_id, spot_id, geometry) "
                "VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE geometry = VALUES(geometry)",
                (lot_id, bay["id"], json.dumps(bay["p"])),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
    print(f"Registered lot {lot_id} with camera {camera_id} and {len(bays)} bays.")


if __name__ == "__main__":
    main()
