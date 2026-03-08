# HR + IT Multi-App Task Catalog (V2)

This catalog is designed for long-horizon enterprise workflow RL in the hackathon theme:
- Multi-app coordination
- Policy-heavy decisions
- Hard reward with business-rule nuance

## App Coverage

- Workday (worker lifecycle + compensation)
- Okta (provision/deprovision)
- ServiceNow (HR/IT case and task handling)
- Jira (compliance workflow and evidence tracking)
- Confluence (policy updates)
- Slack (stakeholder notifications)
- Google Workspace (identity surface context)
- NetSuite (finance-entity context)

## Tool Coverage (12)

- `workday_get_worker_profile`
- `workday_update_worker_lifecycle`
- `workday_update_compensation`
- `okta_provision_access_bundle`
- `okta_deprovision_access_bundle`
- `servicenow_open_hr_case`
- `servicenow_open_it_task`
- `jira_create_compliance_ticket`
- `jira_transition_ticket`
- `confluence_update_policy_page`
- `slack_notify_stakeholders`
- `workflow_finalize`

## Task Families and Counts

- Onboarding: 15
- Offboarding: 15
- Role change: 15
- Leave management: 15
- Contractor lifecycle: 15
- Cross-border transfer: 15
- Performance/PIP: 15
- Audit remediation: 15

Total templates: 120

Difficulty mix:
- Medium: 80
- Hard: 24
- Very hard: 16

Horizon:
- Medium: 8-step
- Hard: 10-step
- Very hard: 12-step

## Compliance Tags Embedded

- `i9_timeline`
- `least_privilege`
- `gdpr_data_minimization`
- `record_retention`
- `fmla_eligibility`

## Source Notes Used for Workflow/Policy Direction

- Atlassian Jira workflow concepts and status transitions:
  - https://www.atlassian.com/software/jira/guides/workflows/overview
- Atlassian Confluence permissions/restrictions:
  - https://support.atlassian.com/confluence-cloud/docs/assign-space-permissions/
- Okta lifecycle provisioning/deprovisioning concepts:
  - https://www.okta.com/products/lifecycle-management/
- NIST least privilege control (AC-6):
  - https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final
- USCIS I-9 timing requirements:
  - https://www.uscis.gov/i-9-central
- DOL FMLA eligibility baseline:
  - https://www.dol.gov/general/topic/benefits-leave/fmla
- GDPR regulation text (data minimization principle):
  - https://eur-lex.europa.eu/eli/reg/2016/679/oj

## Implementation

The code-first catalog lives at:
- `greenfield_hr_hard/hr_hard_env/catalog_v2.py`

It provides:
- `TASK_CATALOG_V2` (120 `TaskTemplateV2` entries)
- `TOOL_CATALOG` (12 tools)
- `catalog_summary()` for quick stats
