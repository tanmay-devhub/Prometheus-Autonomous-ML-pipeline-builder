import base64
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from e2b_code_interpreter import Sandbox

from shared.config import E2B_API_KEY


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    parsed_metrics: Dict[str, float]
    error_type: Optional[str]
    error_message: Optional[str]
    execution_time_seconds: float
    model_pkl_b64: Optional[str] = None


class E2BExecutor:
    def __init__(self):
        self.api_key = E2B_API_KEY

    async def run(self, code: str, dataset_path: str, timeout: int = 300) -> ExecutionResult:
        start_time = time.time()
        sandbox = None
        try:
            sandbox = Sandbox.create(api_key=self.api_key, timeout=timeout)

            with open(dataset_path, "rb") as f:
                dataset_content = f.read()
            sandbox.files.write("/home/user/dataset.csv", dataset_content)
            sandbox.files.write("/home/user/pipeline.py", code.encode())

            sandbox.commands.run(
                "pip install scikit-learn xgboost lightgbm pandas numpy scipy shap -q",
                timeout=120.0,
            )

            result = sandbox.commands.run(
                "python /home/user/pipeline.py /home/user/dataset.csv",
                timeout=float(timeout),
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = result.exit_code if result.exit_code is not None else 0

            parsed_metrics: Dict[str, float] = {}
            error_type: Optional[str] = None
            error_message: Optional[str] = None
            success = False

            all_lines = [l.strip() for l in stdout.strip().split("\n") if l.strip()]

            _PKL_TAG = "__MODEL_PKL__:"
            model_pkl_b64: Optional[str] = None
            metric_lines = []
            for line in all_lines:
                if line.startswith(_PKL_TAG):
                    model_pkl_b64 = line[len(_PKL_TAG):]
                else:
                    metric_lines.append(line)

            if metric_lines:
                last_line = metric_lines[-1]
                try:
                    output_json = json.loads(last_line)
                    if output_json.get("error"):
                        error_type = output_json.get("error_type", "UnknownError")
                        error_message = output_json.get("error_message", "")
                        success = False
                    elif "metric_name" not in output_json or "metric_value" not in output_json:
                        error_type = "OutputParseError"
                        error_message = f"Output JSON missing metric_name/metric_value keys: {last_line[:300]}"
                        success = False
                    else:
                        metric_key = output_json["metric_name"]
                        parsed_metrics = {metric_key: output_json["metric_value"]}
                        parsed_metrics["train_samples"] = output_json.get("train_samples", 0)
                        parsed_metrics["test_samples"] = output_json.get("test_samples", 0)
                        # Capture all extra numeric/bool fields from output JSON
                        for extra in (
                            "mae", "r2", "rmse",
                            "rmse_pct_of_mean", "within_10_pct", "within_15_pct", "within_20_pct",
                            "target_mean", "target_log_transformed",
                            # multiclass extras
                            "accuracy", "f1_macro", "f1_weighted", "num_classes",
                        ):
                            if extra in output_json:
                                parsed_metrics[extra] = output_json[extra]
                        # Capture dict/list fields for multiclass
                        for extra_complex in ("per_class_f1", "class_names"):
                            if extra_complex in output_json:
                                parsed_metrics[extra_complex] = output_json[extra_complex]
                        success = True
                except json.JSONDecodeError:
                    error_type = "OutputParseError"
                    error_message = f"Last stdout line was not valid JSON: {last_line[:200]}"
                    success = False

            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                success=success,
                parsed_metrics=parsed_metrics,
                error_type=error_type,
                error_message=error_message,
                execution_time_seconds=time.time() - start_time,
                model_pkl_b64=model_pkl_b64,
            )

        except TimeoutError:
            return ExecutionResult(
                stdout="", stderr="Execution timed out", exit_code=-1,
                success=False, parsed_metrics={},
                error_type="TimeoutError",
                error_message=f"Execution exceeded {timeout} seconds",
                execution_time_seconds=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                stdout="", stderr=str(e), exit_code=-1,
                success=False, parsed_metrics={},
                error_type=type(e).__name__,
                error_message=str(e),
                execution_time_seconds=time.time() - start_time,
            )
        finally:
            if sandbox:
                try:
                    sandbox.kill()
                except Exception:
                    pass
