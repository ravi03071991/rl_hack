"""Test HR Onboarding Environment with OpenAI GPT as the agent."""

import sys
import json
import os
import re

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, ".")
sys.path.insert(0, "./server")

from openai import OpenAI
from server.hr_onboarding_environment import HROnboardingEnvironment
from models import HROnboardingAction, HROnboardingObservation
from server.tools import TOOL_DEFINITIONS
from server.rubrics import RubricEvaluator

# --- Setup ---
client = OpenAI()
env = HROnboardingEnvironment(seed=42, max_steps=15)
tool_desc = json.dumps(TOOL_DEFINITIONS, indent=2)

# Pick which task to test (default: 0, or pass via CLI)
task_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

# --- Reset to the desired task ---
for _ in range(task_idx + 1):
    obs = env.reset()

print("=" * 70)
print("HR ONBOARDING ENVIRONMENT — LLM AGENT TEST")
print("=" * 70)
print(f"\nTask ID: {obs.task_id}")
print(f"Difficulty: {obs.metadata.get('difficulty', '?')}")
print(f"Category: {obs.metadata.get('category', '?')}")
print(f"\nInstruction: {obs.instruction}")
print(f"\nAvailable tools ({len(obs.available_tools)}): {', '.join(obs.available_tools[:10])}...")
print("=" * 70)

system_prompt = f"""You are an HR automation agent for AcmeCorp. You help with employee onboarding and offboarding by calling the appropriate tools.

For each step, respond with ONLY a JSON tool call in this exact format:
{{"tool": "<tool_name>", "params": {{<parameters>}}}}

When you believe the task is complete, respond with:
{{"tool": "__done__", "params": {{}}}}

Important rules:
- Respond with ONLY the JSON object, no other text
- Use the exact tool names and parameter names from the tool definitions
- Think about what information you need and what tools to call in what order

Available tools:
{tool_desc}
"""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": obs.instruction},
]

# --- Agent loop ---
for step in range(1, obs.max_steps + 1):
    print(f"\n--- Step {step}/{obs.max_steps} ---")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1,
        max_tokens=512,
    )

    assistant_msg = response.choices[0].message.content.strip()
    print(f"LLM: {assistant_msg[:200]}")

    # Parse tool call
    try:
        json_match = re.search(r'\{.*\}', assistant_msg, re.DOTALL)
        if json_match:
            tool_call = json.loads(json_match.group())
        else:
            tool_call = json.loads(assistant_msg)
    except json.JSONDecodeError:
        print(f"  ERROR: Could not parse JSON")
        messages.append({"role": "assistant", "content": assistant_msg})
        messages.append({"role": "user", "content": 'Respond with valid JSON: {"tool": "<name>", "params": {<args>}}'})
        continue

    tool_name = tool_call.get("tool", "")
    params = tool_call.get("params", {})

    if tool_name == "__done__":
        print("\n  Agent signaled DONE.")
        break

    # Execute action
    action = HROnboardingAction(tool_name=tool_name, arguments=params)
    obs = env.step(action)

    result_str = json.dumps(obs.tool_result, indent=2)
    print(f"  Tool: {tool_name}")
    print(f"  Result: {result_str[:300]}{'...' if len(result_str) > 300 else ''}")

    messages.append({"role": "assistant", "content": assistant_msg})
    messages.append({"role": "user", "content": f"Tool result:\n{result_str}\n\nContinue with next tool call, or {{\"tool\": \"__done__\", \"params\": {{}}}} if done."})

    if obs.done:
        print(f"\n  Episode done. Reward: {obs.reward}")
        break

# --- Final evaluation ---
print("\n" + "=" * 70)
print("FINAL EVALUATION")
print("=" * 70)

evaluator = RubricEvaluator()
task = env._current_task
eval_result = evaluator.evaluate(task, env.world.action_log)

print(f"\nTask: {task.task_id}")
print(f"Score: {eval_result['score']:.0%} ({eval_result['passed_count']}/{eval_result['total_criteria']} criteria)")
print(f"Passed: {eval_result['passed']}")
print(f"\nCriteria breakdown:")
for c in eval_result["criteria_results"]:
    status = "PASS" if c["passed"] else "FAIL"
    print(f"  [{status}] {c['name']}: {c['description']}")

print(f"\nAction log ({len(env.world.action_log)} calls):")
for i, a in enumerate(env.world.action_log):
    print(f"  {i+1}. {a['tool']}({json.dumps(a['params'])[:80]})")
