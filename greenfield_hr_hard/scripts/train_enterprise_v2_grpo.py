#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import re

import torch
from datasets import Dataset

from greenfield_hr_hard.hr_hard_env.environment_v2 import EnterpriseWorkflowEnvironmentV2, TOOL_DEFINITIONS_V2
from greenfield_hr_hard.hr_hard_env.models import HardHRAction
from greenfield_hr_hard.hr_hard_env.tasks_v2 import TASKS_V2, TASK_INDEX_V2

SYSTEM_PROMPT = (
    "You are an enterprise HR-IT automation agent. "
    "Return ONLY JSON as an array of tool calls. "
    "Each item must be {\"tool\": string, \"params\": object}."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train GRPO on enterprise HR+IT catalog v2")
    p.add_argument("--model-name", default="Qwen/Qwen2.5-1.5B-Instruct")
    p.add_argument("--max-seq-length", type=int, default=1280)
    p.add_argument("--max-steps", type=int, default=60)
    p.add_argument("--repeats-per-task", type=int, default=6)
    p.add_argument("--learning-rate", type=float, default=5e-6)
    p.add_argument("--per-device-train-batch-size", type=int, default=6)
    p.add_argument("--gradient-accumulation-steps", type=int, default=1)
    p.add_argument("--num-generations", type=int, default=6)
    p.add_argument("--generation-batch-size", type=int, default=None)
    p.add_argument("--steps-per-generation", type=int, default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", default="greenfield_hr_hard/outputs/enterprise_v2_grpo")
    p.add_argument("--load-in-4bit", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--wandb-project", default="hr-enterprise-v2-rl")
    p.add_argument("--wandb-entity", default=None)
    p.add_argument("--wandb-api-key", default=None)
    p.add_argument("--wandb-run-name", default=None)
    p.add_argument("--eval-every-steps", type=int, default=10)
    p.add_argument("--eval-max-tasks", type=int, default=12)
    p.add_argument("--use-vllm", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--vllm-gpu-memory-utilization", type=float, default=0.55)
    p.add_argument("--vllm-mode", default="server")
    p.add_argument("--vllm-server-timeout", type=float, default=240.0)
    return p.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_prompt(task_id: str, instruction: str, required_tools: list[str], max_horizon: int, tokenizer=None) -> str:
    tool_names = ", ".join(t["name"] for t in TOOL_DEFINITIONS_V2)
    required = " -> ".join(required_tools)
    user_content = (
        f"{SYSTEM_PROMPT}\n"
        f"TASK_ID={task_id}\n"
        f"Instruction: {instruction}\n"
        f"Required tool path: {required}\n"
        f"Max horizon: {max_horizon}\n"
        f"Allowed tools: {tool_names}\n"
        "Rules:\n"
        "1) Call workday_get_worker_profile first.\n"
        "2) Use exact values from lookup response.\n"
        "3) Use jira_transition_ticket only after jira_create_compliance_ticket.\n"
        "4) End with workflow_finalize.\n"
    )
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        messages = [
            {"role": "system", "content": "You are a strict JSON tool-calling assistant."},
            {"role": "user", "content": user_content},
        ]
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return user_content


def extract_text(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if "text" in item:
            return str(item["text"])
        content = item.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return extract_text(content)
        return str(content)
    if isinstance(item, list):
        out = []
        for x in item:
            out.append(extract_text(x))
        return "\n".join(out)
    return str(item)


def parse_tool_sequence(text: str) -> list[tuple[str, dict]] | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    decoder = json.JSONDecoder()

    def to_steps(candidate) -> list[tuple[str, dict]] | None:
        if isinstance(candidate, dict) and isinstance(candidate.get("calls"), list):
            candidate = candidate["calls"]
        if isinstance(candidate, dict):
            candidate = [candidate]
        if not isinstance(candidate, list):
            return None
        out: list[tuple[str, dict]] = []
        for step in candidate:
            if not isinstance(step, dict):
                continue
            tool = step.get("tool") or step.get("name") or step.get("tool_name")
            params = step.get("params")
            if params is None:
                params = step.get("arguments", {})
            if isinstance(tool, str) and isinstance(params, dict):
                out.append((tool, params))
        return out if out else None

    best = None
    try:
        best = to_steps(json.loads(cleaned))
    except json.JSONDecodeError:
        pass

    for start in [m.start() for m in re.finditer(r"[\[{]", cleaned)]:
        try:
            parsed, _ = decoder.raw_decode(cleaned[start:])
        except json.JSONDecodeError:
            continue
        steps = to_steps(parsed)
        if steps and (best is None or len(steps) > len(best)):
            best = steps
    return best


def extract_task_id(prompt: str) -> str | None:
    m = re.search(r"TASK_ID=(v2_[a-z_0-9]+)", prompt)
    return m.group(1) if m else None


def replay_sequence(task_id: str, sequence: list[tuple[str, dict]]) -> float:
    env = EnterpriseWorkflowEnvironmentV2(seed=0)
    env.reset_to_task(task_id)
    task = TASK_INDEX_V2[task_id]

    obs = None
    for tool, params in sequence[: task.max_steps]:
        obs = env.step(HardHRAction(tool_name=tool, arguments=params))
        if obs.done:
            break

    if obs is None or not obs.done:
        obs = env.step(HardHRAction(tool_name="workflow_finalize", arguments={}))

    return float(obs.reward or 0.0)


def rubric_reward(completions, **kwargs):
    prompts = kwargs.get("prompt", kwargs.get("prompts", []))
    task_ids = kwargs.get("task_id", [])
    rewards = []

    for i, completion in enumerate(completions):
        text = extract_text(completion)
        sequence = parse_tool_sequence(text)

        task_id = task_ids[i] if i < len(task_ids) else None
        if not task_id and i < len(prompts):
            task_id = extract_task_id(str(prompts[i]))

        if sequence is None or not task_id:
            rewards.append(-2.0)
            continue

        score = replay_sequence(task_id, sequence)
        rewards.append(score * 10.0 - 2.0)
    return rewards


@torch.inference_mode()
def evaluate_model(model, tokenizer, max_tasks: int | None = None) -> float:
    total = 0.0
    tasks = TASKS_V2 if max_tasks is None else TASKS_V2[:max_tasks]
    for task in tasks:
        prompt = build_prompt(task.task_id, task.instruction, task.required_tools, task.max_steps, tokenizer=tokenizer)
        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        gen = model.generate(
            **inputs,
            max_new_tokens=420,
            do_sample=False,
            temperature=None,
            top_p=None,
            pad_token_id=tokenizer.eos_token_id,
        )
        out_ids = gen[:, inputs["input_ids"].shape[1]:]
        text = tokenizer.batch_decode(out_ids, skip_special_tokens=True)[0]
        sequence = parse_tool_sequence(text)
        reward = 0.0 if sequence is None else replay_sequence(task.task_id, sequence)
        total += reward
        print(f"eval task={task.task_id:28s} reward={reward:.3f} calls={(len(sequence) if sequence else 0)}")
    return total / len(tasks)


def build_dataset(repeats_per_task: int, tokenizer) -> Dataset:
    rows = []
    for task in TASKS_V2:
        for _ in range(repeats_per_task):
            rows.append(
                {
                    "prompt": build_prompt(task.task_id, task.instruction, task.required_tools, task.max_steps, tokenizer=tokenizer),
                    "task_id": task.task_id,
                }
            )
    random.shuffle(rows)
    return Dataset.from_list(rows)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    if not torch.cuda.is_available():
        raise RuntimeError("No CUDA device detected. Unsloth RL training requires a GPU.")

    from unsloth import FastLanguageModel

    try:
        from unsloth import PatchFastRL
    except ImportError:
        PatchFastRL = None
    if PatchFastRL is not None:
        PatchFastRL("GRPO", FastLanguageModel)

    from trl import GRPOConfig, GRPOTrainer
    from transformers import TrainerCallback
    import wandb

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=args.max_seq_length,
        load_in_4bit=args.load_in_4bit,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    ds = build_dataset(args.repeats_per_task, tokenizer=tokenizer)
    bf16_supported = bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported())

    os.environ.setdefault("WANDB_PROJECT", args.wandb_project)
    if args.wandb_entity:
        os.environ["WANDB_ENTITY"] = args.wandb_entity
    if args.wandb_api_key:
        os.environ["WANDB_API_KEY"] = args.wandb_api_key
    if args.wandb_run_name:
        os.environ["WANDB_NAME"] = args.wandb_run_name

    train_args = GRPOConfig(
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        num_generations=args.num_generations,
        generation_batch_size=args.generation_batch_size,
        steps_per_generation=args.steps_per_generation,
        max_steps=args.max_steps,
        logging_steps=1,
        save_steps=args.max_steps,
        report_to="wandb",
        run_name=args.wandb_run_name,
        max_prompt_length=900,
        max_completion_length=420,
        remove_unused_columns=False,
        bf16=bf16_supported,
        fp16=not bf16_supported,
        seed=args.seed,
        use_vllm=args.use_vllm,
        vllm_gpu_memory_utilization=args.vllm_gpu_memory_utilization,
        vllm_mode=args.vllm_mode,
        vllm_server_timeout=args.vllm_server_timeout,
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[rubric_reward],
        args=train_args,
        train_dataset=ds,
    )

    def log_wandb(payload: dict) -> None:
        if getattr(wandb, "run", None) is not None:
            wandb.log(payload)

    class PeriodicEvalCallback(TrainerCallback):
        def on_step_end(self, args_cb, state, control, **kwargs):
            if args.eval_every_steps <= 0:
                return control
            step = int(state.global_step)
            if step <= 0 or (step % args.eval_every_steps) != 0:
                return control
            print(f"\n[periodic_eval] step={step} running fixed-set eval...")
            score = evaluate_model(model, tokenizer, max_tasks=args.eval_max_tasks)
            print(f"[periodic_eval] step={step} eval_mean_reward={score:.3f}")
            log_wandb({"eval_mean_reward": score, "eval_tasks": args.eval_max_tasks, "step": step})
            return control

    trainer.add_callback(PeriodicEvalCallback())

    print(f"Training rows: {len(ds)}")
    print("\nBaseline evaluation:")
    baseline = evaluate_model(model, tokenizer, max_tasks=args.eval_max_tasks)
    log_wandb({"eval_mean_reward": baseline, "eval_tasks": args.eval_max_tasks, "step": 0})
    print(f"Baseline mean reward: {baseline:.3f}")

    trainer.train()

    print("\nPost-training evaluation:")
    after = evaluate_model(model, tokenizer, max_tasks=args.eval_max_tasks)
    log_wandb({"eval_mean_reward": after, "eval_tasks": args.eval_max_tasks, "step": int(trainer.state.global_step)})
    print(f"Post-training mean reward: {after:.3f}")
    print(f"Delta: {after - baseline:.3f}")

    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


if __name__ == "__main__":
    main()
