# Smart Parking Prototype

The detector posts parking-space occupancy to the Flask API on the same laptop.
The API stores the latest status and status-change history in a local MySQL
Server database.

## Local MySQL setup

MySQL Workbench is the client used to manage MySQL; the MySQL Server service
must also be installed and running. For this demo, create a local database and
a dedicated app account in a Workbench SQL tab:

```sql
CREATE DATABASE IF NOT EXISTS smart_parking
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'parking_app'@'127.0.0.1'
  IDENTIFIED BY 'choose-a-local-password';

GRANT ALL PRIVILEGES ON smart_parking.* TO 'parking_app'@'127.0.0.1';
```

Replace `choose-a-local-password` with a password you choose locally. Do not
commit it or send it to anyone. If MySQL Workbench already has a local server
connection, run this script in that connection, then activate the
`smart_parking` schema in the SCHEMAS panel.

From the project folder in Command Prompt, install the Python connector:

```cmd
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a `.env` file in the project folder with the database settings. The
initializer and Flask API both read this file, regardless of which Command
Prompt starts them:

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=parking_app
MYSQL_PASSWORD=the-password-you-chose
MYSQL_DATABASE=smart_parking
```

Replace the password with the one configured in Workbench. Do not commit or
share `.env`. Next, create the tables and load the lots, cameras, parking
spaces, and polygon coordinates:

```cmd
venv\Scripts\python.exe init_db.py
```

`init_db.py` creates/updates the tables from `schema.sql` and inserts the
configured camera and spot data. Re-running it updates geometry but preserves
current spot status and occupancy history.

## Run the app

In the first Command Prompt on the host laptop, start the API and leave it running:

```cmd
venv\Scripts\python.exe backend.py
```

Flask listens on `0.0.0.0:5000`, which makes the API reachable from other
devices on the same LAN. This does not expose MySQL; `db.py` connects to
`127.0.0.1:3306` on the host laptop.

Find the host laptop's LAN IPv4 address with:

```cmd
ipconfig
```

Use the IPv4 address of the network adapter shared with the other devices
(for example `192.168.1.25`). On the host, verify the API and database:

```cmd
curl.exe http://127.0.0.1:5000/api/health
```

A healthy response includes `"database":"connected"`. Start the detector in
another host-laptop Command Prompt:

```cmd
venv\Scripts\python.exe detector.py
```

Other devices call the API using the host laptop's LAN address, for example:

```text
http://192.168.1.25:5000/api/health
```

Replace the example IP with the host's actual IPv4 address. Allow Python or
TCP port 5000 through Windows Defender Firewall on the **Private** network if
Windows prompts you. The client devices and host must be on the same reachable
network. The demo API has no authentication, so use it only on a trusted local
network; do not forward the port to the public internet.

Only `CAM_FEED_1` for `BAC_PARKING` is currently enabled in `cameras.json`.
The detector starts one worker for each configured camera entry. Add another
entry there when a second feed is ready. The current BAC source is an IP
Webcam stream URL; keep the phone stream running and both devices on the same
network.

Preview windows request a 1920x1080 display size; this does not change camera
capture resolution. Spot coordinates are scaled from each camera's configured
`coordinate_reference` image to the incoming frame size.

If a camera cannot be opened or returns no frame, its worker logs an error
and exits. MySQL is the database for this project; the local `parking.db`
SQLite file from earlier experiments is not used.

## API

`GET /api/lots` lists the configured lots:

```json
{
  "lots": [
    { "lot_id": "BAC_PARKING", "name": "BAC_PARKING" }
  ]
}
```

`GET /api/lots/<lot_id>/spots` returns the current status and mapped geometry
for every space in a lot. `updated_at` is an ISO 8601 timestamp, or `null`
when the detector has not reported a status change for that space:

```json
{
  "lot_id": "BAC_PARKING",
  "name": "BAC_PARKING",
  "spots": [
    {
      "spot_id": "A-001",
      "geometry": [[10, 20], [30, 20], [30, 50], [10, 50]],
      "status": "vacant",
      "updated_at": null
    }
  ]
}
```

`GET /api/lots/<lot_id>/events` returns recent occupancy changes, newest
first. An optional `limit` query parameter accepts an integer from 1 to 100
and defaults to 50. For example:

```text
GET /api/lots/BAC_PARKING/events?limit=20
```

Unknown lot IDs return HTTP 404. An invalid history limit returns HTTP 400;
database connection errors return HTTP 503.

`POST /api/occupancy` expects the detector's current payload format:

```json
{
  "camera_id": "CAM_FEED_1",
  "lot_id": "BAC_PARKING",
  "spots": [
    { "spot_id": "A-001", "status": "occupied" }
  ]
}
```

Every camera and space in an update must have been loaded by `init_db.py`.
Statuses must be `vacant` or `occupied`. Invalid payloads return HTTP 400,
unregistered cameras/spaces return 404, and MySQL errors return 503. Valid
updates are stored transactionally; unchanged statuses do not create duplicate
history events. `GET /api/health` checks both the API and its MySQL connection.

## Kiosk

Open `http://127.0.0.1:5000/` on the host laptop to display the kiosk page.
It polls the selected lot's status and can assign the next available space.
Active assignments remain reserved until the detector reports the spot as
occupied or a user cancels them with `POST /api/assignments/<id>/cancel`.
Assignments do not expire automatically.

`GET /api/lots/<lot_id>/status` reports total and available spaces.
`GET /api/lots/<lot_id>/map` returns mapped polygons and reference-image
dimensions. `POST /api/lots/<lot_id>/assign` creates an assignment;
`POST /api/assignments/<id>/confirm` confirms it.

## Remapping BAC parking spaces

`draw_spots.py` displays `bac_park_empty.jpg` and maps four clicked corners
for each marked bay. The `s` key saves to `configs/parking_spots.json`; `q`
exits without saving. Existing saved bays appear when the tool opens. Press
Backspace to undo a corner or `u` to remove the last completed bay. After
saving a new map, run `init_db.py` to update database geometry.

For BAC, `cameras.json` uses the IP Webcam `/video` stream URL. If the phone's
IP changes, update the `source` value. The detector scales polygons from the
`coordinate_reference` image to the incoming frame. The camera still needs a
similar viewpoint and framing; substantial viewpoint or aspect-ratio
differences may require remapping.
