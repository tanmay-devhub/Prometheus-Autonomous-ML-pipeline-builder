import asyncio
import traceback
from typing import Any, Dict

from backend.celery_app import celery_app
from backend.db import get_job, save_job


def _run_async(coro):
    # Only catch errors from get_event_loop() itself (no current loop, or closed loop).
    # Never catch RuntimeError from inside run_until_complete — that would try to
    # reuse an already-started coroutine on a new loop, which Python forbids.
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


def _save(job_id: str, state: dict):
    save_job(job_id, state)


# ── Phase runners ────────────────────────────────────────────────────────────

def _phase1_analyze(job_id: str, state: dict):
    """Run problem_analyzer → pause at awaiting_problem_approval."""
    from backend.agents.problem_analyzer import problem_analyzer_node
    state = _run_async(problem_analyzer_node(state))
    _save(job_id, state)


def _phase2_profile_and_run(job_id: str, state: dict):
    """data_profiler → pipeline_designer → parallel experiments → model_selector."""
    from backend.agents.data_profiler import data_profiler_node
    from backend.agents.pipeline_designer import pipeline_designer_node
    from backend.graph import parallel_experiments_node
    from backend.agents.model_selector import model_selector_node

    state["problem_approved"] = True
    state["current_phase"] = "profiling"
    _save(job_id, state)

    state = _run_async(data_profiler_node(state))
    _save(job_id, state)

    state = _run_async(pipeline_designer_node(state))
    _save(job_id, state)

    state = _run_async(parallel_experiments_node(state))
    _save(job_id, state)

    state = _run_async(model_selector_node(state))
    _save(job_id, state)


def _phase3_output(job_id: str, state: dict):
    """documentation_agent → output_agent → complete."""
    from backend.agents.documentation_agent import documentation_agent_node
    from backend.agents.output_agent import output_agent_node

    state["model_approved"] = True
    state["current_phase"] = "generating_outputs"
    _save(job_id, state)

    state = _run_async(documentation_agent_node(state))
    _save(job_id, state)

    state = _run_async(output_agent_node(state))
    _save(job_id, state)


# ── Celery tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.run_pipeline_task")
def run_pipeline_task(job_id: str):
    state = get_job(job_id)
    if not state:
        return {"error": "Job not found"}
    try:
        _phase1_analyze(job_id, state)
    except Exception as e:
        state = get_job(job_id) or state
        state["current_phase"] = "failed"
        state["error_message"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        _save(job_id, state)
    return {"job_id": job_id, "status": "awaiting_problem_approval"}


@celery_app.task(name="tasks.resume_pipeline_task")
def resume_pipeline_task(job_id: str, resume_at: str, payload: Dict[str, Any]):
    state = get_job(job_id)
    if not state:
        return {"error": "Job not found"}

    try:
        if resume_at == "await_problem_approval":
            # Apply any user corrections
            corrections = payload.get("corrections") or {}
            if corrections.get("target_column"):
                state["target_column"] = corrections["target_column"]
            if corrections.get("task_type"):
                state["task_type"] = corrections["task_type"]
            _save(job_id, state)
            _phase2_profile_and_run(job_id, state)

        elif resume_at == "await_model_approval":
            # Allow user to override winning experiment
            selected_id = payload.get("selected_experiment_id")
            if selected_id:
                for exp in state.get("experiment_results", []):
                    if exp.get("experiment_id") == selected_id:
                        state["winning_experiment"] = exp
                        state["winning_justification"] = "Manually selected by user."
                        break
            _save(job_id, state)
            _phase3_output(job_id, state)

    except Exception as e:
        state = get_job(job_id) or state
        state["current_phase"] = "failed"
        state["error_message"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        _save(job_id, state)

    return {"job_id": job_id, "status": "resumed"}
