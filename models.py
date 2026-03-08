"""
Data models for the HR Onboarding/Offboarding Environment.

Defines the Action and Observation types used by the environment.
The agent sends HROnboardingAction (a tool call) and receives
HROnboardingObservation (the tool result + task context).
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from openenv.core.env_server.types import Action, Observation


class HROnboardingAction(Action):
    """Action for the HR environment — a tool call with name and arguments.

    The agent picks one of 25 available tools and provides arguments.

    Example:
        HROnboardingAction(
            tool_name="hr_create_employee",
            arguments={"name": "Priya Sharma", "department": "Engineering",
                       "level": "L2", "role": "Software Engineer"}
        )
    """

    tool_name: str = Field(..., description="Name of the tool to call (e.g. hr_create_employee, it_assign_asset)")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")


class HROnboardingObservation(Observation):
    """Observation returned after each step in the HR environment.

    Contains the tool execution result, task context, and episode progress.
    """

    task_id: str = Field(default="", description="Current task identifier")
    instruction: str = Field(default="", description="Task instruction for the agent")
    tool_name: str = Field(default="", description="Name of the tool that was called")
    tool_result: Dict[str, Any] = Field(default_factory=dict, description="Result returned by the tool")
    step: int = Field(default=0, description="Current step number")
    max_steps: int = Field(default=15, description="Maximum steps allowed")
    available_tools: List[str] = Field(default_factory=list, description="List of available tool names")
