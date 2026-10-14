import sqlite3

from flask import Flask, jsonify, request

from db import get_connection


def create_app():
    app = Flask(__name__)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

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
            cursor = connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            cursor.execute(
                "SELECT camera_id FROM cameras WHERE camera_id = ? AND lot_id = ?",
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
                    WHERE lot_id = ? AND spot_id = ?
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
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE lot_id = ? AND spot_id = ?
                    """,
                    (status, lot_id, spot_id),
                )
                cursor.execute(
                    """
                    INSERT INTO occupancy_events (lot_id, spot_id, camera_id, status)
                    VALUES (?, ?, ?, ?)
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
        except sqlite3.Error:
            if connection is not None:
                connection.rollback()
            app.logger.exception("Could not store occupancy update")
            return jsonify({
                "error": "Database unavailable; occupancy update was not saved"
            }), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
