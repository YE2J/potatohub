# Community Skill Repos & OfficeCLI — 2026-08 Evaluation Detail

Session evidence behind the `project-evaluation` Step-3 install-and-verify loop. Three repos evaluated back-to-back at user request; network context: GitHub direct was DOWN (HTTP 000) at first probe, recovered later in the session; Skills Hub CLI worked throughout.

## 1. sickn33/agentic-awesome-skills (AAS) — ⭐ 44,549

| Dimension | Finding |
|-----------|---------|
| Scale | 2,003 skills, MIT, has docs_zh-CN, `skills_index.json` (1.4MB), CATALOG.md generated 2026-08-04 |
| Coverage | dev / testing / security / infra / product / marketing / agent-orchestration / agent-squad — **NO finance/quant category** |
| Target agents | Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Copilot, Kiro, Antigravity — **no Hermes native path** |
| Distribution | npx installer, 60+ bundle plugins, AAS Core (MCP + aas CLI + browser Workbench) |
| Verdict | **Reference-only.** 定位错位 (general coding supermarket) + 生态错位 (no Hermes) + user's classes already covered (Kanban/MOA for orchestration, docx/xlsx/pdf skills for docs). Never batch-install 2003 skills. |
| Useful takeaway | Its SKILL.md conventions (Risk tiers, Triggers, Source attribution) are a good authoring model. |

## 2. RKiding/Awesome-finance-skills (AlphaEar) — ⭐ 2,754

| Dimension | Finding |
|-----------|---------|
| Scale | 10 skills, Apache 2.0, updated same-day, has 中文 README |
| Skills | alphaear-news / -stock / -sentiment / -predictor / -signal-tracker / -logic-visualizer / -reporter / -search / -deepear-lite / skill-creator |
| Data sources | akshare (EastMoney) + yfinance — **duplicates user's Tushare + DC stack** (user's own pipeline is stronger: local SQLite + cron + QFQ) |
| Incremental value | alphaear-news (聚合财联社/微博/知乎/华尔街见闻 + Polymarket) — the ONLY true gap vs user's data-driven pipeline; sentiment (-1~+1) secondary |
| Heavy deps | alphaear-predictor needs torch/transformers/Kronos weights (hundreds MB), black-box forecast — conflicts with user's factor-verification style |
| Verdict | User said "算了" (skip) — duplication-heavy, only news was incremental, and news sources need live anti-scraping verification before trust. If revisited: install ONLY alphaear-news, copy whole skill dir (includes scripts/ + local DB), test source reachability first. |

## 3. iOfficeAI/OfficeCLI — ⭐ 26,040 — INSTALLED & VERIFIED

| Dimension | Finding |
|-----------|---------|
| What | AI-agent Office suite: read/edit .docx/.xlsx/.pptx. C#, Apache 2.0, single binary, no Office install |
| Killer feature | Built-in HTML render engine → `.docx/.xlsx/.pptx` to HTML/SVG/PNG (**render → look → fix loop gives AI eyes**) |
| Install | `npm install -g @officecli/officecli` (4s). `brew install officecli` HUNG (timed out 300s). Binary: `~/.npm-global/bin/officecli` (in .zshrc PATH line 5; not on in-session PATH — export or full path) |
| Version | 1.0.143 (2026-08-06) |
| SKILL.md | https://officecli.ai/SKILL.md → 301 cloudflare redirect → `curl -sL`; 25,974 bytes, standard frontmatter (`name: officecli`), installed to `~/.hermes/skills/officecli/SKILL.md` |

### Verified commands (Chinese content test passed)

```bash
officecli create 晨报演示.pptx
officecli add 晨报演示.pptx / --type slide --prop title="A股晨报自动化" --prop background=1A1A2E
officecli add 晨报演示.pptx '/slide[1]' --type shape --prop text="三层决策架构" --prop x=1cm --prop y=4cm --prop size=20 --prop color=FFFFFF
officecli close 晨报演示.pptx                      # flush resident to disk
officecli view 晨报演示.pptx outline               # structure check
officecli view 晨报演示.pptx html > slide1.html     # grep Chinese text to verify content
officecli view 晨报演示.pptx screenshot -o slide1.png   # → vision_analyze for 中文/排版/配色
```

**Verification result:** 中文渲染清晰无乱码、排版规范、深色配色协调（vision_analyze 确认）。View modes: text / annotated / outline / stats / issues / html / svg / screenshot / pdf / forms. Live preview: `officecli watch <file>` → http://localhost:26315.

### User follow-up value
User explicitly asked to "install one and test" — the keep/delete decision flow: verified → kept. Test artifacts left at `~/officecli_test/` (晨报演示.pptx, slide1.html, slide1.png). Future: "用 OfficeCLI 把上周资金流做成 PPT" is a concrete supported scenario.
