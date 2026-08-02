# Coze CLI `agent file download` 行为参考

## 关键发现：`--format json` 的退出码问题

`coze agent file download --project-id <ID> --project-file-path <PATH> --format json`

**无论文件是否存在，始终返回 exit code 0。**

### 文件存在时
- 下载 197+ 字节的有效 JSON（信号文件）
- JSON 含 `status`, `trade_date`, `row_count` 等字段
- `local_file_path` 指向下载位置

### 文件不存在时
- 下载 37 字节的错误 JSON
- 内容: `{"code":1000002,"msg":"系统错误"}`
- 仍然返回 exit=0，文件仍然被创建
- `ok` 字段在 JSON 中不存在（不是 `"ok": false`，是压根没有）

### 文件为空时（Coze 空文件上传）
- 下载 49 字节的 gzip 头（仅 `1f 8b 08 ... 00 00 00 00 00 00 00 00 00`）
- gunzip 解压后 0 行数据
- 文件大小 < 100 字节

## 安全性建议

```python
# 检查文件是否有效（不是错误响应）
def is_valid_coze_file(filepath):
    if os.path.getsize(filepath) < 100:
        return False
    try:
        with open(filepath) as f:
            data = json.load(f)
        # 错误响应包含 code 字段
        if 'code' in data:
            return False
        return True
    except (json.JSONDecodeError, IOError):
        return False
```

## 相关错误码

| code | msg | 含义 |
|------|-----|------|
| 1000002 | 系统错误 | 文件路径不存在或项目空间异常 |

## token 过期时间

在 `~/.coze/cli/config.json` 中:
- `accessToken`: 当前访问令牌
- `refreshToken`: 刷新令牌
- `tokenExpiresAt`: 毫秒级 Unix 时间戳，标记令牌过期时刻

注意: cron 环境下 token 刷新可能失败（网络/environment 问题），导致 coze CLI 所有操作返回非零退出码。
