CREATE DATABASE IF NOT EXISTS smart_parking
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'parking_app'@'127.0.0.1'
  IDENTIFIED BY 'DAMESEVERUS@455';

GRANT ALL PRIVILEGES ON smart_parking.* TO 'parking_app'@'127.0.0.1';
FLUSH PRIVILEGES;

CREATE USER IF NOT EXISTS 'parking_app'@'localhost'
  IDENTIFIED BY 'DAMESEVERUS@455';

ALTER USER 'parking_app'@'localhost'
  IDENTIFIED BY 'DAMESEVERUS@455';

GRANT ALL PRIVILEGES ON smart_parking.* TO 'parking_app'@'localhost';