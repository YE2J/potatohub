# Bulk Import Pattern: LLMQuant Skills into Hermes

Tested pattern for importing a repo of pre-made third-party skills into Hermes Agent.

## Source
- GitHub repo: LLMQuant/skills (branch: master, MIT License)
- 18 skills, 79 workflow files
- Raw URL base: `https://raw.githubusercontent.com/LLMQuant/skills/master/skills/`

## Steps (concrete example)

### 1. Discover skill directories
Fetch `https://api.github.com/repos/LLMQuant/skills/contents/skills` to list all skills.

### 2. Create each skill
```python
from hermes_tools import web_extract, write_file

# Download SKILL.md
result = web_extract(urls=["https://raw.githubusercontent.com/LLMQuant/skills/master/skills/llmquant-equities/SKILL.md"])
content = result["results"][0]["content"]

# Create the skill
# Use skill_manage(action='create', name='llmquant-equities', content=content, category='llmquant')
```

### 3. Add workflow files
```python
# Download workflow
result = web_extract(urls=["https://raw.githubusercontent.com/LLMQuant/skills/master/skills/llmquant-equities/workflows/five-lens-stock-analysis.md"])

# Write directly to disk (NOT via skill_manage write_file)
write_file(path="~/.hermes/skills/llmquant/llmquant-equities/workflows/five-lens-stock-analysis.md", content=content)
```

### 4. Verify
```bash
# Count all skills
ls ~/.hermes/skills/llmquant/*/SKILL.md | wc -l

# Count all workflow files
find ~/.hermes/skills/llmquant -path "*/workflows/*" -name "*.md" | wc -l
```

## Known Issues
- `skill_manage write_file` rejects `workflows/` — write directly with `write_file` tool instead.
- YAML description with colons — wrap in quotes.
- 50 tool-call limit in `execute_code` — split batch imports.
- web_extract truncates long files (~5000 chars via LLM summarization); for full content use `browser_navigate` on the raw URL.
