"""
HR Onboarding/Offboarding Environment Implementation.

An OpenEnv environment that simulates enterprise HR workflows.
The agent calls tools (hr_create_employee, it_assign_asset, etc.)
to complete onboarding/offboarding tasks. Reward is computed via rubrics.
"""

import json
import random
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from models import HROnboardingAction, HROnboardingObservation

try:
    from .world import WorldState
    from .tools import ToolRegistry, TOOL_DEFINITIONS
    from .tasks import TaskGenerator
    from .rubrics import RubricEvaluator
except ImportError:
    from world import WorldState
    from tools import ToolRegistry, TOOL_DEFINITIONS
    from tasks import TaskGenerator
    from rubrics import RubricEvaluator


class HROnboardingEnvironment(Environment):
    """
    HR Onboarding/Offboarding environment.

    Simulates an enterprise HR system with 200+ employees, 8 departments,
    RBAC, approval chains, and IT provisioning. The agent calls one of 25
    tools per step to complete onboarding/offboarding tasks.

    Example:
        >>> env = HROnboardingEnvironment()
        >>> obs = env.reset()
        >>> print(obs.instruction)  # "Onboard Priya Sharma to Engineering..."
        >>>
        >>> obs = env.step(HROnboardingAction(
        ...     tool_name="hr_create_employee",
        ...     arguments={"name": "Priya Sharma", "department": "Engineering",
        ...                "level": "L2", "role": "Software Engineer"}
        ... ))
        >>> print(obs.tool_result)  # {"success": true, "employee": {...}}
        >>> print(obs.reward)       # 0.0 (intermediate) or 0.85 (final)
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self, seed: int = 42, max_steps: int = 15):
        """Initialize the HR environment."""
        self._seed = seed
        self._max_steps = max_steps
        self._rng = random.Random(seed)

        # World state + tools
        self.world = WorldState()
        self.tool_registry = ToolRegistry(self.world)
        self.evaluator = RubricEvaluator()

        # Tasks
        self._task_gen = TaskGenerator(self.world, seed=seed)
        self._tasks = self._task_gen.generate_all_tasks()
        self._task_idx = 0
        self._current_task = None

        # Episode state
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._done = False
        self._tool_names = [t["name"] for t in TOOL_DEFINITIONS]

    def reset(self) -> HROnboardingObservation:
        """
        Reset the environment for a new episode.

        Picks the next task, resets world state, returns initial observation
        with the task instruction and available tools.
        """
        self.world.reset()
        self._done = False

        # Pick next task (cycle through)
        self._current_task = self._tasks[self._task_idx % len(self._tasks)]
        self._task_idx += 1

        # Apply task setup if any
        if self._current_task.setup_fn:
            self._current_task.setup_fn(self.world)

        self._state = State(episode_id=str(uuid4()), step_count=0)

        return HROnboardingObservation(
            task_id=self._current_task.task_id,
            instruction=self._current_task.instruction,
            tool_name="",
            tool_result={},
            step=0,
            max_steps=self._max_steps,
            available_tools=self._tool_names,
            done=False,
            reward=0.0,
            metadata={
                "difficulty": self._current_task.difficulty,
                "category": self._current_task.category,
                "context": self._current_task.context,
            },
        )

    def step(self, action: HROnboardingAction) -> HROnboardingObservation:  # type: ignore[override]
        """
        Execute one step: call the specified tool and return the result.

        Args:
            action: HROnboardingAction with tool_name and arguments.

        Returns:
            HROnboardingObservation with tool result, reward (on final step), and done flag.
        """
        if self._done:
            return HROnboardingObservation(
                task_id=self._current_task.task_id if self._current_task else "",
                instruction="",
                tool_name=action.tool_name,
                tool_result={"error": "Episode already finished"},
                step=self._state.step_count,
                max_steps=self._max_steps,
                available_tools=self._tool_names,
                done=True,
                reward=0.0,
            )

        self._state.step_count += 1

        # Execute the tool
        result = self.tool_registry.execute(action.tool_name, action.arguments)

        # Check if episode is done
        done = self._state.step_count >= self._max_steps
        self._done = done

        # Compute reward on final step
        reward = 0.0
        eval_info = {}
        if done and self._current_task:
            eval_result = self.evaluator.evaluate(self._current_task, self.world.action_log)
            reward = eval_result["score"]
            eval_info = eval_result

        return HROnboardingObservation(
            task_id=self._current_task.task_id if self._current_task else "",
            instruction=self._current_task.instruction if self._current_task else "",
            tool_name=action.tool_name,
            tool_result=result,
            step=self._state.step_count,
            max_steps=self._max_steps,
            available_tools=self._tool_names,
            done=done,
            reward=reward,
            metadata={
                "step": self._state.step_count,
                **({"evaluation": eval_info} if eval_info else {}),
            },
        )

    @property
    def state(self) -> State:
        """Get the current environment state."""
        return self._state
