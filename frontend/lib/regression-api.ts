const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/regression";

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

export async function getProfile(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/profile`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExperiments(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/experiments`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDebugLog(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/debug-log`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getModelCard(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/model-card`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getEndpointCode(jobId: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/endpoint-code`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExplanation(jobId: string) {
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

export async function approveModel(jobId: string, approved: boolean, selected_experiment_id?: string) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/approve-model`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved, selected_experiment_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function testPredict(jobId: string, data: Record<string, any>) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/test-predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function modelPklUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/model.pkl`;
}
