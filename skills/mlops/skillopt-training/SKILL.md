---
name: skillopt-training
description: "Deploy and run Microsoft SkillOpt — train reusable agent skills via text-space optimization. Setup, backend config (DeepSeek/OpenAI-compatible), and benchmark data download."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skillopt, training, agent-skills, optimization, deepseek, benchmarks]
    related_skills: [karing-proxy]
---

# SkillOpt — Training Agent Skills

## Overview

[SkillOpt](https://github.com/microsoft/SkillOpt) (Microsoft Research) treats a compact `SKILL.md` document as the trainable state of a frozen LLM agent. It optimizes it through rollout → reflect → edit → gate cycles, without touching model weights.

The repo lives at `~/code/SkillOpt` with a Python 3.12 venv and DeepSeek as the backend.

## When to Use

- User wants to train/optimize an agent skill document with disciplined validation gating
- User wants to run SkillOpt benchmarks (SearchQA, ALFWorld, LiveMath, etc.)
- User asks about SkillOpt-Sleep (nightly skill evolution from session transcripts)
- User needs to configure SkillOpt with a new backend provider

## Quick Start

```bash
cd ~/code/SkillOpt && source .venv/bin/activate && source .env

# SearchQA (easiest — pure text, 400/200/1400 split)
python scripts/train.py \
    --config configs/searchqa/default.yaml \
    --split_dir data/searchqa_split \
    --optimizer_model deepseek-chat \
    --target_model deepseek-chat

# LiveMathematicianBench (math reasoning)
python scripts/train.py \
    --config configs/livemathematicianbench/default.yaml \
    --split_dir data/livemathematicianbench_split \
    --optimizer_model deepseek-chat \
    --target_model deepseek-chat

# ALFWorld (embodied agent — needs env var)
export ALFWORLD_DATA=$PWD/data/alfworld_data
python scripts/train.py \
    --config configs/alfworld/default.yaml \
    --split_dir data/alfworld_path_split \
    --optimizer_model deepseek-chat \
    --target_model deepseek-chat
```

## Backend Configuration

SkillOpt uses `AZURE_OPENAI_*` env vars even for OpenAI-compatible providers. For DeepSeek:

```bash
export AZURE_OPENAI_ENDPOINT=https://api.deepseek.com/v1
export AZURE_OPENAI_API_KEY=sk-...
export AZURE_OPENAI_AUTH_MODE=openai_compatible
```

The key is stored in `~/code/SkillOpt/.env` (protected from read_file; use `source .env` to load).

For different optimizer/target models:
- `--optimizer_model deepseek-reasoner` (stronger, for reflection)
- `--target_model deepseek-chat` (frozen, being optimized)

## Benchmark Data

Six benchmarks are supported. Three are ready-to-run; three need extra setup. See `references/benchmark-data.md` for per-benchmark download methods and split sizes.

Ready (3/6):
- **SearchQA** — HF `lucadiliello/searchqa` (pure text, 400/200/1400)
- **LiveMathematicianBench** — HF `LiveMathematicianBench/LiveMathematicianBench` (177 total)
- **ALFWorld** — GitHub `alfworld/alfworld` + `alfworld-download` (39/18/134)

Needs extra work (3/6):
- **DocVQA** — needs image download (~10GB) + Pillow
- **SpreadsheetBench** — needs raw tar.gz (WebDataset format incompatible with HF datasets lib)
- **OfficeQA** — gated on Hugging Face, needs access request

## Installation Notes

### Python venv on macOS 26.2
Homebrew Python 3.11/3.12 may have broken `ensurepip` and `pyexpat` on macOS 26.2. Use `uv venv` instead:

```bash
brew install uv
cd ~/code/SkillOpt
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

### GitHub access
If `git clone` fails with "Proxy CONNECT aborted", check for stale git proxy config (`git config --global --get http.proxy`). Bypass with `git -c http.proxy= -c https.proxy= clone ...`. Open Karing first if GitHub is unreachable (see karing-proxy skill).

## SkillOpt-Sleep

The companion tool for nightly skill evolution from coding sessions:

```bash
python -m skillopt_sleep run          # full cycle
python -m skillopt_sleep dry-run      # report only, no staging
python -m skillopt_sleep status       # show state + latest proposal
python -m skillopt_sleep adopt        # apply latest staged proposal
```

Default config is for Claude Code / Codex transcripts. Adapting to Hermes sessions requires modifying `harvest_sources.py`.

## Pitfalls

1. **`.env` is unreadable by read_file.** Hermes protects `.env` files. Use `source .env` in terminal commands, or write to it via heredoc in terminal.
2. **DeepSeek model alias.** Specifying `deepseek-chat` may resolve to `deepseek-v4-flash` at the API level. This is expected and doesn't affect training.
3. **HF_TOKEN not set.** Hugging Face downloads work without auth but have lower rate limits. Set `HF_TOKEN` for faster downloads.
4. **DocVQA needs Pillow.** Install with `pip install Pillow` before loading DocVQA images.
5. **ALFWorld needs $ALFWORLD_DATA.** Set this env var before running ALFWorld training, pointing at the directory containing `json_2.1.1/`.
