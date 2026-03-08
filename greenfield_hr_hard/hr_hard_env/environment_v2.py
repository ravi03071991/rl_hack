from __future__ import annotations

from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

from .models import HardHRAction, HardHRObservation
from .rubric import HardRubricEvaluator
from .tasks_v2 import TASKS_V2, TASK_INDEX_V2, EnterpriseTaskV2


TOOL_DEFINITIONS_V2 = [
    {"name": "workday_get_worker_profile", "description": "Fetch worker profile and policy payload.", "parameters": {"worker_ref": "string"}},
    {"name": "workday_update_worker_lifecycle", "description": "Update worker lifecycle event in Workday.", "parameters": {"worker_ref": "string", "event": "string"}},
    {"name": "workday_update_compensation", "description": "Update compensation band in Workday.", "parameters": {"worker_ref": "string", "comp_band": "string"}},
    {"name": "okta_provision_access_bundle", "description": "Provision access profile in Okta.", "parameters": {"worker_ref": "string", "access_profile": "string"}},
    {"name": "okta_deprovision_access_bundle", "description": "Deprovision access profile in Okta.", "parameters": {"worker_ref": "string", "access_profile": "string"}},
    {"name": "servicenow_open_hr_case", "description": "Open an HR case in ServiceNow.", "parameters": {"worker_ref": "string", "case_type": "string"}},
    {"name": "servicenow_open_it_task", "description": "Open an IT task in ServiceNow.", "parameters": {"worker_ref": "string", "task_type": "string"}},
    {"name": "jira_create_compliance_ticket", "description": "Create compliance ticket in Jira.", "parameters": {"worker_ref": "string", "control_domain": "string"}},
    {"name": "jira_transition_ticket", "description": "Transition Jira ticket status.", "parameters": {"ticket_id": "string", "status": "string"}},
    {"name": "confluence_update_policy_page", "description": "Update Confluence policy page.", "parameters": {"page_id": "string"}},
    {"name": "slack_notify_stakeholders", "description": "Notify workflow stakeholders in Slack.", "parameters": {"channel": "string"}},
    {"name": "workflow_finalize", "description": "Finalize and score the workflow.", "parameters": {}},
]


