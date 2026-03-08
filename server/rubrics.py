"""Reward/evaluation rubrics for HR Onboarding/Offboarding tasks.

Each task has a set of rubric criteria. This module evaluates agent action logs
against those criteria to compute rewards.
"""

import re
from typing import Any
try:
    from .tasks import Task
except ImportError:
    from tasks import Task


class RubricEvaluator:
    """Evaluates agent performance against task rubric criteria."""

    def __init__(self):
        self._checkers = {
            "tool_used": self._check_tool_used,
            "tool_not_used": self._check_tool_not_used,
            "tool_used_any": self._check_tool_used_any,
            "param_value": self._check_param_value,
            "param_contains": self._check_param_contains,
            "tool_order": self._check_tool_order,
            "tool_count": self._check_tool_count,
            "result_contains": self._check_result_contains,
        }

    def evaluate(self, task: Task, action_log: list[dict]) -> dict:
        """Evaluate action log against task rubric criteria.

        Returns:
            {
                "task_id": str,
                "criteria_results": list of {name, passed, description},
                "score": float (0.0-1.0),
                "passed": bool (all criteria satisfied),
            }
        """
        criteria_results = []
        for criterion in task.rubric_criteria:
            check_str = criterion["check"]
            passed = self._evaluate_criterion(check_str, action_log)
            criteria_results.append({
                "name": criterion["name"],
                "description": criterion["description"],
                "passed": passed,
            })

        total = len(criteria_results)
        passed_count = sum(1 for c in criteria_results if c["passed"])
        score = passed_count / total if total > 0 else 0.0

        return {
            "task_id": task.task_id,
            "criteria_results": criteria_results,
            "score": score,
            "passed": all(c["passed"] for c in criteria_results),
            "passed_count": passed_count,
            "total_criteria": total,
        }

    def _evaluate_criterion(self, check_str: str, action_log: list[dict]) -> bool:
        """Parse and evaluate a single criterion check string."""
        # Parse check type and args
        parts = check_str.split(":", 1)
        if len(parts) != 2:
            return False

        check_type = parts[0]
        check_args = parts[1]

        checker = self._checkers.get(check_type)
        if not checker:
            return False

        return checker(check_args, action_log)

    def _check_tool_used(self, tool_name: str, action_log: list[dict]) -> bool:
        """Check if a specific tool was used at least once."""
        return any(a["tool"] == tool_name for a in action_log)

    def _check_tool_not_used(self, tool_name: str, action_log: list[dict]) -> bool:
        """Check that a specific tool was NOT used."""
        return not any(a["tool"] == tool_name for a in action_log)

    def _check_tool_used_any(self, tools_csv: str, action_log: list[dict]) -> bool:
        """Check if any of the comma-separated tools were used."""
        tool_names = [t.strip() for t in tools_csv.split(",")]
        return any(a["tool"] in tool_names for a in action_log)

    def _check_param_value(self, spec: str, action_log: list[dict]) -> bool:
        """Check if a tool was called with a specific parameter value.
        Format: tool_name.param_name=expected_value
        """
        match = re.match(r"(\w+)\.(\w+)=(.+)", spec)
        if not match:
            return False
        tool_name, param_name, expected_value = match.groups()

        for action in action_log:
            if action["tool"] == tool_name:
                actual = action["params"].get(param_name)
                if actual is not None and str(actual) == expected_value:
                    return True
                # Check nested in 'updates' dict
                updates = action["params"].get("updates", {})
                if param_name in updates and str(updates[param_name]) == expected_value:
                    return True
        return False

    def _check_param_contains(self, spec: str, action_log: list[dict]) -> bool:
        """Check if a tool parameter contains a substring.
        Format: tool_name.param_name=substring
        """
        match = re.match(r"(\w+)\.(\w+)=(.+)", spec)
        if not match:
            return False
        tool_name, param_name, substring = match.groups()

        for action in action_log:
            if action["tool"] == tool_name:
                actual = action["params"].get(param_name, "")
                if substring.lower() in str(actual).lower():
                    return True
        return False

    def _check_tool_order(self, spec: str, action_log: list[dict]) -> bool:
        """Check that tool A was called before tool B.
        Format: tool_a<tool_b
        """
        parts = spec.split("<")
        if len(parts) != 2:
            return False
        tool_a, tool_b = parts

        idx_a = None
        idx_b = None
        for i, action in enumerate(action_log):
            if action["tool"] == tool_a and idx_a is None:
                idx_a = i
            if action["tool"] == tool_b and idx_b is None:
                idx_b = i

        if idx_a is None or idx_b is None:
            return False
        return idx_a < idx_b

    def _check_tool_count(self, spec: str, action_log: list[dict]) -> bool:
        """Check that a tool was called at least N times.
        Format: tool_name>=N
        """
        match = re.match(r"(\w+)>=(\d+)", spec)
        if not match:
            return False
        tool_name, min_count = match.groups()
        min_count = int(min_count)

        count = sum(1 for a in action_log if a["tool"] == tool_name)
        return count >= min_count

    def _check_result_contains(self, substring: str, action_log: list[dict]) -> bool:
        """Check if any tool result contains a substring."""
        for action in action_log:
            result_str = str(action.get("result", ""))
            if substring.lower() in result_str.lower():
                return True
        return False


def compute_reward(task: Task, action_log: list[dict]) -> float:
    """Convenience function to compute reward for a task given action log."""
    evaluator = RubricEvaluator()
    result = evaluator.evaluate(task, action_log)
    return result["score"]
