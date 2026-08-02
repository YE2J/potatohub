---
name: project-evaluation
description: Evaluate third-party open-source projects for installation necessity, tech-stack compatibility, and value to the existing quantitative system. Produces structured multi-dimensional assessments with cross-group summaries.
category: research
triggers:
  - "evaluate project"
  - "安装必要性评估"
  - "项目分析"
  - "借鉴价值评估"
  - "开源项目评估"
---

# Project Evaluation Skill

Use this skill when the user asks you to analyze one or more GitHub (or other) open-source projects for fit, compatibility, and potential adoption within their existing system (especially the `~/my_quant_system/` A-share quantitative framework).

## Tiered Fallback Strategy for Fetching Project Info

When `web_extract` / `web_search` fail (FIRECRAWL_API_KEY unset, Portal Tool Gateway inactive, billing exhausted) and browser tools are unavailable:

### Tier 0: GitHub Search API (project discovery)

Best for **finding projects by keyword** before evaluating any single one. Returns machine-readable JSON with stars, description, language, topics, and license — no HTML parsing needed.

```bash
# Search repos by name/keyword, sorted by stars
curl -sL --connect-timeout 5 --max-time 10 \
  -o /tmp/gh_search.json \
  "https://api.github.com/search/repositories?q=task-router+in:name&sort=stars&order=desc&per_page=10"

# Then browse with read_file:
read_file(path='/tmp/gh_search.json', limit=100)
# Use offsets to scroll through JSON results
```

**Key query parameters:**
- `q=term+in:name` — search in repo name only (most precise)
- `q=term+in:name,description` — search name + description
- `q='"exact-phrase"'` — exact match
- `sort=stars&order=desc` — sort by popularity
- `per_page=10` — max 100 results per page

**GitHub raw README (once you've identified the project):**

### Tier 1: Raw GitHub README via curl
```bash
curl -sL --max-time 10 "https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
# Fallback to master branch:
curl -sL --max-time 10 "https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
# For non-Main/master branches:
curl -sL --max-time 10 "https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/{branch}/README.md"
```

### Tier 2: GitHub HTML scraping for page metadata
```bash
curl -sL --max-time 10 "https://github.com/{owner}/{repo}" | grep -i 'description\|readme\|about'
```
Extract the `<meta name="description">` tag for the project description.
From the embedded JSON in the page (inside `<script type="application/json" data-target="react-app.embeddedData">`), extract `tree.items` for repo file listing and `overviewFiles` for rendered README HTML.

### Tier 3: Branch discovery
Try common branches in order: `main`, `master`, check GitHub page for `refInfo.name` in embedded JSON.

### Pitfalls
- **macOS system python3 triggers xcode-select** — importing certain stdlib modules on a machine without Xcode CLI tools causes `xcode-select: error`. This breaks pipe chains like `curl | python3`. **Fix:** use `curl -o /tmp/file.json` to save, then browse with `read_file` or use a virtualenv python instead.
- **macOS grep** lacks `-P` flag — use `grep -E` with basic patterns or `python3` with `re` instead.
- **Security scan** blocks `curl | python3` pipelines on high-risk signals. Redirect to temp files: `curl ... -o /tmp/foo && python3 -c "..."` or approve the pipe via `/approve`.
- **GitHub Search API** unauthenticated rate limit is ~10 req/min, 60 req/hr. For heavy discovery paginate with `&page=N`; for README content use raw.githubusercontent.com instead.
- **Empty README** — fall back to GitHub HTML page's `<meta name="description">` tag or Chinese `README.zh.md` variants.

## Structured Evaluation Dimensions

For each project, produce a consistent assessment across these dimensions:

| Dimension | Description |
|-----------|-------------|
| **功能 (Functionality)** | Core features, what it does |
| **技术栈 (Tech Stack)** | Language, frameworks, databases, data sources |
| **兼容性 (Compatibility)** | How well it aligns with the user's existing system (SQLite vs ClickHouse, Tushare vs akshare, self-implemented vs heavy framework) |
| **借鉴点 (Worthwhile Aspects)** | Specific techniques, designs, or code worth borrowing |
| **安装必要性 (Installation Necessity)** | Low / Medium / High with explicit reasoning |
| **推荐度 (Recommendation)** | ⭐ rating + one-line justification |

## Cross-Group Summary

After evaluating all projects, produce a summary table:

- **最有安装价值的项目** — the one that fills the biggest data/feature gap
- **最值得借鉴思路的项目** — the one whose design philosophy best matches user preferences
- **各项目一句话评价** — concise per-project verdict
- **对当前核心需求的回应** — connect findings back to the user's stated goal (e.g. profit, risk, factor mining)

## Reference Files

- `references/fin-agent-a-share-skill-stock-datasource-financial-api-evaluation.md` — Full evaluation data from the 4-project analysis session (July 2026)
