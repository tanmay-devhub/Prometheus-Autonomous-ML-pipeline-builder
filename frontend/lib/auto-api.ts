const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AutoJobResult {
  job_id: string;
  task_type: "binary_classification" | "multiclass_classification" | "regression";
  redirect_to: "classification" | "multiclassification" | "regression";
  target_column: string;
  confidence: number;
  reasoning: string;
}

export async function autoCreateJob(
  file: File,
  description: string
): Promise<AutoJobResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("description", description);
  const res = await fetch(`${API_BASE}/auto/jobs`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
