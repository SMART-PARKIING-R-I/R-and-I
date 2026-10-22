import os
import tempfile
import unittest
from unittest.mock import patch

import db


class DatabaseConfigurationTests(unittest.TestCase):
    def test_connection_uses_project_env_settings(self):
        settings = {
            "MYSQL_HOST": "127.0.0.1",
            "MYSQL_PORT": "3306",
            "MYSQL_USER": "parking_app",
            "MYSQL_PASSWORD": "test-only-password",
            "MYSQL_DATABASE": "smart_parking",
        }
        with (
            patch.object(db, "load_dotenv") as load_dotenv,
            patch.dict(os.environ, settings, clear=True),
            patch.object(db.mysql.connector, "connect") as connect,
        ):
            db.get_connection()

        load_dotenv.assert_called_once_with(db.ENV_FILE, override=True)
        connect.assert_called_once_with(
            host="127.0.0.1",
            port=3306,
            user="parking_app",
            password="test-only-password",
            database="smart_parking",
            connection_timeout=5,
            charset="utf8mb4",
        )

    def test_reads_credentials_from_dotenv_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".env",
            delete=False,
        ) as env_file:
            env_file.write(
                "MYSQL_HOST=127.0.0.1\n"
                "MYSQL_PORT=3306\n"
                "MYSQL_USER=parking_app\n"
                "MYSQL_PASSWORD=test-only-password\n"
                "MYSQL_DATABASE=smart_parking\n"
            )
            env_path = env_file.name

        try:
            with (
                patch.object(db, "ENV_FILE", env_path),
                patch.dict(os.environ, {}, clear=True),
                patch.object(db.mysql.connector, "connect") as connect,
            ):
                db.get_connection()
        finally:
            os.unlink(env_path)

        self.assertEqual(connect.call_args.kwargs["user"], "parking_app")
        self.assertEqual(connect.call_args.kwargs["password"], "test-only-password")

    def test_missing_password_has_actionable_error(self):
        with (
            patch.object(db, "load_dotenv"),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(
                db.DatabaseConfigurationError,
                r"MYSQL_PASSWORD is missing",
            ):
                db.get_connection()


if __name__ == "__main__":
    unittest.main()
