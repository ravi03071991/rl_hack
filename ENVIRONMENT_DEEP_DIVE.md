# HR Onboarding & Offboarding Environment — Deep Dive

This document explains **everything** about the environment in detail: what it is, how it works internally, what each component does, how the agent interacts with it, how reward is computed, and what makes tasks easy or hard. Read this if you want a complete mental model of the system.

---

## Table of Contents

1. [What Is This Environment?](#1-what-is-this-environment)
2. [The Big Picture: How It All Fits Together](#2-the-big-picture-how-it-all-fits-together)
3. [World State: The Simulated Company](#3-world-state-the-simulated-company)
4. [Tools: What the Agent Can Do](#4-tools-what-the-agent-can-do)
5. [Tasks: What the Agent Is Asked To Do](#5-tasks-what-the-agent-is-asked-to-do)
6. [Rubrics: How We Score the Agent](#6-rubrics-how-we-score-the-agent)
7. [The OpenEnv Interface: How It All Connects](#7-the-openenv-interface-how-it-all-connects)
8. [A Full Episode Walkthrough](#8-a-full-episode-walkthrough)
9. [Business Rules & Edge Cases](#9-business-rules--edge-cases)
10. [File-by-File Reference](#10-file-by-file-reference)

---

## 1. What Is This Environment?

This is a **reinforcement learning environment** that simulates the HR department of a fictional company called **AcmeCorp**. The environment is designed to train and evaluate LLM agents on real-world enterprise workflows.

### The Analogy

Think of it like a video game:
- **The world** is AcmeCorp — a company with 200 employees, 8 departments, laptops, software licenses, access badges, etc.
- **The player** is an LLM agent that acts as an HR automation bot.
- **The quest** is a task like "Onboard Priya Sharma to Engineering" or "Offboard a departing director."
- **The moves** are tool calls — the agent can call `hr_create_employee`, `it_assign_asset`, `email_send`, etc.
- **The score** is computed by a rubric that checks: Did the agent call the right tools? In the right order? With the right parameters?

### Why Does This Exist?

We're training LLMs to be better at **multi-step tool calling** in enterprise settings. Most LLM benchmarks test simple Q&A or single-tool-use. This environment tests whether an agent can:

1. **Plan** a sequence of 3-10 tool calls to complete a complex workflow
2. **Follow business rules** (RBAC levels, department restrictions, headcount limits)
3. **Handle edge cases** (license seats full, manager on leave, contractor-specific policies)
4. **Recover from errors** (tool returns an error → agent adapts)
5. **Prioritize** (complete all required steps within a limited step budget of 15)

---

## 2. The Big Picture: How It All Fits Together

```
┌─────────────────────────────────────────────────────────┐
│                    LLM AGENT                            │
│  (GPT, Claude, Qwen, etc.)                             │
│                                                         │
│  Receives: task instruction + tool results              │
│  Produces: tool calls (JSON)                            │
└────────────────────────┬────────────────────────────────┘
                         │
                    tool call
                  {"tool": "hr_create_employee",
                   "params": {"name": "Priya Sharma", ...}}
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ENVIRONMENT (this repo)                    │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │  Tasks   │   │  Tools   │   │ Rubrics  │            │
│  │ (77)     │   │ (25)     │   │ (scoring)│            │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘            │
│       │              │              │                   │
│       │    ┌─────────▼──────────┐   │                   │
│       └───►│    World State     │◄──┘                   │
│            │  (500+ entities)   │                       │
│            │  - 200 employees   │                       │
│            │  - 100 IT assets   │                       │
│            │  - 20 access roles │                       │
│            │  - 15 policies     │                       │
│            │  - 15 licenses     │                       │
│            │  - 15 sec groups   │                       │
│            │  - 8 departments   │                       │
│            └────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

**Data flow for one episode:**

1. `env.reset()` → Picks a task, resets world state, returns task instruction to agent
2. Agent reads instruction → decides which tool to call → sends `HROnboardingAction`
3. `env.step(action)` → Executes tool against world state → returns result to agent
4. Repeat steps 2-3 up to 15 times
5. When episode ends → Rubric evaluator checks the action log → computes reward (0.0 to 1.0)

---

## 3. World State: The Simulated Company

The world state (`server/world.py`) is the **single source of truth** for everything in the simulated company. It's an in-memory database that tools read from and write to.

### 3.1 Entities (loaded from `server/data/`)

#### Employees (`employees.json` — 200 records)

Every employee has:

```json
{
  "emp_id": "emp_0001",
  "name": "Alice Johnson",
  "email": "alice.johnson@acmecorp.com",
  "department": "Engineering",
  "level": "L4",
  "role": "Engineering Manager",
  "manager_id": "emp_0003",
  "status": "active",
  "date_of_joining": "2019-03-15",
  "date_of_leaving": null,
  "is_contractor": false,
  "phone": "+1-650-555-1234",
  "location": "San Francisco"
}
```

Key fields:
- **`level`**: L1 (Associate) → L2 (Senior) → L3 (Team Lead) → L4 (Manager) → L5 (Director) → L6 (VP). This drives RBAC — certain actions require certain levels.
- **`status`**: `active` (normal), `pending` (just created, not yet onboarded), `offboarded` (no longer at company)
- **`manager_id`**: Creates a tree hierarchy. Every employee (except department heads) has a manager.
- **`is_contractor`**: Contractors have different onboarding rules (no VPN, limited access, requires legal approval).

The 200 employees are distributed across 8 departments with realistic org hierarchies (each department has a head at L5/L6, managers at L3/L4, and individual contributors at L1/L2).

#### Departments (`departments.json` — 8 departments)

```json
{
  "dept_id": "dept_001",
  "name": "Engineering",
  "head": "emp_0003",
  "budget": 5000000,
  "headcount_limit": 45,
  "required_tools": ["GitHub", "Jira", "AWS", "Slack", "VSCode"],
  "onboarding_steps": [
    "Submit signed offer letter and NDA",
    "Complete background check verification",
    "Provision email and Slack accounts",
    "Assign laptop and peripherals",
    "Set up development environment access",
    "Schedule orientation with team lead",
    "Add to relevant Slack channels"
  ],
  "offboarding_steps": [
    "Revoke all system access",
    "Return laptop and equipment",
    "Complete knowledge transfer",
    "Conduct exit interview",
    "Process final payroll",
    "Remove from Slack channels and mailing lists"
  ]
}
```

Key fields:
- **`headcount_limit`**: Maximum number of active+pending employees allowed. If a department is at its limit, `hr_create_employee` will return an error. Two departments (Data Science = 25, Marketing = 30) are intentionally at or near their limits to create edge cases.
- **`onboarding_steps` / `offboarding_steps`**: Department-specific checklists. When you create an onboarding request, these become the steps that must be completed.
- **`required_tools`**: Which software tools the department uses (used for context, not enforced).

#### IT Assets (`it_assets.json` — 100 assets)

```json
{
  "asset_id": "asset_001",
  "type": "laptop",
  "brand": "Apple",
  "model": "MacBook Pro 16\" M3 Max",
  "specs": "16-inch Liquid Retina XDR, M3 Max, 64GB RAM, 2TB SSD",
  "status": "assigned",
  "assigned_to": "emp_0001",
  "purchase_date": "2024-01-15"
}
```

Breakdown: 50 laptops, 25 monitors, 15 phones, 10 headsets. About half are assigned, half are available. The agent needs to check available assets before assigning one during onboarding.

#### Access Roles (`access_roles.json` — 20 roles)

```json
{
  "role_id": "role_001",
  "name": "basic_employee",
  "permissions": ["email_access", "slack_access", "intranet_access"],
  "department": "all",
  "level_requirement": "L1"
}
```

Each role has:
- **`department`**: Which department can use this role. `"all"` means any department. `"Engineering"` means only Engineering employees.
- **`level_requirement`**: Minimum level needed. `"L1"` means anyone. `"L4"` means only managers and above.

Example roles:
- `basic_employee` (all departments, L1+) — email, slack, intranet
- `engineering_developer` (Engineering only, L1+) — github, aws_dev, ci_cd
- `security_admin` (Security only, L4+) — siem, vault, firewall_mgmt
- `executive_access` (all departments, L5+) — board_docs, exec_dashboard

If an L1 employee tries to get `security_admin` (L4+ required), the tool returns an error. If a Marketing employee tries to get `engineering_developer` (Engineering only), the tool returns an error. These are the RBAC constraints the agent must learn.

#### Policies (`policies.json` — 15 policies)

```json
{
  "policy_id": "pol_001",
  "title": "Standard Employee Onboarding Policy",
  "department": "all",
  "content": "All new employees must complete the following steps within their first 30 days...",
  "last_updated": "2024-06-15",
  "key_rules": [
    "Employee record must be created before any provisioning",
    "Manager approval required for all onboarding requests",
    "IT assets must be checked for availability before assignment"
  ]
}
```

Policies cover: onboarding, offboarding, badge access, contractor hiring, termination procedures, software licensing, data handling, remote work, etc. The `policy_lookup` tool lets the agent read these before acting.

#### Software Licenses (dynamically initialized — 15 licenses)

Not stored in a JSON file; initialized in `world.py` at runtime. Each license tracks:
- `total_seats` and `used_seats`
- `department_restriction` (which department can use it, or `null` for all)

**Two licenses are intentionally full** (used_seats = total_seats):
- **Netsuite** (15/15 seats) — Finance tool
- **LinkedIn Sales Navigator** (25/25 seats) — Sales tool

This creates edge cases: if a task asks the agent to assign a Netsuite license to a new Finance hire, the agent should discover it's full and handle that situation.

#### Security Groups (dynamically initialized — 15 groups)

Groups like `all_employees`, `engineering_team`, `vpn_users`, `server_room_access`, `contractors`, etc. Each has a list of accessible resources.

#### Templates (`templates.json` — 12 templates)

Email and Slack message templates for welcome messages, farewell emails, IT setup notifications, etc. These provide context for communication tasks.

### 3.2 Dynamic Collections (created during episodes)

These start empty and get populated as the agent takes actions:
- **`onboarding_requests`**: Created by `onboarding_create_request`
- **`offboarding_requests`**: Created by `offboarding_create_request`
- **`approvals`**: Created by `approval_request`
- **`emails`**: Created by `email_send`
- **`slack_messages`**: Created by `slack_send_message`
- **`meetings`**: Created by `meeting_schedule`
- **`badges`**: Created by `access_create_badge`

### 3.3 World State Reset

At the start of each episode (`env.reset()`), the world state is deep-copied back to its initial state. This means:
- All 200 employees are back to their original status
- All assets are back to their original assignment
- All dynamic collections (requests, emails, meetings, etc.) are cleared
- The action log is cleared

This ensures each episode is independent — the agent starts from a clean slate every time.

### 3.4 Indexes

For performance, the world state builds lookup indexes:
- `_emp_by_id`: O(1) employee lookup by emp_id
- `_emp_by_email`: O(1) lookup by email
- `_emp_by_dept`: O(1) lookup by department (returns list)
- `_dept_by_id` / `_dept_by_name`: O(1) department lookup
- `_asset_by_id`: O(1) asset lookup
- `_role_by_id`: O(1) access role lookup
- `_policy_by_id`: O(1) policy lookup

These are rebuilt after every reset and after certain mutations (like `reassign_reports`).

---

## 4. Tools: What the Agent Can Do

The agent interacts with the world through **25 tools** defined in `server/tools.py`. Each tool is a function that takes parameters, operates on the world state, and returns a result dict.

### 4.1 Architecture

```
Agent sends: {"tool_name": "hr_create_employee", "arguments": {...}}
                        │
                        ▼
              ┌─────────────────┐
              │  ToolRegistry   │
              │                 │
              │  execute(name,  │──── if unknown tool ──→ {"success": false, "error": "Unknown tool"}
              │         params) │
              │                 │
              │  routes to:     │
              │  _hr_create_..()│──→ calls world.create_employee(params)
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   WorldState    │
              │                 │──→ validates inputs
              │  create_employee│──→ checks headcount limits
              │                 │──→ generates emp_id
              │                 │──→ adds to state
              │                 │──→ updates indexes
              └────────┬────────┘
                       │
                       ▼
              Result: {"success": true, "employee": {...}}
              + logged to action_log for rubric evaluation
```

Every tool call is **logged** to the action log with:
- `tool`: name of the tool called
- `params`: parameters passed
- `result`: what the tool returned
- `timestamp`: when it was called

This log is what the rubric evaluator uses to score the agent.

### 4.2 Tool Categories

#### HR System Tools (5 tools)

| Tool | What It Does | Modifies State? |
|------|-------------|----------------|
| `hr_create_employee` | Creates a new employee record. Validates department exists, checks headcount limit, generates emp_id, sets status to "pending". | YES — adds employee |
| `hr_read_employee` | Looks up one employee by emp_id or email. | No — read only |
| `hr_update_employee` | Updates any employee field (except emp_id). Used to change status, department, manager, etc. | YES — modifies employee |
| `hr_search_employees` | Searches employees by filters (department, level, status, location, role, name). Returns all matches. | No — read only |
| `hr_get_org_chart` | Returns the org hierarchy for a department as a tree structure (who reports to whom). | No — read only |

#### Onboarding/Offboarding Tools (6 tools)

| Tool | What It Does | Modifies State? |
|------|-------------|----------------|
| `onboarding_create_request` | Creates an onboarding request for a "pending" employee. Generates a checklist of department-specific steps. | YES — creates request |
| `onboarding_get_status` | Checks progress of an onboarding request (which steps are done/pending). | No — read only |
| `onboarding_complete_step` | Marks a specific onboarding step as completed. If all steps are done, sets request to "completed" and employee status to "active". | YES — updates request & employee |
| `offboarding_create_request` | Creates an offboarding request. Different steps for resignation vs termination. | YES — creates request |
| `offboarding_get_status` | Checks offboarding progress. | No — read only |
| `offboarding_complete_step` | Marks an offboarding step as completed. If all done, sets employee to "offboarded". | YES — updates request & employee |

**Important**: Termination offboarding has different steps than resignation: `["access_revocation", "asset_return", "final_payroll", "legal_review"]` — notably, no farewell communications or exit interview.

#### IT Provisioning Tools (5 tools)

| Tool | What It Does | Modifies State? |
|------|-------------|----------------|
| `it_assign_asset` | Assigns a specific asset (by asset_id) to an employee. Asset must be "available". | YES — marks asset as assigned |
| `it_get_available_assets` | Lists all unassigned assets, optionally filtered by type (laptop, monitor, phone, headset). | No — read only |
| `it_create_account` | Creates IT accounts (email, Slack, VPN, GitHub, etc.) for an employee. | YES — adds accounts to employee |
| `it_revoke_access` | Revokes all IT accounts for an employee (sets status to "revoked"). Used in offboarding. | YES — modifies accounts |
| `it_get_software_licenses` | Checks license seat availability. Shows total_seats, used_seats, and department_restriction. | No — read only |

#### Access Control Tools (4 tools)

| Tool | What It Does | Modifies State? |
|------|-------------|----------------|
| `access_assign_role` | Assigns an RBAC role to an employee. **Checks level requirements and department restrictions.** | YES — adds role to employee |
| `access_create_badge` | Creates a physical access badge with zone permissions. **Server room access requires L4+ security approval.** | YES — creates badge |
| `access_revoke_role` | Removes a specific role from an employee. | YES — removes role |
| `access_get_security_groups` | Lists all 15 security groups and their resources. | No — read only |

#### Communication Tools (3 tools)

| Tool | What It Does | Modifies State? |
|------|-------------|----------------|
| `email_send` | Sends an email. Requires from_address, to_address, subject, body. | YES — logs email |
| `slack_send_message` | Posts a Slack message. Requires channel, sender, text. | YES — logs message |
| `meeting_schedule` | Schedules a meeting. Requires title, attendees (list of emp_ids), datetime, meeting_type. | YES — logs meeting |

#### Policy & Approval Tools (2 tools)

| Tool | What It Does | Modifies State? |
|------|-------------|----------------|
| `policy_lookup` | Searches policies by topic, department, or policy_id. Returns policy content and key_rules. | No — read only |
| `approval_request` | Submits an approval. **Checks approver level** (L3+ for manager approval, L4+ for security approval). | YES — creates approval |

### 4.3 Error Handling

Every tool returns `{"success": true, ...}` or `{"success": false, "error": "..."}`. Common errors:

- `"Employee emp_XXXX not found"` — invalid emp_id
- `"Department 'X' has reached its headcount limit (N)"` — can't create more employees
- `"Asset asset_XXX is not available"` — already assigned to someone
- `"Role X not found"` — invalid role_id
- `"Employee level L1 does not meet minimum L4 for role security_admin"` — RBAC violation
- `"Role engineering_developer is restricted to Engineering department"` — department restriction
- `"No available seats for Netsuite (all 15 seats in use)"` — license full
- `"Approver must be L4+ for security approval"` — approver too junior
- `"Server room access requires L4+ security approval"` — missing prerequisite approval

The agent must learn to handle these errors gracefully — check availability before assigning, verify role requirements before assigning access, etc.

---

## 5. Tasks: What the Agent Is Asked To Do

Tasks are defined in `server/tasks.py`. The `TaskGenerator` class creates 77 tasks using the world state data (actual employee names, IDs, departments).

### 5.1 Task Structure

Every task has:

```python
Task(
    task_id="task_0015",
    instruction="Onboard new hire Priya Sharma to Engineering as L2 Software Engineer. Create their employee record and initiate the onboarding request.",
    difficulty="medium",
    category="onboarding",
    expected_tools=["hr_create_employee", "onboarding_create_request"],
    rubric_criteria=[
        {"name": "created_employee", "description": "Created employee record", "check": "tool_used:hr_create_employee"},
        {"name": "correct_name", "description": "Used correct name", "check": "param_value:hr_create_employee.name=Priya Sharma"},
        {"name": "correct_dept", "description": "Assigned to correct department", "check": "param_value:hr_create_employee.department=Engineering"},
        {"name": "correct_level", "description": "Set correct level", "check": "param_value:hr_create_employee.level=L2"},
        {"name": "correct_role", "description": "Set correct role", "check": "param_value:hr_create_employee.role=Software Engineer"},
        {"name": "initiated_onboarding", "description": "Created onboarding request", "check": "tool_used:onboarding_create_request"},
        {"name": "sequencing", "description": "Created employee before onboarding request", "check": "tool_order:hr_create_employee<onboarding_create_request"},
    ],
    setup_fn=None,  # or a function that pre-configures world state
    context={"name": "Priya Sharma", "department": "Engineering", "level": "L2", "role": "Software Engineer"},
)
```

### 5.2 Task Categories & Counts

#### Simple Lookup Tasks (14 tasks)

These require 1-2 tool calls. Testing basic tool selection and parameter passing.

- **Employee lookups** (3): "Look up the employee record for X (ID: emp_XXXX)."
  - Expected: `hr_read_employee` with correct emp_id
  - Rubric: 2 criteria (correct tool + correct parameter)

- **Department search** (2): "List all employees in the Y department."
  - Expected: `hr_search_employees` with department filter
  - Rubric: 2 criteria

- **Org chart** (1): "Show me the organizational chart for the Z department."
  - Expected: `hr_get_org_chart`
  - Rubric: 2 criteria

- **Asset availability** (1): "What laptops are currently available for assignment?"
  - Expected: `it_get_available_assets`
  - Rubric: 1 criterion

- **License check** (1): "Check how many Jira license seats are available."
  - Expected: `it_get_software_licenses`
  - Rubric: 1 criterion

- **Policy lookup** (1): "What is the company's policy on onboarding new employees?"
  - Expected: `policy_lookup`
  - Rubric: 1 criterion

- **Security groups** (1): "List all security groups and their accessible resources."
  - Expected: `access_get_security_groups`
  - Rubric: 1 criterion

- **Onboarding status** (3): "Check the onboarding status for employee X (emp_XXXX)."
  - Expected: `onboarding_get_status`
  - Rubric: 2 criteria
  - **Setup function**: Pre-creates an onboarding request so there's something to look up

- **Resource availability** (1): "Check if there are available laptops and Jira licenses for a new Engineering hire."
  - Expected: `it_get_available_assets` + `it_get_software_licenses`
  - Rubric: 2 criteria

#### Medium Onboarding Tasks (10 tasks)

These require 2-4 tool calls. Testing multi-step workflows.

- "Onboard new hire X to Y as LZ Role. Create their employee record and initiate the onboarding request."
  - Expected: `hr_create_employee` → `onboarding_create_request`
  - Rubric: 7 criteria (create, correct name/dept/level/role, onboarding, sequencing)
  - 10 different hire combinations across different departments

#### Complex Onboarding Tasks (10 tasks)

These require 5-10 tool calls. Full end-to-end workflows.

**Full onboarding (5 tasks)**: "Fully onboard X as LY Role in Z. Create employee record, initiate onboarding, assign a laptop, create IT accounts, set up access roles, send welcome email, and schedule orientation meeting."
  - Expected: `hr_create_employee` → `onboarding_create_request` → `it_get_available_assets` → `it_assign_asset` → `it_create_account` → `access_assign_role` → `email_send` or `slack_send_message` → `meeting_schedule`
  - Rubric: 10 criteria (all the above + sequencing + completeness)
  - Context includes manager emp_id

**Complex onboarding with approvals (5 tasks)**: "Onboard X as LY Role in Z. Create record, initiate onboarding, complete at least 3 onboarding steps, assign access roles, and get required approvals."
  - Expected: `hr_create_employee` → `onboarding_create_request` → `onboarding_complete_step` (×3+) → `access_assign_role` → `approval_request`
  - Rubric: 6-7 criteria

#### Medium Offboarding Tasks (12 tasks)

- "Initiate offboarding for X who is resigning. Create the offboarding request and revoke their system access."
  - Expected: `offboarding_create_request` → `it_revoke_access`
  - Rubric: 3-4 criteria
  - **Setup function**: Sets the employee's `date_of_leaving` to create realistic context

#### Complex Offboarding Tasks (8 tasks)

**Full offboarding (4 tasks)**: "Fully offboard X, a LY Role in Z who is resigning. Create offboarding request, revoke all access roles, reclaim their laptop, revoke IT access, send farewell email, schedule exit interview."
  - Expected: many tools in sequence
  - Rubric: 8-10 criteria
  - **Setup function**: Assigns assets, roles, and badges to the employee so there's something to revoke/reclaim

**Complex offboarding with handover (4 tasks)**: "Process the complete offboarding for X from Y. Create the offboarding request, revoke access, reclaim assets, send farewell, complete at least 3 offboarding steps."
  - Rubric: 6-7 criteria

#### Edge Case Tasks (12 tasks)

These test business rule awareness and error handling.

- **Headcount limit** (2): "Onboard a new L1 to Marketing/Finance." (Department is at limit)
  - Agent should get an error from `hr_create_employee` and the rubric checks that the error message contains "headcount_limit"

- **License full** (2): "Assign a Netsuite/LinkedIn Sales Navigator license to a new hire."
  - Agent should discover no seats available

- **Manager on leave** (1): "Onboard to Security but the manager is on leave — find the skip-level manager."
  - **Setup function**: Sets the designated manager's status to "on_leave"
  - Agent needs to use `hr_read_employee` to check, realize the manager is unavailable, then look up the org chart or the manager's manager

- **Contractor onboarding** (1): "Onboard contractor Amit Verma to Engineering. Contractors need legal approval."
  - Agent should set `is_contractor: true` and submit a `legal_approval`

- **Asset return during offboarding** (1): "Offboard Marta Wagner who has company assets that need to be returned."
  - **Setup function**: Assigns assets to this employee
  - Agent should use `it_get_available_assets` or similar to find assigned assets, then reclaim them

- **Offer rescinded** (1): "The offer for Wei Xu has been rescinded. They are currently mid-onboarding."
  - **Setup function**: Creates an in-progress onboarding request
  - Agent should offboard someone who hasn't fully onboarded yet

- **Termination** (1): "Mark Taylor is being terminated effective immediately."
  - Agent should use `reason: "termination"` (different offboarding steps, no farewell email)
  - Rubric checks `tool_not_used:email_send` (no farewell for terminations)

- **Level mismatch** (1): "Assign the security_admin access role to a new L1 Security Associate."
  - security_admin requires L4+ → should fail
  - Rubric checks that the error contains the level requirement

- **Department restriction** (1): "A Marketing employee needs access to the Engineering GitHub repository."
  - engineering_developer role is Engineering-only → should fail

- **Policy-dependent task** (1): "Before onboarding a new Security team member, look up the badge access policy and check what approvals are needed."
  - Agent should call `policy_lookup` before acting

#### Cross-Workflow Tasks (10 tasks)

**Department transfers** (3): "X is transferring from A to B. Process the department transfer."
  - Agent needs to offboard from old department + onboard to new one
  - Expected: `hr_update_employee` (change department) + `offboarding_create_request` + `onboarding_create_request`

**Rehires** (2): "Rehire X who was previously offboarded."
  - **Setup function**: Sets employee status to "offboarded"
  - Agent should update status back to "pending" and create new onboarding request

**Bulk status queries** (3): "Generate a status report for all employees in X department. List each employee, their status, and current onboarding/offboarding status."
  - Tests multiple tool calls: `hr_search_employees` + multiple `onboarding_get_status`

**Manager departure** (2): "Manager X in Engineering is leaving. They have N direct reports. Process their offboarding and reassign their reports."
  - Agent needs to: find direct reports → find skip-level manager → offboard departing manager → reassign reports
  - **Setup function**: Ensures the manager has direct reports

### 5.3 Setup Functions

Many tasks have a `setup_fn` — a function that modifies the world state before the task starts. This creates the preconditions the task assumes.

Examples:
- Onboarding status tasks: Creates an onboarding request so there's something to look up
- Offboarding tasks: Assigns assets/roles/badges to the employee, sets their leaving date
- Edge case tasks: Sets a manager's status to "on_leave", or an employee's status to "offboarded" for rehire
- Manager departure: Ensures the manager has direct reports in the org hierarchy

The agent never sees the setup function — it only sees the task instruction and tool results.

---

## 6. Rubrics: How We Score the Agent

The rubric system (`server/rubrics.py`) evaluates the agent's action log against a set of criteria for each task.

### 6.1 How Scoring Works

```
Agent's action log:
  1. hr_create_employee({"name": "Priya Sharma", "department": "Engineering", ...})
  2. onboarding_create_request({"employee_id": "emp_0201"})

Task rubric:
  ✓ tool_used:hr_create_employee               → PASS (tool was called)
  ✓ param_value:hr_create_employee.name=Priya Sharma  → PASS (correct name)
  ✓ param_value:hr_create_employee.department=Engineering → PASS
  ✓ param_value:hr_create_employee.level=L2     → PASS
  ✓ param_value:hr_create_employee.role=Software Engineer → PASS
  ✓ tool_used:onboarding_create_request         → PASS
  ✓ tool_order:hr_create_employee<onboarding_create_request → PASS (correct order)

Score = 7/7 = 1.0 (100%)
Passed = True (all criteria met)
```

### 6.2 Rubric Check Types (8 types)

| Check Type | Format | What It Checks |
|-----------|--------|---------------|
| `tool_used` | `tool_used:hr_create_employee` | Was this tool called at least once? |
| `tool_not_used` | `tool_not_used:email_send` | Was this tool **NOT** called? (e.g., no farewell email for terminations) |
| `tool_used_any` | `tool_used_any:email_send,slack_send_message` | Was at **least one** of these tools called? |
| `param_value` | `param_value:hr_create_employee.name=Priya Sharma` | Was the tool called with this **exact** parameter value? |
| `param_contains` | `param_contains:policy_lookup.topic=onboard` | Does the parameter **contain** this substring? (case-insensitive) |
| `tool_order` | `tool_order:hr_create_employee<onboarding_create_request` | Was tool A called **before** tool B? |
| `tool_count` | `tool_count:onboarding_complete_step>=3` | Was the tool called at **least N times**? |
| `result_contains` | `result_contains:headcount_limit` | Does any tool result contain this substring? (for edge cases where we expect errors) |

### 6.3 How Checks Work Internally

The `RubricEvaluator` parses each criterion's `check` string:

```python
"tool_order:hr_create_employee<onboarding_create_request"
    ↓
check_type = "tool_order"
check_args = "hr_create_employee<onboarding_create_request"
    ↓
_check_tool_order("hr_create_employee<onboarding_create_request", action_log)
    ↓
Find first occurrence of hr_create_employee → index 0
Find first occurrence of onboarding_create_request → index 1
Is 0 < 1? → True → PASS
```

For `param_value`, it checks both direct parameters and nested `updates` dict (for `hr_update_employee`):

```python
"param_value:hr_update_employee.status=active"
    ↓
For each action where tool == "hr_update_employee":
  Check params.get("status") == "active"
  OR check params.get("updates", {}).get("status") == "active"
```

### 6.4 Reward Computation

```
reward = passed_criteria_count / total_criteria_count
```

- A score of 1.0 means all criteria passed
- A score of 0.5 means half the criteria passed
- The task is considered "passed" only if ALL criteria are satisfied (score == 1.0)

In the training script, additional modifiers are applied:
- **Step penalty**: -0.01 per step taken (encourages efficiency)
- **Completion bonus**: +0.2 if all criteria passed

---

## 7. The OpenEnv Interface: How It All Connects

### 7.1 What Is OpenEnv?

OpenEnv is Meta + HuggingFace's standard for packaging RL environments for LLM agents. It provides:
- A base `Environment` class (server-side) with `reset()`, `step()`, `state`
- An `EnvClient` class (client-side) that connects over HTTP/WebSocket
- A `create_app()` function that wraps the environment in a FastAPI server
- Pydantic `Action` and `Observation` base classes for type safety

### 7.2 Our Implementation

```
┌──────────────────────────────────────────┐
│           models.py                       │
│  HROnboardingAction(Action):              │
│    - tool_name: str                       │
│    - arguments: Dict[str, Any]            │
│                                           │
│  HROnboardingObservation(Observation):    │
│    - task_id: str                         │
│    - instruction: str                     │
│    - tool_name: str                       │
│    - tool_result: Dict[str, Any]          │
│    - step: int                            │
│    - max_steps: int                       │
│    - available_tools: List[str]           │
│    - done: bool        (from Observation) │
│    - reward: float     (from Observation) │
│    - metadata: dict    (from Observation) │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  server/hr_onboarding_environment.py      │
│                                           │
│  class HROnboardingEnvironment(Environment):
│                                           │
│    reset() → HROnboardingObservation      │
│      1. Reset world state                 │
│      2. Pick next task                    │
│      3. Run setup_fn if any               │
│      4. Return observation with:          │
│         - task instruction                │
│         - available tool names            │
│         - difficulty & category metadata  │
│                                           │
│    step(action) → HROnboardingObservation │
│      1. Increment step counter            │
│      2. Execute tool via ToolRegistry     │
│      3. Check if max_steps reached        │
│      4. If done: evaluate rubric → reward │
│      5. Return observation with:          │
│         - tool result                     │
│         - reward (0.0 until final step)   │
│         - done flag                       │
│         - eval breakdown in metadata      │
│                                           │
│    state → State(episode_id, step_count)  │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  server/app.py                            │
│                                           │
│  app = create_app(                        │
│    HROnboardingEnvironment,               │
│    HROnboardingAction,                    │
│    HROnboardingObservation,               │
│    env_name="hr_onboarding_env",          │
│    max_concurrent_envs=4,                 │
│  )                                        │
│                                           │
│  Endpoints:                               │
│    POST /reset  → reset + return obs      │
│    POST /step   → execute action          │
│    GET  /state  → current state           │
│    GET  /schema → Action/Obs schemas      │
│    GET  /health → {"status": "healthy"}   │
│    WS   /ws     → persistent session      │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  client.py                                │
│                                           │
│  class HROnboardingEnv(EnvClient):        │
│    Connects to server via HTTP/WebSocket  │
│    Provides Python API: .reset(), .step() │
└──────────────────────────────────────────┘
```

### 7.3 Episode Lifecycle

1. **Client calls `reset()`** → Server creates new episode, picks task, returns observation
2. **Client calls `step(action)`** (up to 15 times) → Server executes tool, returns result
3. **On step 15 (or earlier if agent signals done)** → Server evaluates rubric, sets `done=True`, returns final reward
4. **If client calls `step()` after done** → Server returns `{"error": "Episode already finished"}`

### 7.4 Important: Reward is Only on Final Step

During intermediate steps (1 to 14), `reward` is always `0.0`. The actual rubric evaluation only happens when `done=True` (step 15 or agent signals done). This is by design — the agent doesn't get feedback until the episode ends, which makes it a proper RL problem (delayed reward).

---

## 8. A Full Episode Walkthrough

Let's trace a **complex onboarding task** step by step.

### Task

> "Fully onboard John Lee as L3 Team Lead - ML in Data Science. Their manager will be Rohan Reddy (emp_0128). Create the employee record, initiate onboarding, assign a laptop, create IT accounts (email, Slack, VPN), set up appropriate access roles for their level, send a welcome email to the team channel, and schedule an orientation meeting with their manager."

### What the Agent Should Do

```
Step 1: hr_create_employee
  → name: "John Lee", department: "Data Science", level: "L3",
    role: "Team Lead - ML", manager_id: "emp_0128"
  → Result: {success: true, employee: {emp_id: "emp_0201", ...}}

Step 2: onboarding_create_request
  → employee_id: "emp_0201"
  → Result: {success: true, request: {request_id: "onb_0001", steps: {...}}}

Step 3: it_get_available_assets
  → asset_type: "laptop"
  → Result: {success: true, count: 24, assets: [{asset_id: "asset_003", ...}, ...]}

Step 4: it_assign_asset
  → asset_id: "asset_003", employee_id: "emp_0201"
  → Result: {success: true}

Step 5: it_create_account
  → employee_id: "emp_0201", account_types: ["email", "slack", "vpn"]
  → Result: {success: true, accounts_created: [...]}

Step 6: access_assign_role
  → employee_id: "emp_0201", role_id: "role_004" (data_scientist, requires L1+, Data Science)
  → Result: {success: true, role: "data_scientist", permissions: [...]}

Step 7: slack_send_message
  → channel: "#data-science", sender: "hr-bot", text: "Welcome John Lee to the team! ..."
  → Result: {success: true}

Step 8: meeting_schedule
  → title: "Orientation: John Lee", attendees: ["emp_0201", "emp_0128"],
    datetime: "2026-03-10T10:00:00", meeting_type: "orientation"
  → Result: {success: true}

Agent signals done.
```

### Rubric Evaluation

```
 [PASS] created_employee:     tool_used:hr_create_employee         ✓
 [PASS] initiated_onboarding: tool_used:onboarding_create_request  ✓
 [PASS] assigned_laptop:      tool_used:it_assign_asset            ✓
 [PASS] created_accounts:     tool_used:it_create_account          ✓
 [PASS] assigned_access:      tool_used:access_assign_role         ✓
 [PASS] sent_welcome:         tool_used_any:email_send,slack_send_message  ✓
 [PASS] scheduled_orientation: tool_used:meeting_schedule           ✓
 [PASS] sequencing_create_first: tool_order:hr_create_employee<onboarding_create_request  ✓
 [PASS] sequencing_asset_check: tool_order:it_get_available_assets<it_assign_asset  ✓
 [PASS] completeness:         tool_count:onboarding_complete_step>=3  ✗

Score: 9/10 = 0.9 (90%)
```

Note: The agent scored 9/10 because it didn't complete any onboarding steps (the `onboarding_complete_step` tool was not called at all). A perfect agent would also call `onboarding_complete_step` 3+ times to mark steps like "Provision email and Slack accounts", "Assign laptop and peripherals", etc. as done.

### What Happens When Things Go Wrong

If the agent calls `hr_create_employee` with `department: "Data Science"` and the department is at its headcount limit:

```
Step 1: hr_create_employee → {success: false, error: "Department 'Data Science' has reached its headcount limit (25)"}
```

A good agent should recognize this error and try a different approach (or report the issue). A bad agent will keep retrying the same call.

---

## 9. Business Rules & Edge Cases

### 9.1 RBAC (Role-Based Access Control)

The level hierarchy governs who can do what:

```
L1 (Associate)  → Basic access roles only
L2 (Senior)     → Same as L1 + can mentor
L3 (Team Lead)  → Can approve onboarding (manager_approval)
L4 (Manager)    → Can approve security (security_approval), server room badge access
L5 (Director)   → All approvals + executive access
L6 (VP)         → Same as L5
```

Access roles have two constraints:
1. **Level requirement**: Employee must be at or above the role's minimum level
2. **Department restriction**: Employee must be in the role's allowed department (or role allows "all")

### 9.2 Headcount Limits

Each department has a `headcount_limit`. When the number of active+pending employees reaches this limit, `hr_create_employee` fails. The agent should recognize this and either:
- Report the limitation
- Check headcount first with `hr_search_employees`
- Look up the relevant policy

### 9.3 License Seat Limits

Two licenses are intentionally full:
- **Netsuite** (15/15) — used by Finance
- **LinkedIn Sales Navigator** (25/25) — used by Sales

Agents should call `it_get_software_licenses` to check availability before trying to assign.

### 9.4 Contractor Rules

When `is_contractor: true`:
- **Legal approval required** in addition to manager approval
- **No VPN access** by default
- **Limited access roles** (contractors group, not full department group)

### 9.5 Termination vs Resignation

Different offboarding steps:
- **Resignation**: access_revocation, asset_return, knowledge_transfer, exit_interview, final_payroll, farewell_communications
- **Termination**: access_revocation, asset_return, final_payroll, legal_review (NO farewell email, NO exit interview)

The rubric for termination tasks checks `tool_not_used:email_send` — the agent should NOT send a farewell email.

### 9.6 Server Room Badge Access

Creating a badge with `access_zones: ["server_room"]` requires:
1. Employee must be L4+ OR
2. A `security_approval` must exist for the relevant onboarding request

### 9.7 Manager On Leave

Some tasks set a manager's status to "on_leave". The agent should:
1. Try to look up the manager and see they're on leave
2. Use `hr_get_org_chart` or `hr_read_employee` on the manager to find the skip-level manager
3. Use the skip-level manager for approvals and orientation scheduling

---

## 10. File-by-File Reference

```
rl_hack/
├── __init__.py                    # Exports: HROnboardingEnv, HROnboardingAction, HROnboardingObservation
├── models.py                      # Pydantic models: Action (tool_name + arguments) and Observation (task_id + instruction + tool_result + step + reward + done)
├── client.py                      # EnvClient subclass: connects to server via HTTP/WebSocket, provides .reset() and .step()
├── openenv.yaml                   # OpenEnv manifest: tells HF Spaces this is a FastAPI environment on port 7860
├── pyproject.toml                 # Python package config: name, version, dependencies (openenv-core)
├── test_with_llm.py               # Test script: runs GPT-4o-mini against a task, prints rubric evaluation
├── .env                           # API keys (gitignored)
├── README.md                      # User-facing docs with quick start, tool table, task overview
├── ENVIRONMENT_DEEP_DIVE.md       # This document
│
└── server/
    ├── __init__.py                # Exports HROnboardingEnvironment
    ├── app.py                     # FastAPI app created via create_app(), serves on port 7860
    ├── hr_onboarding_environment.py  # Core environment class: reset(), step(), state. Orchestrates world, tools, tasks, rubrics.
    ├── world.py                   # WorldState: loads data, manages 500+ entities, enforces business rules, provides mutation methods
    ├── tools.py                   # 25 tool definitions (TOOL_DEFINITIONS list) + ToolRegistry class that maps names to functions
    ├── tasks.py                   # TaskGenerator: creates 77 tasks with instructions, rubric criteria, and setup functions
    ├── rubrics.py                 # RubricEvaluator: 8 check types, evaluates action log against criteria, computes score
    ├── Dockerfile                 # Multi-stage Docker build using openenv-base image
    ├── requirements.txt           # Server dependencies: openenv, fastapi, uvicorn
    └── data/
        ├── employees.json         # 200 employee records with full org hierarchy
        ├── departments.json       # 8 departments with headcount limits, required tools, onboarding/offboarding steps
        ├── it_assets.json         # 100 IT assets (50 laptops, 25 monitors, 15 phones, 10 headsets)
        ├── access_roles.json      # 20 RBAC roles with level/department restrictions
        ├── policies.json          # 15 company policies (onboarding, offboarding, badges, contractors, etc.)
        └── templates.json         # 12 email/Slack message templates
```

---

## Appendix: Quick Numbers

| Metric | Value |
|--------|-------|
| Total entities | ~500+ |
| Employees | 200 |
| Departments | 8 |
| IT Assets | 100 |
| Access Roles | 20 |
| Software Licenses | 15 (2 intentionally full) |
| Security Groups | 15 |
| Policies | 15 |
| Message Templates | 12 |
| Tools | 25 |
| Tasks | 77 |
| Max steps per episode | 15 |
| Simple tasks | 14 |
| Medium tasks | 22 |
| Complex tasks | 29 |
| Edge case tasks | 12 |
| Rubric check types | 8 |
