from __future__ import annotations

from dataclasses import dataclass

from .catalog_v2 import TASK_CATALOG_V2, TaskTemplateV2


DEPARTMENTS = [
    "Engineering",
    "Product",
    "Finance",
    "HR",
    "Security",
    "Sales",
    "Operations",
    "Data",
]

COUNTRIES = ["US", "DE", "UK", "IN", "JP", "CA", "FR", "NL"]
ROLES = [
    "Backend Engineer",
    "Product Manager",
    "FPA Analyst",
    "HR Specialist",
    "Security Engineer",
    "Account Executive",
    "Program Manager",
    "Data Analyst",
]
ACCESS_PROFILES = [
    "eng_standard",
    "prod_standard",
    "finance_restricted",
    "hr_sensitive",
    "security_privileged",
    "sales_crm",
    "ops_standard",
    "data_readonly",
]
COMP_BANDS = ["L2", "L3", "L4", "L5", "M1"]
POLICY_PAGES = [
    "policy/onboarding-controls",
    "policy/access-governance",
    "policy/leave-compliance",
    "policy/performance-process",
    "policy/audit-remediation",
]
SLACK_CHANNELS = ["hr-ops", "it-helpdesk", "manager-ops", "compliance-ops"]


@dataclass(frozen=True)
class EnterpriseTaskV2:
    task_id: str
    instruction: str
    family: str
    difficulty: str
    max_steps: int
    required_tools: list[str]
    rubric_criteria: list[dict]
    expected_params: dict[str, dict]


def _idx(seed: int, offset: int, size: int) -> int:
    return (seed * 17 + offset * 13) % size


def _seed_from_template(template_id: str) -> int:
    tail = template_id.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else sum(ord(c) for c in template_id)


def _case_type_for_family(family: str) -> str:
    return {
        "onboarding": "new_hire_workflow",
        "offboarding": "termination_workflow",
        "role_change": "role_change_workflow",
        "leave_management": "leave_workflow",
        "contractor_lifecycle": "contractor_workflow",
        "cross_border_transfer": "global_transfer_workflow",
        "performance_and_pip": "performance_workflow",
        "audit_and_policy_remediation": "audit_remediation_workflow",
    }.get(family, "general_hr_workflow")


def _build_expected(template: TaskTemplateV2, seed: int) -> tuple[dict[str, dict], dict]:
    worker_ref = f"wrk_{seed:04d}"
    worker_country = COUNTRIES[_idx(seed, 1, len(COUNTRIES))]
    department = DEPARTMENTS[_idx(seed, 2, len(DEPARTMENTS))]
    role_title = ROLES[_idx(seed, 3, len(ROLES))]
    access_profile = ACCESS_PROFILES[_idx(seed, 4, len(ACCESS_PROFILES))]
    comp_band = COMP_BANDS[_idx(seed, 5, len(COMP_BANDS))]
    policy_page = POLICY_PAGES[_idx(seed, 6, len(POLICY_PAGES))]
    slack_channel = SLACK_CHANNELS[_idx(seed, 7, len(SLACK_CHANNELS))]
    case_type = _case_type_for_family(template.family)

    shared_payload = {
        "worker_ref": worker_ref,
        "country": worker_country,
        "department": department,
        "role_title": role_title,
        "access_profile": access_profile,
        "comp_band": comp_band,
        "policy_page": policy_page,
        "slack_channel": slack_channel,
        "case_type": case_type,
        "compliance_tags": list(template.compliance_tags),
    }

    expected: dict[str, dict] = {
        "workday_get_worker_profile": {"worker_ref": worker_ref},
        "workday_update_worker_lifecycle": {"worker_ref": worker_ref, "event": case_type},
        "workday_update_compensation": {"worker_ref": worker_ref, "comp_band": comp_band},
        "okta_provision_access_bundle": {"worker_ref": worker_ref, "access_profile": access_profile},
        "okta_deprovision_access_bundle": {"worker_ref": worker_ref, "access_profile": access_profile},
        "servicenow_open_hr_case": {"worker_ref": worker_ref, "case_type": case_type},
        "servicenow_open_it_task": {"worker_ref": worker_ref, "task_type": case_type},
        "jira_create_compliance_ticket": {"worker_ref": worker_ref, "control_domain": template.family},
        "jira_transition_ticket": {"status": "done"},
        "confluence_update_policy_page": {"page_id": policy_page},
        "slack_notify_stakeholders": {"channel": slack_channel},
        "workflow_finalize": {},
    }
    return expected, shared_payload


def _criteria_for_template(template: TaskTemplateV2, expected: dict[str, dict], worker_ref: str) -> list[dict]:
    criteria = [
        {"name": "lookup_used", "description": "Worker profile looked up", "check": "tool_used:workday_get_worker_profile"},
        {"name": "lookup_ref", "description": "Correct worker ref used", "check": f"param_value:workday_get_worker_profile.worker_ref={worker_ref}"},
    ]

    for tool in template.required_tools:
        if tool == "workflow_finalize":
            continue
        criteria.append({"name": f"used_{tool}", "description": f"Used {tool}", "check": f"tool_used:{tool}"})
        for k, v in expected.get(tool, {}).items():
            if tool == "jira_transition_ticket" and k == "status":
                pass
            criteria.append(
                {
                    "name": f"param_{tool}_{k}",
                    "description": f"Parameter {k} for {tool}",
                    "check": f"param_value:{tool}.{k}={v}",
                }
            )

    ordered = [t for t in template.required_tools if t != "workflow_finalize"]
    for i in range(len(ordered) - 1):
        left = ordered[i]
        right = ordered[i + 1]
        criteria.append(
            {
                "name": f"order_{left}_before_{right}",
                "description": f"{left} before {right}",
                "check": f"tool_order:{left}<{right}",
            }
        )

    criteria.append(
        {"name": "workflow_finalize", "description": "Finalize called", "check": "tool_used:workflow_finalize"}
    )
    return criteria


def build_enterprise_tasks_v2() -> list[EnterpriseTaskV2]:
    out: list[EnterpriseTaskV2] = []
    for template in TASK_CATALOG_V2:
        seed = _seed_from_template(template.template_id)
        expected, payload = _build_expected(template, seed)
        worker_ref = payload["worker_ref"]
        criteria = _criteria_for_template(template, expected, worker_ref)

        instruction = (
            f"Task {template.template_id}: {template.scenario} "
            f"Family={template.family}; Difficulty={template.difficulty}; WorkerRef={worker_ref}. "
            f"Systems in scope: {', '.join(template.apps)}. "
            "You must call workday_get_worker_profile first and then execute the required workflow tools "
            "in correct policy order before workflow_finalize. "
            "Use exact values from the lookup response."
        )

        out.append(
            EnterpriseTaskV2(
                task_id=f"v2_{template.template_id}",
                instruction=instruction,
                family=template.family,
                difficulty=template.difficulty,
                max_steps=template.horizon_steps,
                required_tools=list(template.required_tools),
                rubric_criteria=criteria,
                expected_params=expected,
            )
        )
    return out


TASKS_V2 = build_enterprise_tasks_v2()
TASK_INDEX_V2 = {task.task_id: task for task in TASKS_V2}
