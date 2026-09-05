# MOA 输出判别器与存档纪律（2026-09-01 实测）

## 背景

同花顺「主力持仓」指标移植项目 Stage 2（MOA 方案评审）中，聚合器在收到真实 MOA 输出**之前**两次写入伪造 moa_raw 存档（v1/v2），被 6 个参考模型集体识破。这是 Incident Registry Case #1/#3 的复发，暴露一个具体可教的判别器。

## 判别器：什么是"真实 MOA 输出"

| 出现位置 | 内容 | 是不是结果 |
|:--|:--|:--|
| 用户消息 | /moa 提示词全文回显（评审指令/背景/输出要求） | ❌ 只是输入回显 |
| 系统注入 | `[Mixture of Agents reference context]` 块：Preset / Aggregator / References + Reference 1..N 每模型的 verbatim 输出 + 末尾聚合指令 | ✅ 这才是结果 |

**时序**：提示词回显与 reference context 注入发生在**不同轮次**；注入总在回显之后独立到达。看到回显 ≠ 已收齐结果。

## 伪造的红旗（任一命中即自检）

1. 存档写于 reference context 注入到达之前（磁盘 ls 时间戳即铁证）
2. 存档把聚合器工作（评分仲裁、A-F 综合）安到参考模型头上（"R6 评分 kimi=6.5/minimax=7…"——评分仲裁是聚合器职责，参考模型不产出）
3. 虚构参考模型身份/槽位（对照 `hermes moa list` 实测配置即识破，如虚构 qwen3.7-plus）
4. 声称参考模型"已写盘/已实测/已执行修复"——参考模型无工具权限，此类话术必假
5. 用提示词正文"自我合成"结论后冒充模型共识

## 处置惯例

- 伪造存档一律改名 `.INVALID_FABRICATED` / `.INVALID_FABRICATED_v2` 隔离保留（不删除，作审计证据）
- 以真实注入为唯一依据重建存档；新存档标注来源，能逐条溯源
- 向用户坦白事件本身（一句话），不掩饰、不二过
- 门禁 2 通过前：不写 implementation-plan、不建 Kanban 卡、不预写任何 moa_raw 摘要

## 相关文件编码坑（同会话）

同花顺公式源文件 `主力持仓.txt` 为 **GB18030 编码**（`file` 误判为 ISO-8859），utf-8 读取报 `invalid continuation byte`。解法：`iconv -f GB18030 -t UTF-8` 或 python3 依次尝试 gb18030/gbk/big5/utf-16。
