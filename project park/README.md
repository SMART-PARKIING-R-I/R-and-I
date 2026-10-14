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

The source configured as `Lot_2_empty.png` is a still image, not a live camera.
The detector processes it once and leaves its preview window open until you
press `q`. If the webcam cannot be opened or returns no frame, its worker logs
an error and exits instead of repeatedly retrying the broken source.

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
