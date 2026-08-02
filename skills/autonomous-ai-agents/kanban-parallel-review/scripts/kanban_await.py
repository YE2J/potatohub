#!/usr/bin/env python3
"""kanban_await.py — 等待 Kanban 卡完成并输出结果（自动推送）

用法:
  python scripts/kanban_await.py <card_id1> [card_id2 ...]

功能:
  1. 每15秒轮询所有指定卡的状态（使用 --json 输出，稳定可靠）
  2. 所有卡 done 后读取 summary 并打印
  3. 超时（默认10分钟，可通过 --timeout 调整）仍未完成则报错退出

依赖: hermes CLI 在 PATH 中

输出格式:
  [DONE] t_xxx: 标题
  [SUMMARY] 评审完成，发现3个P0...
  ---
  [FAILED] t_yyy: 标题 (状态: failed)
"""
import subprocess
import sys
import time
import json
import argparse

def kanban_show_json(card_id: str) -> dict:
    """调用 hermes kanban show --json 返回结构化数据"""
    r = subprocess.run(
        ['hermes', 'kanban', 'show', card_id, '--json'],
        capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        return {'status': 'error', 'error': r.stderr.strip()}
    try:
        data = json.loads(r.stdout)
        task = data.get('task', {})
        return {
            'status': task.get('status', 'unknown'),
            'title': task.get('title', card_id),
            'summary': data.get('latest_summary', ''),
        }
    except json.JSONDecodeError:
        return {'status': 'error', 'error': f'JSON解析失败: {r.stdout[:200]}'}


def wait_for_cards(card_ids: list[str], timeout: int = 600, interval: int = 15,
                   extra_ticks: int = 0) -> bool:
    """等待所有卡完成，打印结果到stdout

    Args:
        card_ids: Kanban 卡ID列表
        timeout: 总超时秒数
        interval: 轮询间隔秒数
        extra_ticks: 超时后的额外轮询次数（应对"临门一脚"场景）

    Returns:
        True=全部完成, False=超时
    """
    start = time.time()
    pending = set(card_ids)
    results = {}

    print(f"⏳ 等待 {len(card_ids)} 张卡完成 (超时 {timeout}s, 间隔 {interval}s)...")
    sys.stdout.flush()

    while pending and (time.time() - start) < timeout:
        for cid in list(pending):
            info = kanban_show_json(cid)
            status = info.get('status', 'unknown')
            title = info.get('title', cid)
            summary = info.get('summary', '')

            if status == 'done':
                results[cid] = {'status': 'done', 'title': title, 'summary': summary}
                pending.remove(cid)
                print(f'✅ [DONE] {cid}: {title}')
                if summary:
                    print(f'   ↳ {summary}')
                print('---')
                sys.stdout.flush()

            elif status in ('failed', 'crashed'):
                results[cid] = {'status': status, 'title': title, 'summary': summary or '无摘要'}
                pending.remove(cid)
                print(f'❌ [FAILED] {cid}: {title} (状态: {status})')
                if summary:
                    print(f'   ↳ {summary}')
                print('---')
                sys.stdout.flush()

            elif status == 'error':
                err = info.get('error', '未知错误')
                print(f'⚠️  [WARN] {cid}: 读取失败 ({err})，下次重试')
                sys.stdout.flush()

        if pending:
            elapsed = int(time.time() - start)
            remaining = timeout - elapsed
            print(f"⏳ 等待中... 已完成 {len(results)}/{len(card_ids)}, "
                  f"剩余: {', '.join(pending)}, "
                  f"剩余时间: {remaining}s")
            sys.stdout.flush()
            time.sleep(interval)

    if pending:
        elapsed = int(time.time() - start)
        print(f'⏰ 超时: 以下卡未完成 (已等 {elapsed}s):')
        for cid in pending:
            info = kanban_show_json(cid)
            print(f'  {cid}: 状态={info.get("status", "unknown")}')

        # 超时后额外轮询：卡可能在最后一次轮询瞬间完成（"临门一脚"场景）
        if extra_ticks > 0 and pending:
            grace_interval = max(5, interval // 3)
            print(f'🔄 开始超时后额外轮询 ({extra_ticks}次, 间隔{grace_interval}s)...')
            sys.stdout.flush()
            for tick in range(extra_ticks):
                time.sleep(grace_interval)
                for cid in list(pending):
                    info = kanban_show_json(cid)
                    status = info.get('status', 'unknown')
                    title = info.get('title', cid)
                    summary = info.get('summary', '')
                    if status == 'done':
                        results[cid] = {'status': 'done', 'title': title, 'summary': summary}
                        pending.remove(cid)
                        print(f'✅ [DONE] {cid}: {title}（超时后第{tick+1}次轮询补救）')
                        if summary:
                            print(f'   ↳ {summary}')
                        sys.stdout.flush()
                if not pending:
                    print(f'✅ 全部完成! (耗时 {int(time.time()-start)}s, 含{tick+1}次超时后轮询)')
                    sys.stdout.flush()
                    return True

        if pending:
            sys.stdout.flush()
            return False

    print(f'✅ 全部完成! (耗时 {int(time.time()-start)}s)')
    sys.stdout.flush()
    return True


def main():
    parser = argparse.ArgumentParser(
        description='等待 Kanban 卡完成并自动输出结果'
    )
    parser.add_argument('card_ids', nargs='+', help='Kanban 卡ID (支持多个)')
    parser.add_argument('--timeout', type=int, default=600,
                       help='总超时秒数 (默认: 600)')
    parser.add_argument('--interval', type=int, default=15,
                       help='轮询间隔秒数 (默认: 15)')
    parser.add_argument('--extra-ticks', type=int, default=3,
                       help='超时后额外轮询次数，每次间隔 interval/3 (默认: 3, 防"临门一脚"错过)')

    args = parser.parse_args()
    success = wait_for_cards(args.card_ids, args.timeout, args.interval, args.extra_ticks)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
