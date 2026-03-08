"""HR Onboarding/Offboarding Environment Client."""

from typing import Dict

from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State
from openenv.core import EnvClient

from .models import HROnboardingAction, HROnboardingObservation


class HROnboardingEnv(
    EnvClient[HROnboardingAction, HROnboardingObservation]
):
    """
    Client for the HR Onboarding/Offboarding Environment.

    Maintains a persistent WebSocket connection to the environment server.
    Each client instance has its own dedicated environment session.

    Example:
        >>> with HROnboardingEnv(base_url="http://localhost:7860") as client:
        ...     result = client.reset()
        ...     print(result.observation.instruction)
        ...
        ...     result = client.step(HROnboardingAction(
        ...         tool_name="hr_read_employee",
        ...         arguments={"emp_id": "emp_0001"}
        ...     ))
        ...     print(result.observation.tool_result)

    Example with Docker:
        >>> client = HROnboardingEnv.from_docker_image("hr-onboarding-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(HROnboardingAction(
        ...         tool_name="hr_search_employees",
        ...         arguments={"department": "Engineering"}
        ...     ))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: HROnboardingAction) -> Dict:
        """Convert HROnboardingAction to JSON payload for step message."""
        return {
            "tool_name": action.tool_name,
            "arguments": action.arguments,
        }

    def _parse_result(self, payload: Dict) -> StepResult[HROnboardingObservation]:
        """Parse server response into StepResult[HROnboardingObservation]."""
        obs_data = payload.get("observation", {})
        observation = HROnboardingObservation(
            task_id=obs_data.get("task_id", ""),
            instruction=obs_data.get("instruction", ""),
            tool_name=obs_data.get("tool_name", ""),
            tool_result=obs_data.get("tool_result", {}),
            step=obs_data.get("step", 0),
            max_steps=obs_data.get("max_steps", 15),
            available_tools=obs_data.get("available_tools", []),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """Parse server response into State object."""
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
