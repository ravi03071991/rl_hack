# Harder HR RL (OpenEnv + Unsloth)

This package is a harder greenfield HR environment than `greenfield_minimal`.

## Design

- HR onboarding theme retained
- Hidden packet workflow: instruction gives `packet_id`, agent must lookup details first
- Multi-step sequence required: lookup -> create employee -> provision IT -> assign access -> send welcome -> complete
- Strict rubric checks for tool usage, exact parameter values, and tool order

## Files

- `hr_hard_env/environment.py`: environment + tools
- `hr_hard_env/environment_v2.py`: enterprise multi-app long-horizon environment
- `hr_hard_env/tasks.py`: task/packet definitions
- `hr_hard_env/tasks_v2.py`: generated 120-template enterprise catalog tasks
- `hr_hard_env/rubric.py`: rubric evaluator
- `scripts/train_hard_hr_grpo.py`: Unsloth + GRPO script (non-notebook)
- `scripts/train_enterprise_v2_grpo.py`: Unsloth + GRPO script for v2 catalog

## Run training

```bash
python -m greenfield_hr_hard.scripts.train_hard_hr_grpo \
  --model-name unsloth/Llama-3.2-1B-Instruct \
  --max-steps 120 \
  --repeats-per-task 24 \
  --output-dir greenfield_hr_hard/outputs/hard_hr_grpo
```

## Run enterprise v2 training

```bash
python -m greenfield_hr_hard.scripts.train_enterprise_v2_grpo \
  --model-name Qwen/Qwen2.5-1.5B-Instruct \
  --max-steps 20 \
  --repeats-per-task 2 \
  --eval-max-tasks 6 \
  --output-dir greenfield_hr_hard/outputs/enterprise_v2_smoke
```

## Run env server

```bash
python -m greenfield_hr_hard.hr_hard_env.app --port 7862
```

```bash
python -m greenfield_hr_hard.hr_hard_env.app_v2 --port 7863
```
