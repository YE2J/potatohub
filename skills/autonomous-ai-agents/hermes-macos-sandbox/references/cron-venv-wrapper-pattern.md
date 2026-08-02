# Cron-venv + Python Wrapper Pattern

当 cron 脚本需要特定的 Python 包（如 tushare）且需要兼容 cron TCC 沙箱时，使用此模式。

## 场景

- `no_agent=true` cron 脚本需要调用 Python + 第三方包
- 必须兼容 **launchd**（scheduled）和 **manual trigger**（`action='run'`）两种 cron 上下文
- 本地模块（如 `db_utils`、`factor_engine`）需要在 PYTHONPATH 上

## 架构

```
~/.hermes/
├── python-standalone/cpython-3.11.15-.../    ← 静态编译 Python（无 Homebrew 依赖）
├── venv_cron/                                ← 基于 standalone Python 的 venv
│   └── bin/python3                           ← symlink → python-standalone/.../python3
├── scripts/
│   ├── cron_python_wrapper.sh                ← 设置 PYTHONPATH + 调用 venv_cron Python
│   ├── daily_sector_moneyflow.sh             ← no_agent=true 脚本
│   └── ...
```

## 步骤

### 1. 创建 cron-venv

```bash
# 创建基于 standalone Python 的 venv（避免 pip externally-managed 报错）
uv venv ~/.hermes/cron-venv \
  --python ~/.hermes/python-standalone/cpython-3.11.15-macos-aarch64-none/bin/python3

# 安装所需包
uv pip install tushare -python ~/.hermes/cron-venv/bin/python3
```

或直接使用已有的 standalone Python（检查是否已有 venv 存在）：

```bash
# 检查已有 cron-venv
ls ~/.hermes/venv_cron/bin/python3
# 验证包
~/.hermes/venv_cron/bin/python3 -c "import tushare; print(tushare.__version__)"
```

### 2. 创建 Python Wrapper 脚本

```bash
#!/bin/bash
# cron_python_wrapper.sh — 供 cron 脚本使用的沙箱 Python + 正确 PYTHONPATH
set -u
CRON_PYTHON="$HOME/.hermes/venv_cron/bin/python3"
PROJECT_DIR="$HOME/my_quant_system"
export PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/scripts:$PYTHONPATH"
exec "$CRON_PYTHON" "$@"
```

关键点：
- `set -u` 避免未定义变量导致静默失败
- `exec` 替换当前进程，不产生子进程残留
- PYTHONPATH 包含项目根目录 + scripts 目录（本地模块所在）

### 3. 批量替换脚本中的 Python 路径

```bash
WRAPPER="$HOME/.hermes/scripts/cron_python_wrapper.sh"
OLD_PATH="$HOME/.pyenv/versions/3.11.11/bin/python3"

cd "$HOME/.hermes/scripts"
for f in *.sh; do
  sed -i '' "s|$OLD_PATH|$WRAPPER|g" "$f"
done
```

### 4. 修复 cron_log_helper.sh 中的裸 python3 调用

```bash
sed -i '' 's|$(python3 -c "import time;|$(~/.hermes/scripts/cron_python_wrapper.sh -c "import time;|g' cron_log_helper.sh
```

## 验证

```bash
# 1. 基本可用性
~/.hermes/scripts/cron_python_wrapper.sh -c "import tushare; print(tushare.__version__)"

# 2. 本地模块导入
cd ~/my_quant_system
~/.hermes/scripts/cron_python_wrapper.sh -c "from db_utils import get_conn; print('ok')"

# 3. DB 访问（含 symlink）
~/.hermes/scripts/cron_python_wrapper.sh -c "
import sqlite3
conn = sqlite3.connect('$HOME/my_quant_system/stock_data.db')
print('tables:', len(conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()))
conn.close()
"
```

## 已知陷阱

| 陷阱 | 现象 | 原因 | 修复 |
|:-----|:------|:------|:------|
| **xcode-select 触发** | cron 日志显示 `xcode-select: error: No developer tools` | bare `python3` 调用了 macOS 的 `/usr/bin/python3` 占位符，触发 xcode-select —install | 替换所有 bare `python3` 为 wrapper |
| **可执行位缺失** | `Permission denied` 运行 wrapper | `chmod +x` 忘记执行 | `chmod +x cron_python_wrapper.sh` |
| **PYTHONPATH 缺失** | `ModuleNotFoundError: No module named 'db_utils'` | 脚本运行时工作目录不是项目根，PYTHONPATH 未包含 scripts/ | wrapper 中显式设置 `PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/scripts"` |
| **gettext 阻断** | `dyld: Library not loaded: /opt/homebrew/opt/gettext/lib/libintl.8.dylib` | pyenv Python 依赖 Homebrew 安装的 gettext，在 TCC 沙箱内被阻断 | 改用 standalone Python（python-build-standalone）或 venv_cron |
