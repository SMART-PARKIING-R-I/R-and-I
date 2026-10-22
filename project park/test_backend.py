from datetime import datetime
import unittest
from unittest.mock import patch

import backend
from mysql.connector import Error as MySQLError


class FakeCursor:
    def __init__(self, statuses):
        self.statuses = statuses
        self.result = None
        self.rows = []
        self.last_query = None
        self.last_params = None
        self.events = []
        self.rowcount = 1
        self.lastrowid = 7

    def execute(self, query, params=()):
        self.last_query = query
        self.last_params = params
        if "SELECT lot_id, name FROM parking_lots ORDER BY lot_id" in query:
            self.rows = [{"lot_id": "BAC_PARKING", "name": "BAC_PARKING"}]
        elif "SELECT lot_id, name FROM parking_lots WHERE lot_id" in query:
            self.result = (
                {"lot_id": params[0], "name": params[0]}
                if params[0] == "BAC_PARKING"
                else None
            )
        elif "SELECT lot_id FROM parking_lots WHERE lot_id" in query:
            self.result = {"lot_id": params[0]} if params[0] == "BAC_PARKING" else None
        elif "SELECT name FROM parking_lots WHERE lot_id" in query:
            self.result = (
                {"name": "BAC_PARKING"}
                if params[0] == "BAC_PARKING"
                else None
            )
        elif "SELECT spot_id, status," in query:
            self.rows = [
                {"spot_id": "A-001", "status": "vacant", "reserved": 0},
                {"spot_id": "A-002", "status": "occupied", "reserved": 0},
            ]
        elif "SELECT parking_spots.spot_id" in query:
            self.result = {"spot_id": "A-001"}
        elif "INSERT INTO assignments" in query:
            self.lastrowid = 7
        elif "UPDATE assignments" in query:
            self.rowcount = 1
        elif "SELECT spot_id, geometry, status, updated_at" in query:
            self.rows = [{
                "spot_id": "A-001",
                "geometry": "[[1, 2], [3, 4], [5, 6], [7, 8]]",
                "status": "occupied",
                "updated_at": datetime(2026, 10, 22, 12, 30),
            }]
        elif "SELECT event_id, spot_id, camera_id, status, observed_at" in query:
            self.rows = [{
                "event_id": 12,
                "spot_id": "A-001",
                "camera_id": "CAM_FEED_1",
                "status": "occupied",
                "observed_at": datetime(2026, 10, 22, 12, 30),
            }]
        elif "SELECT camera_id FROM cameras" in query:
            self.result = {"camera_id": params[0]} if params[1] == "BAC_PARKING" else None
        elif "SELECT status" in query:
            self.result = (
                {"status": self.statuses[params[1]]}
                if params[1] in self.statuses
                else None
            )
        elif "UPDATE parking_spots" in query:
            self.statuses[params[2]] = params[0]
        elif "INSERT INTO occupancy_events" in query:
            self.events.append(params)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, statuses):
        self.fake_cursor = FakeCursor(statuses)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def start_transaction(self):
        pass

    def ping(self, reconnect=False):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class OccupancyEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = backend.create_app()
        self.client = self.app.test_client()
        self.payload = {
            "camera_id": "CAM_FEED_1",
            "lot_id": "BAC_PARKING",
            "spots": [{"spot_id": "A-001", "status": "occupied"}],
        }

    def test_health_checks_mysql_connection(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok", "database": "connected"})
        self.assertTrue(connection.closed)

    def test_health_reports_mysql_unavailable(self):
        with patch.object(
            backend,
            "get_connection",
            side_effect=MySQLError("database is down"),
        ):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["database"], "disconnected")

    def test_rejects_invalid_status_without_connecting_to_database(self):
        self.payload["spots"][0]["status"] = "reserved"
        with patch.object(backend, "get_connection") as connect:
            response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 400)
        connect.assert_not_called()

    def test_saves_status_change_and_event(self):
        connection = FakeConnection({"A-001": "vacant"})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["changed"], ["A-001"])
        self.assertEqual(connection.fake_cursor.statuses["A-001"], "occupied")
        self.assertEqual(len(connection.fake_cursor.events), 1)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_does_not_add_event_for_unchanged_status(self):
        connection = FakeConnection({"A-001": "occupied"})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["changed"], [])
        self.assertEqual(connection.fake_cursor.events, [])
        self.assertTrue(connection.committed)

    def test_unknown_spot_rolls_back_the_update(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_rejects_camera_registered_to_another_lot(self):
        connection = FakeConnection({"A-001": "vacant"})
        self.payload["lot_id"] = "WRONG_LOT"
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/occupancy", json=self.payload)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(connection.rolled_back)

    def test_lists_parking_lots(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/lots")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["lots"], [{
            "lot_id": "BAC_PARKING",
            "name": "BAC_PARKING",
        }])
        self.assertTrue(connection.closed)

    def test_lists_spots_with_geometry_and_current_status(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/lots/BAC_PARKING/spots")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            "lot_id": "BAC_PARKING",
            "name": "BAC_PARKING",
            "spots": [{
                "spot_id": "A-001",
                "geometry": [[1, 2], [3, 4], [5, 6], [7, 8]],
                "status": "occupied",
                "updated_at": "2026-10-22T12:30:00",
            }],
        })
        self.assertTrue(connection.closed)

    def test_unknown_lot_returns_404_for_spots(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/lots/UNKNOWN/spots")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(connection.closed)

    def test_kiosk_lot_status_counts_available_spaces(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/lots/BAC_PARKING/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total"], 2)
        self.assertEqual(response.json["free"], 1)
        self.assertEqual(response.json["name"], "BAC_PARKING")
        self.assertTrue(connection.closed)

    def test_kiosk_unknown_lot_status_returns_404(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/lots/UNKNOWN/status")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(connection.closed)

    def test_assignment_is_created_for_a_vacant_spot(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/lots/BAC_PARKING/assign")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["assignment_id"], 7)
        self.assertEqual(response.json["spot_id"], "A-001")
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_assignment_confirmation_updates_only_pending_assignment(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/assignments/7/confirm")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(connection.committed)
        self.assertIn("status = 'pending'", connection.fake_cursor.last_query)
        self.assertTrue(connection.closed)

    def test_assignment_can_be_manually_cancelled(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.post("/api/assignments/7/cancel")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(connection.committed)
        self.assertIn("status = 'cancelled'", connection.fake_cursor.last_query)
        self.assertTrue(connection.closed)

    def test_lists_recent_events_with_bounded_limit(self):
        connection = FakeConnection({})
        with patch.object(backend, "get_connection", return_value=connection):
            response = self.client.get("/api/lots/BAC_PARKING/events?limit=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["events"], [{
            "event_id": 12,
            "spot_id": "A-001",
            "camera_id": "CAM_FEED_1",
            "status": "occupied",
            "observed_at": "2026-10-22T12:30:00",
        }])
        self.assertIn("LIMIT %s", connection.fake_cursor.last_query)
        self.assertEqual(connection.fake_cursor.last_params, ("BAC_PARKING", 10))
        self.assertTrue(connection.closed)

    def test_rejects_invalid_event_limit_without_connecting(self):
        with patch.object(backend, "get_connection") as connect:
            response = self.client.get("/api/lots/BAC_PARKING/events?limit=101")

        self.assertEqual(response.status_code, 400)
        connect.assert_not_called()

    def test_read_endpoint_reports_database_unavailable(self):
        with patch.object(
            backend,
            "get_connection",
            side_effect=MySQLError("database is down"),
        ):
            response = self.client.get("/api/lots")

        self.assertEqual(response.status_code, 503)
        self.assertIn("MySQL unavailable", response.json["error"])


if __name__ == "__main__":
    unittest.main()
