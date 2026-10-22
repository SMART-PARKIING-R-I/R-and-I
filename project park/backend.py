import json

from flask import Flask, jsonify, request
from mysql.connector import Error as MySQLError

from db import DatabaseConfigurationError, get_connection


def create_app():
    app = Flask(__name__)

    @app.get("/api/health")
    def health():
        connection = None
        try:
            connection = get_connection()
            connection.ping(reconnect=False)
            return jsonify({"status": "ok", "database": "connected"})
        except (MySQLError, DatabaseConfigurationError):
            app.logger.exception("MySQL health check failed")
            return jsonify({"status": "unavailable", "database": "disconnected"}), 503
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/lots")
    def list_lots():
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT lot_id, name FROM parking_lots ORDER BY lot_id")
            return jsonify({"lots": cursor.fetchall()})
        except (MySQLError, DatabaseConfigurationError):
            app.logger.exception("Could not retrieve parking lots")
            return jsonify({"error": "MySQL unavailable; parking lots could not be retrieved"}), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.get("/api/lots/<lot_id>/spots")
    def list_parking_spots(lot_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT lot_id, name FROM parking_lots WHERE lot_id = %s",
                (lot_id,),
            )
            lot = cursor.fetchone()
            if lot is None:
                return jsonify({"error": f"Unknown parking lot: {lot_id}"}), 404

            cursor.execute(
                """
                SELECT spot_id, geometry, status, updated_at
                FROM parking_spots
                WHERE lot_id = %s
                ORDER BY spot_id
                """,
                (lot_id,),
            )
            spots = cursor.fetchall()
            for spot in spots:
                if isinstance(spot["geometry"], str):
                    spot["geometry"] = json.loads(spot["geometry"])
                if spot["updated_at"] is not None:
                    spot["updated_at"] = spot["updated_at"].isoformat()

            return jsonify({"lot_id": lot_id, "name": lot["name"], "spots": spots})
        except (MySQLError, DatabaseConfigurationError):
            app.logger.exception("Could not retrieve parking spots for lot %s", lot_id)
            return jsonify({
                "error": "MySQL unavailable; parking spaces could not be retrieved"
            }), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.get("/api/lots/<lot_id>/events")
    def list_occupancy_events(lot_id):
        raw_limit = request.args.get("limit", "50")
        try:
            limit = int(raw_limit)
        except ValueError:
            return jsonify({"error": "limit must be an integer between 1 and 100"}), 400
        if not 1 <= limit <= 100:
            return jsonify({"error": "limit must be an integer between 1 and 100"}), 400

        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT lot_id FROM parking_lots WHERE lot_id = %s",
                (lot_id,),
            )
            if cursor.fetchone() is None:
                return jsonify({"error": f"Unknown parking lot: {lot_id}"}), 404

            cursor.execute(
                """
                SELECT event_id, spot_id, camera_id, status, observed_at
                FROM occupancy_events
                WHERE lot_id = %s
                ORDER BY observed_at DESC, event_id DESC
                LIMIT %s
                """,
                (lot_id, limit),
            )
            events = cursor.fetchall()
            for event in events:
                event["observed_at"] = event["observed_at"].isoformat()

            return jsonify({"lot_id": lot_id, "events": events})
        except (MySQLError, DatabaseConfigurationError):
            app.logger.exception("Could not retrieve occupancy events for lot %s", lot_id)
            return jsonify({
                "error": "MySQL unavailable; occupancy history could not be retrieved"
            }), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.post("/api/occupancy")
    def receive_occupancy():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object"}), 400

        camera_id = payload.get("camera_id")
        lot_id = payload.get("lot_id")
        spots = payload.get("spots")
        if not isinstance(camera_id, str) or not camera_id.strip():
            return jsonify({"error": "camera_id must be a non-empty string"}), 400
        if not isinstance(lot_id, str) or not lot_id.strip():
            return jsonify({"error": "lot_id must be a non-empty string"}), 400
        if not isinstance(spots, list) or not spots:
            return jsonify({"error": "spots must be a non-empty list"}), 400

        camera_id = camera_id.strip()
        lot_id = lot_id.strip()
        normalized_spots = []
        seen_spot_ids = set()
        for index, spot in enumerate(spots):
            if not isinstance(spot, dict):
                return jsonify({"error": f"spots[{index}] must be an object"}), 400

            spot_id = spot.get("spot_id")
            status = spot.get("status")
            if not isinstance(spot_id, str) or not spot_id.strip():
                return jsonify({
                    "error": f"spots[{index}].spot_id must be a non-empty string"
                }), 400
            if status not in ("vacant", "occupied"):
                return jsonify({
                    "error": f"spots[{index}].status must be 'vacant' or 'occupied'"
                }), 400

            spot_id = spot_id.strip()
            if spot_id in seen_spot_ids:
                return jsonify({"error": f"Duplicate spot_id: {spot_id}"}), 400
            seen_spot_ids.add(spot_id)
            normalized_spots.append((spot_id, status))

        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            connection.start_transaction()

            cursor.execute(
                "SELECT camera_id FROM cameras WHERE camera_id = %s AND lot_id = %s",
                (camera_id, lot_id),
            )
            if cursor.fetchone() is None:
                connection.rollback()
                return jsonify({"error": "Camera is not registered for this lot"}), 404

            current_states = {}
            for spot_id, _ in normalized_spots:
                cursor.execute(
                    """
                    SELECT status
                    FROM parking_spots
                    WHERE lot_id = %s AND spot_id = %s
                    FOR UPDATE
                    """,
                    (lot_id, spot_id),
                )
                row = cursor.fetchone()
                if row is None:
                    connection.rollback()
                    return jsonify({"error": f"Unknown parking spot: {spot_id}"}), 404
                current_states[spot_id] = row["status"]

            changed_spots = []
            for spot_id, status in normalized_spots:
                if current_states[spot_id] == status:
                    continue

                cursor.execute(
                    """
                    UPDATE parking_spots
                    SET status = %s, updated_at = CURRENT_TIMESTAMP(6)
                    WHERE lot_id = %s AND spot_id = %s
                    """,
                    (status, lot_id, spot_id),
                )
                cursor.execute(
                    """
                    INSERT INTO occupancy_events (lot_id, spot_id, camera_id, status)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (lot_id, spot_id, camera_id, status),
                )
                changed_spots.append(spot_id)

            connection.commit()
            return jsonify({
                "status": "ok",
                "received": len(normalized_spots),
                "changed": changed_spots,
            })
        except (MySQLError, DatabaseConfigurationError):
            if connection is not None:
                connection.rollback()
            app.logger.exception("Could not store occupancy update")
            return jsonify({
                "error": "MySQL unavailable; occupancy update was not saved"
            }), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
