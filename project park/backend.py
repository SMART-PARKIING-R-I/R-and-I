import sqlite3
import json
from flask import Flask, jsonify, request, render_template
from db import get_connection


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        # Serves the gate kiosk HTML view
        return render_template("kiosk.html", lot_id="BAC_PARK_A")

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

    # -------------------------------------------------------------------
    # Kiosk & Mobile App API Endpoints
    # -------------------------------------------------------------------

    @app.get("/api/lots/<lot_id>/status")
    def get_lot_status(lot_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT spot_id, status FROM parking_spots WHERE lot_id = ?",
                (lot_id,)
            )
            rows = cursor.fetchall()
            if not rows:
                return jsonify({"error": f"Unknown lot: {lot_id}"}), 404

            spots = [{"spot_id": row["spot_id"], "status": row["status"]} for row in rows]
            total = len(spots)
            free = sum(1 for s in spots if s["status"] == "vacant")

            return jsonify({
                "lot_id": lot_id,
                "name": "Parking Space A",
                "total": total,
                "free": free,
                "spots": spots
            })
        except sqlite3.Error:
            app.logger.exception("Error reading lot status")
            return jsonify({"error": "Database error"}), 500
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.get("/api/lots/<lot_id>/map")
    def get_lot_map(lot_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT spot_id, polygon FROM parking_spots WHERE lot_id = ?",
                (lot_id,)
            )
            rows = cursor.fetchall()
            
            bays = []
            for idx, row in enumerate(rows, start=1):
                raw_poly = row["polygon"]
                polygon = json.loads(raw_poly) if isinstance(raw_poly, str) else raw_poly
                bays.append({
                    "number": idx,
                    "spot_id": row["spot_id"],
                    "polygon": polygon
                })

            return jsonify({
                "lot_id": lot_id,
                "width": 2560,
                "height": 1179,
                "entrance": [200, 1100],
                "spots": bays
            })
        except sqlite3.Error:
            app.logger.exception("Error fetching lot map")
            return jsonify({"error": "Database error"}), 500
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.post("/api/lots/<lot_id>/assign")
    def assign_spot(lot_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            # Updated query: removed 'polygon' column dependency
            cursor.execute(
                """
                SELECT spot_id FROM parking_spots
                WHERE lot_id = ? AND status = 'vacant'
                ORDER BY spot_id ASC LIMIT 1
                """,
                (lot_id,)
            )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                return jsonify({"error": "Lot is full"}), 409

            assigned_spot_id = row["spot_id"]

            cursor.execute(
                """
                INSERT INTO assignments (lot_id, spot_id, status)
                VALUES (?, ?, 'pending')
                """,
                (lot_id, assigned_spot_id)
            )
            assignment_id = cursor.lastrowid
            connection.commit()

            # Extract integer spot number (e.g. "A-012" -> 12)
            try:
                spot_num = int(assigned_spot_id.split("-")[-1])
            except ValueError:
                spot_num = 1

            return jsonify({
                "assignment_id": assignment_id,
                "spot_id": assigned_spot_id,
                "number": spot_num,
                "route": [[200, 1100], [400, 1100]],
                "steps": [
                    "Drive past the gate barrier.",
                    f"Follow the road directly to bay {assigned_spot_id}."
                ]
            })
        except sqlite3.Error:
            if connection is not None:
                connection.rollback()
            app.logger.exception("Error assigning spot")
            return jsonify({"error": "Database error"}), 500
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.post("/api/assignments/<int:assignment_id>/confirm")
    def confirm_assignment(assignment_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE assignments
                SET status = 'confirmed'
                WHERE id = ?
                """,
                (assignment_id,)
            )
            connection.commit()
            return jsonify({"status": "ok", "assignment_id": assignment_id})
        except sqlite3.Error:
            if connection is not None:
                connection.rollback()
            app.logger.exception("Error confirming assignment")
            return jsonify({"error": "Database error"}), 500
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)