#!/bin/sh
# Banco proprio do WuzAPI no mesmo Postgres, separado do banco do app.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE USER wuzapi WITH PASSWORD '${WUZAPI_DB_PASSWORD}';
CREATE DATABASE wuzapi OWNER wuzapi;
SQL
