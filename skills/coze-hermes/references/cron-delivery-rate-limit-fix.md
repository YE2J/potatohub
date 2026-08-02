# Cron 推送限流修复记录

## 问题

Hermes cron 任务 `deliver: origin` 推送到微信时，触发 iLink API 30s cooldown 限流。

## 根因
- 多个 cron 整点同时推微信
- selfcheck 每分钟推送
- 每 job retry 2 次

## 修复（2026-06-23~26）
- 移除 8 个 origin job
- 迁移到系统 crontab
- 创建统一晨报（10:00, origin, 单条）
- Wiki 整理 origin→local

## 规则
> 新增 cron 默认 deliver: local。仅晨报（10:00）可 deliver: origin。
