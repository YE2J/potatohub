# 因子导入操作记录（2026-07-02）

## 已验证的 daily 命令

```bash
cd ~/my_quant_system
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py daily --date 2026-06-24  # 5,206只, 335s, 0失败
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py daily --date 2026-06-25  # 5,206只, 345s, 0失败
~/.pyenv/versions/3.11.11/bin/python3 scripts/import_daily_factors.py daily --date 2026-06-26  # 5,206只, 343s, 0失败
```

## 已验证的 screen_v4.py 查询

```bash
python screen_v4.py --date 2026-06-25  # 44只4条件命中（因子表查表，毫秒级）
python screen_v4.py --date 2026-06-26  # 24只4条件命中
```

## 验证结果

| 日期 | 因子表4条件 | 手动逐只 | 差异 |
|------|-----------|---------|------|
| 2026-06-25 | 44只 | 43只 | 1只（MONEY对齐） |
| 2026-06-26 | 24只 | 0只（日期bug只扫147只） | 因子表正确 |

## 注意事项

- 首次跑 daily 可能看到 `[SKIP] already has records`——这是之前的测试占位数据，需 `DELETE FROM daily_factors` 后重跑
- daily 命令计算耗时约5.5分钟（串行），瓶颈在逐只 for 循环
- 加 `--parallel 4` 可加速（待实现）
- backfill 命令按月分批，自带断点续传
