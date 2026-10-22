# Smart Parking Prototype

The detector posts parking-space occupancy to the Flask API at
`http://127.0.0.1:5000/api/occupancy`. The API stores the latest status in a
local SQLite database and adds a history row when a space changes between
vacant and occupied. SQLite is included with Python, so no database server is
needed for the demo.

## Setup

1. Activate the project virtual environment and install the requirements:

   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Create the local database, schema, and configured lots/cameras/spaces:

   ```powershell
   python .\init_db.py
   ```

   By default, this creates `parking.db` in this folder. To store it elsewhere,
   set `PARKING_DB_PATH` before running both the initializer and backend:

   ```powershell
   $env:PARKING_DB_PATH = "C:\path\to\parking.db"
   ```

3. In one terminal, start the API and leave it running:

   ```powershell
   python .\backend.py
   ```

   Confirm the API responds before starting the detector:

   ```powershell
   Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/health'
   ```

4. In another terminal, start the detector:

   ```powershell
   python .\detector.py
   ```

The secondary-lot source configured as `Lot_2_empty.png` is a still image, not
a live camera. The detector processes it once and leaves its preview window
open until you press `q`. The BAC camera uses the IP Webcam video stream URL
configured in `cameras.json`.

Preview windows are resizable and request a 1920x1080 display size. The actual
window may be limited by the desktop display; this setting does not change the
camera stream's capture resolution, which is read from each incoming frame.

`parking.db` is local demo data and is ignored by Git. `init_db.py` can be run
again to refresh configured cameras and spot geometry; it preserves current
spot status and occupancy history.

## API

`POST /api/occupancy` expects the detector's current payload format:

```json
{
  "camera_id": "CAM_BAC_MAIN",
  "lot_id": "BAC_PARKING",
  "spots": [
    { "spot_id": "A-001", "status": "occupied" }
  ]
}
```

Every camera and space in an update must have been loaded by `init_db.py`.
Statuses must be `vacant` or `occupied`. Invalid payloads return HTTP 400,
unregistered cameras/spaces return 404, and SQLite errors return 503. Valid
updates are stored transactionally; unchanged statuses do not create duplicate
history events.

`GET /api/health` is a lightweight API-process check; it does not test the
database connection.

## Remapping BAC parking spaces

`draw_spots.py` displays `bac_park_empty.jpg` at its original dimensions and
maps four clicked corners for each marked bay. The `s` key overwrites
`configs/parking_spots.json`; `q` exits without saving. Map the actual bays,
not the drive lanes. After saving, run `python .\init_db.py` to refresh the
stored polygon geometry. Existing saved bays are displayed when the tool opens.
Press Backspace to undo a corner of the bay currently being drawn, or `u` to
remove the last completed bay so you can redraw it.

For the BAC camera, `cameras.json` uses the IP Webcam stream URL
`http://10.202.152.251:8080/video`. The `/browserfs.html` page is a browser
viewer; the detector must use its `/video` stream endpoint. Keep IP Webcam
running and both devices on the same network. If the camera's IP address
changes, update `source` with the new HTTP video URL. The detector scales
mapped coordinates from the `coordinate_reference` image dimensions to the
incoming frame; the camera still needs the same viewpoint and framing as the
reference image. Large aspect-ratio differences can distort the overlay and
require remapping.
