import os

import mysql.connector
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")


class DatabaseConfigurationError(RuntimeError):
    pass


def get_connection():
    load_dotenv(ENV_FILE, override=True)
    password = os.getenv("MYSQL_PASSWORD")
    if not password:
        raise DatabaseConfigurationError(
            f"MYSQL_PASSWORD is missing. Set it in {ENV_FILE} before starting the app."
        )

    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "parking_app"),
        password=password,
        database=os.getenv("MYSQL_DATABASE", "smart_parking"),
        connection_timeout=5,
        charset="utf8mb4",
    )
