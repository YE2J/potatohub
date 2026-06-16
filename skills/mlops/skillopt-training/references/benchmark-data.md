# SkillOpt Benchmark Data — Download Reference

All six benchmarks use lightweight **split manifests** provided in `data/*_id_split/` (or `data/alfworld_path_split/`). These manifests contain only IDs/paths — you need the **raw data** from the source to materialize full runnable items.

## Ready-to-Run (materialized)

### SearchQA
- **Source:** Hugging Face `lucadiliello/searchqa`
- **Split:** 400 train / 200 val / 1400 test
- **Type:** Pure text QA (question + context + answers)
- **Download + materialize:**
  ```python
  from datasets import load_dataset
  ds = load_dataset('lucadiliello/searchqa')
  # IDs from data/searchqa_id_split/{train,val,test}/items.json
  # match ds[*]['key'] exactly
  ```
- **Output path:** `data/searchqa_split/{train,val,test}/items.json`

### LiveMathematicianBench
- **Source:** Hugging Face `LiveMathematicianBench/LiveMathematicianBench`
- **Split:** 35 train / 18 val / 124 test (from 177 total rows)
- **Type:** Math theorem MCQ (theorem + sketch + choices)
- **Download + materialize:**
  ```python
  ds = load_dataset('LiveMathematicianBench/LiveMathematicianBench', split='train')
  # IDs: "<month>:<no>" format (e.g. "202602:22")
  # fields: month, no, paper_link, theorem, sketch, theorem_type, mcq
  ```
- **Output path:** `data/livemathematicianbench_split/{train,val,test}/items.json`

### ALFWorld
- **Source:** GitHub `alfworld/alfworld` + `pip install alfworld`
- **Split:** 39 train / 18 val / 134 test (uses gamefile paths, not IDs)
- **Download:**
  ```bash
  pip install alfworld
  export ALFWORLD_DATA=~/code/SkillOpt/data/alfworld_data
  alfworld-download  # downloads json_2.1.1 (72MB zip + 35MB pddl)
  ```
- **Split path:** `data/alfworld_path_split/` (can be used directly as `--split_dir`)
- **Note:** The split manifest contains `gamefile` paths relative to `$ALFWORLD_DATA`

## Needs Extra Work

### DocVQA
- **Source:** Hugging Face `lmms-lab/DocVQA` (DocVQA config)
- **Split:** 107 train / 53 val / 374 test (10% of validation set)
- **Blocked by:** Images must be downloaded separately to `data/docvqa_images/`
- **Requires:** `pip install Pillow` for image decoding
- **CSV format:** question, answer/ground_truth, image_path, questionId, docId
- **Dataloader:** Reads CSV from split directory, parses `question` and `document_path:` fields

### SpreadsheetBench
- **Source:** Hugging Face `KAKA22/SpreadsheetBench`
- **Split:** 80 train / 40 val / 280 test (Verified 400 subset)
- **Blocked by:** WebDataset format — HF `datasets` library can't load the TAR archives
- **Workaround:** Download raw `spreadsheetbench_verified_400.tar.gz` and extract to `data/spreadsheetbench_verified_400/`
- **Dataloader path:** `data/spreadsheetbench_split/`

### OfficeQA
- **Source:** Hugging Face `databricks/officeqa`
- **Split:** 50 train / 24 val / 172 test
- **Blocked by:** **Gated dataset** — requires Hugging Face access request
- **To request:** Visit https://huggingface.co/databricks/officeqa and click "Access repository"
- **Format:** CSV with uid, question, ground_truth, source_files, source_docs

## Split Manifest Structure

Every benchmark follows the same layout:
```
data/<benchmark>_<type>/
├── split_manifest.json    # metadata: source, counts, fields
├── train/items.json       # list[{"id": "..."}]
├── val/items.json
└── test/items.json
```

Materialized output goes to `data/<benchmark>_split/{train,val,test}/items.json` with full item data (question, answer, etc.).
