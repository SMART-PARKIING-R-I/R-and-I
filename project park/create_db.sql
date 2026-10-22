-- Run once as the MySQL root user:
--   mysql.exe -u root -p < create_db.sql
-- BEFORE running, replace CHANGE_ME below with your own local password and use
-- the same password for MYSQL_PASSWORD in your .env file. Never commit the real one.

CREATE DATABASE IF NOT EXISTS smart_parking
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'parking_app'@'127.0.0.1'
  IDENTIFIED BY 'CHANGE_ME';

GRANT ALL PRIVILEGES ON smart_parking.* TO 'parking_app'@'127.0.0.1';
FLUSH PRIVILEGES;

CREATE USER IF NOT EXISTS 'parking_app'@'localhost'
  IDENTIFIED BY 'CHANGE_ME';

ALTER USER 'parking_app'@'localhost'
  IDENTIFIED BY 'CHANGE_ME';

GRANT ALL PRIVILEGES ON smart_parking.* TO 'parking_app'@'localhost';
