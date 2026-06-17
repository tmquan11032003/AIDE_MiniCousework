"""
Batch pipeline DAG: orchestrate the Spark medallion jobs Bronze -> Silver -> Gold -> DQ.

Each task runs `docker exec spark-iceberg spark-submit ...` against the sibling Spark
container (the Airflow image ships the docker CLI; the host socket is mounted).
Trigger manually:  airflow dags trigger batch_pipeline
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

SPARK = "docker exec spark-iceberg spark-submit /workspace/src/spark"

default_args = {"retries": 1}

with DAG(
    dag_id="batch_pipeline",
    description="Bronze -> Silver -> Gold -> DQ (Spark on Iceberg/MinIO)",
    start_date=datetime(2025, 1, 1),
    schedule=None,  # manual trigger
    catchup=False,
    default_args=default_args,
    tags=["coffee", "section02", "batch"],
) as dag:
    bronze = BashOperator(task_id="bronze_load", bash_command=f"{SPARK}/bronze_load.py")
    silver = BashOperator(task_id="silver", bash_command=f"{SPARK}/silver.py")
    gold = BashOperator(task_id="gold", bash_command=f"{SPARK}/gold.py")
    dq = BashOperator(task_id="dq_checks", bash_command=f"{SPARK}/dq_checks.py")

    bronze >> silver >> gold >> dq
