#!/usr/bin/env python3
"""精准同步 default profile skills → 各 worker profile（方案 B：量化+评审规范+hermes配置类）。

背景：worker profile 的 skills 目录物理独立，default 新建/修改 skill 不自动传播。
本脚本按需复制缺失的量化类(56) + 评审规范类 + worker-xiaomi 缺的 hermes 配置类。

用法：
    python3 sync_worker_skills.py            # 默认同步到 4 个 worker profile
    python3 sync_worker_skills.py --dry-run  # 只打印将同步的清单，不复制

备份建议（同步前执行）：
    for p in worker-glm worker-kimi worker-xiaomi orchestrator; do
      find ~/.hermes/profiles/$p/skills -name "SKILL.md" \
        | sed "s|$HOME/.hermes/profiles/$p/skills/||" | sort \
        > ~/.hermes/backups/skill_sync_$(date +%Y%m%d)/${p}_before.txt
    done
"""
import os, shutil, glob, sys

HOME = os.path.expanduser('~')
SRC = os.path.join(HOME, '.hermes', 'skills')
DRY_RUN = '--dry-run' in sys.argv

def get_skills(base):
    skills = set()
    for sk in glob.glob(os.path.join(base, '**', 'SKILL.md'), recursive=True):
        rel = os.path.relpath(os.path.dirname(sk), base)
        skills.add(rel)
    return skills

default = get_skills(SRC)

# 量化类关键词（覆盖三层架构/数据/回测/估值/资金流/选股/案例方法论）
QUANT_KEYS = ['a-share', 'stock', 'ths', 'tuige', 'macd', 'valuation', 'quant',
              'factor', 'moneyflow', 'zhishu', 'backtest', 'csrc', 'kline']
def is_quant(s):
    return any(k in s.lower() for k in QUANT_KEYS)

# 评审规范类（显式，worker 评审量化系统必须有）
REVIEW_SPECIAL = {'a-share/code-review-checklist', 'a-share/review-process-enhancement'}

# worker-xiaomi 额外要补的 hermes 配置类（其余 worker 视需要加入）
XIAOMI_EXTRA = {
    'autonomous-ai-agents/gateway-troubleshooting',
    'autonomous-ai-agents/hermes-config-management',
    'autonomous-ai-agents/hermes-vision-config',
    'autonomous-ai-agents/hermes-vision-setup',
    'autonomous-ai-agents/moa-multi-model-review',
    'autonomous-ai-agents/multi-model-orchestration',
    'software-development/agents-md-authoring',
}

profiles = {
    'worker-glm':     os.path.join(HOME, '.hermes/profiles/worker-glm/skills'),
    'worker-kimi':    os.path.join(HOME, '.hermes/profiles/worker-kimi/skills'),
    'worker-xiaomi':  os.path.join(HOME, '.hermes/profiles/worker-xiaomi/skills'),
    'orchestrator':   os.path.join(HOME, '.hermes/profiles/orchestrator/skills'),
}

total = 0
for name, dst_base in profiles.items():
    dst_skills = get_skills(dst_base)
    sync_set = set(s for s in default if is_quant(s)) | REVIEW_SPECIAL
    if name == 'worker-xiaomi':
        sync_set |= XIAOMI_EXTRA
    to_copy = sorted(s for s in sync_set if s not in dst_skills and s in default)
    if DRY_RUN:
        print(f'{name}: 待同步 {len(to_copy)} 个 -> {", ".join(to_copy[:6])}')
        total += len(to_copy)
        continue
    copied = 0
    for rel in to_copy:
        src_dir = os.path.join(SRC, rel)
        dst_dir = os.path.join(dst_base, rel)
        os.makedirs(dst_dir, exist_ok=True)
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(dst_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        copied += 1
    total += copied
    print(f'{name}: 同步 {copied} 个')

print(f'\n总计 {"待同步" if DRY_RUN else "复制"} {total} 个 skill 目录')
