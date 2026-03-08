from __future__ import annotations

from dataclasses import dataclass


APP_STACK = [
    "workday",
    "okta",
    "servicenow",
    "jira",
    "confluence",
    "slack",
    "google_workspace",
    "netsuite",
]


TOOL_CATALOG = [
    "workday_get_worker_profile",
    "workday_update_worker_lifecycle",
    "workday_update_compensation",
    "okta_provision_access_bundle",
    "okta_deprovision_access_bundle",
    "servicenow_open_hr_case",
    "servicenow_open_it_task",
    "jira_create_compliance_ticket",
    "jira_transition_ticket",
    "confluence_update_policy_page",
    "slack_notify_stakeholders",
    "workflow_finalize",
]


COMPLIANCE_TAGS = [
    "i9_timeline",
    "least_privilege",
    "gdpr_data_minimization",
    "record_retention",
    "fmla_eligibility",
]


@dataclass(frozen=True)
class TaskTemplateV2:
    template_id: str
    family: str
    difficulty: str
    horizon_steps: int
    apps: tuple[str, ...]
    required_tools: tuple[str, ...]
    compliance_tags: tuple[str, ...]
    scenario: str
    hard_rules: tuple[str, ...]
    success_checks: tuple[str, ...]
    weight: float


def _family_block(
    family: str,
    base_scenario: str,
    hard_rules: list[str],
    success_checks: list[str],
    required_tools: list[str],
    apps: list[str],
    compliance_tags: list[str],
    variants: list[str],
    start_index: int,
) -> list[TaskTemplateV2]:
    out: list[TaskTemplateV2] = []
    for i, variant in enumerate(variants):
        template_idx = start_index + i
        difficulty = "medium"
        horizon_steps = 8
        weight = 1.0
        if i >= 10:
            difficulty = "hard"
            horizon_steps = 10
            weight = 1.25
        if i >= 13:
            difficulty = "very_hard"
            horizon_steps = 12
            weight = 1.5

        out.append(
            TaskTemplateV2(
                template_id=f"{family}_{template_idx:03d}",
                family=family,
                difficulty=difficulty,
                horizon_steps=horizon_steps,
                apps=tuple(apps),
                required_tools=tuple(required_tools),
                compliance_tags=tuple(compliance_tags),
                scenario=f"{base_scenario} Variant: {variant}.",
                hard_rules=tuple(hard_rules),
                success_checks=tuple(success_checks),
                weight=weight,
            )
        )
    return out


