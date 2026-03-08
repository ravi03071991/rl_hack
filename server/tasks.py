"""Task definitions and generation for HR Onboarding/Offboarding environment.

Each task has:
- A natural language instruction
- Difficulty level (simple, medium, complex, edge_case)
- Category (onboarding, offboarding, cross_workflow, lookup)
- Expected tool sequence (for rubric evaluation)
- Rubric criteria
- World state setup (pre-conditions to set before the task)
"""

import random
import copy
from typing import Any, Optional
try:
    from .world import WorldState
except ImportError:
    from world import WorldState


class Task:
    """A single task definition."""

    def __init__(self, task_id: str, instruction: str, difficulty: str, category: str,
                 expected_tools: list[str], rubric_criteria: list[dict],
                 setup_fn: Any = None, context: dict = None):
        self.task_id = task_id
        self.instruction = instruction
        self.difficulty = difficulty  # simple, medium, complex, edge_case
        self.category = category  # onboarding, offboarding, cross_workflow, lookup
        self.expected_tools = expected_tools
        self.rubric_criteria = rubric_criteria
        self.setup_fn = setup_fn  # function to prepare world state
        self.context = context or {}  # dynamic context (emp_ids, etc.)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "difficulty": self.difficulty,
            "category": self.category,
            "expected_tools": self.expected_tools,
            "rubric_criteria": [c for c in self.rubric_criteria],
            "context": self.context,
        }


def _pick_employee(world: WorldState, status: str = "active", department: str = None,
                   level: str = None, has_manager: bool = None) -> Optional[dict]:
    """Pick a random employee matching criteria."""
    candidates = world.state["employees"]
    if status:
        candidates = [e for e in candidates if e["status"] == status]
    if department:
        candidates = [e for e in candidates if e["department"] == department]
    if level:
        candidates = [e for e in candidates if e["level"] == level]
    if has_manager is True:
        candidates = [e for e in candidates if e.get("manager_id")]
    if has_manager is False:
        candidates = [e for e in candidates if not e.get("manager_id")]
    return random.choice(candidates) if candidates else None


def _pick_manager_in_dept(world: WorldState, department: str, min_level: str = "L3") -> Optional[dict]:
    """Pick a manager-level employee in a department."""
    min_lvl = int(min_level[1])
    candidates = [e for e in world.state["employees"]
                  if e["department"] == department
                  and e["status"] == "active"
                  and int(e["level"][1]) >= min_lvl]
    return random.choice(candidates) if candidates else None


