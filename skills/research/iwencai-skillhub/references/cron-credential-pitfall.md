# Cron 环境下 Hermes `.env` 凭证不可读 — 完整排查记录

> 日期：2026-06-20～21 | 涉及脚本：`daily_update_iwencai.py`, `daily_update_v2.sh`

## 问题

cron job `fda7975b8524`（每日 00:00 行情同步）中问财 API 全线 401，但降级链（问财→腾讯）能自动接住数据，数据未丢失。

## 排查过程

### 1. 初步假设：`source .env` 未执行

修改 `daily_update_v2.sh` wrapper 添加 `source ~/.hermes/.env` 和 `export IWENCAI_API_KEY`。结果：仍 401。

### 2. 直接读文件测试

```python
env_path = os.path.expanduser("~/.hermes/.env")
with open(env_path) as f:
    for line in f:
        if "IWENCAI_API_KEY" in line:
            val = line.strip().split("=",1)[1].strip('"').strip("'")
            print(f"KEY_LEN: {len(val)}")  # → 3
```

**KEY_LEN = 3**。文件内容为 `IWENCAI_API_KEY=***`——真 Key 被掩码为 3 个星号。

### 3. 根因确认

Hermes 凭证存储机制在持久化 `.env` 时会将敏感值替换为 `***`。交互式会话中 Hermes 通过内部通道注入真 Key 到进程环境变量，但 cron 子进程没有这个通路。

`grep IWENCAI_API_KEY ~/.hermes/.env` 输出仅 20 字节（`IWENCAI_API_KEY=***` + 换行）。

## 修复

1. **用户操作**：将真实 Key 存入 Hermes 凭证存储之外的纯文本文件
   ```bash
   echo "sk-proj-xxx" > ~/.hermes/scripts/.iwencai_key
   chmod 600 ~/.hermes/scripts/.iwencai_key
   ```

2. **Wrapper 修改**：从独立文件加载 Key
   ```bash
   export IWENCAI_API_KEY=*** ~/.hermes/scripts/.iwencai_key 2>/dev/null)
   ```

3. **Python 脚本修改**：`read_api_key()` 优先检查环境变量
   ```python
   def read_api_key():
       key = os.environ.get("IWENCAI_API_KEY", "")
       if key and len(key) > 10:
           return key
       # 回退：读 .env 文件（仅交互式有效）
       ...
   ```

## 通用教训

**此陷阱适用于所有需要通过 cron 访问外部 API 的 Hermes 脚本**，不限于问财。任何在 `~/.hermes/.env` 中配置的密钥、token、凭证，在 cron 子进程中都是不可读的。

解决方案模板：
```bash
# 1. 存真 Key 到独立文件
echo "your-real-key" > ~/.hermes/scripts/.your_api_key

# 2. Wrapper 中加载
export YOUR_API_KEY=*** ~/.hermes/scripts/.your_api_key)
```