def build_catalog_v2() -> list[TaskTemplateV2]:
    templates: list[TaskTemplateV2] = []

    templates += _family_block(
        family="onboarding",
        base_scenario="Execute new-hire onboarding across HR and IT systems",
        hard_rules=[
            "must_create_workday_worker_before_access_provisioning",
            "must_open_servicenow_it_task_before_jira_ticket_transition_done",
            "must_finalize_with_workflow_finalize",
        ],
        success_checks=[
            "workday_worker_status=pre_hire_to_active",
            "okta_bundle_matches_role_policy",
            "notifications_sent_to_manager_and_it",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "workday_update_worker_lifecycle",
            "okta_provision_access_bundle",
            "servicenow_open_it_task",
            "jira_create_compliance_ticket",
            "slack_notify_stakeholders",
            "workflow_finalize",
        ],
        apps=["workday", "okta", "servicenow", "jira", "slack"],
        compliance_tags=["i9_timeline", "least_privilege", "record_retention"],
        variants=[
            "US full-time engineer",
            "US sales hire with CRM access",
            "EU analyst requiring GDPR-aware data scope",
            "manager hire requiring elevated approvals",
            "finance hire with ERP segregation of duties",
            "security hire with privileged account constraints",
            "new grad hire with limited starter permissions",
            "rehire within one year requiring record reconciliation",
            "internal referral with expedited start date",
            "cross-functional product hire with shared toolset",
            "contract-to-hire conversion with staged access",
            "remote-first onboarding with delayed hardware shipment",
            "executive assistant requiring confidential calendar scopes",
            "intern cohort onboarding with template deviations",
            "acquisition hire with legacy identity mapping",
        ],
        start_index=1,
    )

    templates += _family_block(
        family="offboarding",
        base_scenario="Execute termination and secure offboarding workflow",
        hard_rules=[
            "must_deprovision_okta_before_workflow_finalize",
            "must_open_hr_case_for_termination_reason",
            "must_not_notify_broad_channels_for_confidential_terminations",
        ],
        success_checks=[
            "all_high_risk_access_removed",
            "servicenow_asset_return_task_opened",
            "jira_audit_ticket_closed_with_evidence",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "workday_update_worker_lifecycle",
            "okta_deprovision_access_bundle",
            "servicenow_open_hr_case",
            "servicenow_open_it_task",
            "jira_create_compliance_ticket",
            "jira_transition_ticket",
            "workflow_finalize",
        ],
        apps=["workday", "okta", "servicenow", "jira"],
        compliance_tags=["least_privilege", "record_retention", "gdpr_data_minimization"],
        variants=[
            "voluntary resignation with two-week notice",
            "involuntary termination immediate lockout",
            "contract end-date deactivation",
            "offboarding for employee on protected leave",
            "executive departure requiring legal hold",
            "security incident-driven termination",
            "cross-border employee departure",
            "acquisition rollback offboarding",
            "intern end-of-term offboarding",
            "retirement with phased access sunset",
            "high-risk privileged admin departure",
            "finance approver departure with SoD cleanup",
            "employee no-show on start date rescind",
            "vendor offboarding with shared credentials sweep",
            "deceased employee records-sensitive closure",
        ],
        start_index=16,
    )

    templates += _family_block(
        family="role_change",
        base_scenario="Handle internal transfer, promotion, or team move",
        hard_rules=[
            "must_update_workday_role_before_okta_access_changes",
            "must_enforce_least_privilege_deltas",
            "must_preserve_audit_trail_ticket",
        ],
        success_checks=[
            "old_access_removed_and_new_access_granted",
            "manager_and_hr_notified",
            "jira_transition_reaches_done",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "workday_update_worker_lifecycle",
            "workday_update_compensation",
            "okta_provision_access_bundle",
            "okta_deprovision_access_bundle",
            "jira_create_compliance_ticket",
            "jira_transition_ticket",
            "workflow_finalize",
        ],
        apps=["workday", "okta", "jira", "slack"],
        compliance_tags=["least_privilege", "record_retention"],
        variants=[
            "promotion from IC to manager",
            "lateral move from engineering to product",
            "team shift with confidential project restrictions",
            "temporary acting manager assignment",
            "return from leave with role reactivation",
            "demotion with sensitive access reduction",
            "cross-functional matrix assignment",
            "finance approver reassignment with SoD rules",
            "security team rotation with break-glass controls",
            "region transfer with local policy mapping",
            "compensation-only role refresh",
            "role change during performance plan",
            "new manager with inherited direct reports",
            "sales to customer-success transition",
            "high-volume annual org redesign batch change",
        ],
        start_index=31,
    )

    templates += _family_block(
        family="leave_management",
        base_scenario="Process leave of absence and reactivation workflow",
        hard_rules=[
            "must_validate_leave_eligibility_before_approval",
            "must_disable_nonessential_access_for_long_leave",
            "must_restore_access_on_return_with_policy_checks",
        ],
        success_checks=[
            "eligibility_case_documented",
            "it_tasks_and_hr_case_linked",
            "return_to_work_state_consistent",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "workday_update_worker_lifecycle",
            "servicenow_open_hr_case",
            "servicenow_open_it_task",
            "okta_deprovision_access_bundle",
            "okta_provision_access_bundle",
            "workflow_finalize",
        ],
        apps=["workday", "servicenow", "okta"],
        compliance_tags=["fmla_eligibility", "record_retention", "least_privilege"],
        variants=[
            "medical leave standard duration",
            "parental leave with intermittent schedule",
            "military caregiver leave extension",
            "short-term disability transition",
            "long leave with temporary replacement",
            "leave denial due to eligibility gap",
            "leave conversion from PTO to protected leave",
            "cross-state leave policy differences",
            "return-to-work with phased schedule",
            "leave request with incomplete documentation",
            "multiple overlapping leave requests",
            "leave during probation period",
            "manager escalation on staffing impact",
            "confidential health-related request",
            "global leave case with local entity override",
        ],
        start_index=46,
    )

    templates += _family_block(
        family="contractor_lifecycle",
        base_scenario="Manage contractor onboarding, renewals, and expirations",
        hard_rules=[
            "must_set_expiration_controls_on_access",
            "must_require_sponsor_approval_for_extensions",
            "must_apply_minimum_data_access",
        ],
        success_checks=[
            "contractor_identity_marked_non_employee",
            "okta_access_has_expiry",
            "renewal_or_offboard_path_completed",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "workday_update_worker_lifecycle",
            "okta_provision_access_bundle",
            "okta_deprovision_access_bundle",
            "servicenow_open_it_task",
            "jira_create_compliance_ticket",
            "workflow_finalize",
        ],
        apps=["workday", "okta", "servicenow", "jira", "confluence"],
        compliance_tags=["least_privilege", "gdpr_data_minimization", "record_retention"],
        variants=[
            "new contractor with standard 90-day term",
            "vendor engineer requiring repository read-only",
            "contract extension with manager sign-off",
            "contractor conversion to full-time",
            "expired contract auto-deprovision path",
            "high-risk contractor with restricted data room",
            "cross-company shared account cleanup",
            "external consultant requiring temporary admin",
            "multiple sponsor conflict resolution",
            "contingent worker location change",
            "contractor with inactive sponsor escalation",
            "procurement delay impacting start date",
            "early termination for policy violation",
            "seasonal contractor batch offboarding",
            "multi-entity contractor record merge",
        ],
        start_index=61,
    )

    templates += _family_block(
        family="cross_border_transfer",
        base_scenario="Execute international transfer with entity and compliance updates",
        hard_rules=[
            "must_update_legal_entity_before_payroll_actions",
            "must_limit_access_to_destination_jurisdiction_needs",
            "must_capture_transfer_approvals_in_ticketing",
        ],
        success_checks=[
            "workday_entity_and_location_consistent",
            "okta_roles_reflect_destination_policy",
            "jira_compliance_ticket_contains_audit_notes",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "workday_update_worker_lifecycle",
            "workday_update_compensation",
            "okta_provision_access_bundle",
            "okta_deprovision_access_bundle",
            "jira_create_compliance_ticket",
            "jira_transition_ticket",
            "confluence_update_policy_page",
            "workflow_finalize",
        ],
        apps=["workday", "okta", "jira", "confluence", "netsuite"],
        compliance_tags=["gdpr_data_minimization", "record_retention", "least_privilege"],
        variants=[
            "US to EU transfer",
            "EU to UK transfer",
            "India to US transfer",
            "Japan to Germany transfer",
            "temporary assignment under six months",
            "permanent transfer with legal-entity change",
            "transfer with concurrent promotion",
            "compensation parity exception handling",
            "restricted project reassignment due to export controls",
            "return transfer to original entity",
            "dual-reporting period with staged permissions",
            "cross-border transfer for finance approver",
            "transfer with family leave overlap",
            "acquisition entity consolidation transfer",
            "urgent relocation due to operational risk",
        ],
        start_index=76,
    )

    templates += _family_block(
        family="performance_and_pip",
        base_scenario="Handle sensitive performance workflow with confidentiality controls",
        hard_rules=[
            "must_restrict_case_visibility_to_need_to_know",
            "must_track_acknowledgement_milestones",
            "must_not_grant_extra_privileged_access",
        ],
        success_checks=[
            "pip_case_opened_and_state_tracked",
            "manager_hr_actions_timestamped",
            "policy_page_reference_updated_when_required",
        ],
        required_tools=[
            "workday_get_worker_profile",
            "servicenow_open_hr_case",
            "jira_create_compliance_ticket",
            "jira_transition_ticket",
            "confluence_update_policy_page",
            "slack_notify_stakeholders",
            "workflow_finalize",
        ],
        apps=["workday", "servicenow", "jira", "confluence", "slack"],
        compliance_tags=["record_retention", "gdpr_data_minimization"],
        variants=[
            "initial PIP setup with manager coaching plan",
            "midpoint review and documentation quality check",
            "PIP extension requiring HRBP approval",
            "final review resulting in successful completion",
            "final review resulting in termination recommendation",
            "appeal request requiring additional evidence",
            "cross-functional employee with dual-manager input",
            "employee on leave during PIP timeline",
            "employee transfer request during PIP",
            "manager changed mid-process",
            "legal hold triggered by complaint",
            "confidentiality breach remediation path",
            "performance process for executive role",
            "global employee local-law adjusted timeline",
            "high-volume annual performance cycle exception",
        ],
        start_index=91,
    )

    templates += _family_block(
        family="audit_and_policy_remediation",
        base_scenario="Run audit remediation across HR, IT, and documentation systems",
        hard_rules=[
            "must_open_jira_ticket_before_remediation_actions",
            "must_attach_control_evidence_before_close",
            "must_finalize_only_when_all_findings_resolved_or_escalated",
        ],
        success_checks=[
            "all_findings_have_owner_and_due_date",
            "confluence_policy_page_updated_when_control_changed",
            "ticket_transition_done_requires_evidence",
        ],
        required_tools=[
            "jira_create_compliance_ticket",
            "jira_transition_ticket",
            "confluence_update_policy_page",
            "servicenow_open_hr_case",
            "servicenow_open_it_task",
            "okta_deprovision_access_bundle",
            "slack_notify_stakeholders",
            "workflow_finalize",
        ],
        apps=["jira", "confluence", "servicenow", "okta", "slack", "workday"],
        compliance_tags=["least_privilege", "record_retention", "gdpr_data_minimization"],
        variants=[
            "quarterly access review failures",
            "orphaned accounts detected in IAM sweep",
            "late offboarding closure findings",
            "missing policy acknowledgment evidence",
            "I-9 timeline breach remediation",
            "leave eligibility documentation gaps",
            "sensitive page exposure in Confluence",
            "privileged group over-assignment",
            "stale contractor access exception",
            "cross-system identity mismatch",
            "audit sample requires retroactive evidence",
            "repeat finding escalation path",
            "control redesign and documentation update",
            "external auditor follow-up packet",
            "merger-driven policy harmonization",
        ],
        start_index=106,
    )

    return templates


TASK_CATALOG_V2 = build_catalog_v2()


def catalog_summary() -> dict:
    by_family: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    by_compliance_tag: dict[str, int] = {}

    for item in TASK_CATALOG_V2:
        by_family[item.family] = by_family.get(item.family, 0) + 1
        by_difficulty[item.difficulty] = by_difficulty.get(item.difficulty, 0) + 1
        for tag in item.compliance_tags:
            by_compliance_tag[tag] = by_compliance_tag.get(tag, 0) + 1

    return {
        "total_templates": len(TASK_CATALOG_V2),
        "total_tools": len(TOOL_CATALOG),
        "apps": APP_STACK,
        "by_family": by_family,
        "by_difficulty": by_difficulty,
        "by_compliance_tag": by_compliance_tag,
    }
