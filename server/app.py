"""
FastAPI application for the HR Onboarding/Offboarding Environment.

Serves both the OpenEnv API endpoints and an interactive web playground UI.
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required. Install with: uv sync"
    ) from e

from models import HROnboardingAction, HROnboardingObservation
from .hr_onboarding_environment import HROnboardingEnvironment
from .tools import TOOL_DEFINITIONS
from .rubrics import RubricEvaluator

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
import json


# Required for OpenEnv to mount the HF-style web UI at /web.
os.environ.setdefault("ENABLE_WEB_INTERFACE", "true")


# Create the OpenEnv app
app = create_app(
    HROnboardingEnvironment,
    HROnboardingAction,
    HROnboardingObservation,
    env_name="hr_onboarding_env",
    max_concurrent_envs=4,
)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Shared environment instance for the playground
_playground_env = HROnboardingEnvironment(seed=42, max_steps=15)


# --- Playground API endpoints ---

@app.get("/", include_in_schema=False)
def root_redirect():
    """Serve the interactive playground UI."""
    return RedirectResponse(url="/playground")


@app.get("/playground", include_in_schema=False)
def playground():
    """Serve the interactive playground HTML."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/api/tasks")
def get_tasks():
    """Return all tasks with metadata for the task picker."""
    env = _playground_env
    tasks = []
    # Save current state
    orig_idx = env._task_idx

    for i in range(len(env._tasks)):
        task = env._tasks[i]
        tasks.append({
            "index": i,
            "task_id": task.task_id,
            "instruction": task.instruction,
            "difficulty": task.difficulty,
            "category": task.category,
            "expected_tools": task.expected_tools,
            "num_criteria": len(task.rubric_criteria),
        })

    env._task_idx = orig_idx
    return tasks


@app.get("/api/tool_definitions")
def get_tool_definitions():
    """Return all tool definitions with descriptions and parameters."""
    return TOOL_DEFINITIONS


@app.post("/api/reset")
async def playground_reset(request: Request):
    """Reset the environment to a specific task."""
    body = await request.json()
    task_idx = body.get("task_idx", 0)

    env = _playground_env
    # Set task index so reset() picks the right task
    env._task_idx = task_idx
    obs = env.reset()

    return {
        "task_id": obs.task_id,
        "instruction": obs.instruction,
        "step": obs.step,
        "max_steps": obs.max_steps,
        "available_tools": obs.available_tools,
        "done": obs.done,
        "reward": obs.reward,
        "metadata": obs.metadata,
    }


@app.post("/api/step")
async def playground_step(request: Request):
    """Execute one tool call step."""
    body = await request.json()
    tool_name = body.get("tool_name", "")
    arguments = body.get("arguments", {})

    env = _playground_env
    action = HROnboardingAction(tool_name=tool_name, arguments=arguments)
    obs = env.step(action)

    return {
        "task_id": obs.task_id,
        "instruction": obs.instruction,
        "tool_name": obs.tool_name,
        "tool_result": obs.tool_result,
        "step": obs.step,
        "max_steps": obs.max_steps,
        "done": obs.done,
        "reward": obs.reward,
        "metadata": obs.metadata,
    }


@app.post("/api/evaluate")
async def playground_evaluate():
    """Force evaluation of current episode."""
    env = _playground_env
    evaluator = RubricEvaluator()

    if env._current_task:
        result = evaluator.evaluate(env._current_task, env.world.action_log)
        return result

    return {"score": 0, "passed": False, "criteria_results": [], "passed_count": 0, "total_criteria": 0}


def main():
    """Entry point for direct execution."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
