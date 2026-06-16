# 通达信公式核心函数 Python 实现参考

本文档记录通达信公式语言 → Python 的关键函数翻译。

## 1. SMA — 通达信特殊移动平均

通达信的 `SMA(X, N, M)` 不是标准简单移动平均，而是递归加权：

```
SMA(X, N, M) = (X × M + PREV × (N - M)) / N
```

其中 PREV 是前一日 SMA 值，首日使用 X 值本身。

```python
def TDX_SMA(arr, n, m):
    out = np.full_like(arr, np.nan)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = (arr[i] * m + out[i-1] * (n - m)) / n
    return out
```

**⚠️ 关键陷阱**：`SMA(X, N, 1)` 是 Wilder 平滑（如 RSI 计算），不是指数加权 EMA。
`SMA(X, 2, 1)` 的公式是 `(X*1 + PREV*(2-1))/2` = `(X + PREV)/2`。

## 2. EMA

```
EMA(X, N) = X × α + PREV × (1 - α)，α = 2/(N+1)
```

```python
def TDX_EMA(arr, n):
    alpha = 2.0 / (n + 1)
    out = np.full_like(arr, np.nan)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = arr[i] * alpha + out[i-1] * (1 - alpha)
    return out
```

## 3. CROSS — 金叉/死叉

`CROSS(A, B)` = A 上穿 B = 昨日 A <= B 且 今日 A > B

```python
def TDX_CROSS(a, b):
    a_prev = np.roll(a, 1)
    b_prev = np.roll(b, 1)
    a_prev[0] = b_prev[0] = np.nan
    return (np.less_equal(a_prev, b_prev) | np.isnan(a_prev)) & (a > b)
```

## 4. HHV / LLV — N日极值

```python
def TDX_HHV(arr, n):
    return pd.Series(arr).rolling(n).max().values

def TDX_LLV(arr, n):
    return pd.Series(arr).rolling(n).min().values
```

## 5. REF — 前N日值

```python
def TDX_REF(arr, n):
    return np.roll(arr, n)  # arr[0:n]会回绕到末尾
```

## 6. SUM / COUNT

```python
def TDX_SUM(arr, n):
    return pd.Series(arr).rolling(n).sum().values

def TDX_COUNT(cond, n):
    return pd.Series(cond.astype(float)).rolling(n).sum().values
```

## 7. IF 条件选择

```python
def TDX_IF(cond, a, b):
    return np.where(cond, a, b)
```

## 8. 运算符优先级陷阱

**通达信中 AND 优先级高于 OR**。

原始代码：
```
X_23:=X_19>=25 OR X_20>=23 OR X_22>=23 AND COUNT(...)>=2 AND COUNT(...)>=4;
```

在通达信中等价于：
```
X_19>=25 OR X_20>=23 OR (X_22>=23 AND count>=2 AND count>=4)
```

**正确翻译**：
```python
X_23 = (X_19 >= 25) | (X_20 >= 23) | ((X_22 >= 23) & (count1 >= 2) & (count2 >= 4))
```

## 9. 安全除法

```python
def safe_div(a, b, default=0.0):
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(np.abs(b) > 1e-12, a / b, default)
```
