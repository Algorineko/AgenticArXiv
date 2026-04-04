# AgenticArxiv

## 项目概览
ReAct Agent + arXiv 论文管理系统。Python FastAPI 后端 + Vue 3 前端。

## 技术栈
- **后端**: FastAPI + uvicorn, SQLAlchemy 2.0 (pymysql), MySQL 8
- **前端**: Vue 3 + TypeScript + Pinia + Vite
- **Agent**: 三种架构并存 (通过 agent_type 切换), 最多 5 轮迭代
  - `react_regex`: ReAct prompt + 正则解析 + 进程内函数调用
  - `mcp`: ReAct prompt + 正则解析 + MCP JSON-RPC 跨进程调用
  - `skill_cli`: Skill 文档 + LLM 生成 CLI 命令 + subprocess 执行
- **实时通信**: SSE (Server-Sent Events) 推送翻译进度 + Agent 思考步骤

## 目录结构
```
AgenticArxiv/          # Python 后端
  api/                 # FastAPI 路由 (app.py, endpoints.py)
  agents/              # Agent 基类 (base_agent.py) + ReAct 引擎 (agent_engine.py)
  skill_cli/           # 方案 C: Skill/CLI (SKILL.md + tool_cli.py + skill_agent.py)
  mcp_protocol/        # 方案 B: MCP 协议 (server.py + mcp_agent.py)
  tools/               # 底层工具 (arxiv_search, pdf_download, pdf_translate, cache_status)
  models/              # ORM (orm.py), 数据库 (db.py), Store (store.py), Pydantic (schemas.py)
  services/            # 日志服务 (log_service.py), 事件总线 (event_bus.py), 翻译 runner
  config.py            # 环境变量配置
AgenticArxivWeb/       # Vue 3 前端
  src/components/      # ChatPanel, PapersPanel, AssetsPanel, LogsPanel, SettingsPanel, Sidebar
  src/stores/          # Pinia appStore
  src/api/             # axios client, SSE, types
```

## 存储架构
- MySQL: 所有元数据 (7 张表: pdf_assets, translate_assets, sessions, session_papers, translate_tasks, chat_logs, agent_steps)
- 本地文件: PDF 文件存于 output/ 目录
- 启动时 validate_local_paths() 检查 READY 文件是否存在

## 开发命令
```sh
make install    # 安装依赖 (venv + npm)
make            # 启动前后端
make stop       # 停止
make restart    # 重启
```

## 环境变量
在 `AgenticArxiv/.env` 中配置:
- `LLM_BASE_URL`, `LLM_API_KEY`, `MODEL` — LLM 网关
- `MYSQL_URI` — MySQL 连接串

## 注意事项
- Store 使用同步 pymysql (非 aiomysql)，因为 tools/agent 在同步线程中运行
- Agent 日志写入用 try/except 包裹，不影响主流程
- 前端 5 页布局: 左侧 60px Sidebar + KeepAlive 动态组件
- 翻译任务异步执行 (translate_runner.enqueue 立即返回)，进度通过 SSE 推送
- Agent 每个思考步骤通过 SSE agent_step 事件实时推送到前端
- 翻译进度直接透传 pdf2zh 原始进度 (0%~100%)
- 前端 taskId 关联: 只有 sendChat 期间 SSE task_created 事件中的新任务才会绑定到消息上 (避免同步操作误显示旧任务进度)
- 翻译进度在 Agent 思考阶段通过 thinkingTaskId 显示在 thinking card 中
- 前端支持昼夜主题切换 (data-theme="light" on root element, localStorage 持久化)
- Sidebar "A" 图标点击弹出 CS 分类参考表
