import asyncio
import traceback
from typing import Any, Dict

from classification.celery_app import celery_app
from classification.db import get_job, save_job


def _run_async(coro):
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


def _phase1_analyze(job_id: str, state: dict):
    from classification.agents.problem_analyzer import problem_analyzer_node
    state = _run_async(problem_analyzer_node(state))
    _save(job_id, state)


def _phase2_profile_and_run(job_id: str, state: dict):
    from classification.agents.data_profiler import data_profiler_node
    from classification.agents.pipeline_designer import pipeline_designer_node
    from classification.graph import parallel_experiments_node
    from classification.agents.model_selector import model_selector_node

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
    from classification.agents.documentation_agent import documentation_agent_node
    from classification.agents.output_agent import output_agent_node

    state["model_approved"] = True
    state["current_phase"] = "generating_outputs"
    _save(job_id, state)

    state = _run_async(documentation_agent_node(state))
    _save(job_id, state)

    state = _run_async(output_agent_node(state))
    _save(job_id, state)


@celery_app.task(name="classification.tasks.run_pipeline_task")
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


@celery_app.task(name="classification.tasks.resume_pipeline_task")
def resume_pipeline_task(job_id: str, resume_at: str, payload: Dict[str, Any]):
    state = get_job(job_id)
    if not state:
        return {"error": "Job not found"}

    try:
        if resume_at == "await_problem_approval":
            corrections = payload.get("corrections") or {}
            if corrections.get("target_column"):
                state["target_column"] = corrections["target_column"]
            if corrections.get("task_type"):
                state["task_type"] = corrections["task_type"]
            _save(job_id, state)
            _phase2_profile_and_run(job_id, state)

        elif resume_at == "await_model_approval":
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
