# Flink image with the jars needed to read Kafka and write Apache Iceberg on MinIO (S3).
# Versions chosen for compatibility: Flink 1.19 + Iceberg 1.6.1 + Kafka connector 3.2.0-1.19.
FROM flink:1.19.1-scala_2.12-java11

ENV ICEBERG_VERSION=1.6.1
ENV FLINK_MINOR=1.19
ENV KAFKA_CONNECTOR_VERSION=3.2.0-1.19

# Iceberg Flink runtime (connector + catalog) and AWS bundle (S3FileIO + AWS SDK)
RUN cd /opt/flink/lib && \
    curl -fSL -o iceberg-flink-runtime.jar \
      https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime-${FLINK_MINOR}/${ICEBERG_VERSION}/iceberg-flink-runtime-${FLINK_MINOR}-${ICEBERG_VERSION}.jar && \
    curl -fSL -o iceberg-aws-bundle.jar \
      https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar && \
    curl -fSL -o flink-sql-connector-kafka.jar \
      https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR_VERSION}/flink-sql-connector-kafka-${KAFKA_CONNECTOR_VERSION}.jar && \
    curl -fSL -o flink-shaded-hadoop.jar \
      https://repo1.maven.org/maven2/org/apache/flink/flink-shaded-hadoop-2-uber/2.8.3-10.0/flink-shaded-hadoop-2-uber-2.8.3-10.0.jar
