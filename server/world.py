"""World state management for HR Onboarding/Offboarding environment.

Manages all entities (employees, departments, assets, etc.) and enforces
business rules like RBAC, approval chains, and headcount limits.
"""

import json
import copy
import os
from datetime import datetime, timedelta
from typing import Any, Optional
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


class WorldState:
    """Manages the full world state: all entities and their relationships."""

    def __init__(self):
        self._initial_state: dict[str, Any] = {}
        self.state: dict[str, Any] = {}
        self._action_log: list[dict] = []
        self._load_data()

    def _load_data(self):
        """Load all entity data from JSON files."""
        data_files = {
            "employees": "employees.json",
            "departments": "departments.json",
            "policies": "policies.json",
            "it_assets": "it_assets.json",
            "access_roles": "access_roles.json",
            "templates": "templates.json",
        }
        for key, filename in data_files.items():
            path = DATA_DIR / filename
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                # Handle wrapped data (e.g. {"departments": [...]})
                if isinstance(data, dict) and key in data:
                    data = data[key]
                self.state[key] = data
            else:
                self.state[key] = []

        # Initialize dynamic collections
        self.state.setdefault("onboarding_requests", [])
        self.state.setdefault("offboarding_requests", [])
        self.state.setdefault("approvals", [])
        self.state.setdefault("emails", [])
        self.state.setdefault("slack_messages", [])
        self.state.setdefault("meetings", [])
        self.state.setdefault("badges", [])
        self.state.setdefault("security_groups", self._init_security_groups())

        # Build indexes for fast lookup
        self._build_indexes()

        # Save initial state for reset
        self._initial_state = copy.deepcopy(self.state)

    def _init_security_groups(self) -> list[dict]:
        """Create default security groups."""
        groups = [
            {"group_id": "sg_001", "name": "all_employees", "members": [], "resources_accessible": ["email", "slack", "intranet"]},
            {"group_id": "sg_002", "name": "engineering_team", "members": [], "resources_accessible": ["github", "aws_dev", "ci_cd", "jira"]},
            {"group_id": "sg_003", "name": "prod_access", "members": [], "resources_accessible": ["aws_prod", "monitoring", "pagerduty"]},
            {"group_id": "sg_004", "name": "data_team", "members": [], "resources_accessible": ["databricks", "snowflake", "jupyter"]},
            {"group_id": "sg_005", "name": "finance_access", "members": [], "resources_accessible": ["netsuite", "expense_system", "payroll"]},
            {"group_id": "sg_006", "name": "hr_access", "members": [], "resources_accessible": ["workday", "benefits_portal", "recruiting"]},
            {"group_id": "sg_007", "name": "security_team", "members": [], "resources_accessible": ["siem", "vault", "firewall_mgmt"]},
            {"group_id": "sg_008", "name": "sales_team", "members": [], "resources_accessible": ["salesforce", "hubspot", "linkedin_sales"]},
            {"group_id": "sg_009", "name": "server_room_access", "members": [], "resources_accessible": ["server_room_a", "server_room_b"]},
            {"group_id": "sg_010", "name": "vpn_users", "members": [], "resources_accessible": ["vpn_corporate", "vpn_dev"]},
            {"group_id": "sg_011", "name": "admin_access", "members": [], "resources_accessible": ["admin_console", "user_mgmt", "audit_logs"]},
            {"group_id": "sg_012", "name": "product_team", "members": [], "resources_accessible": ["figma", "amplitude", "productboard"]},
            {"group_id": "sg_013", "name": "marketing_team", "members": [], "resources_accessible": ["hubspot", "canva", "google_analytics"]},
            {"group_id": "sg_014", "name": "executives", "members": [], "resources_accessible": ["board_docs", "exec_dashboard", "all_financials"]},
            {"group_id": "sg_015", "name": "contractors", "members": [], "resources_accessible": ["email", "slack", "jira"]},
        ]
        # Populate members from employees
        return groups

    def _build_indexes(self):
        """Build lookup indexes for fast entity access."""
        self._emp_by_id = {}
        self._emp_by_email = {}
        self._emp_by_dept = {}
        for emp in self.state.get("employees", []):
            self._emp_by_id[emp["emp_id"]] = emp
            self._emp_by_email[emp.get("email", "")] = emp
            dept = emp.get("department", "")
            self._emp_by_dept.setdefault(dept, []).append(emp)

        self._dept_by_id = {d["dept_id"]: d for d in self.state.get("departments", [])}
        self._dept_by_name = {d["name"]: d for d in self.state.get("departments", [])}
        self._asset_by_id = {a["asset_id"]: a for a in self.state.get("it_assets", [])}
        self._role_by_id = {r["role_id"]: r for r in self.state.get("access_roles", [])}
        self._policy_by_id = {p["policy_id"]: p for p in self.state.get("policies", [])}

    def reset(self):
        """Reset world state to initial conditions and clear action log."""
        self.state = copy.deepcopy(self._initial_state)
        self._action_log = []
        self._build_indexes()

    def snapshot(self) -> dict:
        """Return a deep copy of the current state (for debugging/evaluation)."""
        return copy.deepcopy(self.state)

    def log_action(self, tool_name: str, params: dict, result: Any):
        """Log a tool call for rubric evaluation."""
        self._action_log.append({
            "tool": tool_name,
            "params": params,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def action_log(self) -> list[dict]:
        return list(self._action_log)

    # ---- Entity Lookup Methods ----

    def get_employee(self, emp_id: str) -> Optional[dict]:
        return self._emp_by_id.get(emp_id)

    def get_employee_by_email(self, email: str) -> Optional[dict]:
        return self._emp_by_email.get(email)

    def search_employees(self, **filters) -> list[dict]:
        results = list(self.state["employees"])
        for key, value in filters.items():
            if value is not None:
                results = [e for e in results if str(e.get(key, "")).lower() == str(value).lower()]
        return results

    def get_department(self, dept_id: str = None, name: str = None) -> Optional[dict]:
        if dept_id:
            return self._dept_by_id.get(dept_id)
        if name:
            return self._dept_by_name.get(name)
        return None

    def get_employees_in_dept(self, department: str) -> list[dict]:
        return self._emp_by_dept.get(department, [])

    def get_manager(self, emp_id: str) -> Optional[dict]:
        emp = self.get_employee(emp_id)
        if emp and emp.get("manager_id"):
            return self.get_employee(emp["manager_id"])
        return None

    def get_skip_level_manager(self, emp_id: str) -> Optional[dict]:
        manager = self.get_manager(emp_id)
        if manager:
            return self.get_manager(manager["emp_id"])
        return None

    def get_direct_reports(self, emp_id: str) -> list[dict]:
        return [e for e in self.state["employees"] if e.get("manager_id") == emp_id]

    def get_org_chart(self, department: str) -> dict:
        """Build org chart for a department as a tree."""
        dept_emps = self.get_employees_in_dept(department)
        if not dept_emps:
            return {}

        # Find the root (highest level with no manager in dept, or L6)
        def build_tree(emp):
            reports = [e for e in dept_emps if e.get("manager_id") == emp["emp_id"]]
            return {
                "emp_id": emp["emp_id"],
                "name": emp["name"],
                "level": emp["level"],
                "role": emp["role"],
                "status": emp["status"],
                "reports": [build_tree(r) for r in reports],
            }

        roots = [e for e in dept_emps if e.get("manager_id") is None
                 or e["manager_id"] not in {x["emp_id"] for x in dept_emps}]
        if not roots:
            roots = sorted(dept_emps, key=lambda e: e.get("level", "L1"), reverse=True)[:1]

        return {"department": department, "org_tree": [build_tree(r) for r in roots]}

    # ---- Asset Methods ----

    def get_available_assets(self, asset_type: str = None) -> list[dict]:
        assets = [a for a in self.state["it_assets"] if a["status"] == "available"]
        if asset_type:
            assets = [a for a in assets if a["type"].lower() == asset_type.lower()]
        return assets

    def assign_asset(self, asset_id: str, emp_id: str) -> dict:
        asset = self._asset_by_id.get(asset_id)
        if not asset:
            return {"success": False, "error": f"Asset {asset_id} not found"}
        if asset["status"] != "available":
            return {"success": False, "error": f"Asset {asset_id} is not available (status: {asset['status']})"}
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}

        asset["status"] = "assigned"
        asset["assigned_to"] = emp_id
        return {"success": True, "asset_id": asset_id, "assigned_to": emp_id}

    def reclaim_asset(self, asset_id: str) -> dict:
        asset = self._asset_by_id.get(asset_id)
        if not asset:
            return {"success": False, "error": f"Asset {asset_id} not found"}
        if asset["status"] != "assigned":
            return {"success": False, "error": f"Asset {asset_id} is not currently assigned"}
        prev_owner = asset["assigned_to"]
        asset["status"] = "available"
        asset["assigned_to"] = None
        return {"success": True, "asset_id": asset_id, "reclaimed_from": prev_owner}

    def get_assets_for_employee(self, emp_id: str) -> list[dict]:
        return [a for a in self.state["it_assets"] if a.get("assigned_to") == emp_id]

    # ---- Software License Methods ----

    def get_software_licenses(self, software_name: str = None) -> list[dict]:
        licenses = self.state.get("access_roles", [])
        # Licenses are tracked in departments' required_tools + a separate license pool
        # For simplicity, we embed license info in a dedicated structure
        if not self.state.get("software_licenses"):
            self.state["software_licenses"] = self._init_software_licenses()
        result = self.state["software_licenses"]
        if software_name:
            result = [l for l in result if l["software_name"].lower() == software_name.lower()]
        return result

    def _init_software_licenses(self) -> list[dict]:
        return [
            {"license_id": "lic_001", "software_name": "Jira", "total_seats": 80, "used_seats": 72, "department_restriction": None},
            {"license_id": "lic_002", "software_name": "GitHub", "total_seats": 60, "used_seats": 55, "department_restriction": "Engineering"},
            {"license_id": "lic_003", "software_name": "AWS", "total_seats": 40, "used_seats": 35, "department_restriction": "Engineering"},
            {"license_id": "lic_004", "software_name": "Slack", "total_seats": 250, "used_seats": 195, "department_restriction": None},
            {"license_id": "lic_005", "software_name": "Salesforce", "total_seats": 35, "used_seats": 30, "department_restriction": "Sales"},
            {"license_id": "lic_006", "software_name": "Hubspot", "total_seats": 30, "used_seats": 28, "department_restriction": "Marketing"},
            {"license_id": "lic_007", "software_name": "Figma", "total_seats": 25, "used_seats": 20, "department_restriction": "Product"},
            {"license_id": "lic_008", "software_name": "Databricks", "total_seats": 20, "used_seats": 18, "department_restriction": "Data Science"},
            {"license_id": "lic_009", "software_name": "Netsuite", "total_seats": 15, "used_seats": 15, "department_restriction": "Finance"},  # Full!
            {"license_id": "lic_010", "software_name": "Workday", "total_seats": 20, "used_seats": 12, "department_restriction": "HR"},
            {"license_id": "lic_011", "software_name": "Canva", "total_seats": 25, "used_seats": 20, "department_restriction": "Marketing"},
            {"license_id": "lic_012", "software_name": "Google Analytics", "total_seats": 30, "used_seats": 22, "department_restriction": None},
            {"license_id": "lic_013", "software_name": "VSCode License", "total_seats": 70, "used_seats": 60, "department_restriction": None},
            {"license_id": "lic_014", "software_name": "Amplitude", "total_seats": 20, "used_seats": 15, "department_restriction": "Product"},
            {"license_id": "lic_015", "software_name": "LinkedIn Sales Navigator", "total_seats": 25, "used_seats": 25, "department_restriction": "Sales"},  # Full!
        ]

    def consume_license(self, license_id: str) -> dict:
        if not self.state.get("software_licenses"):
            self.state["software_licenses"] = self._init_software_licenses()
        for lic in self.state["software_licenses"]:
            if lic["license_id"] == license_id:
                if lic["used_seats"] >= lic["total_seats"]:
                    return {"success": False, "error": f"No available seats for {lic['software_name']} (all {lic['total_seats']} seats in use)"}
                lic["used_seats"] += 1
                return {"success": True, "software": lic["software_name"], "remaining_seats": lic["total_seats"] - lic["used_seats"]}
        return {"success": False, "error": f"License {license_id} not found"}

    def release_license(self, license_id: str) -> dict:
        if not self.state.get("software_licenses"):
            return {"success": False, "error": "No licenses initialized"}
        for lic in self.state["software_licenses"]:
            if lic["license_id"] == license_id:
                if lic["used_seats"] > 0:
                    lic["used_seats"] -= 1
                return {"success": True, "software": lic["software_name"], "remaining_seats": lic["total_seats"] - lic["used_seats"]}
        return {"success": False, "error": f"License {license_id} not found"}

    # ---- Employee Mutation Methods ----

    def create_employee(self, data: dict) -> dict:
        required = ["name", "department", "level", "role"]
        for field in required:
            if field not in data:
                return {"success": False, "error": f"Missing required field: {field}"}

        dept = self.get_department(name=data["department"])
        if not dept:
            return {"success": False, "error": f"Department '{data['department']}' not found"}

        # Check headcount limit
        current = len([e for e in self.state["employees"]
                       if e["department"] == data["department"] and e["status"] in ("active", "pending")])
        if current >= dept.get("headcount_limit", 999):
            return {"success": False, "error": f"Department '{data['department']}' has reached its headcount limit ({dept['headcount_limit']})"}

        # Generate emp_id
        existing_ids = [int(e["emp_id"].split("_")[1]) for e in self.state["employees"]]
        new_id = f"emp_{max(existing_ids) + 1:04d}" if existing_ids else "emp_0001"

        email = f"{data['name'].lower().replace(' ', '.')}@acmecorp.com"

        employee = {
            "emp_id": new_id,
            "name": data["name"],
            "email": data.get("email", email),
            "department": data["department"],
            "level": data["level"],
            "role": data["role"],
            "manager_id": data.get("manager_id"),
            "status": "pending",
            "date_of_joining": data.get("date_of_joining", datetime.now().strftime("%Y-%m-%d")),
            "date_of_leaving": None,
            "is_contractor": data.get("is_contractor", False),
            "phone": data.get("phone", ""),
            "location": data.get("location", "San Francisco"),
        }

        self.state["employees"].append(employee)
        self._emp_by_id[new_id] = employee
        self._emp_by_email[employee["email"]] = employee
        self._emp_by_dept.setdefault(employee["department"], []).append(employee)

        return {"success": True, "employee": employee}

    def update_employee(self, emp_id: str, updates: dict) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}

        protected_fields = {"emp_id"}
        for key, value in updates.items():
            if key in protected_fields:
                return {"success": False, "error": f"Cannot modify protected field: {key}"}
            emp[key] = value

        return {"success": True, "employee": emp}

    # ---- Onboarding/Offboarding Request Methods ----

    def create_onboarding_request(self, emp_id: str) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}
        if emp["status"] == "active":
            return {"success": False, "error": f"Employee {emp_id} is already active"}

        existing = [r for r in self.state["onboarding_requests"]
                    if r["employee_id"] == emp_id and r["status"] != "completed"]
        if existing:
            return {"success": False, "error": f"Active onboarding request already exists for {emp_id}"}

        dept = self.get_department(name=emp["department"])
        steps = dept.get("onboarding_steps", [
            "hr_paperwork", "it_account_setup", "asset_assignment",
            "access_provisioning", "orientation_scheduled", "manager_intro",
            "welcome_communications"
        ]) if dept else ["hr_paperwork", "it_account_setup", "asset_assignment",
                         "access_provisioning", "orientation_scheduled", "manager_intro",
                         "welcome_communications"]

        req_ids = [int(r["request_id"].split("_")[1]) for r in self.state["onboarding_requests"]] or [0]
        new_id = f"onb_{max(req_ids) + 1:04d}"

        request = {
            "request_id": new_id,
            "employee_id": emp_id,
            "department": emp["department"],
            "status": "in_progress",
            "steps": {step: "pending" for step in steps},
            "steps_completed": [],
            "approvals_required": self._get_required_approvals(emp),
            "approvals_received": [],
            "created_date": datetime.now().strftime("%Y-%m-%d"),
        }

        self.state["onboarding_requests"].append(request)
        return {"success": True, "request": request}

    def create_offboarding_request(self, emp_id: str, reason: str = "resignation", exit_date: str = None) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}
        if emp["status"] == "offboarded":
            return {"success": False, "error": f"Employee {emp_id} is already offboarded"}

        existing = [r for r in self.state["offboarding_requests"]
                    if r["employee_id"] == emp_id and r["status"] != "completed"]
        if existing:
            return {"success": False, "error": f"Active offboarding request already exists for {emp_id}"}

        dept = self.get_department(name=emp["department"])
        steps = dept.get("offboarding_steps", [
            "access_revocation", "asset_return", "knowledge_transfer",
            "exit_interview", "final_payroll", "farewell_communications"
        ]) if dept else ["access_revocation", "asset_return", "knowledge_transfer",
                         "exit_interview", "final_payroll", "farewell_communications"]

        if reason == "termination":
            steps = ["access_revocation", "asset_return", "final_payroll", "legal_review"]

        req_ids = [int(r["request_id"].split("_")[1]) for r in self.state["offboarding_requests"]] or [0]
        new_id = f"off_{max(req_ids) + 1:04d}"

        if not exit_date:
            exit_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

        request = {
            "request_id": new_id,
            "employee_id": emp_id,
            "department": emp["department"],
            "reason": reason,
            "status": "in_progress",
            "exit_date": exit_date,
            "steps": {step: "pending" for step in steps},
            "steps_completed": [],
            "handover_status": "pending",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
        }

        self.state["offboarding_requests"].append(request)
        return {"success": True, "request": request}

    def complete_onboarding_step(self, request_id: str, step: str) -> dict:
        req = next((r for r in self.state["onboarding_requests"] if r["request_id"] == request_id), None)
        if not req:
            return {"success": False, "error": f"Onboarding request {request_id} not found"}
        if req["status"] == "completed":
            return {"success": False, "error": f"Onboarding request {request_id} is already completed"}
        if step not in req["steps"]:
            return {"success": False, "error": f"Invalid step '{step}'. Valid steps: {list(req['steps'].keys())}"}
        if req["steps"][step] == "completed":
            return {"success": False, "error": f"Step '{step}' is already completed"}

        req["steps"][step] = "completed"
        req["steps_completed"].append(step)

        # Check if all steps are done
        if all(v == "completed" for v in req["steps"].values()):
            req["status"] = "completed"
            emp = self.get_employee(req["employee_id"])
            if emp:
                emp["status"] = "active"

        return {"success": True, "request_id": request_id, "step": step,
                "all_complete": req["status"] == "completed",
                "remaining_steps": [k for k, v in req["steps"].items() if v != "completed"]}

    def complete_offboarding_step(self, request_id: str, step: str) -> dict:
        req = next((r for r in self.state["offboarding_requests"] if r["request_id"] == request_id), None)
        if not req:
            return {"success": False, "error": f"Offboarding request {request_id} not found"}
        if req["status"] == "completed":
            return {"success": False, "error": f"Offboarding request {request_id} is already completed"}
        if step not in req["steps"]:
            return {"success": False, "error": f"Invalid step '{step}'. Valid steps: {list(req['steps'].keys())}"}
        if req["steps"][step] == "completed":
            return {"success": False, "error": f"Step '{step}' is already completed"}

        req["steps"][step] = "completed"
        req["steps_completed"].append(step)

        if all(v == "completed" for v in req["steps"].values()):
            req["status"] = "completed"
            emp = self.get_employee(req["employee_id"])
            if emp:
                emp["status"] = "offboarded"
                emp["date_of_leaving"] = req["exit_date"]

        return {"success": True, "request_id": request_id, "step": step,
                "all_complete": req["status"] == "completed",
                "remaining_steps": [k for k, v in req["steps"].items() if v != "completed"]}

    def get_onboarding_status(self, request_id: str = None, emp_id: str = None) -> Optional[dict]:
        if request_id:
            return next((r for r in self.state["onboarding_requests"] if r["request_id"] == request_id), None)
        if emp_id:
            reqs = [r for r in self.state["onboarding_requests"] if r["employee_id"] == emp_id]
            return reqs[-1] if reqs else None
        return None

    def get_offboarding_status(self, request_id: str = None, emp_id: str = None) -> Optional[dict]:
        if request_id:
            return next((r for r in self.state["offboarding_requests"] if r["request_id"] == request_id), None)
        if emp_id:
            reqs = [r for r in self.state["offboarding_requests"] if r["employee_id"] == emp_id]
            return reqs[-1] if reqs else None
        return None

    # ---- Approval Methods ----

    def _get_required_approvals(self, emp: dict) -> list[str]:
        """Determine what approvals are needed based on employee level and department."""
        approvals = ["manager_approval"]
        level_num = int(emp["level"][1])
        if level_num >= 3:
            approvals.append("it_approval")
        if emp["department"] == "Security" or level_num >= 4:
            approvals.append("security_approval")
        if emp.get("is_contractor"):
            approvals.append("legal_approval")
        return approvals

    def create_approval(self, request_id: str, approver_id: str, approval_type: str) -> dict:
        emp = self.get_employee(approver_id)
        if not emp:
            return {"success": False, "error": f"Approver {approver_id} not found"}

        level_num = int(emp["level"][1])
        if approval_type == "manager_approval" and level_num < 3:
            return {"success": False, "error": f"Approver must be L3+ for manager approval (current: {emp['level']})"}
        if approval_type == "security_approval" and level_num < 4:
            return {"success": False, "error": f"Approver must be L4+ for security approval (current: {emp['level']})"}

        approval_ids = [int(a["approval_id"].split("_")[1]) for a in self.state["approvals"]] or [0]
        new_id = f"apr_{max(approval_ids) + 1:04d}"

        approval = {
            "approval_id": new_id,
            "request_id": request_id,
            "approver_id": approver_id,
            "type": approval_type,
            "status": "approved",
            "timestamp": datetime.now().isoformat(),
        }
        self.state["approvals"].append(approval)

        # Update onboarding/offboarding request approvals
        for req in self.state["onboarding_requests"] + self.state["offboarding_requests"]:
            if req["request_id"] == request_id:
                if approval_type not in req.get("approvals_received", []):
                    req.setdefault("approvals_received", []).append(approval_type)

        return {"success": True, "approval": approval}

    # ---- Access Role Methods ----

    def assign_role(self, emp_id: str, role_id: str) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}
        role = self._role_by_id.get(role_id)
        if not role:
            return {"success": False, "error": f"Role {role_id} not found"}

        # Check level requirement
        emp_level = int(emp["level"][1])
        req_level = int(role.get("level_requirement", "L1")[1])
        if emp_level < req_level:
            return {"success": False, "error": f"Employee level {emp['level']} does not meet minimum {role['level_requirement']} for role {role['name']}"}

        # Check department restriction
        if role["department"] != "all" and role["department"] != emp["department"]:
            return {"success": False, "error": f"Role {role['name']} is restricted to {role['department']} department"}

        emp.setdefault("assigned_roles", []).append(role_id)
        return {"success": True, "emp_id": emp_id, "role": role["name"], "permissions": role["permissions"]}

    def revoke_role(self, emp_id: str, role_id: str) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}
        roles = emp.get("assigned_roles", [])
        if role_id not in roles:
            return {"success": False, "error": f"Employee {emp_id} does not have role {role_id}"}
        roles.remove(role_id)
        return {"success": True, "emp_id": emp_id, "revoked_role": role_id}

    def revoke_all_access(self, emp_id: str) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}
        revoked_roles = emp.get("assigned_roles", []).copy()
        emp["assigned_roles"] = []

        # Remove from security groups
        for sg in self.state["security_groups"]:
            if emp_id in sg["members"]:
                sg["members"].remove(emp_id)

        return {"success": True, "emp_id": emp_id, "revoked_roles": revoked_roles}

    # ---- Badge Methods ----

    def create_badge(self, emp_id: str, access_zones: list[str] = None) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}

        # Server room access requires L4+ approval
        if access_zones and "server_room" in access_zones:
            level_num = int(emp["level"][1])
            if level_num < 4:
                approvals = [a for a in self.state["approvals"]
                             if a["type"] == "security_approval"
                             and a["status"] == "approved"]
                relevant = [a for a in approvals
                            if any(r["employee_id"] == emp_id
                                   for r in self.state["onboarding_requests"]
                                   if r["request_id"] == a["request_id"])]
                if not relevant:
                    return {"success": False, "error": "Server room access requires L4+ security approval"}

        badge_ids = [int(b["badge_id"].split("_")[1]) for b in self.state["badges"]] or [0]
        new_id = f"badge_{max(badge_ids) + 1:04d}"

        if not access_zones:
            access_zones = ["main_entrance", "floor_" + emp.get("location", "sf").lower().replace(" ", "_")]

        badge = {
            "badge_id": new_id,
            "employee_id": emp_id,
            "access_zones": access_zones,
            "status": "active",
            "issued_date": datetime.now().strftime("%Y-%m-%d"),
        }
        self.state["badges"].append(badge)
        return {"success": True, "badge": badge}

    def revoke_badge(self, badge_id: str) -> dict:
        badge = next((b for b in self.state["badges"] if b["badge_id"] == badge_id), None)
        if not badge:
            return {"success": False, "error": f"Badge {badge_id} not found"}
        badge["status"] = "revoked"
        return {"success": True, "badge_id": badge_id, "status": "revoked"}

    def get_badges_for_employee(self, emp_id: str) -> list[dict]:
        return [b for b in self.state["badges"] if b["employee_id"] == emp_id and b["status"] == "active"]

    # ---- Communication Methods ----

    def send_email(self, from_addr: str, to_addr: str, subject: str, body: str) -> dict:
        email_ids = [int(e["email_id"].split("_")[1]) for e in self.state["emails"]] or [0]
        new_id = f"email_{max(email_ids) + 1:04d}"
        email = {
            "email_id": new_id,
            "from": from_addr,
            "to": to_addr,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat(),
        }
        self.state["emails"].append(email)
        return {"success": True, "email": email}

    def send_slack_message(self, channel: str, sender: str, text: str) -> dict:
        msg_ids = [int(m["msg_id"].split("_")[1]) for m in self.state["slack_messages"]] or [0]
        new_id = f"msg_{max(msg_ids) + 1:04d}"
        message = {
            "msg_id": new_id,
            "channel": channel,
            "sender": sender,
            "text": text,
            "timestamp": datetime.now().isoformat(),
        }
        self.state["slack_messages"].append(message)
        return {"success": True, "message": message}

    def schedule_meeting(self, title: str, attendees: list[str], meeting_datetime: str,
                         meeting_type: str = "general") -> dict:
        meeting_ids = [int(m["meeting_id"].split("_")[1]) for m in self.state["meetings"]] or [0]
        new_id = f"mtg_{max(meeting_ids) + 1:04d}"
        meeting = {
            "meeting_id": new_id,
            "title": title,
            "attendees": attendees,
            "datetime": meeting_datetime,
            "type": meeting_type,
        }
        self.state["meetings"].append(meeting)
        return {"success": True, "meeting": meeting}

    # ---- Policy Methods ----

    def lookup_policy(self, topic: str = None, department: str = None, policy_id: str = None) -> list[dict]:
        policies = self.state.get("policies", [])
        if policy_id:
            return [p for p in policies if p["policy_id"] == policy_id]
        results = policies
        if topic:
            results = [p for p in results if topic.lower() in p.get("title", "").lower()
                       or topic.lower() in p.get("content", "").lower()]
        if department:
            results = [p for p in results if p.get("department") in (department, "all")]
        return results

    # ---- IT Account Methods ----

    def create_it_account(self, emp_id: str, account_types: list[str] = None) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}

        if not account_types:
            account_types = ["email", "slack", "vpn"]

        created = []
        for acct_type in account_types:
            created.append({
                "type": acct_type,
                "username": emp["email"].split("@")[0],
                "status": "active",
            })

        emp.setdefault("it_accounts", []).extend(created)
        return {"success": True, "emp_id": emp_id, "accounts_created": created}

    def revoke_it_access(self, emp_id: str) -> dict:
        emp = self.get_employee(emp_id)
        if not emp:
            return {"success": False, "error": f"Employee {emp_id} not found"}

        accounts = emp.get("it_accounts", [])
        for acct in accounts:
            acct["status"] = "revoked"

        return {"success": True, "emp_id": emp_id, "accounts_revoked": len(accounts)}

    # ---- Reassignment (for offboarding) ----

    def reassign_reports(self, from_emp_id: str, to_emp_id: str) -> dict:
        from_emp = self.get_employee(from_emp_id)
        to_emp = self.get_employee(to_emp_id)
        if not from_emp:
            return {"success": False, "error": f"Employee {from_emp_id} not found"}
        if not to_emp:
            return {"success": False, "error": f"Employee {to_emp_id} not found"}

        reports = self.get_direct_reports(from_emp_id)
        for report in reports:
            report["manager_id"] = to_emp_id

        self._build_indexes()
        return {"success": True, "reassigned_count": len(reports),
                "from": from_emp_id, "to": to_emp_id,
                "reassigned_employees": [r["emp_id"] for r in reports]}
