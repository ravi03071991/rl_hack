"""Run all 77 tasks with GPT-4o-mini and compute aggregate metrics."""

import sys
import json
import os
import re
import time

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, ".")
sys.path.insert(0, "./server")

from openai import OpenAI
from server.hr_onboarding_environment import HROnboardingEnvironment
from models import HROnboardingAction
from server.tools import TOOL_DEFINITIONS
from server.rubrics import RubricEvaluator

client = OpenAI()
tool_desc = json.dumps(TOOL_DEFINITIONS, indent=2)

system_prompt = (
    "You are an HR automation agent for AcmeCorp. You help with employee "
    "onboarding and offboarding by calling the appropriate tools.\n\n"
    "For each step, respond with ONLY a JSON tool call in this exact format:\n"
    '{"tool": "<tool_name>", "params": {<parameters>}}\n\n'
    'When you believe the task is complete, respond with:\n'
    '{"tool": "__done__", "params": {}}\n\n'
    "Important rules:\n"
    "- Respond with ONLY the JSON object, no other text\n"
    "- Use the exact tool names and parameter names from the tool definitions\n"
    "- Think about what information you need and what tools to call in what order\n\n"
    f"Available tools:\n{tool_desc}"
)

results = []
evaluator = RubricEvaluator()

num_tasks = 77
print("=" * 70)
print("HR ONBOARDING ENVIRONMENT — FULL EVALUATION (77 tasks)")
print(f"Model: gpt-4o-mini")
print("=" * 70)

for task_idx in range(num_tasks):
    env = HROnboardingEnvironment(seed=42, max_steps=15)
    # Cycle to the desired task
    for _ in range(task_idx + 1):
        obs = env.reset()

    task = env._current_task
    task_id = obs.task_id
    difficulty = obs.metadata.get("difficulty", "?")
    category = obs.metadata.get("category", "?")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": obs.instruction},
    ]

    steps_taken = 0
    error_count = 0

    for step in range(1, obs.max_steps + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=512,
            )
            assistant_msg = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  API error on {task_id} step {step}: {e}")
            time.sleep(5)
            continue

        # Parse tool call
        try:
            json_match = re.search(r'\{.*\}', assistant_msg, re.DOTALL)
            if json_match:
                tool_call = json.loads(json_match.group())
            else:
                tool_call = json.loads(assistant_msg)
        except json.JSONDecodeError:
            messages.append({"role": "assistant", "content": assistant_msg})
            messages.append({"role": "user", "content": 'Respond with valid JSON: {"tool": "<name>", "params": {<args>}}'})
            error_count += 1
            continue

        tool_name = tool_call.get("tool", "")
        params = tool_call.get("params", {})

        if tool_name == "__done__":
            break

        action = HROnboardingAction(tool_name=tool_name, arguments=params)
        obs = env.step(action)
        steps_taken += 1

        result_str = json.dumps(obs.tool_result, indent=2)
        messages.append({"role": "assistant", "content": assistant_msg})
        messages.append({"role": "user", "content": f"Tool result:\n{result_str}\n\nContinue with next tool call, or {{\"tool\": \"__done__\", \"params\": {{}}}} if done."})

        if obs.done:
            break

    # Evaluate
    eval_result = evaluator.evaluate(task, env.world.action_log)

    result = {
        "task_id": task_id,
        "difficulty": difficulty,
        "category": category,
        "score": eval_result["score"],
        "passed": eval_result["passed"],
        "passed_count": eval_result["passed_count"],
        "total_criteria": eval_result["total_criteria"],
        "steps_taken": steps_taken,
        "parse_errors": error_count,
    }
    results.append(result)

    status = "PASS" if result["passed"] else "FAIL"
    print(f"  [{task_idx+1:2d}/77] {task_id:10s} [{difficulty:10s}] [{category:14s}] "
          f"Score: {result['score']:.0%} ({result['passed_count']}/{result['total_criteria']}) "
          f"Steps: {steps_taken:2d}  {status}")

# --- Aggregate metrics ---
print("\n" + "=" * 70)
print("AGGREGATE RESULTS")
print("=" * 70)

total = len(results)
pass_count = sum(1 for r in results if r["passed"])
mean_score = sum(r["score"] for r in results) / total
mean_steps = sum(r["steps_taken"] for r in results) / total
total_criteria = sum(r["total_criteria"] for r in results)
total_passed_criteria = sum(r["passed_count"] for r in results)

print(f"\nOverall:")
print(f"  Tasks:           {total}")
print(f"  Pass rate:       {pass_count}/{total} ({pass_count/total:.1%})")
print(f"  Mean score:      {mean_score:.3f}")
print(f"  Mean steps:      {mean_steps:.1f}")
print(f"  Criteria hit:    {total_passed_criteria}/{total_criteria} ({total_passed_criteria/total_criteria:.1%})")

# By difficulty
print(f"\nBy Difficulty:")
for diff in ["simple", "medium", "complex", "edge_case"]:
    subset = [r for r in results if r["difficulty"] == diff]
    if not subset:
        continue
    n = len(subset)
    p = sum(1 for r in subset if r["passed"])
    s = sum(r["score"] for r in subset) / n
    st = sum(r["steps_taken"] for r in subset) / n
    print(f"  {diff:10s}: {p:2d}/{n:2d} pass ({p/n:.0%})  mean_score={s:.2f}  mean_steps={st:.1f}")

# By category
print(f"\nBy Category:")
for cat in ["lookup", "onboarding", "offboarding", "cross_workflow"]:
    subset = [r for r in results if r["category"] == cat]
    if not subset:
        continue
    n = len(subset)
    p = sum(1 for r in subset if r["passed"])
    s = sum(r["score"] for r in subset) / n
    print(f"  {cat:14s}: {p:2d}/{n:2d} pass ({p/n:.0%})  mean_score={s:.2f}")

# Save results
os.makedirs("outputs", exist_ok=True)
with open("outputs/full_eval_results.json", "w") as f:
    json.dump({
        "model": "gpt-4o-mini",
        "total_tasks": total,
        "pass_count": pass_count,
        "pass_rate": pass_count / total,
        "mean_score": mean_score,
        "mean_steps": mean_steps,
        "criteria_hit_rate": total_passed_criteria / total_criteria,
        "results": results,
    }, f, indent=2)
print(f"\nDetailed results saved to outputs/full_eval_results.json")
