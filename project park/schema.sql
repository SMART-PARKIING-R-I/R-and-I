CREATE TABLE IF NOT EXISTS parking_lots (
    lot_id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,
    lot_id TEXT NOT NULL,
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
);

CREATE TABLE IF NOT EXISTS parking_spots (
    lot_id TEXT NOT NULL,
    spot_id TEXT NOT NULL,
    geometry TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'vacant',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (lot_id, spot_id),
    FOREIGN KEY (lot_id) REFERENCES parking_lots(lot_id)
);

CREATE TABLE IF NOT EXISTS occupancy_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id TEXT NOT NULL,
    spot_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ADD THIS TABLE AT THE BOTTOM OF SCHEMA.SQL:
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id TEXT NOT NULL,
    spot_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);