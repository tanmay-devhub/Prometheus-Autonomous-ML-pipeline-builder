const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface JobStatus {
  job_id: string;
  current_phase: string;
  error_message?: string;
  task_type?: string;
  target_column?: string;
  evaluation_metric?: string;
  experiment_count: number;
  winning_experiment?: string;
}

export interface ExperimentResult {
  experiment_id: string;
  architecture_name: string;
  generated_code: string;
  stdout: string;
  stderr: string;
  exit_code: number;
  parsed_metrics: Record<string, number>;
  success: boolean;
  retry_count: number;
  failure_type?: string;
  fix_history: Array<{ retry: number; failure_type: string; fix_applied: string }>;
  mlflow_run_id?: string;
}

export interface ColumnStat {
  column: string;
  dtype: string;
  null_count: number;
  null_pct: number;
  unique_count: number;
  min?: number;
  max?: number;
  mean?: number;
  std?: number;
  top_values?: Record<string, number>;
}

export interface ProfileReport {
  row_count: number;
  column_count: number;
  duplicate_count: number;
  duplicate_pct: number;
  columns: ColumnStat[];
  target_distribution: Record<string, number | string>;
  llm_interpretation: string;
  shap_features?: Array<{ feature: string; importance: number }>;
}

export async function createJob(file: File, description: string): Promise<{ job_id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("description", description);
  const res = await fetch(`${API_BASE}/jobs`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getFullJob(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getProfile(jobId: string): Promise<{
  profile_report: ProfileReport;
  validation_warnings: Array<{ severity: string; message: string; column: string }>;
  leakage_warnings: string[];
  class_imbalance_detected: boolean;
  imbalance_ratio?: number;
}> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/profile`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExperiments(jobId: string): Promise<{ experiment_results: ExperimentResult[] }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/experiments`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDebugLog(jobId: string): Promise<{ debug_log: any[] }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/debug-log`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getModelCard(jobId: string): Promise<{ model_card: string }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/model-card`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getEndpointCode(jobId: string): Promise<{ endpoint_code: string; requirements: string }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/endpoint-code`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExplanation(jobId: string): Promise<{
  plain_english_explanation: string;
  shap_features: Array<{ feature: string; importance: number }>;
  winning_justification: string;
}> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/explanation`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveProblem(
  jobId: string,
  approved: boolean,
  corrections?: { target_column?: string; task_type?: string }
) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/approve-problem`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, corrections }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveModel(
  jobId: string,
  approved: boolean,
  selected_experiment_id?: string
) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/approve-model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, selected_experiment_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
