"""
FastAPI application for the HR Onboarding/Offboarding Environment.

This module creates an HTTP server that exposes the HROnboardingEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action (tool call)
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 7860

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 7860 --workers 4
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

# Import from local models.py (PYTHONPATH includes /app/env in Docker)
from models import HROnboardingAction, HROnboardingObservation
from .hr_onboarding_environment import HROnboardingEnvironment
from fastapi.responses import RedirectResponse
import os


# Required for OpenEnv to mount the HF-style web UI at /web.
os.environ.setdefault("ENABLE_WEB_INTERFACE", "true")


# Create the app with web interface and README integration
app = create_app(
    HROnboardingEnvironment,
    HROnboardingAction,
    HROnboardingObservation,
    env_name="hr_onboarding_env",
    max_concurrent_envs=4,
)


@app.get("/", include_in_schema=False)
def root_redirect():
    """Match HF Space UX: open app at /web UI."""
    return RedirectResponse(url="/web")


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
