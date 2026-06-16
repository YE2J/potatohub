# SkillOpt — Deployment & Quickstart

Microsoft's text-space optimizer for agent skill documents. From
`github.com/microsoft/SkillOpt` (MIT, 7k+ stars). Installed at `~/code/SkillOpt`.

## Quick context

SkillOpt treats a SKILL.md document as the trainable state of a frozen LLM agent.
It runs rollouts, reflects on failures, proposes bounded edits, and gate-checks
against held-out validation — all without touching model weights.

Two modes:
- **Training** (`scripts/train.py`) — optimize a skill against a benchmark
- **Sleep** (`python -m skillopt_sleep`) — nightly consolidation from session transcripts

## Installation (macOS)

```bash
# Clone (Karing proxy may be needed for GitHub access)
cd ~/code && git clone https://github.com/microsoft/SkillOpt.git

# Python venv — Homebrew Python 3.11/3.12 may have broken ensurepip.
# Use uv instead:
cd ~/code/SkillOpt
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

## Backend: DeepSeek via OpenAI-compatible mode

SkillOpt reuses `AZURE_OPENAI_*` env var names even in compatible mode.
There is no separate `OPENAI_API_KEY`.

```bash
# ~/code/SkillOpt/.env
export AZURE_OPENAI_ENDPOINT=https://api.deepseek.com/v1
export AZURE_OPENAI_API_KEY=sk-...
export AZURE_OPENAI_AUTH_MODE=openai_compatible
```

CLI override when env vars aren't set:
```bash
python scripts/train.py \
    --azure_openai_endpoint https://api.deepseek.com/v1 \
    --azure_openai_api_key sk-... \
    --azure_openai_auth_mode openai_compatible
```

## Benchmark Data

SkillOpt ships **ID-only split manifests** in `data/<name>_id_split/`. Raw data
must be downloaded separately from Hugging Face and materialized into the
expected `split_dir` path.

### Ready to use (data materialized)

| Benchmark | split_dir | Source |
|-----------|-----------|--------|
| SearchQA | `data/searchqa_split` (400/200/1400) | HF `lucadiliello/searchqa` |
| LiveMath | `data/livemathematicianbench_split` (35/18/124) | HF `LiveMathematicianBench/LiveMathematicianBench` |
| ALFWorld | `data/alfworld_path_split` (39/18/134) | `alfworld-download` → `$ALFWORLD_DATA` |

### Needs extra work

| Benchmark | Blocker |
|-----------|---------|
| DocVQA | Images (~10GB) — install Pillow, stream-download to `data/docvqa_images/` |
| SpreadsheetBench | WebDataset format — download `spreadsheetbench_verified_400.tar.gz` manually |
| OfficeQA | **Gated** on HF — request access at `databricks/officeqa` |

### Materialization recipe (SearchQA example)

```python
from datasets import load_dataset
import json, os

# Load all splits from HF
ds_all = load_dataset('lucadiliello/searchqa')
lookup = {}
for split_name, ds in ds_all.items():
    for row in ds:
        lookup[row['key']] = {
            'question': row['question'],
            'context': row['context'],
            'answers': row['answers'],
            'id': row['key'],
        }

# Materialize against the ID manifest
for split in ['train', 'val', 'test']:
    with open(f'data/searchqa_id_split/{split}/items.json') as f:
        manifest = json.load(f)
    materialized = [lookup[item['id']] for item in manifest if item['id'] in lookup]
    os.makedirs(f'data/searchqa_split/{split}', exist_ok=True)
    with open(f'data/searchqa_split/{split}/items.json', 'w') as f:
        json.dump(materialized, f, ensure_ascii=False)
```

## Training

```bash
cd ~/code/SkillOpt && source .venv/bin/activate && source .env

# SearchQA (recommended first run — pure text, fastest)
python scripts/train.py \
    --config configs/searchqa/default.yaml \
    --split_dir data/searchqa_split \
    --optimizer_model deepseek-chat \
    --target_model deepseek-chat

# ALFWorld
export ALFWORLD_DATA=$PWD/data/alfworld_data
python scripts/train.py \
    --config configs/alfworld/default.yaml \
    --split_dir data/alfworld_path_split \
    --optimizer_model deepseek-chat \
    --target_model deepseek-chat

# LiveMath
python scripts/train.py \
    --config configs/livemathematicianbench/default.yaml \
    --split_dir data/livemathematicianbench_split \
    --optimizer_model deepseek-chat \
    --target_model deepseek-chat
```

**Key CLI flags:** `--optimizer_model`, `--target_model`, `--optimizer_backend`,
`--target_backend`, `--reasoning_effort`, `--azure_openai_*` overrides.

Config: `configs/_base_/default.yaml` (4 epochs, lr=4, batch_size=40, gate on).

## Pitfalls

- **Python venv**: Homebrew Python on macOS 26 may have broken `ensurepip`/`pyexpat`.
  Use `uv venv --python 3.12` instead of `python3 -m venv`.
- **Git proxy**: if `git config http.proxy` points to a dead proxy (e.g. `127.0.0.1:18789`),
  clone with `git -c http.proxy= -c https.proxy= clone <url>`.
- **DeepSeek model name**: specify `deepseek-chat` or `deepseek-reasoner` — the
  actual deployed model is auto-selected by DeepSeek.
- **Training runtime**: SearchQA validation rollout alone (200 items × ~1-2s each)
  takes ~5-10 min with DeepSeek. Full 4-epoch training: 30-60 min.
- **Rate limits**: Some SearchQA questions have very long contexts (full web pages).
  Config has `exec_timeout: 120` per call — slow questions are expected.
