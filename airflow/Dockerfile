# Airflow image + docker CLI so DAGs can `docker exec spark-iceberg spark-submit ...`
# to orchestrate the Spark batch pipeline running in the sibling container.
FROM apache/airflow:2.10.4-python3.11

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
    | tar -xz -C /usr/local/bin --strip-components=1 docker/docker \
    && rm -rf /var/lib/apt/lists/*
USER airflow
