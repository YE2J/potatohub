#!/usr/bin/env python3
"""
边界测试套件：router.py 安全审查 & 路由逻辑验证
用法：python3 boundary_test.py
前提：router.py 在 ~/.hermes/scripts/ 下
"""
import sys, os, subprocess, json, re

SCRIPT = os.path.expanduser("~/.hermes/scripts/router.py")

def run_router(task_text, extra_args="", dry=True):
    cmd = [sys.executable, SCRIPT, task_text, "--dry-run", "--json-only"]
    if extra_args:
        cmd = [sys.executable, SCRIPT, task_text, "--dry-run", "--json-only"] + extra_args.split()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr.strip()[-500:], "exit_code": result.returncode}
        return json.loads(result.stdout.strip())
    except Exception as e:
        return {"error": str(e), "exit_code": -1}

def run_raw(args_list):
    cmd = [sys.executable, SCRIPT] + args_list
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except:
        return None

def test_header(text):
    print(f"\n{'='*70}\n  {text}\n{'='*70}")

def assert_result(condition, msg, severity="🔴"):
    icons = {"🔴": "🔴 致命", "🟡": "🟡 警告", "🔵": "🔵 建议"}
    icon = icons.get(severity, severity)
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"  {icon} {msg}: {status}")

def run_all_tests():
    print("=" * 70)
    print("  router.py 边界测试 — Kimi 测试工程师审查")
    print("=" * 70)

    # C1: 路由误排序
    test_header("🔴 致命: C1 路由误排序")
    r = run_router("审查架构设计方案")
    pk = r.get("profile_key", "N/A")
    assert_result(pk == "analysis", f"C1: '审查架构设计方案' → {pk} (应为 analysis)")

    # C2: 输入长度限制
    test_header("🔴 致命: C2 输入长度限制")
    with open(SCRIPT) as f:
        content = f.read()
    assert_result("MAX_TASK_LENGTH" in content, "C2: MAX_TASK_LENGTH 常量存在")

    # W1: 空输入拒绝
    test_header("🟡 警告: W1 空输入")
    for label, task in [("空字符串", ""), ("纯空格", "   ")]:
        r = run_raw(["--dry-run", "--json-only", task])
        assert_result(r and r.returncode != 0, f"W1: {label}被拒绝", "🟡")

    # W1-3: 超长输入
    r = run_raw(["--dry-run", "--json-only", "A" * 10001])
    assert_result(r and r.returncode != 0, "W1-3: 10001字符被拒绝", "🟡")

    # W4: 硬编码路径
    assert_result("os.path.expanduser" in content, "W4: 路径通过 os.path.expanduser 探测", "🟡")

    # W5: 展示注入
    has_trunc = "task[:120]" in content
    has_ansi = "ansi_escape" in content
    assert_result(has_trunc and has_ansi, "W5: 截断+ANSI清理", "🟡")

    # B2: 安全
    test_header("🔵 建议: B2 安全")
    assert_result("shell=True" not in content, "B2-1: 无 shell=True", "🔵")
    assert_result("cmd +" in content or "cmd = [" in content, "B2-2: 列表形式命令", "🔵")

    # B3, B4: 规则顺序
    test_header("🔵 建议: B3/B4 规则顺序")
    ti = content.index("(code\\s*review") if "(code\\s*review" in content else -1
    ai = content.index("(分析|研究|调研") if "(分析|研究|调研" in content else -1
    assert_result(ti < ai, "B3: testing 规则在 analysis 之前", "🔵")

    ci = content.index('"complex"') if '"complex"' in content else -1
    mi = content.index('"medium"') if '"medium"' in content else -1
    assert_result(ci < mi, "B4: complex 在 medium 之前", "🔵")

    # 核心路由逻辑
    test_header("🔴 核心路由逻辑")
    tasks = {
        "分析A股市场趋势": ("analysis", "orchestrator"),
        "编写单元测试用例": ("testing", "worker-kimi"),
        "写一个排序函数": ("coding", "worker-glm"),
        "修复代码中的SQL注入bug": ("coding", "worker-glm"),
        "审查代码安全问题": ("testing", "worker-kimi"),
        "复杂的多模块架构设计任务": ("analysis", "orchestrator"),
        "运行pytest测试套件": ("testing", "worker-kimi"),
        "查找并修复代码bug": ("coding", "worker-glm"),
        "设计一个微服务系统架构": ("analysis", "orchestrator"),
        "从零搭建完整项目框架": ("analysis", "orchestrator"),
        "优化多个文件的性能": ("coding", "worker-glm"),  # 已知缺口
    }
    for task, (exp_key, exp_prof) in tasks.items():
        r = run_router(task)
        pk = r.get("profile_key", "N/A")
        pr = r.get("selected_profile", "N/A")
        ok = pk == exp_key and pr == exp_prof
        mark = "✓" if ok else "✗"
        print(f"     {task:30s} → {pk}/{pr} {mark}" + (f" (期望:{exp_key}/{exp_prof})" if not ok else ""))

    print(f"\n  🔑 '审查架构设计方案' → {run_router('审查架构设计方案').get('profile_key', 'N/A')}")
    print("     C1 状态: " + ("✅ 已修复" if run_router("审查架构设计方案").get("profile_key") == "analysis" else "❌ 仍存在"))

if __name__ == "__main__":
    run_all_tests()
