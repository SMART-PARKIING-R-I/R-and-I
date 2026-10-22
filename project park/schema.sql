CREATE TABLE IF NOT EXISTS parking_lots (
    lot_id VARCHAR(64) NOT NULL PRIMARY KEY,
    name VARCHAR(120) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cameras (
    camera_id VARCHAR(64) NOT NULL PRIMARY KEY,
    lot_id VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_cameras_camera_lot (camera_id, lot_id),
    CONSTRAINT fk_cameras_lot
        FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS parking_spots (
    lot_id VARCHAR(64) NOT NULL,
    spot_id VARCHAR(64) NOT NULL,
    geometry JSON NOT NULL,
    status ENUM('vacant', 'occupied') NOT NULL DEFAULT 'vacant',
    updated_at DATETIME(6) NULL,
    PRIMARY KEY (lot_id, spot_id),
    CONSTRAINT fk_spots_lot
        FOREIGN KEY (lot_id) REFERENCES parking_lots (lot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS occupancy_events (
    event_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    lot_id VARCHAR(64) NOT NULL,
    spot_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    status ENUM('vacant', 'occupied') NOT NULL,
    observed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    KEY ix_events_spot_time (lot_id, spot_id, observed_at),
    CONSTRAINT fk_events_spot
        FOREIGN KEY (lot_id, spot_id)
        REFERENCES parking_spots (lot_id, spot_id),
    CONSTRAINT fk_events_camera_lot
        FOREIGN KEY (camera_id, lot_id)
        REFERENCES cameras (camera_id, lot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
