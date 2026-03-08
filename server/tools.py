"""MCP Tool definitions for HR Onboarding/Offboarding environment.

Each tool is a callable that takes parameters and operates on the WorldState.
Tools are designed to mirror realistic enterprise HR/IT APIs.
"""

import json
from typing import Any, Callable
try:
    from .world import WorldState
except ImportError:
    from world import WorldState


TOOL_DEFINITIONS = [
    {
        "name": "hr_create_employee",
        "description": "Create a new employee record in the HR system. Requires name, department, level, and role. Returns the created employee record with generated emp_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full name of the employee"},
                "department": {"type": "string", "description": "Department name (Engineering, Product, Marketing, Sales, Finance, HR, Data Science, Security)"},
                "level": {"type": "string", "description": "Employee level (L1-L6)"},
                "role": {"type": "string", "description": "Job title/role"},
                "manager_id": {"type": "string", "description": "Employee ID of the manager"},
                "is_contractor": {"type": "boolean", "description": "Whether this is a contractor (default: false)"},
                "location": {"type": "string", "description": "Office location"},
                "date_of_joining": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
            },
            "required": ["name", "department", "level", "role"],
        },
    },
    {
        "name": "hr_read_employee",
        "description": "Look up an employee by their employee ID or email address. Returns full employee record.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {"type": "string", "description": "Employee ID (e.g. emp_0001)"},
                "email": {"type": "string", "description": "Employee email address"},
            },
        },
    },
    {
        "name": "hr_update_employee",
        "description": "Update fields on an existing employee record. Cannot modify emp_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {"type": "string", "description": "Employee ID to update"},
                "updates": {"type": "object", "description": "Dictionary of fields to update (e.g. {status: 'active', department: 'Engineering'})"},
            },
            "required": ["emp_id", "updates"],
        },
    },
    {
        "name": "hr_search_employees",
        "description": "Search employees by criteria. Filter by department, level, status, location, or role.",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Filter by department"},
                "level": {"type": "string", "description": "Filter by level (L1-L6)"},
                "status": {"type": "string", "description": "Filter by status (active, pending, offboarded)"},
                "location": {"type": "string", "description": "Filter by location"},
                "role": {"type": "string", "description": "Filter by role/title"},
                "name": {"type": "string", "description": "Filter by name (exact match)"},
            },
        },
    },
    {
        "name": "hr_get_org_chart",
        "description": "Get the organizational hierarchy/reporting structure for a department. Shows manager-report relationships.",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Department name"},
            },
            "required": ["department"],
        },
    },
    {
        "name": "onboarding_create_request",
        "description": "Initiate an onboarding request for a new hire. The employee must exist in the HR system with 'pending' status. Creates a checklist of onboarding steps based on department.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID of the new hire"},
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "onboarding_get_status",
        "description": "Check the status of an onboarding request. Can look up by request ID or employee ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Onboarding request ID"},
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
        },
    },
    {
        "name": "onboarding_complete_step",
        "description": "Mark an onboarding step as completed. Steps must be valid for the request.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Onboarding request ID"},
                "step": {"type": "string", "description": "Step name to mark as completed"},
            },
            "required": ["request_id", "step"],
        },
    },
    {
        "name": "offboarding_create_request",
        "description": "Initiate an offboarding request for a departing employee. Specify reason (resignation, termination, transfer) and optional exit date.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "reason": {"type": "string", "description": "Reason for offboarding (resignation, termination, transfer)"},
                "exit_date": {"type": "string", "description": "Last working date (YYYY-MM-DD)"},
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "offboarding_get_status",
        "description": "Check the status of an offboarding request. Can look up by request ID or employee ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Offboarding request ID"},
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
        },
    },
    {
        "name": "offboarding_complete_step",
        "description": "Mark an offboarding step as completed.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "Offboarding request ID"},
                "step": {"type": "string", "description": "Step name to mark as completed"},
            },
            "required": ["request_id", "step"],
        },
    },
    {
        "name": "it_assign_asset",
        "description": "Assign an IT asset (laptop, monitor, phone, headset) to an employee. Asset must be available.",
        "parameters": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset ID to assign"},
                "employee_id": {"type": "string", "description": "Employee ID to assign to"},
            },
            "required": ["asset_id", "employee_id"],
        },
    },
    {
        "name": "it_get_available_assets",
        "description": "List available (unassigned) IT assets. Optionally filter by type.",
        "parameters": {
            "type": "object",
            "properties": {
                "asset_type": {"type": "string", "description": "Filter by asset type (laptop, monitor, phone, headset)"},
            },
        },
    },
    {
        "name": "it_create_account",
        "description": "Create IT accounts (email, Slack, VPN, etc.) for an employee.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "account_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Types of accounts to create (email, slack, vpn, github, jira, etc.)",
                },
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "it_revoke_access",
        "description": "Revoke all IT system access for an employee (used during offboarding).",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "it_get_software_licenses",
        "description": "Check software license availability. Optionally filter by software name.",
        "parameters": {
            "type": "object",
            "properties": {
                "software_name": {"type": "string", "description": "Filter by software name"},
            },
        },
    },
    {
        "name": "access_assign_role",
        "description": "Assign an access role to an employee. Checks level requirements and department restrictions.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "role_id": {"type": "string", "description": "Access role ID to assign"},
            },
            "required": ["employee_id", "role_id"],
        },
    },
    {
        "name": "access_create_badge",
        "description": "Create a physical access badge for an employee. Server room access requires L4+ security approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "access_zones": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of access zones (main_entrance, floor_X, server_room, parking)",
                },
            },
            "required": ["employee_id"],
        },
    },
    {
        "name": "access_revoke_role",
        "description": "Revoke a specific access role from an employee.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee ID"},
                "role_id": {"type": "string", "description": "Access role ID to revoke"},
            },
            "required": ["employee_id", "role_id"],
        },
    },
    {
        "name": "access_get_security_groups",
        "description": "List all security groups. Optionally see members and resources.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "email_send",
        "description": "Send an email. Used for welcome emails, notifications, farewell messages, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Sender email address"},
                "to_address": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body text"},
            },
            "required": ["from_address", "to_address", "subject", "body"],
        },
    },
    {
        "name": "slack_send_message",
        "description": "Post a message in a Slack channel or send a DM.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Slack channel (e.g. #engineering, #general, @username)"},
                "sender": {"type": "string", "description": "Sender username or bot name"},
                "text": {"type": "string", "description": "Message text"},
            },
            "required": ["channel", "sender", "text"],
        },
    },
    {
        "name": "meeting_schedule",
        "description": "Schedule a meeting (orientation, 1-on-1, exit interview, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Meeting title"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee employee IDs or emails",
                },
                "datetime": {"type": "string", "description": "Meeting date and time (ISO format)"},
                "meeting_type": {"type": "string", "description": "Type of meeting (orientation, one_on_one, exit_interview, team_intro)"},
            },
            "required": ["title", "attendees", "datetime"],
        },
    },
    {
        "name": "policy_lookup",
        "description": "Look up company policies by topic or department. Returns policy content and key rules.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Policy topic to search for"},
                "department": {"type": "string", "description": "Department-specific policies"},
                "policy_id": {"type": "string", "description": "Specific policy ID"},
            },
        },
    },
    {
        "name": "approval_request",
        "description": "Submit an approval request (manager approval, IT approval, security approval). Approver must meet level requirements.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "The onboarding/offboarding request ID this approval is for"},
                "approver_id": {"type": "string", "description": "Employee ID of the approver"},
                "approval_type": {"type": "string", "description": "Type of approval (manager_approval, it_approval, security_approval, legal_approval)"},
            },
            "required": ["request_id", "approver_id", "approval_type"],
        },
    },
]


