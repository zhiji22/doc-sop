# Doc SOP AI

AI tool that converts documents into SOP, checklist and structured knowledge.

## Stack

Frontend
- Next.js
- Clerk Auth
- Tailwind

Backend
- FastAPI
- PostgreSQL (Supabase)
- MinIO (S3 compatible storage)

AI
- LLM API (OpenAI / Dashscope / etc.)

## Features

- Document upload
- SOP generation
- Checklist extraction
- Structured JSON output
- History runs
- Authentication

## Development

### Start storage

```bash
docker compose up -d


##  Supabase
https://supabase.com/dashboard/project/ifwydlcuhfgaushkxihy/database/settings
## MinlO Console
http://localhost:9001/browser/doc-sop
## Clerk
https://dashboard.clerk.com/apps/app_3AOHsnGJ0zau75BC2RSiPzTJmuO/instances/ins_3AOHsnrVEd903pUvyF0IOaU1RDP/api-keys

## =======================================

## Phase 1：基础架构增强
# 1.引入 SQLAlchemy ORM Models + Alembic 迁移 — 现在全是裸 SQL 拼接，不可维护
# 2.LLM 调用加 Streaming（SSE） — 这是 Agent 的基础能力，先在 Q&A 上实现
# 3.Q&A 对话带历史上下文 — 现在每次问答都是独立的，LLM 不知道之前聊了什么
# 4.加入任务队列（Celery / ARQ） — 替代 BackgroundTasks，支持重试、并发控制

## Phase 2：引入 Agent 核心模式
# 6.Function Calling / Tool Use — 让 LLM 能调用你定义的工具（搜索文档、查数据库、生成图表等）
# 7.ReAct Agent 循环 — 实现 思考→调用工具→观察结果→继续思考 的循环
# 8.多步骤文档分析 Agent — 比如 "分析这份合同的风险点，并对比行业标准"，Agent 自动分解为多步
# 9.Agent 记忆系统 — 短期（对话上下文）+ 长期（向量存储的用户偏好/知识）

## Phase 3：进阶 Agent 能力
# 12.Multi-Agent 协作 — 比如"规划 Agent" + "执行 Agent" + "审查 Agent"
# 13.Agent 可观测性 — 用 LangSmith / Phoenix 追踪每次 Agent 的决策链路
# 14.用户自定义 Agent Workflow — 前端可视化编排 Agent 的工具和流程


## Agent编排、Planner、ReAct
Multi-Agent 编排
  ├── Planner（规划）
  ├── Executor（执行）──→ 内部是 ReAct 循环（思考→工具→观察→...）
  └── Reviewer（审查）