class EnterpriseWorkflowEnvironmentV2(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self, seed: int = 42):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task_idx = 0
        self._done = False
        self._current_task: EnterpriseTaskV2 | None = None
        self._evaluator = HardRubricEvaluator()
        self.action_log: list[dict] = []

        self._lookup_done = False
        self._last_jira_ticket_id: str | None = None
        self._next_ticket_num = 1000
        self._next_case_num = 2000
        self._next_it_task_num = 3000

    def reset(self) -> HardHRObservation:
        self._current_task = TASKS_V2[self._task_idx % len(TASKS_V2)]
        self._task_idx += 1
        return self._reset_common()

    def reset_to_task(self, task_id: str) -> HardHRObservation:
        self._current_task = TASK_INDEX_V2[task_id]
        return self._reset_common()

    def _reset_common(self) -> HardHRObservation:
        self._done = False
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.action_log = []
        self._lookup_done = False
        self._last_jira_ticket_id = None
        return self._obs("", {}, reward=0.0, done=False)

    def step(self, action: HardHRAction) -> HardHRObservation:  # type: ignore[override]
        if self._done:
            return self._obs(action.tool_name, {"ok": False, "error": "episode_already_done"}, reward=0.0, done=True)

        self._state.step_count += 1
        result = self._execute_tool(action)
        self.action_log.append({"tool": action.tool_name, "params": action.arguments, "result": result})

        max_steps = self._current_task.max_steps if self._current_task is not None else 8
        forced_done = action.tool_name == "workflow_finalize"
        done = forced_done or self._state.step_count >= max_steps
        self._done = done

        reward = 0.0
        metadata = {}
        if done and self._current_task is not None:
            eval_result = self._evaluator.evaluate(self._current_task.rubric_criteria, self.action_log)
            reward = float(eval_result["score"])
            metadata = {"evaluation": eval_result}

        return self._obs(action.tool_name, result, reward=reward, done=done, metadata=metadata)

    @property
    def state(self) -> State:
        return self._state

    def _validate_expected(self, tool_name: str, args: dict) -> tuple[bool, str]:
        if self._current_task is None:
            return False, "no_task"
        expected = self._current_task.expected_params.get(tool_name, {})
        for key, expected_value in expected.items():
            if key == "ticket_id":
                continue
            actual = args.get(key)
            if actual is None or str(actual) != str(expected_value):
                return False, f"{key}_mismatch"
        return True, ""

    def _execute_tool(self, action: HardHRAction) -> dict:
        if self._current_task is None:
            return {"ok": False, "error": "no_task"}

        tool = action.tool_name
        args = action.arguments
        allowed = set(self._current_task.required_tools)

        if tool not in allowed and tool != "workday_get_worker_profile":
            return {"ok": False, "error": "tool_not_in_required_path"}

        if tool == "workday_get_worker_profile":
            ok, error = self._validate_expected(tool, args)
            if not ok:
                return {"ok": False, "error": error}
            self._lookup_done = True
            expected = self._current_task.expected_params
            payload = {
                "ok": True,
                "worker_ref": expected["workday_get_worker_profile"]["worker_ref"],
                "event": expected["workday_update_worker_lifecycle"]["event"],
                "comp_band": expected["workday_update_compensation"]["comp_band"],
                "access_profile": expected["okta_provision_access_bundle"]["access_profile"],
                "case_type": expected["servicenow_open_hr_case"]["case_type"],
                "control_domain": expected["jira_create_compliance_ticket"]["control_domain"],
                "policy_page": expected["confluence_update_policy_page"]["page_id"],
                "channel": expected["slack_notify_stakeholders"]["channel"],
                "required_tools": self._current_task.required_tools,
            }
            return payload

        if not self._lookup_done and tool != "workflow_finalize":
            return {"ok": False, "error": "lookup_required"}

        if tool == "jira_create_compliance_ticket":
            ok, error = self._validate_expected(tool, args)
            if not ok:
                return {"ok": False, "error": error}
            self._last_jira_ticket_id = f"JIRA-{self._next_ticket_num}"
            self._next_ticket_num += 1
            return {"ok": True, "ticket_id": self._last_jira_ticket_id}

        if tool == "jira_transition_ticket":
            if self._last_jira_ticket_id is None:
                return {"ok": False, "error": "ticket_required"}
            ticket_id = str(args.get("ticket_id", ""))
            status = str(args.get("status", ""))
            if ticket_id != self._last_jira_ticket_id:
                return {"ok": False, "error": "ticket_id_mismatch"}
            if status != "done":
                return {"ok": False, "error": "status_mismatch"}
            return {"ok": True, "ticket_id": ticket_id, "status": status}

        if tool == "servicenow_open_hr_case":
            ok, error = self._validate_expected(tool, args)
            if not ok:
                return {"ok": False, "error": error}
            case_id = f"HRCASE-{self._next_case_num}"
            self._next_case_num += 1
            return {"ok": True, "case_id": case_id}

        if tool == "servicenow_open_it_task":
            ok, error = self._validate_expected(tool, args)
            if not ok:
                return {"ok": False, "error": error}
            it_task = f"ITTASK-{self._next_it_task_num}"
            self._next_it_task_num += 1
            return {"ok": True, "task_id": it_task}

        if tool == "workflow_finalize":
            return {"ok": True, "status": "finalizing"}

        ok, error = self._validate_expected(tool, args)
        if not ok:
            return {"ok": False, "error": error}
        return {"ok": True}

    def _obs(self, tool_name: str, tool_result: dict, reward: float, done: bool, metadata: dict | None = None) -> HardHRObservation:
        metadata = metadata or {}
        if self._current_task is None:
            task_id = ""
            instruction = ""
            max_steps = 8
        else:
            task_id = self._current_task.task_id
            instruction = self._current_task.instruction
            max_steps = self._current_task.max_steps

        return HardHRObservation(
            task_id=task_id,
            instruction=instruction,
            tool_name=tool_name,
            tool_result=tool_result,
            step=self._state.step_count,
            max_steps=max_steps,
            available_tools=[t["name"] for t in TOOL_DEFINITIONS_V2],
            done=done,
            reward=reward,
            metadata=metadata,
        )
