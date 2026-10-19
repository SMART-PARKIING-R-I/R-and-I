import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import backend
from db import get_connection


class OccupancyEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_dir.name, "test.db")
        self.database_path_override = patch.dict(
            os.environ, {"PARKING_DB_PATH": self.database_path}
        )
        self.database_path_override.start()

        connection = get_connection()
        with open("schema.sql", "r", encoding="utf-8") as schema_file:
            connection.executescript(schema_file.read())
        connection.execute(
            "INSERT INTO parking_lots (lot_id, name) VALUES (?, ?)",
            ("BAC_PARKING", "BAC_PARKING"),
        )
        connection.execute(
            "INSERT INTO cameras (camera_id, lot_id) VALUES (?, ?)",
            ("CAM_BAC_MAIN", "BAC_PARKING"),
        )
        connection.execute(
            """
            INSERT INTO parking_spots (lot_id, spot_id, geometry, status)
            VALUES (?, ?, ?, ?)
            """,
            ("BAC_PARKING", "A-001", "[]", "vacant"),
        )
        connection.commit()
        connection.close()

        self.client = backend.create_app().test_client()
        self.payload = {
            "camera_id": "CAM_BAC_MAIN",
            "lot_id": "BAC_PARKING",
            "spots": [{"spot_id": "A-001", "status": "occupied"}],
        }

    def tearDown(self):
        self.database_path_override.stop()
        self.temp_dir.cleanup()

    def read_database(self, query, parameters=()):
        connection = sqlite3.connect(self.database_path)
        try:
            return connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

    def test_rejects_invalid_status_without_database_change(self):
        self.payload["spots"][0]["status"] = "reserved"
        response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.read_database(
                "SELECT status FROM parking_spots WHERE lot_id = ? AND spot_id = ?",
                ("BAC_PARKING", "A-001"),
            ),
            [("vacant",)],
        )

    def test_saves_status_change_and_event(self):
        response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["changed"], ["A-001"])
        self.assertEqual(
            self.read_database(
                "SELECT status FROM parking_spots WHERE lot_id = ? AND spot_id = ?",
                ("BAC_PARKING", "A-001"),
            ),
            [("occupied",)],
        )
        self.assertEqual(
            self.read_database(
                "SELECT lot_id, spot_id, camera_id, status FROM occupancy_events"
            ),
            [("BAC_PARKING", "A-001", "CAM_BAC_MAIN", "occupied")],
        )

    def test_does_not_add_event_for_unchanged_status(self):
        self.payload["spots"][0]["status"] = "vacant"
        response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["changed"], [])
        self.assertEqual(self.read_database("SELECT event_id FROM occupancy_events"), [])

    def test_unknown_spot_rolls_back_the_whole_payload(self):
        self.payload["spots"].append(
            {"spot_id": "UNKNOWN", "status": "occupied"}
        )
        response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.read_database(
                "SELECT status FROM parking_spots WHERE lot_id = ? AND spot_id = ?",
                ("BAC_PARKING", "A-001"),
            ),
            [("vacant",)],
        )
        self.assertEqual(self.read_database("SELECT event_id FROM occupancy_events"), [])

    def test_rejects_camera_registered_to_another_lot(self):
        self.payload["lot_id"] = "WRONG_LOT"
        response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
