# MOA preset 生命周期：配置、禁用、清理

## 为什么 worker profile 里会冒出「用不了」的 MOA preset

profile 多是克隆/默认模板生成的，`moa` 段往往带一份 `openai-codex:gpt-5.5` + `openrouter:anthropic/claude-opus-4.8` 的 preset。这两个 provider 在本机通常**没有凭据**（OpenRouter key 未配、Codex OAuth 未登录），所以是一份「看起来配好了、真跑必失败」的死配置。

## 关键事实：它不是你的配置，删不掉

| 事实 | 证据 |
|:-----|:-----|
| CLI 拒绝删除最后一条 preset | `hermes moa delete default` → `Cannot delete the only MoA preset` |
| 内置默认 preset 存在于代码里 | `hermes_cli/moa_config.py`：`DEFAULT_MOA_REFERENCE_MODELS` / `DEFAULT_MOA_AGGREGATOR` |
| 清空配置会被「复活」 | 同文件 `_normalize_preset`：`reference_models` 为空 → 用内置默认填充；`aggregator` 缺失 → 用内置默认填充。所以删掉 `moa:` 段后行为**与删除前完全一致** |
| 显示层也会填充 | `hermes moa list` 会把内置默认参考席打印出来，看起来像还配着 |

结论：**死 preset 只能禁用，不能删除**。

## 禁用配方（profile 级 config）

```yaml
moa:
  default_preset: ''      # 不留默认选中项
  active_preset: ''
  presets:
    default:
      enabled: false      # ← 真正生效的开关
      reference_models: [] # 清掉指向无凭据 provider 的引用
      aggregator:
        provider: openrouter
        model: anthropic/claude-opus-4.8
```

写入方式：profile 级 config 用 `patch`（文本级替换，带上下文锚点）或终端 python 定点替换；**不要 `yaml.dump` 回写**整份文件。改前备份到 `~/.hermes/backups/<date>_<用途>/`。

## 禁用后运行时是什么行为

| 检查点 | 依据 |
|:-------|:-----|
| 按名字查找会跳过禁用 preset | `hermes_cli/moa_config.py`：`exact_moa_preset_name` 对 `enabled: false` 的 preset 返回 None |
| 参考层为空 | `agent/moa_loop.py`：preset `enabled` 为假时参考列表取空 |
| 不会打到没凭据的 provider | 冒烟 `/moa` 未出现 openrouter 调用/报错 |

⚠️ **未验证项写法**：如果只做了配置态 + 代码路径核对、没有真人交互式 `/moa` 实测拒绝文案，汇报时必须写成「配置 + 代码路径已核，交互路径未实测」——不要写成「已确认 /moa 会拒绝」。

## 验证命令（按顺序，缺一步不算完成）

```bash
# 1) 配置态（唯一可信来源，忽略 moa list 的显示填充）
hermes -p worker-xiaomi config get moa

# 2) 该 profile 仍可正常工作（一次性冒烟，最便宜的回归测试）
hermes -p worker-xiaomi -z "只回复：可用"      # 看到字面回复 + exit=0

# 3) 默认 profile 的 MOA 未被误伤（改 worker 时必查）
hermes moa list                                # 应仍是 6 参考席 + 聚合器
```

## 什么时候该「启用」而不是「禁用」

在某 profile 里真的要用 MOA 时，不要保留内置默认（引用无凭据 provider），直接写一份指向**已有凭据**的 preset：

- 现成可用的异质模型源（按账号实测）：z.ai 的 glm 系列、alibaba-coding-plan 网关（含 qwen/glm/kimi/minimax 镜像）、MiniMax 全球端点、xiaomi mimo、deepseek、已登录的 Nous Portal inference（模型数最多、含多家厂商）。
- MOA 参考席要**避免与聚合器同源**：参考席里放一个与聚合器同款模型，等于这一席在自问自答（浪费一次调用、异质度不增）。发现同源就换掉该席，而不是扩大席位数。
- 换席后必须跑一次最小 `/moa` 核对每席都返回、无 401/超时，再把结果告诉用户。

## 备份与回滚

```bash
# 备份
mkdir -p ~/.hermes/backups/$(date +%Y%m%d_%H%M%S)_<用途>
cp ~/.hermes/profiles/<p>/config.yaml ~/.hermes/backups/<刚建的目录>/<p>__config.yaml
# 回滚
cp ~/.hermes/backups/<目录>/<p>__config.yaml ~/.hermes/profiles/<p>/config.yaml
```
