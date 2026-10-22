import json
import os
import unittest
from unittest.mock import patch

import init_db


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class DatabaseInitializationTests(unittest.TestCase):
    def test_creates_schema_and_seeds_all_configured_cameras_and_spots(self):
        connection = FakeConnection()
        with patch.object(init_db, "get_connection", return_value=connection):
            init_db.seed_database()

        with open(init_db.CAMERAS_CONFIG, "r", encoding="utf-8") as file:
            cameras = json.load(file)
        expected_spot_count = 0
        for camera in cameras:
            spot_path = os.path.join(init_db.BASE_DIR, camera["spots_file"])
            with open(spot_path, "r", encoding="utf-8") as file:
                expected_spot_count += len(json.load(file))

        sql_statements = [query for query, _ in connection.fake_cursor.executed]
        self.assertTrue(
            any("CREATE TABLE IF NOT EXISTS parking_lots" in query for query in sql_statements)
        )
        self.assertTrue(
            any("CREATE TABLE IF NOT EXISTS occupancy_events" in query for query in sql_statements)
        )
        self.assertTrue(
            any("CREATE TABLE IF NOT EXISTS assignments" in query for query in sql_statements)
        )
        self.assertEqual(
            sum("INSERT INTO cameras" in query for query in sql_statements),
            len(cameras),
        )
        self.assertEqual(
            sum("INSERT INTO parking_spots" in query for query in sql_statements),
            expected_spot_count,
        )
        self.assertTrue(connection.committed)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
