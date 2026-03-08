import os

from openenv.core.env_server.http_server import create_app

from .environment_v2 import EnterpriseWorkflowEnvironmentV2
from .models import HardHRAction, HardHRObservation

os.environ.setdefault("ENABLE_WEB_INTERFACE", "true")

app = create_app(
    EnterpriseWorkflowEnvironmentV2,
    HardHRAction,
    HardHRObservation,
    env_name="enterprise_hr_it_v2_env",
    max_concurrent_envs=8,
)


def main() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7863)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
