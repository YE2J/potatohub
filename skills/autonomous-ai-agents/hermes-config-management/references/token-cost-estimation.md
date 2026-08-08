# SOUL 体积与 token 成本估算

SOUL.md 只在**会话启动时注入一次**（系统提示前缀），之后每轮被 prompt caching 复用，不重复计费。体积增加 = "每次会话一次性成本"。

## 估算方法（deepseek BPE 近似）

中文按 ~1 字/token，英文按 ~4 字符/token：

```bash
python3 -c "
import re
def est(t):
    zh = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', t))
    return int(zh * 1.0 + (len(t)-zh) / 4)
print(est(open('/Users/yellow/.hermes/SOUL.md').read()))"
```

## 实测参考（2026-08-05）

| 文件 | 字节 | 估算 token |
|:-----|:-----|:-----------|
| 主 SOUL（PM 流程版） | 1107 | ~355 |
| orchestrator SOUL 原版 | 2604 | ~785 |
| orchestrator SOUL 新版（对齐精简） | 3110 | ~945 |

## 成本换算

- ~160 token 增量 × deepseek 输入价 ≈ $0.00004/会话（单模型）
- MOA 模式 ×5 参考模型 ≈ 每次多 ~800 token
- 年化（每周 4 次）：单模型 ~$0.01，MOA ~$0.05

## 决策原则

决定是否压缩时**先算 token 账**：删掉硬知识（Worker 矩阵、能力边界、验证铁律）的省 token 收益（~$0.00004/会话）远小于踩坑后重查的成本（每次几千 token）。体积多 500B 不是压缩理由，功能损失才是。