class ToolRegistry:
    """Registry of all available tools, mapping names to executors."""

    def __init__(self, world: WorldState):
        self.world = world
        self._tools: dict[str, Callable] = self._register_tools()

    def _register_tools(self) -> dict[str, Callable]:
        return {
            "hr_create_employee": self._hr_create_employee,
            "hr_read_employee": self._hr_read_employee,
            "hr_update_employee": self._hr_update_employee,
            "hr_search_employees": self._hr_search_employees,
            "hr_get_org_chart": self._hr_get_org_chart,
            "onboarding_create_request": self._onboarding_create_request,
            "onboarding_get_status": self._onboarding_get_status,
            "onboarding_complete_step": self._onboarding_complete_step,
            "offboarding_create_request": self._offboarding_create_request,
            "offboarding_get_status": self._offboarding_get_status,
            "offboarding_complete_step": self._offboarding_complete_step,
            "it_assign_asset": self._it_assign_asset,
            "it_get_available_assets": self._it_get_available_assets,
            "it_create_account": self._it_create_account,
            "it_revoke_access": self._it_revoke_access,
            "it_get_software_licenses": self._it_get_software_licenses,
            "access_assign_role": self._access_assign_role,
            "access_create_badge": self._access_create_badge,
            "access_revoke_role": self._access_revoke_role,
            "access_get_security_groups": self._access_get_security_groups,
            "email_send": self._email_send,
            "slack_send_message": self._slack_send_message,
            "meeting_schedule": self._meeting_schedule,
            "policy_lookup": self._policy_lookup,
            "approval_request": self._approval_request,
        }

    @property
    def tool_definitions(self) -> list[dict]:
        return TOOL_DEFINITIONS

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def execute(self, tool_name: str, params: dict) -> dict:
        """Execute a tool by name with given parameters. Returns result dict."""
        if tool_name not in self._tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}. Available tools: {self.tool_names}"}
        try:
            result = self._tools[tool_name](params)
            self.world.log_action(tool_name, params, result)
            return result
        except Exception as e:
            error_result = {"success": False, "error": f"Tool execution error: {str(e)}"}
            self.world.log_action(tool_name, params, error_result)
            return error_result

    # ---- Tool Implementations ----

    def _hr_create_employee(self, params: dict) -> dict:
        return self.world.create_employee(params)

    def _hr_read_employee(self, params: dict) -> dict:
        emp = None
        if "emp_id" in params:
            emp = self.world.get_employee(params["emp_id"])
        elif "email" in params:
            emp = self.world.get_employee_by_email(params["email"])
        if emp:
            return {"success": True, "employee": emp}
        return {"success": False, "error": "Employee not found"}

    def _hr_update_employee(self, params: dict) -> dict:
        return self.world.update_employee(params["emp_id"], params["updates"])

    def _hr_search_employees(self, params: dict) -> dict:
        results = self.world.search_employees(**params)
        return {"success": True, "count": len(results), "employees": results}

    def _hr_get_org_chart(self, params: dict) -> dict:
        chart = self.world.get_org_chart(params["department"])
        if chart:
            return {"success": True, "org_chart": chart}
        return {"success": False, "error": f"No employees found in department '{params['department']}'"}

    def _onboarding_create_request(self, params: dict) -> dict:
        return self.world.create_onboarding_request(params["employee_id"])

    def _onboarding_get_status(self, params: dict) -> dict:
        status = self.world.get_onboarding_status(
            request_id=params.get("request_id"),
            emp_id=params.get("employee_id"),
        )
        if status:
            return {"success": True, "onboarding_status": status}
        return {"success": False, "error": "Onboarding request not found"}

    def _onboarding_complete_step(self, params: dict) -> dict:
        return self.world.complete_onboarding_step(params["request_id"], params["step"])

    def _offboarding_create_request(self, params: dict) -> dict:
        return self.world.create_offboarding_request(
            params["employee_id"],
            reason=params.get("reason", "resignation"),
            exit_date=params.get("exit_date"),
        )

    def _offboarding_get_status(self, params: dict) -> dict:
        status = self.world.get_offboarding_status(
            request_id=params.get("request_id"),
            emp_id=params.get("employee_id"),
        )
        if status:
            return {"success": True, "offboarding_status": status}
        return {"success": False, "error": "Offboarding request not found"}

    def _offboarding_complete_step(self, params: dict) -> dict:
        return self.world.complete_offboarding_step(params["request_id"], params["step"])

    def _it_assign_asset(self, params: dict) -> dict:
        return self.world.assign_asset(params["asset_id"], params["employee_id"])

    def _it_get_available_assets(self, params: dict) -> dict:
        assets = self.world.get_available_assets(params.get("asset_type"))
        return {"success": True, "count": len(assets), "assets": assets}

    def _it_create_account(self, params: dict) -> dict:
        return self.world.create_it_account(
            params["employee_id"],
            account_types=params.get("account_types"),
        )

    def _it_revoke_access(self, params: dict) -> dict:
        return self.world.revoke_it_access(params["employee_id"])

    def _it_get_software_licenses(self, params: dict) -> dict:
        licenses = self.world.get_software_licenses(params.get("software_name"))
        return {"success": True, "licenses": licenses}

    def _access_assign_role(self, params: dict) -> dict:
        return self.world.assign_role(params["employee_id"], params["role_id"])

    def _access_create_badge(self, params: dict) -> dict:
        return self.world.create_badge(
            params["employee_id"],
            access_zones=params.get("access_zones"),
        )

    def _access_revoke_role(self, params: dict) -> dict:
        return self.world.revoke_role(params["employee_id"], params["role_id"])

    def _access_get_security_groups(self, params: dict) -> dict:
        return {"success": True, "security_groups": self.world.state["security_groups"]}

    def _email_send(self, params: dict) -> dict:
        return self.world.send_email(
            params["from_address"], params["to_address"],
            params["subject"], params["body"],
        )

    def _slack_send_message(self, params: dict) -> dict:
        return self.world.send_slack_message(
            params["channel"], params["sender"], params["text"],
        )

    def _meeting_schedule(self, params: dict) -> dict:
        return self.world.schedule_meeting(
            params["title"], params["attendees"],
            params["datetime"], params.get("meeting_type", "general"),
        )

    def _policy_lookup(self, params: dict) -> dict:
        policies = self.world.lookup_policy(
            topic=params.get("topic"),
            department=params.get("department"),
            policy_id=params.get("policy_id"),
        )
        return {"success": True, "count": len(policies), "policies": policies}

    def _approval_request(self, params: dict) -> dict:
        return self.world.create_approval(
            params["request_id"], params["approver_id"], params["approval_type"],
        )
