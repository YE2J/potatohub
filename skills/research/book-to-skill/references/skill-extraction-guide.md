# 书本 → 领域 Skill 提炼规范（步骤 6b）

> 用途：用户确认后，把书本的**可操作知识**提炼为可复用 SKILL.md。
> 核心原则：**skill 是操作流程，不是读书笔记**。全书摘要 → 笔记；
> 可复用的方法/流程/规则 → skill。两者是不同产物，勿混写。

## 判断哪些书适合提炼 skill

| 书本类型 | 适合？ | 说明 |
|---|---|---|
| 方法论/操作手册（如何做X） | ✅ 非常适合 | 流程、步骤、规则可直接转 skill |
| 知识体系（概念/原理） | ⚠️ 视内容 | 若有决策规则/判断流程 → 可提炼；纯概念 → 只做笔记 |
| 数学/公式推导书 | ⚠️ 部分 | 公式速查表可入 skill，推导过程留笔记 |
| 小说/散文 | ❌ | 不做 skill |

## 提炼流程

1. **读笔记不读全书**：先读 `<书名>.note.md`（已含关键概念+流程），必要时回 md 查具体章节
2. **识别可操作知识**：问自己「用户下次遇到同类任务，能直接按这个 skill 执行吗？」
   - 有流程 → 列步骤
   - 有公式 → 列表格（公式/适用条件/单位）
   - 有规则 → 列 if-then 决策
   - 有代码 → 保留可运行片段
3. **写 SKILL.md**（frontmatter 必须含 name/description/version）：
   ```yaml
   ---
   name: <领域>-<核心动作>
   description: "Use when <触发场景>。<一句话行为>。"
   version: 1.0.0
   ---
   ```
   - description 约束：**≤60 字符**（超长会被系统截断破坏路由信号）
   - 触发条件放最前，行为一句话
4. **引用来源**：SKILL.md 末尾注明「提炼自《书名》第 X 章，2026-08 学习」
5. **自查**：`skill_view(name="<新skill名>")` 确认加载正常

## 命名规范

- `<领域>-<核心动作>`：如 `quant-factor-ranking`、`calculus-limit-solving`、`python-ebook-to-rag`
- 领域用英文小写+连字符；避免泛化名（如 `trading` 太宽，`momentum-reversal-scan` 更精确）

## 验证 checklist

- [ ] frontmatter 完整（name/description/version）
- [ ] description ≤60 字符且触发词在开头
- [ ] 内容是可执行步骤，不是散文
- [ ] 有验证/收尾检查项（如「转换产物完整 wc -l」）
- [ ] 来源已注明
- [ ] skill_view 加载正常

## 边界（勿越界）

- 一本书可提炼出 **1-2 个** skill，不要为每章都造一个
- 提炼的 skill 要**跨书可用**（不是这本书特有的），否则只是笔记的搬运
- 与已有 skill 重叠时：**先查 skills_list**，已有则 patch 增强，不新建重复 skill
