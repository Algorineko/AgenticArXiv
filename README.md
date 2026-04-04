# AgenticArxiv

基于 ReAct Agent 的 arXiv 论文检索、PDF 下载与中文翻译系统。

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8+

## 快速开始

### 1. 配置 MySQL

```sql
CREATE DATABASE IF NOT EXISTS agentic_arxiv DEFAULT CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'arxiv'@'127.0.0.1' IDENTIFIED BY 'arxiv123';
GRANT ALL PRIVILEGES ON agentic_arxiv.* TO 'arxiv'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### 2. 配置环境变量

编辑 `AgenticArxiv/.env`：

```env
LLM_BASE_URL=https://your-llm-gateway
LLM_API_KEY=sk-xxx
MODEL=claude-sonnet-4.6
MYSQL_URI=mysql+pymysql://arxiv:arxiv123@127.0.0.1:3306/agentic_arxiv?charset=utf8mb4
```

### 3. 安装依赖

```sh
make install
```

### 4. 启动

```sh
make           # 启动前后端（含日志输出）
make stop      # 停止
make restart   # 重启
make logs      # 查看日志
```

## 架构

```
┌─────────────┐      ┌──────────────────┐
│  Vue 3 SPA  │─────▶│  FastAPI Backend  │
│  (Vite)     │ SSE  │  (uvicorn)        │
└─────────────┘      └──────┬───────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        ┌─────┴─────┐ ┌────┴────┐ ┌──────┴──────┐
        │  MySQL    │ │ ReAct   │ │ PDF Files   │
        │ (元数据)  │ │ Agent   │ │ (output/)   │
        └───────────┘ └─────────┘ └─────────────┘
```

- **MySQL** 存储：论文元数据、PDF/翻译缓存记录、会话、翻译任务、Agent 日志
- **本地文件系统** (`output/`)：PDF 原文和翻译后的 PDF 文件

### 数据库表

| 表 | 用途 |
|---|---|
| `pdf_assets` | PDF 下载缓存记录 |
| `translate_assets` | 翻译缓存记录 |
| `sessions` | 会话元数据 |
| `session_papers` | 会话关联的论文 |
| `translate_tasks` | 异步翻译任务 |
| `chat_logs` | 对话日志 |
| `agent_steps` | Agent ReAct 步骤（thought/action/observation + 耗时） |

## 前端页面

| 页面 | 功能 |
|---|---|
| 对话 | 与 Agent 聊天，Agent 自动调用工具搜索/下载/翻译 |
| 论文 | 当前 session 检索到的论文列表，支持一键下载/翻译 |
| 缓存 | 已下载/已翻译 PDF 管理，翻译任务实时进度 |
| 日志 | 按会话查看 Agent 思考链（thought → action → observation） |
| 设置 | Session 管理、Agent 模式切换、SSE 状态 |

## API 端点

### 核心

- `POST /chat` — 发送消息，Agent 自主决策
- `GET /sessions/{sid}/papers` — 获取 session 论文列表

### PDF

- `POST /pdf/download` — 下载论文 PDF
- `POST /pdf/translate/async` — 异步翻译 PDF
- `GET /pdf/assets` — 列出所有 PDF 缓存
- `GET /pdf/view/raw/{paper_id}` — 浏览器查看原始 PDF
- `GET /pdf/view/translated/{paper_id}` — 浏览器查看翻译 PDF
- `DELETE /pdf/assets/{paper_id}` — 删除 PDF 缓存
- `DELETE /translate/assets/{paper_id}` — 删除翻译缓存

### 日志

- `GET /logs/sessions` — 会话列表（含消息计数）
- `GET /logs/sessions/{sid}/messages` — 某会话的消息时间线
- `GET /logs/messages/{msg_id}/steps` — 某消息的 Agent 思考步骤

### SSE

- `GET /events?session_id={sid}` — 服务端推送事件流（翻译进度、资产变更等）
