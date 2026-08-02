# hermes_daily_report.py 章节计数修复

## 背景

2026-06-26 会话发现 `hermes_daily_report.py` 在 2 处硬编码了 `/8`（8 章节），但 `REQUIRED_SECTIONS` 实际已扩展为 9 章（新增 "Coze 日任务同步" 章节）。

## 修复

`len(REQUIRED_SECTIONS)` 替换硬编码数字：

| 位置 | 原代码 | 修复后 |
|:---|:---|:---|
| build_report() 章节完整性提示 | `{len(missing_chapters)}/8` | `{len(missing_chapters)}/{len(REQUIRED_SECTIONS)}` |
| alerts 告警行 | `{len(missing_chapters)}/8 章节` | `{len(missing_chapters)}/{len(REQUIRED_SECTIONS)} 章节` |

## 验证

```bash
grep -n '/8' ~/my_quant_system/scripts/hermes_daily_report.py
# 预期：零输出
```
