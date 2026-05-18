import json
import tempfile
import os
from typing import Dict, Optional

import mlflow

from backend.config import MLFLOW_TRACKING_URI

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


class MLflowTracker:
    def __init__(self):
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    def start_run(self, job_id: str, architecture_name: str) -> str:
        experiment_name = f"prometheus_{job_id}"
        try:
            experiment_id = mlflow.create_experiment(experiment_name)
        except mlflow.exceptions.MlflowException:
            experiment_id = mlflow.get_experiment_by_name(experiment_name).experiment_id

        run = mlflow.start_run(
            experiment_id=experiment_id,
            run_name=architecture_name,
        )
        mlflow.end_run()
        return run.info.run_id

    def log_params(self, run_id: str, params: Dict):
        with mlflow.start_run(run_id=run_id):
            mlflow.log_params(params)

    def log_metrics(self, run_id: str, metrics: Dict):
        with mlflow.start_run(run_id=run_id):
            mlflow.log_metrics(metrics)

    def log_code(self, run_id: str, code: str):
        with mlflow.start_run(run_id=run_id):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", prefix="pipeline_code_", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp_path = f.name
            try:
                mlflow.log_artifact(tmp_path, artifact_path="code")
            finally:
                os.unlink(tmp_path)

    def log_fix_attempt(self, run_id: str, retry_count: int, failure_type: str, fix: str):
        with mlflow.start_run(run_id=run_id):
            mlflow.set_tag(
                f"fix_attempt_{retry_count}",
                json.dumps({"failure_type": failure_type, "fix": fix[:500]}),
            )

    def end_run(self, run_id: str, status: str):
        with mlflow.start_run(run_id=run_id):
            mlflow.set_tag("final_status", status)

    def get_best_run(self, job_id: str, metric: str) -> Optional[Dict]:
        experiment_name = f"prometheus_{job_id}"
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if not experiment:
            return None
        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=[f"metrics.{metric} DESC"],
            max_results=1,
        )
        if runs.empty:
            return None
        row = runs.iloc[0]
        return row.to_dict()
