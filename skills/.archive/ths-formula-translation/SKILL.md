---
name: ths-formula-translation
description: "将同花顺/通达信(TDX)公式语言严格翻译为Python pandas代码。包含核心函数实现、运算符优先级陷阱、数据源API、以及6大指标的参考翻译。"
version: 1.0.0
author: Hermes Agent
tags: [通达信, 同花顺, formula, quant, backtest, python, pandas]
platforms: [macos, linux]
---

# 通达信公式 → Python 翻译

## 触发条件

当需要将同花顺/通达信（.txt/.hxf/.nc/.tml 格式）指标公式翻译为 Python 时，启用本流程。

典型场景：
- 用户给出 `.txt` 后缀的同花顺公式代码
- 用户问"能不能在Python里复现这个指标"
- 需要将 6 大指标（暗盘资金、主力持仓、主力雷达、AI机构活跃度、GS信号）转 Python
- 构建 A 股量化回测模型

## 核心原则

**⚠️ 严格逐行翻译，不做简化。**

通达信公式语言看起来像 C 但语义不同。每行必须对照原版逻辑逐行翻译，不能"优化"或"合并"步骤，否则信号计算结果会有差异。

## 工作流程

### 第一步：理解公式结构

通达信公式由三部分组成：
1. **注释头**（`//#@...`）— 描述和配置信息，不需要翻译
2. **变量定义**（`X:=...;`）— `:=` 是赋值，`=` 是普通赋值（两者在Python中都相当于赋值）
3. **输出线**（`名称:..., colorgreen;`）— 可视化输出，Python中作为结果列保存

### 第二步：加载参考文件

本技能包含三个参考文件，请在翻译前加载：

- `references/tdx_core_functions.md` — 核心函数（SMA, EMA, CROSS, HHV, LLV 等）
- `references/ths_indicators.md` — 6大指标的完整 Python 翻译
- `references/tencent_data_api.md` — 腾讯历史K线API完整参数

### 第三步：严格翻译

1. 先实现 TDX_SMA, TDX_CROSS 等核心函数（见 reference）
2. 逐行翻译每个变量，变量名保留中文（方便对照原版）
3. 特别注意 AND/OR 优先级（通达信中 AND > OR）
4. CROSS 只判断"上穿"方向，不是"方向变化"
5. 使用 safe_div 处理除零
6. 输出列以原版指标名为准

### 第四步：验证

翻译完成后，检查：
- 是否每个变量都被逐行翻译（没有合并或删除步骤）
- 条件判断的括号是否正确（AND/OR 优先级）
- 滚动窗口（HHV/LLV/MA/SUM）的周期参数是否与原版一致
- 迭代次数（如GS信号的10次修正）是否与原版一致

## 已知陷坑

### 1. SMA 不是简单移动平均
`SMA(X, N, M)` 是递归公式 `(X*M + PREV*(N-M))/N`，不是 `pd.Series.rolling(N).mean()`。

### 2. AND > OR 优先级
通达信中 AND 的优先级高于 OR，而 Python 中 `&` 和 `|` 优先级不同。
务必为 OR 子句加括号。

### 3. CROSS 不跨周期
`CROSS(A, B)` 只看当前和上一周期，不看更早。

### 4. IF 的 NULL 处理
`IF(bb0==NULL, bb1, bb0)` → 在Python中用 `np.where(np.isnan(bb0), bb1, bb0)`

### 5. 除零行为
通达信除零返回 0 或忽略异常，Python 必须用 `np.where` 或 try/except 保护。

### 6. 中文编码
同花顺公式文件使用 GBK 编码。Python 读取：
```python
with open(path, 'r', encoding='gbk') as f:
    content = f.read()
```

### 7. 迭代算法严格按次数
GS信号的10次迭代修正必须严格10次，不能少。

## 数据源

参考 `references/tencent_data_api.md` 获取腾讯历史K线API的正确URL和参数格式。
