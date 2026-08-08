# 本机 Hermes 配置关键路径速查（2026-08 实测）

## 文件布局

| 路径 | 内容 |
|:-----|:-----|
| `~/.hermes/SOUL.md` | persona 灵魂文件（agent 人格/语气/流程），直接写入系统提示 |
| `~/.hermes/config.yaml` | 主配置，**写保护**，只能 `hermes config set/get/unset` |
| `~/.hermes/memories/MEMORY.md` | agent 持久记忆 |
| `~/.hermes/config.yaml.bak.*` | 历史备份（自动生成，勿依赖） |

## 关键 config 键

| 键 | 位置 | 示例值 | 说明 |
|:---|:-----|:-------|:-----|
| `display.personality` | display 段 | `pm` / `technical` | **激活的人格开关**，取值来自池 |
| `agent.personalities.<name>` | agent 段 | 人格描述字符串 | **人格池**（catgirl/concise/creative/helpful/hype/kawaii/noir/philosopher/pirate/shakespeare/surfer/teacher/technical/uwu/pm） |
| `agent.model` | agent 段 | `deepseek-ai/deepseek-v4-flash` | 主模型 |
| `moa.presets.default.reference_models` | moa 段 | 5 个 provider:model | MOA 参考模型 |
| `moa.presets.default.aggregator` | moa 段 | deepseek-v4-flash | MOA 聚合器 |

## 陷阱记录（2026-08-03 会话）

1. **config.yaml 写保护**：`patch`/`write_file` 直接拒绝
   ```
   Refusing to write to Hermes config file: /Users/yellow/.hermes/config.yaml
   Agent cannot modify security-sensitive configuration.
   ```
2. **嵌套键漏前缀**：`hermes config set 'personalities.pm'` 创建的是**顶层** `personalities:`（line ~708），
   而真正的人格池在 `agent.personalities`（line ~30）。导致两个 personalities 段并存。
   正确：`hermes config set 'agent.personalities.pm' ...`；清理：`hermes config unset 'personalities.pm'`。
3. **`hermes config set` 静默成功**：对未识别键仍报 `✓ Set`，但附警告
   `'xxx' is not a recognized config key — it was saved anyway`。见到警告立即查路径。
4. **SOUL.md 编码**：历史遗留 UTF-16 乱码在文件头部，`read_file` 报 Binary；`iconv -f UTF-16 -t UTF-8` 可读，重写即清除。
5. **生效时机**：SOUL.md 与新人格**下一个新会话**生效，当前会话沿用旧上下文。

## 验证命令

```bash
hermes config get display.personality
hermes config get 'agent.personalities.pm'
python3 -c "import yaml; yaml.safe_load(open('/Users/yellow/.hermes/config.yaml')); print('OK')"
grep -n '^agent:\|^personalities:\|^  personalities:' ~/.hermes/config.yaml
```
