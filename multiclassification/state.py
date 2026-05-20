from typing import TypedDict, Optional, List, Dict, Any, Literal


class ExperimentResult(TypedDict):
    experiment_id: str
    architecture_name: str
    generated_code: str
    stdout: str
    stderr: str
    exit_code: int
    parsed_metrics: Dict[str, Any]
    success: bool
    retry_count: int
    failure_type: Optional[str]
    fix_history: List[str]
    mlflow_run_id: Optional[str]


class MultiClassState(TypedDict):
    # Job metadata
    job_id: str
    user_description: str
    dataset_path: str
    dataset_columns: List[str]
    dataset_sample_rows: List[Dict[str, Any]]
    dataset_held_out_rows: List[Dict[str, Any]]
    dataset_row_count: int

    # Problem analysis
    task_type: Optional[Literal["multiclass_classification"]]
    target_column: Optional[str]
    evaluation_metric: Optional[str]
    domain_flags: List[str]
    problem_analysis_raw: Optional[str]

    # Human approval gates
    problem_approved: bool
    model_approved: bool

    # Data profile
    profile_report: Optional[Dict[str, Any]]
    validation_warnings: List[Dict[str, str]]
    leakage_warnings: List[str]
    class_imbalance_detected: bool
    imbalance_ratio: Optional[float]
    class_distribution: Dict[str, int]

    # Multiclass-specific
    num_classes: int
    class_names: List[str]
    imbalanced_classes: List[str]
    per_class_metrics: Optional[Dict[str, Any]]
    encoding_map: Optional[Dict]

    # Pipeline design
    architectures: List[Dict[str, Any]]

    # Experiments
    experiment_results: List[ExperimentResult]
    current_retry_count: int

    # Model selection
    winning_experiment: Optional[ExperimentResult]
    winning_justification: Optional[str]

    # Outputs
    model_card: Optional[str]
    shap_plot_path: Optional[str]
    generated_endpoint_code: Optional[str]
    generated_requirements: Optional[str]
    plain_english_explanation: Optional[str]

    # Pipeline control
    current_phase: str
    error_message: Optional[str]
    debug_log: List[Dict[str, Any]]
