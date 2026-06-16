# MECE Resolver Decision Tree Template

Copy this into `~/brain/RESOLVER.md` when creating a new brain repo. Walk this tree before creating any new page. Exactly one directory — no duplicates.

---

## RESOLVER — Filing Decision Tree

1. **Is it about a person?** → `people/`
2. **Is it about an organization (company, non-profit, institution)?** → `companies/`
3. **Is it a financial transaction (investment, acquisition, funding)?** → `deals/`
4. **Is it a specific event with a timestamp (meeting, call, conference)?** → `meetings/`
5. **Is it something being actively built (product, feature, codebase)?** → `projects/`
6. **Is it a raw possibility, not yet committed?** → `ideas/`
7. **Is it a mental model, framework, or teachable concept?** → `concepts/`
8. **Is it a written artifact (essay, post, note)?** → `writing/`
9. **Is it a major life workstream (career track, personal goal)?** → `programs/`
10. **Is it about org strategy, operations, or process?** → `org/`
11. **Is it about politics, policy, or governance?** → `civic/`
12. **Is it about public narrative, content, or media?** → `media/`
13. **Is it a private/personal note?** → `personal/`
14. **Is it about domestic operations (home, family, logistics)?** → `household/`
15. **Is it about a candidate or hiring pipeline?** → `hiring/`
16. **Is it a raw import (transcript, export, scrape)?** → `sources/`
17. **Is it a reusable LLM prompt?** → `prompts/`
18. **Unsure / temporary capture?** → `inbox/`
19. **Page is obsolete / superseded?** → move to `archive/`

Read the target directory's README.md before creating. Every page gets:
- Frontmatter (canonical slug, aliases, type)
- Compiled truth (above the line — always current)
- Timeline (below the line — append-only evidence)

---

## Per-Directory README.md Template

Each directory needs a resolver answering what goes here vs what does NOT go here.

```markdown
# DirectoryName Resolver

## What goes here
[Positive definition + concrete test for inclusion]

## What does NOT go here
[Key distinctions from neighboring directories]
```