class TaskGenerator:
    """Generates tasks from templates, binding them to specific world state entities."""

    def __init__(self, world: WorldState, seed: int = 42):
        self.world = world
        self.rng = random.Random(seed)
        self._task_counter = 0

    def _next_id(self) -> str:
        self._task_counter += 1
        return f"task_{self._task_counter:04d}"

    def generate_all_tasks(self) -> list[Task]:
        """Generate the full task set (~100 tasks)."""
        tasks = []
        tasks.extend(self._simple_lookup_tasks())
        tasks.extend(self._simple_onboarding_tasks())
        tasks.extend(self._medium_onboarding_tasks())
        tasks.extend(self._complex_onboarding_tasks())
        tasks.extend(self._simple_offboarding_tasks())
        tasks.extend(self._medium_offboarding_tasks())
        tasks.extend(self._complex_offboarding_tasks())
        tasks.extend(self._edge_case_tasks())
        tasks.extend(self._cross_workflow_tasks())
        return tasks

    def generate_train_eval_split(self, eval_ratio: float = 0.2) -> tuple[list[Task], list[Task]]:
        """Split tasks into training and evaluation sets."""
        all_tasks = self.generate_all_tasks()
        self.rng.shuffle(all_tasks)
        split_idx = int(len(all_tasks) * (1 - eval_ratio))
        return all_tasks[:split_idx], all_tasks[split_idx:]

    # ---- Simple Lookup Tasks (10) ----
    def _simple_lookup_tasks(self) -> list[Task]:
        tasks = []
        depts = ["Engineering", "Product", "Marketing", "Sales", "Finance", "HR", "Data Science", "Security"]

        # 1. Look up employee by ID
        for _ in range(3):
            emp = _pick_employee(self.world, status="active")
            if not emp:
                continue
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"Look up the employee record for {emp['name']} (ID: {emp['emp_id']}).",
                difficulty="simple",
                category="lookup",
                expected_tools=["hr_read_employee"],
                rubric_criteria=[
                    {"name": "correct_tool", "description": "Used hr_read_employee", "check": "tool_used:hr_read_employee"},
                    {"name": "correct_id", "description": "Passed correct emp_id", "check": f"param_value:hr_read_employee.emp_id={emp['emp_id']}"},
                ],
                context={"target_emp_id": emp["emp_id"], "target_name": emp["name"]},
            ))

        # 2. Search employees by department
        for dept in self.rng.sample(depts, 2):
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"List all employees in the {dept} department.",
                difficulty="simple",
                category="lookup",
                expected_tools=["hr_search_employees"],
                rubric_criteria=[
                    {"name": "correct_tool", "description": "Used hr_search_employees", "check": "tool_used:hr_search_employees"},
                    {"name": "correct_dept", "description": "Filtered by correct department", "check": f"param_value:hr_search_employees.department={dept}"},
                ],
                context={"department": dept},
            ))

        # 3. Get org chart
        dept = self.rng.choice(depts)
        tasks.append(Task(
            task_id=self._next_id(),
            instruction=f"Show me the organizational chart for the {dept} department.",
            difficulty="simple",
            category="lookup",
            expected_tools=["hr_get_org_chart"],
            rubric_criteria=[
                {"name": "correct_tool", "description": "Used hr_get_org_chart", "check": "tool_used:hr_get_org_chart"},
                {"name": "correct_dept", "description": "Passed correct department", "check": f"param_value:hr_get_org_chart.department={dept}"},
            ],
            context={"department": dept},
        ))

        # 4. Check available assets
        tasks.append(Task(
            task_id=self._next_id(),
            instruction="What laptops are currently available for assignment?",
            difficulty="simple",
            category="lookup",
            expected_tools=["it_get_available_assets"],
            rubric_criteria=[
                {"name": "correct_tool", "description": "Used it_get_available_assets", "check": "tool_used:it_get_available_assets"},
                {"name": "correct_type", "description": "Filtered by laptop type", "check": "param_value:it_get_available_assets.asset_type=laptop"},
            ],
        ))

        # 5. Check software licenses
        tasks.append(Task(
            task_id=self._next_id(),
            instruction="Check how many Jira license seats are available.",
            difficulty="simple",
            category="lookup",
            expected_tools=["it_get_software_licenses"],
            rubric_criteria=[
                {"name": "correct_tool", "description": "Used it_get_software_licenses", "check": "tool_used:it_get_software_licenses"},
                {"name": "correct_software", "description": "Filtered by Jira", "check": "param_value:it_get_software_licenses.software_name=Jira"},
            ],
        ))

        # 6. Look up policy
        tasks.append(Task(
            task_id=self._next_id(),
            instruction="What is the company's policy on onboarding new employees?",
            difficulty="simple",
            category="lookup",
            expected_tools=["policy_lookup"],
            rubric_criteria=[
                {"name": "correct_tool", "description": "Used policy_lookup", "check": "tool_used:policy_lookup"},
                {"name": "relevant_topic", "description": "Searched for onboarding topic", "check": "param_contains:policy_lookup.topic=onboard"},
            ],
        ))

        # 7. Get security groups
        tasks.append(Task(
            task_id=self._next_id(),
            instruction="List all security groups and their accessible resources.",
            difficulty="simple",
            category="lookup",
            expected_tools=["access_get_security_groups"],
            rubric_criteria=[
                {"name": "correct_tool", "description": "Used access_get_security_groups", "check": "tool_used:access_get_security_groups"},
            ],
        ))

        return tasks

    # ---- Simple Onboarding Tasks (5) ----
    def _simple_onboarding_tasks(self) -> list[Task]:
        tasks = []

        # Check onboarding status for a pending employee
        for _ in range(3):
            emp = _pick_employee(self.world, status="pending")
            if not emp:
                continue
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"Check the onboarding status for employee {emp['name']} ({emp['emp_id']}).",
                difficulty="simple",
                category="onboarding",
                expected_tools=["onboarding_get_status"],
                rubric_criteria=[
                    {"name": "correct_tool", "description": "Used onboarding_get_status", "check": "tool_used:onboarding_get_status"},
                    {"name": "correct_emp", "description": "Checked correct employee", "check": f"param_value:onboarding_get_status.employee_id={emp['emp_id']}"},
                ],
                context={"target_emp_id": emp["emp_id"]},
            ))

        # Check available assets for a department
        dept = self.rng.choice(["Engineering", "Data Science"])
        tasks.append(Task(
            task_id=self._next_id(),
            instruction=f"Check if there are available laptops and Jira licenses for a new {dept} hire.",
            difficulty="simple",
            category="onboarding",
            expected_tools=["it_get_available_assets", "it_get_software_licenses"],
            rubric_criteria=[
                {"name": "checked_assets", "description": "Checked available assets", "check": "tool_used:it_get_available_assets"},
                {"name": "checked_licenses", "description": "Checked software licenses", "check": "tool_used:it_get_software_licenses"},
            ],
            context={"department": dept},
        ))

        return tasks

    # ---- Medium Onboarding Tasks (10) ----
    def _medium_onboarding_tasks(self) -> list[Task]:
        tasks = []
        names = [
            ("Priya Sharma", "Engineering", "L2", "Software Engineer"),
            ("Alex Chen", "Product", "L2", "Product Analyst"),
            ("Maria Garcia", "Marketing", "L1", "Marketing Associate"),
            ("James Wilson", "Data Science", "L2", "Data Analyst"),
            ("Aisha Patel", "Sales", "L1", "Sales Representative"),
            ("Tom Nguyen", "Finance", "L2", "Financial Analyst"),
            ("Sara Kim", "HR", "L1", "HR Coordinator"),
            ("David Brown", "Security", "L2", "Security Analyst"),
            ("Li Wei", "Engineering", "L3", "Senior Engineer"),
            ("Emma Davis", "Product", "L3", "Senior PM"),
        ]

        for name, dept, level, role in names:
            manager = _pick_manager_in_dept(self.world, dept)
            manager_name = manager["name"] if manager else "their department head"
            manager_id = manager["emp_id"] if manager else None

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"Onboard new hire {name} to {dept} as {level} {role}. "
                           f"Create their employee record and initiate the onboarding request.",
                difficulty="medium",
                category="onboarding",
                expected_tools=["hr_create_employee", "onboarding_create_request"],
                rubric_criteria=[
                    {"name": "created_employee", "description": "Created employee record", "check": "tool_used:hr_create_employee"},
                    {"name": "correct_name", "description": "Used correct name", "check": f"param_value:hr_create_employee.name={name}"},
                    {"name": "correct_dept", "description": "Assigned to correct department", "check": f"param_value:hr_create_employee.department={dept}"},
                    {"name": "correct_level", "description": "Set correct level", "check": f"param_value:hr_create_employee.level={level}"},
                    {"name": "correct_role", "description": "Set correct role", "check": f"param_value:hr_create_employee.role={role}"},
                    {"name": "initiated_onboarding", "description": "Created onboarding request", "check": "tool_used:onboarding_create_request"},
                    {"name": "sequencing", "description": "Created employee before onboarding request", "check": "tool_order:hr_create_employee<onboarding_create_request"},
                ],
                context={"new_hire_name": name, "department": dept, "level": level, "role": role, "manager_id": manager_id},
            ))

        return tasks

    # ---- Complex Onboarding Tasks (10) ----
    def _complex_onboarding_tasks(self) -> list[Task]:
        tasks = []

        # Full onboarding with everything
        complex_hires = [
            ("John Lee", "Data Science", "L3", "Team Lead - ML"),
            ("Fatima Al-Rashid", "Engineering", "L4", "Engineering Manager"),
            ("Carlos Mendez", "Security", "L3", "Senior Security Engineer"),
            ("Rachel Green", "Product", "L2", "Product Designer"),
            ("Raj Kapoor", "Engineering", "L2", "Backend Developer"),
        ]

        for name, dept, level, role in complex_hires:
            manager = _pick_manager_in_dept(self.world, dept)
            manager_ref = f" Their manager will be {manager['name']} ({manager['emp_id']})." if manager else ""

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"Fully onboard {name} as {level} {role} in {dept}.{manager_ref} "
                           f"Create the employee record, initiate onboarding, assign a laptop, "
                           f"create IT accounts (email, Slack, VPN), set up appropriate access roles "
                           f"for their level, send a welcome email to the team channel, "
                           f"and schedule an orientation meeting with their manager.",
                difficulty="complex",
                category="onboarding",
                expected_tools=[
                    "hr_create_employee", "onboarding_create_request", "it_get_available_assets",
                    "it_assign_asset", "it_create_account", "access_assign_role",
                    "slack_send_message", "email_send", "meeting_schedule",
                    "onboarding_complete_step",
                ],
                rubric_criteria=[
                    {"name": "created_employee", "description": "Created employee record", "check": "tool_used:hr_create_employee"},
                    {"name": "initiated_onboarding", "description": "Created onboarding request", "check": "tool_used:onboarding_create_request"},
                    {"name": "assigned_laptop", "description": "Assigned a laptop", "check": "tool_used:it_assign_asset"},
                    {"name": "created_accounts", "description": "Created IT accounts", "check": "tool_used:it_create_account"},
                    {"name": "assigned_access", "description": "Assigned access roles", "check": "tool_used:access_assign_role"},
                    {"name": "sent_welcome", "description": "Sent welcome communication", "check": "tool_used_any:email_send,slack_send_message"},
                    {"name": "scheduled_orientation", "description": "Scheduled orientation meeting", "check": "tool_used:meeting_schedule"},
                    {"name": "sequencing_create_first", "description": "Created employee before other steps", "check": "tool_order:hr_create_employee<onboarding_create_request"},
                    {"name": "sequencing_asset_check", "description": "Checked available assets before assigning", "check": "tool_order:it_get_available_assets<it_assign_asset"},
                    {"name": "completeness", "description": "Completed at least 3 onboarding steps", "check": "tool_count:onboarding_complete_step>=3"},
                ],
                context={"new_hire_name": name, "department": dept, "level": level, "role": role,
                          "manager_id": manager["emp_id"] if manager else None},
            ))

        # Complex with approval chains
        for name, dept, level, role in [
            ("Sanjay Gupta", "Security", "L2", "Security Analyst"),
            ("Nina Petrova", "Engineering", "L4", "Director of Platform"),
            ("Hassan Ahmed", "Data Science", "L3", "Lead Data Scientist"),
            ("Laura Martinez", "Finance", "L3", "Senior Financial Analyst"),
            ("Kevin O'Brien", "Product", "L4", "VP of Product"),
        ]:
            manager = _pick_manager_in_dept(self.world, dept, min_level="L4")
            needs_security = dept == "Security" or int(level[1]) >= 4

            instruction = (
                f"Onboard {name} as {level} {role} in {dept}. "
                f"Create the employee record, initiate onboarding, and obtain all necessary approvals. "
            )
            if needs_security:
                instruction += "Note: this role requires security approval for badge access. "
            instruction += (
                "Then assign appropriate assets, create accounts, provision access roles, "
                "create a physical badge, send welcome communications, and schedule orientation."
            )

            criteria = [
                {"name": "created_employee", "description": "Created employee record", "check": "tool_used:hr_create_employee"},
                {"name": "initiated_onboarding", "description": "Created onboarding request", "check": "tool_used:onboarding_create_request"},
                {"name": "got_approval", "description": "Submitted approval request", "check": "tool_used:approval_request"},
                {"name": "assigned_asset", "description": "Assigned an asset", "check": "tool_used:it_assign_asset"},
                {"name": "created_accounts", "description": "Created IT accounts", "check": "tool_used:it_create_account"},
                {"name": "assigned_role", "description": "Assigned access role", "check": "tool_used:access_assign_role"},
                {"name": "created_badge", "description": "Created physical badge", "check": "tool_used:access_create_badge"},
                {"name": "sent_communications", "description": "Sent welcome communications", "check": "tool_used_any:email_send,slack_send_message"},
                {"name": "scheduled_meeting", "description": "Scheduled orientation", "check": "tool_used:meeting_schedule"},
            ]
            if needs_security:
                criteria.append({"name": "security_approval", "description": "Got security approval before badge",
                                 "check": "tool_order:approval_request<access_create_badge"})

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=instruction,
                difficulty="complex",
                category="onboarding",
                expected_tools=["hr_create_employee", "onboarding_create_request", "approval_request",
                               "it_get_available_assets", "it_assign_asset", "it_create_account",
                               "access_assign_role", "access_create_badge", "email_send",
                               "slack_send_message", "meeting_schedule", "onboarding_complete_step"],
                rubric_criteria=criteria,
                context={"new_hire_name": name, "department": dept, "level": level, "role": role,
                          "manager_id": manager["emp_id"] if manager else None,
                          "needs_security_approval": needs_security},
            ))

        return tasks

    # ---- Simple Offboarding Tasks (5) ----
    def _simple_offboarding_tasks(self) -> list[Task]:
        tasks = []

        for _ in range(5):
            emp = _pick_employee(self.world, status="active")
            if not emp:
                continue
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"Check the offboarding status for {emp['name']} ({emp['emp_id']}).",
                difficulty="simple",
                category="offboarding",
                expected_tools=["offboarding_get_status"],
                rubric_criteria=[
                    {"name": "correct_tool", "description": "Used offboarding_get_status", "check": "tool_used:offboarding_get_status"},
                    {"name": "correct_emp", "description": "Checked correct employee", "check": f"param_value:offboarding_get_status.employee_id={emp['emp_id']}"},
                ],
                context={"target_emp_id": emp["emp_id"]},
            ))

        return tasks

    # ---- Medium Offboarding Tasks (8) ----
    def _medium_offboarding_tasks(self) -> list[Task]:
        tasks = []
        offboarding_scenarios = [
            ("resignation", "Sarah Kim is resigning"),
            ("resignation", "Michael Torres is leaving for another opportunity"),
            ("resignation", "Ananya Desai is moving to a different city"),
            ("termination", "Jake Powell is being terminated for policy violations"),
            ("resignation", "Sophie Liu has accepted an offer elsewhere"),
            ("resignation", "Daniel Park is retiring"),
            ("resignation", "Christina Muller is taking a career break"),
            ("resignation", "Yuki Tanaka is going back to school"),
        ]

        for reason, scenario in offboarding_scenarios:
            emp = _pick_employee(self.world, status="active", has_manager=True)
            if not emp:
                continue

            name = emp["name"]
            instruction = (
                f"Initiate offboarding for {name} ({emp['emp_id']}) who {scenario.split(' is ')[1] if ' is ' in scenario else 'is leaving'}. "
                f"Set the reason to '{reason}'. "
                f"Revoke their system access and notify IT."
            )

            criteria = [
                {"name": "created_request", "description": "Created offboarding request", "check": "tool_used:offboarding_create_request"},
                {"name": "correct_emp", "description": "Used correct employee ID", "check": f"param_value:offboarding_create_request.employee_id={emp['emp_id']}"},
                {"name": "correct_reason", "description": "Set correct reason", "check": f"param_contains:offboarding_create_request.reason={reason}"},
                {"name": "revoked_access", "description": "Revoked IT access", "check": "tool_used:it_revoke_access"},
                {"name": "notified", "description": "Sent notification", "check": "tool_used_any:email_send,slack_send_message"},
            ]

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=instruction,
                difficulty="medium",
                category="offboarding",
                expected_tools=["offboarding_create_request", "it_revoke_access", "email_send"],
                rubric_criteria=criteria,
                context={"target_emp_id": emp["emp_id"], "reason": reason},
            ))

        return tasks

    # ---- Complex Offboarding Tasks (8) ----
    def _complex_offboarding_tasks(self) -> list[Task]:
        tasks = []

        # Full offboarding for managers/directors with reports
        for _ in range(4):
            # Find an employee who has direct reports
            candidates = [e for e in self.world.state["employees"]
                         if e["status"] == "active" and int(e["level"][1]) >= 3]
            if not candidates:
                continue
            emp = self.rng.choice(candidates)
            reports = self.world.get_direct_reports(emp["emp_id"])
            skip_mgr = self.world.get_skip_level_manager(emp["emp_id"])
            skip_mgr_ref = f" Reassign their reports to {skip_mgr['name']} ({skip_mgr['emp_id']})." if skip_mgr else " Reassign their reports to their skip-level manager."

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"Fully offboard {emp['name']} ({emp['emp_id']}), a {emp['level']} {emp['role']} in {emp['department']} "
                    f"who is resigning. Revoke all access roles and IT access, reclaim their assigned assets, "
                    f"revoke their badge.{skip_mgr_ref} "
                    f"Send a farewell email to the team, schedule an exit interview, "
                    f"and complete all offboarding steps."
                ),
                difficulty="complex",
                category="offboarding",
                expected_tools=[
                    "offboarding_create_request", "it_revoke_access", "access_revoke_role",
                    "email_send", "slack_send_message", "meeting_schedule",
                    "offboarding_complete_step",
                ],
                rubric_criteria=[
                    {"name": "created_request", "description": "Created offboarding request", "check": "tool_used:offboarding_create_request"},
                    {"name": "revoked_it", "description": "Revoked IT access", "check": "tool_used:it_revoke_access"},
                    {"name": "revoked_roles", "description": "Revoked access roles", "check": "tool_used_any:access_revoke_role"},
                    {"name": "farewell", "description": "Sent farewell communication", "check": "tool_used_any:email_send,slack_send_message"},
                    {"name": "exit_interview", "description": "Scheduled exit interview", "check": "tool_used:meeting_schedule"},
                    {"name": "completed_steps", "description": "Completed offboarding steps", "check": "tool_count:offboarding_complete_step>=2"},
                ],
                context={"target_emp_id": emp["emp_id"], "has_reports": len(reports) > 0,
                          "skip_manager_id": skip_mgr["emp_id"] if skip_mgr else None},
            ))

        # Offboarding with asset reclamation
        for _ in range(4):
            emp = _pick_employee(self.world, status="active")
            if not emp:
                continue

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"Process the complete offboarding for {emp['name']} ({emp['emp_id']}) from {emp['department']}. "
                    f"Create the offboarding request, revoke all system access and roles, "
                    f"check for and reclaim any assigned assets, send farewell notifications "
                    f"via email and Slack, and complete all offboarding steps."
                ),
                difficulty="complex",
                category="offboarding",
                expected_tools=[
                    "offboarding_create_request", "it_revoke_access",
                    "email_send", "slack_send_message", "offboarding_complete_step",
                ],
                rubric_criteria=[
                    {"name": "created_request", "description": "Created offboarding request", "check": "tool_used:offboarding_create_request"},
                    {"name": "revoked_it", "description": "Revoked IT access", "check": "tool_used:it_revoke_access"},
                    {"name": "farewell_email", "description": "Sent farewell email", "check": "tool_used:email_send"},
                    {"name": "farewell_slack", "description": "Sent farewell Slack message", "check": "tool_used:slack_send_message"},
                    {"name": "completed_steps", "description": "Completed offboarding steps", "check": "tool_count:offboarding_complete_step>=2"},
                ],
                context={"target_emp_id": emp["emp_id"]},
            ))

        return tasks

    # ---- Edge Case Tasks (15) ----
    def _edge_case_tasks(self) -> list[Task]:
        tasks = []

        # 1. Headcount limit exceeded
        for dept in ["Marketing", "Finance"]:
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=f"Onboard a new L1 Associate to the {dept} department. Create their employee record and start onboarding.",
                difficulty="edge_case",
                category="onboarding",
                expected_tools=["hr_create_employee"],
                rubric_criteria=[
                    {"name": "attempted_create", "description": "Attempted to create employee", "check": "tool_used:hr_create_employee"},
                    {"name": "handled_limit", "description": "Recognized or handled headcount limit error", "check": "result_contains:headcount_limit"},
                ],
                context={"department": dept, "edge_case": "headcount_limit"},
            ))

        # 2. Software license full
        tasks.append(Task(
            task_id=self._next_id(),
            instruction="Assign a Netsuite license to a new Finance hire. Check license availability first.",
            difficulty="edge_case",
            category="onboarding",
            expected_tools=["it_get_software_licenses"],
            rubric_criteria=[
                {"name": "checked_licenses", "description": "Checked license availability", "check": "tool_used:it_get_software_licenses"},
                {"name": "identified_full", "description": "Recognized licenses are full", "check": "result_contains:no available seats"},
            ],
            context={"edge_case": "license_full", "software": "Netsuite"},
        ))

        # 3. LinkedIn Sales Navigator also full
        tasks.append(Task(
            task_id=self._next_id(),
            instruction="Check if there are available LinkedIn Sales Navigator licenses for a new Sales hire.",
            difficulty="edge_case",
            category="onboarding",
            expected_tools=["it_get_software_licenses"],
            rubric_criteria=[
                {"name": "checked_licenses", "description": "Checked licenses", "check": "tool_used:it_get_software_licenses"},
            ],
            context={"edge_case": "license_full", "software": "LinkedIn Sales Navigator"},
        ))

        # 4. Manager on leave — find skip-level
        emp = _pick_employee(self.world, status="active", has_manager=True)
        if emp:
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"Onboard a new hire to {emp['department']} but their designated manager "
                    f"({emp['manager_id']}) is on leave. Find the skip-level manager to handle approvals "
                    f"and proceed with onboarding."
                ),
                difficulty="edge_case",
                category="onboarding",
                expected_tools=["hr_read_employee", "hr_get_org_chart", "hr_create_employee", "onboarding_create_request", "approval_request"],
                rubric_criteria=[
                    {"name": "looked_up_manager", "description": "Looked up the manager or org chart", "check": "tool_used_any:hr_read_employee,hr_get_org_chart"},
                    {"name": "found_skip_level", "description": "Identified skip-level manager", "check": "tool_count:hr_read_employee>=2"},
                    {"name": "proceeded", "description": "Proceeded with onboarding", "check": "tool_used:hr_create_employee"},
                ],
                context={"edge_case": "manager_on_leave", "department": emp["department"], "manager_id": emp["manager_id"]},
            ))

        # 5. Onboard contractor (different rules)
        tasks.append(Task(
            task_id=self._next_id(),
            instruction=(
                "Onboard contractor Amit Verma to Engineering as an L2 Contract Developer. "
                "Contractors have limited access — no VPN, restricted to Jira and Slack only, "
                "and require legal approval. Create the record, initiate onboarding, "
                "get legal approval, and provision appropriate (limited) access."
            ),
            difficulty="edge_case",
            category="onboarding",
            expected_tools=["hr_create_employee", "onboarding_create_request", "approval_request",
                           "it_create_account", "access_assign_role"],
            rubric_criteria=[
                {"name": "created_contractor", "description": "Created employee with is_contractor=true", "check": "param_value:hr_create_employee.is_contractor=True"},
                {"name": "initiated_onboarding", "description": "Created onboarding request", "check": "tool_used:onboarding_create_request"},
                {"name": "legal_approval", "description": "Got legal approval", "check": "param_value:approval_request.approval_type=legal_approval"},
                {"name": "limited_access", "description": "Created limited accounts", "check": "tool_used:it_create_account"},
            ],
            context={"edge_case": "contractor_onboarding", "name": "Amit Verma"},
        ))

        # 6. Offboard employee with unreturned assets
        emp = _pick_employee(self.world, status="active")
        if emp:
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"Offboard {emp['name']} ({emp['emp_id']}) who has company assets that need to be returned. "
                    f"Check what assets they have assigned, create the offboarding request, "
                    f"reclaim all assets, revoke access, and complete the process."
                ),
                difficulty="edge_case",
                category="offboarding",
                expected_tools=["hr_read_employee", "offboarding_create_request", "it_revoke_access"],
                rubric_criteria=[
                    {"name": "checked_employee", "description": "Looked up employee record", "check": "tool_used:hr_read_employee"},
                    {"name": "created_request", "description": "Created offboarding request", "check": "tool_used:offboarding_create_request"},
                    {"name": "revoked_access", "description": "Revoked access", "check": "tool_used:it_revoke_access"},
                ],
                context={"target_emp_id": emp["emp_id"], "edge_case": "unreturned_assets"},
            ))

        # 7. Offboard someone mid-onboarding (offer rescinded)
        emp = _pick_employee(self.world, status="pending")
        if emp:
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"The offer for {emp['name']} ({emp['emp_id']}) has been rescinded. "
                    f"They are currently mid-onboarding. Cancel their onboarding, revoke any "
                    f"provisioned access, and update their status to offboarded."
                ),
                difficulty="edge_case",
                category="offboarding",
                expected_tools=["hr_read_employee", "onboarding_get_status", "it_revoke_access",
                               "hr_update_employee"],
                rubric_criteria=[
                    {"name": "checked_onboarding", "description": "Checked onboarding status", "check": "tool_used_any:onboarding_get_status,hr_read_employee"},
                    {"name": "revoked_access", "description": "Revoked any provisioned access", "check": "tool_used:it_revoke_access"},
                    {"name": "updated_status", "description": "Updated employee status to offboarded", "check": "tool_used:hr_update_employee"},
                ],
                context={"target_emp_id": emp["emp_id"], "edge_case": "offer_rescinded"},
            ))

        # 8. Termination (different policy)
        emp = _pick_employee(self.world, status="active", has_manager=True)
        if emp:
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"{emp['name']} ({emp['emp_id']}) is being terminated effective immediately. "
                    f"Follow the termination policy: immediately revoke all access, reclaim assets, "
                    f"create termination offboarding request, and handle final payroll. "
                    f"Do NOT send farewell communications for terminations."
                ),
                difficulty="edge_case",
                category="offboarding",
                expected_tools=["offboarding_create_request", "it_revoke_access", "offboarding_complete_step"],
                rubric_criteria=[
                    {"name": "created_request", "description": "Created offboarding with termination reason", "check": "param_contains:offboarding_create_request.reason=terminat"},
                    {"name": "revoked_access", "description": "Revoked all access", "check": "tool_used:it_revoke_access"},
                    {"name": "no_farewell", "description": "Did NOT send farewell communications", "check": "tool_not_used:slack_send_message"},
                    {"name": "completed_steps", "description": "Completed termination steps", "check": "tool_used:offboarding_complete_step"},
                ],
                context={"target_emp_id": emp["emp_id"], "edge_case": "termination"},
            ))

        # 9. Role level mismatch
        tasks.append(Task(
            task_id=self._next_id(),
            instruction=(
                "Assign the security_admin access role to a new L1 Security Associate. "
                "The security_admin role requires L4+ level."
            ),
            difficulty="edge_case",
            category="onboarding",
            expected_tools=["access_assign_role"],
            rubric_criteria=[
                {"name": "attempted_assign", "description": "Attempted to assign role", "check": "tool_used:access_assign_role"},
                {"name": "handled_error", "description": "Recognized level requirement error", "check": "result_contains:does not meet minimum"},
            ],
            context={"edge_case": "level_mismatch"},
        ))

        # 10. Department restriction on role
        tasks.append(Task(
            task_id=self._next_id(),
            instruction=(
                "A Marketing employee needs access to the Engineering GitHub repository. "
                "Try to assign them the engineering_developer role."
            ),
            difficulty="edge_case",
            category="onboarding",
            expected_tools=["access_assign_role"],
            rubric_criteria=[
                {"name": "attempted_assign", "description": "Attempted to assign role", "check": "tool_used:access_assign_role"},
                {"name": "handled_restriction", "description": "Recognized department restriction", "check": "result_contains:restricted to"},
            ],
            context={"edge_case": "department_restriction"},
        ))

        # 11. Look up policy before action
        tasks.append(Task(
            task_id=self._next_id(),
            instruction=(
                "Before onboarding a new Security team member, look up the badge access policy "
                "and the onboarding policy to understand what approvals are needed. "
                "Then explain the requirements."
            ),
            difficulty="edge_case",
            category="lookup",
            expected_tools=["policy_lookup"],
            rubric_criteria=[
                {"name": "looked_up_badge", "description": "Looked up badge/access policy", "check": "tool_used:policy_lookup"},
                {"name": "multiple_lookups", "description": "Looked up multiple policies", "check": "tool_count:policy_lookup>=2"},
            ],
            context={"edge_case": "policy_check"},
        ))

        return tasks

    # ---- Cross-Workflow Tasks (10) ----
    def _cross_workflow_tasks(self) -> list[Task]:
        tasks = []

        # 1-3. Department transfer
        transfers = [
            ("Engineering", "Product"),
            ("Sales", "Marketing"),
            ("Data Science", "Engineering"),
        ]
        for from_dept, to_dept in transfers:
            emp = _pick_employee(self.world, status="active", department=from_dept)
            if not emp:
                continue
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"{emp['name']} ({emp['emp_id']}) is transferring from {from_dept} to {to_dept}. "
                    f"Process the department transfer: offboard them from {from_dept} "
                    f"(revoke department-specific access), update their department, "
                    f"and onboard them to {to_dept} (assign new access roles, notify new team)."
                ),
                difficulty="complex",
                category="cross_workflow",
                expected_tools=[
                    "hr_read_employee", "it_revoke_access", "hr_update_employee",
                    "access_assign_role", "slack_send_message", "email_send",
                ],
                rubric_criteria=[
                    {"name": "read_employee", "description": "Read employee record", "check": "tool_used:hr_read_employee"},
                    {"name": "revoked_old_access", "description": "Revoked old department access", "check": "tool_used:it_revoke_access"},
                    {"name": "updated_dept", "description": "Updated department", "check": "tool_used:hr_update_employee"},
                    {"name": "new_access", "description": "Assigned new department roles", "check": "tool_used:access_assign_role"},
                    {"name": "notified_team", "description": "Notified new team", "check": "tool_used_any:email_send,slack_send_message"},
                ],
                context={"target_emp_id": emp["emp_id"], "from_dept": from_dept, "to_dept": to_dept},
            ))

        # 4-5. Rehire previously offboarded employee
        for _ in range(2):
            emp = _pick_employee(self.world, status="offboarded")
            if not emp:
                continue
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"Rehire {emp['name']} ({emp['emp_id']}) who was previously offboarded. "
                    f"Update their status, create a new onboarding request, "
                    f"provision IT accounts, assign appropriate access, and send welcome-back communications."
                ),
                difficulty="complex",
                category="cross_workflow",
                expected_tools=[
                    "hr_read_employee", "hr_update_employee", "onboarding_create_request",
                    "it_create_account", "access_assign_role", "email_send", "slack_send_message",
                ],
                rubric_criteria=[
                    {"name": "read_employee", "description": "Read employee record first", "check": "tool_used:hr_read_employee"},
                    {"name": "updated_status", "description": "Updated status to pending/active", "check": "tool_used:hr_update_employee"},
                    {"name": "new_onboarding", "description": "Created new onboarding request", "check": "tool_used:onboarding_create_request"},
                    {"name": "provisioned_accounts", "description": "Created IT accounts", "check": "tool_used:it_create_account"},
                    {"name": "welcome_back", "description": "Sent welcome-back communication", "check": "tool_used_any:email_send,slack_send_message"},
                ],
                context={"target_emp_id": emp["emp_id"], "rehire": True},
            ))

        # 6-8. Bulk operations
        for dept in self.rng.sample(["Engineering", "Product", "Data Science"], 3):
            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"The {dept} team is onboarding 2 new hires at the same time. "
                    f"Check available assets and licenses, then report what resources "
                    f"are available for the new hires."
                ),
                difficulty="medium",
                category="cross_workflow",
                expected_tools=["it_get_available_assets", "it_get_software_licenses", "hr_search_employees"],
                rubric_criteria=[
                    {"name": "checked_assets", "description": "Checked available assets", "check": "tool_used:it_get_available_assets"},
                    {"name": "checked_licenses", "description": "Checked software licenses", "check": "tool_used:it_get_software_licenses"},
                ],
                context={"department": dept},
            ))

        # 9-10. Manager leaving — handle succession
        for _ in range(2):
            candidates = [e for e in self.world.state["employees"]
                         if e["status"] == "active" and int(e["level"][1]) >= 3
                         and e.get("manager_id")]
            if not candidates:
                continue
            mgr = self.rng.choice(candidates)
            reports = self.world.get_direct_reports(mgr["emp_id"])
            skip = self.world.get_skip_level_manager(mgr["emp_id"])

            tasks.append(Task(
                task_id=self._next_id(),
                instruction=(
                    f"Manager {mgr['name']} ({mgr['emp_id']}) in {mgr['department']} is leaving. "
                    f"They have {len(reports)} direct reports. Process their offboarding: "
                    f"reassign their direct reports to the skip-level manager, "
                    f"revoke all their access, create the offboarding request, "
                    f"and notify the team about the transition."
                ),
                difficulty="complex",
                category="cross_workflow",
                expected_tools=[
                    "hr_read_employee", "hr_get_org_chart", "offboarding_create_request",
                    "hr_update_employee", "it_revoke_access", "email_send", "slack_send_message",
                ],
                rubric_criteria=[
                    {"name": "read_manager", "description": "Looked up manager info", "check": "tool_used:hr_read_employee"},
                    {"name": "offboarding", "description": "Created offboarding request", "check": "tool_used:offboarding_create_request"},
                    {"name": "reassigned", "description": "Updated reports' manager", "check": "tool_used:hr_update_employee"},
                    {"name": "revoked_access", "description": "Revoked manager's access", "check": "tool_used:it_revoke_access"},
                    {"name": "notified_team", "description": "Notified team", "check": "tool_used_any:email_send,slack_send_message"},
                ],
                context={"target_emp_id": mgr["emp_id"], "report_count": len(reports),
                          "skip_manager_id": skip["emp_id"] if skip else None},
            ))

        return tasks
