#!/usr/bin/env bash
# M3 smoke test: Spark creates an Iceberg table on MinIO (via the REST catalog),
# inserts rows, reads them back, and lists the files written to the object store.
# Run from the project root: bash docker/smoke_test.sh
set -e

COMPOSE="docker compose --env-file docker/.env -f docker/docker-compose.yml"

echo "=== Spark: create + insert + read an Iceberg table ==="
$COMPOSE exec -T spark-iceberg spark-sql -e "
  CREATE DATABASE IF NOT EXISTS coffee;
  DROP TABLE IF EXISTS coffee.smoke_test;
  CREATE TABLE coffee.smoke_test (id INT, name STRING) USING iceberg;
  INSERT INTO coffee.smoke_test VALUES (1,'espresso'),(2,'latte'),(3,'mocha');
  SELECT count(*) AS n_rows FROM coffee.smoke_test;
"

echo "=== MinIO: files written under s3://warehouse ==="
$COMPOSE exec -T mc mc ls -r minio/warehouse | head -20
