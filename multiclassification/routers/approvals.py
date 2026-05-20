from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from multiclassification.db import get_job, save_job
from multiclassification.tasks import resume_pipeline_task

router = APIRouter(prefix="/jobs", tags=["multiclassification-approvals"])


class ProblemApprovalRequest(BaseModel):
    approved: bool
    corrections: Optional[Dict[str, str]] = None


class ModelApprovalRequest(BaseModel):
    approved: bool
    selected_experiment_id: Optional[str] = None


@router.post("/{job_id}/approve-problem")
async def approve_problem(job_id: str, body: ProblemApprovalRequest):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    if state.get("current_phase") != "awaiting_problem_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting problem approval. Current phase: {state.get('current_phase')}",
        )

    if not body.approved:
        return {"status": "rejected", "message": "Approval rejected. Job remains paused."}

    resume_payload = {"corrections": body.corrections or {}}
    resume_pipeline_task.delay(job_id, "await_problem_approval", resume_payload)

    state["current_phase"] = "resuming"
    save_job(job_id, state)

    return {"status": "approved", "job_id": job_id}


@router.post("/{job_id}/approve-model")
async def approve_model(job_id: str, body: ModelApprovalRequest):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    if state.get("current_phase") != "awaiting_model_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting model approval. Current phase: {state.get('current_phase')}",
        )

    if not body.approved:
        return {"status": "rejected", "message": "Model approval rejected. Job remains paused."}

    resume_payload = {"selected_experiment_id": body.selected_experiment_id}
    resume_pipeline_task.delay(job_id, "await_model_approval", resume_payload)

    state["current_phase"] = "resuming"
    save_job(job_id, state)

    return {"status": "approved", "job_id": job_id}
