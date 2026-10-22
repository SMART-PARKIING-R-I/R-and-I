import json

from flask import Flask, jsonify, render_template, request
from mysql.connector import Error as MySQLError

from db import DatabaseConfigurationError, get_connection
import cv2
import os


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("kiosk.html", lot_id="BAC_PARKING")

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
                if status == "occupied":
                    cursor.execute(
                        """
                        UPDATE assignments
                        SET status = 'fulfilled'
                        WHERE lot_id = %s AND spot_id = %s
                          AND status = 'confirmed'
                        """,
                        (lot_id, spot_id),
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

    # -------------------------------------------------------------------
    # Kiosk & Mobile App API Endpoints
    # -------------------------------------------------------------------

    @app.get("/api/lots/<lot_id>/status")
    def get_lot_status(lot_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT name FROM parking_lots WHERE lot_id = %s",
                (lot_id,),
            )
            lot = cursor.fetchone()
            if lot is None:
                return jsonify({"error": f"Unknown lot: {lot_id}"}), 404

            cursor.execute(
                """
                SELECT spot_id, status,
                    EXISTS (
                        SELECT 1
                        FROM assignments
                        WHERE assignments.lot_id = parking_spots.lot_id
                          AND assignments.spot_id = parking_spots.spot_id
                          AND assignments.status IN ('pending', 'confirmed')
                    ) AS reserved
                FROM parking_spots
                WHERE lot_id = %s
                ORDER BY spot_id
                """,
                (lot_id,),
            )
            rows = cursor.fetchall()
            spots = [
                {"spot_id": row["spot_id"], "status": row["status"]}
                for row in rows
            ]
            total = len(spots)
            free = sum(
                1
                for row in rows
                if row["status"] == "vacant" and not row["reserved"]
            )

            return jsonify({
                "lot_id": lot_id,
                "name": lot["name"],
                "total": total,
                "free": free,
                "spots": spots
            })
        except (MySQLError, DatabaseConfigurationError):
            app.logger.exception("Could not retrieve status for lot %s", lot_id)
            return jsonify({"error": "MySQL unavailable; lot status could not be retrieved"}), 503
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
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT lot_id FROM parking_lots WHERE lot_id = %s",
                (lot_id,),
            )
            if cursor.fetchone() is None:
                return jsonify({"error": f"Unknown lot: {lot_id}"}), 404

            cursor.execute(
                """
                SELECT spot_id, geometry
                FROM parking_spots
                WHERE lot_id = %s
                ORDER BY spot_id
                """,
                (lot_id,),
            )
            rows = cursor.fetchall()
            bays = []
            for index, row in enumerate(rows, start=1):
                polygon = row["geometry"]
                if isinstance(polygon, str):
                    polygon = json.loads(polygon)
                bays.append({
                    "number": index,
                    "spot_id": row["spot_id"],
                    "polygon": polygon
                })

            with open(os.path.join(os.path.dirname(__file__), "cameras.json"), encoding="utf-8") as config_file:
                cameras = json.load(config_file)
            camera = next(
                (item for item in cameras if item["lot_id"] == lot_id),
                None,
            )
            if camera is None:
                return jsonify({"error": f"No camera configured for lot: {lot_id}"}), 404

            reference_path = os.path.join(
                os.path.dirname(__file__),
                camera.get("coordinate_reference", camera["spots_file"]),
            )
            reference_image = cv2.imread(reference_path)
            if reference_image is None:
                app.logger.error("Could not read map reference image: %s", reference_path)
                return jsonify({"error": "Map reference image could not be read"}), 500

            return jsonify({
                "lot_id": lot_id,
                "width": int(reference_image.shape[1]),
                "height": int(reference_image.shape[0]),
                "spots": bays
            })
        except (MySQLError, DatabaseConfigurationError):
            app.logger.exception("Could not retrieve map for lot %s", lot_id)
            return jsonify({"error": "MySQL unavailable; lot map could not be retrieved"}), 503
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
            cursor = connection.cursor(dictionary=True)
            connection.start_transaction()
            cursor.execute(
                "SELECT lot_id FROM parking_lots WHERE lot_id = %s",
                (lot_id,),
            )
            if cursor.fetchone() is None:
                connection.rollback()
                return jsonify({"error": f"Unknown lot: {lot_id}"}), 404

            cursor.execute(
                """
                SELECT parking_spots.spot_id
                FROM parking_spots
                WHERE parking_spots.lot_id = %s
                  AND parking_spots.status = 'vacant'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM assignments
                      WHERE assignments.lot_id = parking_spots.lot_id
                        AND assignments.spot_id = parking_spots.spot_id
                        AND assignments.status IN ('pending', 'confirmed')
                  )
                ORDER BY spot_id ASC LIMIT 1
                FOR UPDATE
                """,
                (lot_id,),
            )
            row = cursor.fetchone()
            if row is None:
                connection.rollback()
                return jsonify({"error": "Lot is full"}), 409

            assigned_spot_id = row["spot_id"]

            cursor.execute(
                """
                INSERT INTO assignments (lot_id, spot_id, status)
                VALUES (%s, %s, 'pending')
                """,
                (lot_id, assigned_spot_id),
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
                "steps": [
                    "Drive past the gate barrier.",
                    f"Follow the road directly to bay {assigned_spot_id}."
                ]
            })
        except (MySQLError, DatabaseConfigurationError):
            if connection is not None:
                connection.rollback()
            app.logger.exception("Could not assign a spot in lot %s", lot_id)
            return jsonify({"error": "MySQL unavailable; parking space was not assigned"}), 503
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
                WHERE assignment_id = %s AND status = 'pending'
                """,
                (assignment_id,),
            )
            if cursor.rowcount == 0:
                connection.rollback()
                return jsonify({"error": "Pending assignment not found"}), 404
            connection.commit()
            return jsonify({"status": "ok", "assignment_id": assignment_id})
        except (MySQLError, DatabaseConfigurationError):
            if connection is not None:
                connection.rollback()
            app.logger.exception("Could not confirm assignment %s", assignment_id)
            return jsonify({"error": "MySQL unavailable; assignment was not confirmed"}), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @app.post("/api/assignments/<int:assignment_id>/cancel")
    def cancel_assignment(assignment_id):
        connection = None
        cursor = None
        try:
            connection = get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE assignments
                SET status = 'cancelled'
                WHERE assignment_id = %s AND status IN ('pending', 'confirmed')
                """,
                (assignment_id,),
            )
            if cursor.rowcount == 0:
                connection.rollback()
                return jsonify({"error": "Active assignment not found"}), 404
            connection.commit()
            return jsonify({"status": "ok", "assignment_id": assignment_id})
        except (MySQLError, DatabaseConfigurationError):
            if connection is not None:
                connection.rollback()
            app.logger.exception("Could not cancel assignment %s", assignment_id)
            return jsonify({"error": "MySQL unavailable; assignment was not cancelled"}), 503
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
