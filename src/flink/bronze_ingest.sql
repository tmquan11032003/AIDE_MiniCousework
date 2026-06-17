-- Flink SQL: stream coffee.events (Kafka) -> Iceberg bronze.raw_events (on MinIO).
-- Bronze is APPEND-ONLY raw capture (keeps upstream duplicates); dedup happens in Silver (M5).
-- event_timestamp carries an event-time watermark (5 min lateness) to model event vs ingest time.

SET 'execution.checkpointing.interval' = '10s';
SET 'table.dml-sync' = 'false';

-- Kafka source: parse JSON, event-time watermark on event_timestamp.
CREATE TEMPORARY TABLE kafka_events (
  event_id STRING,
  event_type STRING,
  event_timestamp TIMESTAMP(3),
  created_ts TIMESTAMP(3),
  customer_id STRING,
  store_id STRING,
  session_id STRING,
  device_type STRING,
  channel STRING,
  product_id STRING,
  order_id STRING,
  quantity INT,
  price DOUBLE,
  WATERMARK FOR event_timestamp AS event_timestamp - INTERVAL '5' MINUTE
) WITH (
  'connector' = 'kafka',
  'topic' = 'coffee.events',
  'properties.bootstrap.servers' = 'kafka:9092',
  'properties.group.id' = 'flink-bronze',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json',
  'json.timestamp-format.standard' = 'ISO-8601',
  'json.ignore-parse-errors' = 'true'
);

-- Iceberg REST catalog backed by MinIO (S3).
CREATE CATALOG iceberg WITH (
  'type' = 'iceberg',
  'catalog-impl' = 'org.apache.iceberg.rest.RESTCatalog',
  'uri' = 'http://rest:8181',
  'warehouse' = 's3://warehouse/',
  'io-impl' = 'org.apache.iceberg.aws.s3.S3FileIO',
  's3.endpoint' = 'http://minio:9000',
  's3.path-style-access' = 'true'
);

CREATE DATABASE IF NOT EXISTS iceberg.bronze;

DROP TABLE IF EXISTS iceberg.bronze.raw_events;

CREATE TABLE IF NOT EXISTS iceberg.bronze.raw_events (
  event_id STRING,
  event_type STRING,
  event_timestamp TIMESTAMP(6),
  created_ts TIMESTAMP(6),
  customer_id STRING,
  store_id STRING,
  session_id STRING,
  device_type STRING,
  channel STRING,
  product_id STRING,
  order_id STRING,
  quantity INT,
  price DOUBLE,
  ingest_ts TIMESTAMP(6) -- pipeline ingest time (Flink), distinct from event/created ts
);

-- Append every event into Bronze (raw). ingest_ts = pipeline write time (Flink).
INSERT INTO iceberg.bronze.raw_events
SELECT
  event_id, event_type,
  CAST(event_timestamp AS TIMESTAMP(6)),
  CAST(created_ts AS TIMESTAMP(6)),
  customer_id, store_id, session_id, device_type, channel,
  product_id, order_id, quantity, price,
  CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6))
FROM kafka_events;
