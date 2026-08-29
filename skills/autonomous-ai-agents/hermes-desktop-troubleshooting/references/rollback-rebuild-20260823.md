# 桌面端回滚+重建实战（2026-08-23 BOTS 空白修复）

诊断结论（BOTS 空白的完整证据链见 `bots-roster-pipeline.md`）确认后，本次实际执行的修复路径：

## 1. 回滚约束：shallow clone
`~/.hermes/hermes-agent` 是 shallow clone（`.git/shallow` 存在、`git rev-parse HEAD^` 失败=HEAD 无父提交）。
回滚前验证目标可达：
```bash
git merge-base --is-ancestor <target> HEAD && echo YES || echo NO
```
- `NO` → 禁止整体 `git checkout <target>`（会 detached HEAD、仓库可能损坏）。
  本机 8-22 提交 503d863fcd 大规模重写历史（10052 文件）后，旧 commit（如 8-18 的 e02d1e41fc）**不在 main 祖先链上**。
- 安全替代：单文件回退
  ```bash
  git checkout <old-commit> -- <relative/path/file>
  ```
  只改工作区该文件，HEAD/分支不动。

## 2. 数据零丢失证明
git 仓库边界 = 仅 `~/.hermes/hermes-agent/`（纯代码）。
所有数据在仓库外：`~/.hermes/` 下的 state.db（会话）、cron.db、memories/、skills/、profiles/、tasks/、kanban.db、hermes.db。
回滚/checkout 只动代码目录，数据物理隔离、无 symlink。

## 3. 重建管线：build ≠ pack
桌面应用运行时从 **release app.asar** 加载渲染资源（renderer console 路径含 `app.asar/dist/assets/...`），
**不是** `apps/desktop/dist/`。`npm run build`（vite → dist/，约 10s）后必须再 `npm run pack`（electron-builder → 更新 release/*.asar）。
```bash
cd ~/.hermes/hermes-agent/apps/desktop
npm install --no-audit --no-fund        # node_modules 常不完整（vite 缺失）
npm run build
npm run pack
```
验证修复进包（extractFile 路径不能带前导 `/`）：
```bash
node -e "const asar=require('@electron/asar');const p='release/mac-arm64/Hermes.app/Contents/Resources/app.asar';const f=asar.listPackage(p).filter(x=>x.includes('/dist/assets/index-')&&x.endsWith('.js'));const s=asar.extractFile(p,f[0].replace(/^\//,'')).toString();console.log('activeBotRoute:',(s.match(/activeBotRoute/g)||[]).length,'| NewAgent:',s.includes('New Agent'))"
```
改完必须重启应用（Cmd+Q 退出重开）——运行中 renderer 加载旧 asar，`ps aux` 确认新 renderer 启动时间。

## 4. 备份清单（执行前）
- `cp config.yaml config.yaml.bak-before-rollback-<date>`
- `git rev-parse HEAD > ~/.hermes/rollback-previous-head.txt`
- `cp apps/desktop/src/plugins/hermes-bots/plugin.js ~/.hermes/plugin.js.bak-<old-hash>-<date>`

## 5. BOTS 标签页关闭后恢复
BOTS = 注册 pane（id `hermes-bots:pane`），dock 到 sessions 成 SESSIONS | BOTS 标签条，`dock.enforce: true` 每次启动强制归位。
关闭=隐藏（`setStripTabHidden`，hide-only chrome tab），恢复三法：
1. 右键标签条区域 → 「Show Bots」（最快，同会话生效）
2. 重启应用（enforce 自动归位）
3. 重置布局（resetLayoutTree 恢复全部关闭 pane）
源码：`apps/desktop/src/components/pane-shell/tree/store.ts`（setStripTabHidden / resetLayoutTree）、
`src/plugins/hermes-bots/plugin.js` 约 8963 行 `ctx.register({id:'pane', dock:{pane:'sessions', pos:'center', enforce:true}})`。

## 回滚后一致性检查
- 后端 serve 正常：`/api/profiles` 仍返回全量 profile（回滚只动前端插件，后端数据不受影响）
- `hermes config check`（官方警告：旧版本可能不识别新配置项）
