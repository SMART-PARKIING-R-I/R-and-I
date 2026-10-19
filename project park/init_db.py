import json
import os

from db import BASE_DIR, get_connection


CAMERAS_CONFIG = os.path.join(BASE_DIR, "cameras.json")
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")


def seed_database():
    with open(CAMERAS_CONFIG, "r", encoding="utf-8") as config_file:
        cameras = json.load(config_file)

    connection = get_connection()
    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as schema_file:
            connection.executescript(schema_file.read())

        for camera in cameras:
            camera_id = camera["camera_id"]
            lot_id = camera["lot_id"]
            spots_path = os.path.join(BASE_DIR, camera["spots_file"])

            with open(spots_path, "r", encoding="utf-8") as spots_file:
                spots = json.load(spots_file)

            connection.execute(
                """
                INSERT INTO parking_lots (lot_id, name)
                VALUES (?, ?)
                ON CONFLICT(lot_id) DO UPDATE SET name = excluded.name
                """,
                (lot_id, lot_id),
            )
            connection.execute(
                """
                INSERT INTO cameras (camera_id, lot_id)
                VALUES (?, ?)
                ON CONFLICT(camera_id) DO UPDATE SET lot_id = excluded.lot_id
                """,
                (camera_id, lot_id),
            )
            for spot in spots:
                connection.execute(
                    """
                    INSERT INTO parking_spots (lot_id, spot_id, geometry)
                    VALUES (?, ?, ?)
                    ON CONFLICT(lot_id, spot_id)
                    DO UPDATE SET geometry = excluded.geometry
                    """,
                    (lot_id, spot["spot_id"], json.dumps(spot["polygon"])),
                )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"Seeded {len(cameras)} cameras and their configured parking spaces.")


if __name__ == "__main__":
    seed_database()
