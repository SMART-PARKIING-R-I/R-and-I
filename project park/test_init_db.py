import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from init_db import seed_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_seeds_configured_data_and_preserves_status_when_reseeded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "test.db")
            with patch.dict(os.environ, {"PARKING_DB_PATH": database_path}):
                seed_database()

                connection = sqlite3.connect(database_path)
                try:
                    camera_count = connection.execute(
                        "SELECT COUNT(*) FROM cameras"
                    ).fetchone()[0]
                    spot_count = connection.execute(
                        "SELECT COUNT(*) FROM parking_spots"
                    ).fetchone()[0]
                    self.assertEqual(camera_count, 2)
                    self.assertEqual(spot_count, 30)

                    with open("cameras.json", "r", encoding="utf-8") as file:
                        cameras = json.load(file)
                    first_camera = cameras[0]
                    with open(
                        first_camera["spots_file"], "r", encoding="utf-8"
                    ) as file:
                        first_spot = json.load(file)[0]

                    connection.execute(
                        """
                        UPDATE parking_spots SET status = 'occupied'
                        WHERE lot_id = ? AND spot_id = ?
                        """,
                        (first_camera["lot_id"], first_spot["spot_id"]),
                    )
                    connection.commit()
                finally:
                    connection.close()

                seed_database()

                connection = sqlite3.connect(database_path)
                try:
                    status = connection.execute(
                        """
                        SELECT status FROM parking_spots
                        WHERE lot_id = ? AND spot_id = ?
                        """,
                        (first_camera["lot_id"], first_spot["spot_id"]),
                    ).fetchone()[0]
                    self.assertEqual(status, "occupied")
                finally:
                    connection.close()


if __name__ == "__main__":
    unittest.main()
