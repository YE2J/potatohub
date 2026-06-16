#!/usr/bin/env python3
"""Bootstrap a GBrain MECE brain repo with directory structure + resolver files.

Usage:
    python3 bootstrap_brain.py ~/brain

Creates:
    brain/
    ├── RESOLVER.md
    ├── schema.md
    ├── index.md
    ├── log.md
    ├── people/  companies/  deals/  meetings/  projects/
    ├── ideas/  concepts/  writing/  programs/  org/
    ├── civic/  media/  personal/  household/  hiring/
    ├── sources/  prompts/  inbox/  archive/
    └── .raw/
"""

import os
import sys

DIRECTORIES = [
    "people", "companies", "deals", "meetings", "projects",
    "ideas", "concepts", "writing", "programs", "org",
    "civic", "media", "personal", "household", "hiring",
    "sources", "prompts", "inbox", "archive",
]

RESOLVER_MD = """# RESOLVER — Brain Filing Decision Tree

Walk this tree when creating a new page. Exactly one directory — no duplicates.

1. **Is it about a person?** → `people/`
2. **Is it about an organization?** → `companies/`
3. **Is it a financial transaction?** → `deals/`
4. **Is it a specific event?** → `meetings/`
5. **Is it being actively built?** → `projects/`
6. **Is it a raw possibility?** → `ideas/`
7. **Is it a teachable framework?** → `concepts/`
8. **Is it a written artifact?** → `writing/`
9. **Is it a major life workstream?** → `programs/`
10. **Is it about org strategy/ops?** → `org/`
11. **Is it about politics/policy?** → `civic/`
12. **Is it about media/narrative?** → `media/`
13. **Is it private/personal?** → `personal/`
14. **Is it domestic/household?** → `household/`
15. **Is it candidate/hiring?** → `hiring/`
16. **Is it a raw import?** → `sources/`
17. **Is it a reusable prompt?** → `prompts/`
18. **Unsure?** → `inbox/`
19. **Page obsolete?** → move to `archive/`
"""

SCHEMA_MD = """# GBrain Schema

## Page Structure

Every page has two layers separated by a horizontal rule:

### Above the line — Compiled Truth (rewritten on each update)
- Title (H1)
- Frontmatter: slug, aliases, type, created, updated
- Executive summary (2-3 sentences)
- State fields (current status, key facts)
- Open threads / questions
- See Also (wikilinks to related pages)

### Below the line — Timeline (append-only, never rewritten)
- Reverse-chronological entries
- Each entry: `YYYY-MM-DD: [source] what happened`

## Frontmatter Convention
```yaml
---
slug: entity-slug
aliases:
  - nickname
type: person | company | concept | project | deal | meeting | idea
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```
"""

DIR_README = """# {title} Resolver

## What goes here
[Define what belongs in this directory]

## What does NOT go here
[Distinguish from neighboring directories]
"""


def bootstrap(path: str) -> None:
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, ".raw"), exist_ok=True)

    # Create directories
    for d in DIRECTORIES:
        os.makedirs(os.path.join(path, d), exist_ok=True)

    # Write resolver files
    files = {
        "RESOLVER.md": RESOLVER_MD,
        "schema.md": SCHEMA_MD,
        "index.md": "# Brain Index\n\nContent catalog — one-line summaries of all pages.\n",
        "log.md": "# Brain Log\n\n| Date | Action | Details |\n|------|--------|---------|\n",
    }
    for name, content in files.items():
        filepath = os.path.join(path, name)
        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write(content)
            print(f"  Created {name}")

    # Write directory READMEs
    for d in DIRECTORIES:
        readme = os.path.join(path, d, "README.md")
        if not os.path.exists(readme):
            title = d.capitalize()
            with open(readme, "w") as f:
                f.write(DIR_README.format(title=title))
            print(f"  Created {d}/README.md")

    print(f"\nBrain repo bootstrapped at: {path}")
    print(f"  {len(DIRECTORIES)} directories + .raw/")

    # Git init if not already
    git_dir = os.path.join(path, ".git")
    if not os.path.exists(git_dir):
        os.system(f"cd {path} && git init && git add -A && git commit -m 'Initialize brain with MECE structure'")
        print("  Git repo initialized and committed")
    else:
        print("  Git repo already exists")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 bootstrap_brain.py <path>")
        sys.exit(1)
    bootstrap(sys.argv[1])
