#!/bin/sh
# Banco do WuzAPI da Barberya (servico wuzapi-barberya). Num volume que ja
# existe o Postgres nao roda esta pasta de novo; crie na mao com:
#   docker compose exec -T postgres sh /docker-entrypoint-initdb.d/02-wuzapi-barberya.sh
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE USER wuzapi_barberya WITH PASSWORD '${BARBERYA_WUZAPI_DB_PASSWORD}';
CREATE DATABASE wuzapi_barberya OWNER wuzapi_barberya;
SQL
