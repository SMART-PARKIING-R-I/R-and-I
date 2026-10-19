PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS parking_lots (
    lot_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,
    lot_id TEXT NOT NULL,
    FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
);

CREATE TABLE IF NOT EXISTS parking_spots (
    lot_id TEXT NOT NULL,
    spot_id TEXT NOT NULL,
    geometry TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'vacant'
        CHECK (status IN ('vacant', 'occupied')),
    updated_at TEXT,
    PRIMARY KEY (lot_id, spot_id),
    FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
);

CREATE TABLE IF NOT EXISTS occupancy_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id TEXT NOT NULL,
    spot_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('vacant', 'occupied')),
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lot_id, spot_id)
        REFERENCES parking_spots (lot_id, spot_id),
    FOREIGN KEY (camera_id) REFERENCES cameras (camera_id)
);

CREATE INDEX IF NOT EXISTS ix_events_spot_time
    ON occupancy_events (lot_id, spot_id, observed_at);
