#!/bin/sh
set -eu
psql --username "$POSTGRES_USER" --dbname postgres --set app_password="$APP_DB_PASSWORD" --set lab_password="$LAB_DB_PASSWORD" <<'SQL'
CREATE USER saipport_app PASSWORD :'app_password';
CREATE USER saipport_lab PASSWORD :'lab_password';
CREATE DATABASE saipport OWNER saipport_app;
CREATE DATABASE saipport_lab OWNER saipport_lab;
REVOKE CONNECT ON DATABASE saipport FROM PUBLIC;
REVOKE CONNECT ON DATABASE saipport_lab FROM PUBLIC;
GRANT CONNECT ON DATABASE saipport TO saipport_app;
GRANT CONNECT ON DATABASE saipport_lab TO saipport_lab;
SQL
