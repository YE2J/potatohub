# venv_stock PYTHONPATH 隔离

## 问题

Hermes agent 运行在 Python 3.11 venv。当终端命令调用 `~/.hermes/venv_stock/bin/python`（Python 3.9）时，Hermes 的 py3.11 site-packages 仍在 `sys.path` 首位，导致：

1. Python 3.9 进程从 `.../python3.11/site-packages` 加载 numpy
2. `_multiarray_umath.cpython-311-darwin.so` 不兼容 cpython-39
3. `ModuleNotFoundError: No module named 'numpy._core._multiarray_umath'`

## 完整错误

```
ImportError: 
IMPORTANT: PLEASE READ THIS FOR ADVICE ON HOW TO SOLVE THIS ISSUE!

Importing the numpy C-extensions failed. This error can happen for
many reasons, often due to issues with your setup or how NumPy was
installed.
The following compiled module files exist, but seem incompatible
with either python 'cpython-39' or the platform 'darwin':

  * _multiarray_umath.cpython-311-darwin.so

The Python version is: Python 3.9 from "/Users/yellow/.hermes/venv_stock/bin/python"
The NumPy version is: "2.4.3"
```

## 检测

```bash
~/.hermes/venv_stock/bin/python -c "import sys; print(sys.path)" | head -3
# 输出第一行: '/Users/yellow/.hermes/hermes-agent'  (Hermes 项目根)
# 输出第二行: '/Users/yellow/.hermes/hermes-agent/venv/lib/python3.11/site-packages'  (py3.11 污染!)
```

## 修复

用 `PYTHONPATH` 环境变量覆盖，确保 Python 只从 `venv_stock` 加载包：

```bash
PYTHONPATH="/Users/yellow/.hermes/venv_stock/lib/python3.9/site-packages" \
  ~/.hermes/venv_stock/bin/python script.py
```

## 验证

```bash
PYTHONPATH="/Users/yellow/.hermes/venv_stock/lib/python3.9/site-packages" \
  ~/.hermes/venv_stock/bin/python -c "import numpy; print(numpy.__version__)"
# 输出: 2.0.2  (venv_stock 内的兼容版本)
```

## venv_stock 环境信息

| 属性 | 值 |
|------|-----|
| Python 版本 | 3.9.6 (macOS 系统自带) |
| venv 路径 | `~/.hermes/venv_stock` |
| site-packages | `~/.hermes/venv_stock/lib/python3.9/site-packages` |
| 关键包 | akshare 1.18.64, numpy 2.0.2, matplotlib 3.9.4, pandas 2.3.3 |

## 适用范围

任何从 Hermes terminal/Python 调用 `venv_stock/bin/python` 的 cron 任务、skill 脚本都会遇到此问题。统一修复方式：在所有调用前加 `PYTHONPATH` 前缀。
