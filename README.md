# AgenticArxiv — ReAct Agent + arXiv 论文管理系统

基于可扩展 Agent 架构的 arXiv 论文检索、PDF 下载与中文翻译系统。支持**三种 Agent 实现方案**（ReAct、MCP、Skill/CLI），通过简单配置切换。

## 项目特点

- 🤖 **三种 Agent 架构可选**：选择最适合的工具调用方式
- 🔄 **实时 SSE 推送**：翻译进度、Agent 思考步骤实时更新
- 💾 **完整日志追踪**：Agent ReAct 链路、消息历史、执行耗时
- 🗄️ **数据自动初始化**：MySQL 表自动创建，无需手动迁移
- 🎨 **现代化前端**：Vue 3 + TypeScript，功能划分页面布局

## 快速开始

### 前置要求

- Python 3.10+、Node.js 18+、MySQL 8.0+
- LLM API（支持 Claude、Gemini 等任何兼容 OpenAI API 的服务）

### 1️⃣ MySQL 初始化

在 Linux 机器上执行：
```bash
mysql -u root -p
```
```sql
CREATE DATABASE IF NOT EXISTS agentic_arxiv DEFAULT CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'arxiv'@'localhost' IDENTIFIED BY 'arxiv123';
GRANT ALL PRIVILEGES ON agentic_arxiv.* TO 'arxiv'@'localhost';
FLUSH PRIVILEGES;
```

### 2️⃣ 克隆项目并配置环境

```bash
git clone <repo-url>
cd AgenticArxiv

# 创建 .env 配置文件
cat > AgenticArxiv/.env << 'EOF'
# LLM API 配置
LLM_BASE_URL=https://your-api-gateway
LLM_API_KEY=sk-your-api-key
MODEL=your-LLM-model

# MySQL 连接（自动创建所有表，无需手动迁移）
MYSQL_URI=mysql+pymysql://arxiv:arxiv123@localhost:3306/agentic_arxiv?charset=utf8mb4

# 可选：Agent 配置（默认 regex）
AGENT_TYPE=regex  # 或 mcp、skill_cli

# 可选：PDF 相关配置
PDF_RAW_PATH=./output/pdf_raw
PDF_TRANSLATED_PATH=./output/pdf_translated
PDF2ZH_SERVICE=bing          # 翻译服务
PDF2ZH_THREADS=4             # 翻译线程数
EOF
```

### 3️⃣ 安装依赖并启动

```bash
make install   # 安装 Python venv + npm 依赖

make           # 启动前后端（日志输出）
# 后端: http://localhost:8000
# 前端: http://localhost:5173
# API 文档: http://localhost:8000/docs

make stop      # 停止所有服务
```

### 4️⃣ 首次使用

打开 http://localhost:5173，在 **设置** 页面选择 Agent 模式，然后在 **对话** 页面测试：

```
你好，帮我检索最近7天内机器学习（cs.ML）方向的论文，最多5篇
```

Agent 会自动调用工具搜索、下载、翻译论文。

---

## 架构概览

### 系统流程图

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 前端 SPA                        │
│  ChatPanel | PapersPanel | AssetsPanel | LogsPanel       │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP + SSE
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI 后端 (uvicorn)                     │
│  ┌────────────────────────────────────┐                │
│  │   BaseAgent (通用执行循环)         │                │
│  │  + 会话上下文注入                  │                │
│  │  + SSE 实时推送                    │                │
│  │  + 日志记录                        │                │
│  └────────────┬───────────────────────┘                │
│               │ (依赖注入)                              │
│  ┌────────────▼───────────────────────────────────────┐│
│  │ 三种 Agent 实现 (选择一种)         │                ││
│  ├─────────────────────────────────────┤               ││
│  │ A. ReActAgent     │ B. MCPAgent     │ C. SkillAgent ││
│  │ (正则 + 同步)    │ (MCP JSON-RPC) │ (CLI 子进程)  ││
│  └────────────┬──────────────────────┬─────────────────┘│
│               │ 调用工具              │                 │
│  ┌────────────▼────────────────────────▼──────┐         │
│  │       ToolRegistry (进程内函数)           │         │
│  │ ├─ get_recently_submitted_cs_papers      │         │
│  │ ├─ download_arxiv_pdf                    │         │
│  │ ├─ translate_arxiv_pdf (异步 enqueue)    │         │
│  │ └─ get_paper_cache_status                │         │
│  └──────────────────────────────────────────┘         │
└─────────────┬────────────────────────────────────────┘
              │
        ┌─────┴──────────┬─────────────┬─────────────┐
        │                │             │             │
    ┌───▼───┐      ┌────▼──────┐ ┌──┴────┐    ┌────▼─────┐
    │MySQL  │      │Translate  │ │ PDF   │    │ Event    │
    │       │      │ Runner    │ │ Files │    │ Bus      │
    │ 7表   │      │(异步)     │ │(本地) │    │(SSE)     │
    └───────┘      └───────────┘ └───────┘    └──────────┘
```

### 数据库架构

| 表 | 字段数 | 用途 |
|---|---|---|
| `pdf_assets` | 9 | PDF 下载记录（URL、路径、SHA256、状态） |
| `translate_assets` | 9 | 翻译记录（输入/输出路径、服务、状态） |
| `sessions` | 4 | 会话元数据（最后活跃论文、时间戳） |
| `session_papers` | 13 | 会话的论文列表（标题、作者、分类、URL 等） |
| `translate_tasks` | 10 | 异步翻译任务队列（进度、状态、元信息） |
| `chat_logs` | 7 | 对话日志（角色、内容、模型、Agent 类型） |
| `agent_steps` | 10 | ReAct 链路日志（thought/action/observation、耗时） |

**🔑 关键点**：启动 FastAPI 时，`lifespan` context manager 自动调用 `init_db()` → `Base.metadata.create_all()` 创建所有表。**完全自动化，无需手动迁移脚本**。

---

## 三种 Agent 模式详解

### A. ReActAgent (regex) — 推荐默认

```
LLM Prompt → ReAct 文本输出 → 正则解析 → 进程内函数调用
```

**优点**：
- 最快（无通信开销）
- 最简单（纯正则解析）
- 最稳定（同步执行）

**使用场景**：本地开发、快速原型、演示

**配置**：
```env
AGENT_TYPE=regex
```

**工作流程** (`agents/agent_engine.py`)：
1. `build_messages()` — 生成 ReAct prompt（包含工具列表 + 历史）
2. `parse_response()` — 正则提取 `Thought: ... Action: {"name":"tool","args":{...}} Observation: ...`
3. `invoke_tool()` — 直接调用 `registry.execute_tool(tool_name, args)`

---

### B. MCPAgent (mcp) — 跨进程通信

```
LLM Prompt → ReAct 文本 → 正则解析 → MCP JSON-RPC → 工具服务器
```

**优点**：
- 工具隔离（分离的进程）
- 符合 MCP 协议标准
- 可扩展（易接入第三方工具服务）

**缺点**：
- 通信延迟
- 配置复杂度增加

**使用场景**：多人团队开发、工具服务化、API 网关

**配置**：
```env
AGENT_TYPE=mcp
```

**工作流程** (`mcp_protocol/mcp_agent.py`)：
1. 启动 MCP 服务器 (`mcp_protocol/server.py`) 作为子进程
2. 通过 stdio 建立 JSON-RPC 通道
3. LLM 响应解析同 ReAct，但工具调用改为 `session.call_tool(tool_name, args)`
4. MCP 服务器侧执行工具，返回结果

**架构图**：
```
┌─────────────────┐                    ┌──────────────────┐
│  FastAPI +      │  JSON-RPC (stdio)  │  MCP 服务器      │
│  ReAct 解析     │◄──────────────────►│  Tool Registry   │
│  MCPAgent       │                    │  + Executors     │
└─────────────────┘                    └──────────────────┘
```

---

### C. SkillAgent (skill_cli) — CLI 命令行驱动

```
LLM 读取 SKILL.md → LLM 生成 bash 命令 → subprocess 执行 → 解析 JSON 输出
```

**输出格式**：`Thought: ... Command: bash ... Observation: ...`

**优点**：
- LLM 更容易理解（文档式）
- 命令可读性高（便于调试）
- 兼容现有 CLI 工具

**缺点**：
- 安全风险（子进程 + bash）
- 启动开销（每次创建新进程）

**使用场景**：学习研究、不信任 LLM 参数、命令式工作流

**配置**：
```env
AGENT_TYPE=skill_cli
```

**关键文件**：
- `skill_cli/SKILL.md` — 工具文档（LLM 会读到）
- `skill_cli/tool_cli.py` — CLI 入口（子命令: `search_papers`, `download_pdf`, `translate_pdf`）
- `skill_cli/skill_prompt.py` — Skill 格式 prompt

**工作流程** (`skill_cli/skill_agent.py`)：
1. `load_skill_doc()` — 读取 SKILL.md
2. `build_messages()` — Prompt 包含文档文本
3. LLM 输出: `Command: bash\n<command>\n`
4. `_parse_cli_command()` — 提取子命令 + `--key=value` 参数
5. `invoke_tool()` — `subprocess.run([python, tool_cli.py, sub_cmd, --args])`

**示例命令**：
```bash
python skill_cli/tool_cli.py search_papers --session_id=demo1 --days=7 --aspect=ML --max_results=5
python skill_cli/tool_cli.py download_pdf --session_id=demo1 --ref=2
```

---

## 在新 Linux 环境部署

### 完整部署步骤（从零开始）

#### Step 1: 系统依赖

```bash
# Ubuntu 20.04+
sudo apt update && sudo apt install -y \
  python3.10 python3-venv python3-pip \
  nodejs npm \
  mysql-server mysql-client \
  libmysqlclient-dev \
  build-essential

# 启动 MySQL
sudo systemctl start mysql
sudo systemctl enable mysql
```

#### Step 2: MySQL 用户和数据库

```bash
sudo mysql -u root << 'EOF'
CREATE DATABASE IF NOT EXISTS agentic_arxiv DEFAULT CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'arxiv'@'localhost' IDENTIFIED BY 'arxiv123';
GRANT ALL PRIVILEGES ON agentic_arxiv.* TO 'arxiv'@'localhost';
FLUSH PRIVILEGES;
EOF

# 验证连接
mysql -u arxiv -parxiv123 -h localhost agentic_arxiv -e "SELECT 1;"
```

#### Step 3: 项目部署

```bash
cd /opt/agentic-arxiv
git clone <your-repo> .

# Python 环境
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r AgenticArxiv/requirements.txt

# Node 环境
cd AgenticArxivWeb
npm install
cd ..
```

#### Step 4: 环境配置

```bash
cat > AgenticArxiv/.env << 'EOF'
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-xxxxxxxx
MODEL=gpt-4-turbo

MYSQL_URI=mysql+pymysql://arxiv:arxiv123@localhost:3306/agentic_arxiv?charset=utf8mb4

AGENT_TYPE=regex
PDF2ZH_SERVICE=bing
PDF2ZH_THREADS=4
EOF

chmod 600 AgenticArxiv/.env
```

#### Step 5: 启动测试

```bash
# 检查 Python 依赖
source .venv/bin/activate
python -c "from api.app import app; print('✓ API 模块加载成功')"

# 测试数据库连接
python -c "from models.db import init_db; init_db(); print('✓ 数据库表已初始化')"

# 启动 FastAPI
cd AgenticArxiv
uvicorn api.app:app --host 0.0.0.0 --port 8000

# 新终端，启动前端
cd AgenticArxivWeb
npm run dev -- --host 0.0.0.0 --port 5173
```

#### Step 6: systemd 服务（可选）

```bash
sudo tee /etc/systemd/system/agentic-arxiv-api.service > /dev/null << 'EOF'
[Unit]
Description=Agentic Arxiv API
After=network.target mysql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/agentic-arxiv
Environment="PATH=/opt/agentic-arxiv/.venv/bin"
ExecStart=/opt/agentic-arxiv/.venv/bin/python -m uvicorn AgenticArxiv.api.app:app \
  --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable agentic-arxiv-api
sudo systemctl start agentic-arxiv-api
```

---

## 数据库初始化详解

### 自动化流程

```python
# api/app.py 启动时执行
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Initializing database tables...")
    init_db()  # ← 这里
    store.validate_local_paths()
    log.info("Database ready.")
    yield
```

```python
# models/db.py
def init_db():
    """Create all tables (safe to call repeatedly)."""
    import models.orm  # 导入 ORM 定义注册到 Base.metadata
    Base.metadata.create_all(bind=engine)  # SQLAlchemy 自动创建所有表
```

**关键特性**：
- ✅ **幂等性**：可安全重复调用，不会重复创建表
- ✅ **无需迁移**：不依赖 Alembic/FlywayDB
- ✅ **自动索引**：ORM 定义的索引自动创建
- ⚠️ **限制**：表结构变更需要手动 ALTER（不过对学生项目一般没问题）

### 验证表创建

```bash
mysql -u arxiv -parxiv123 -h localhost agentic_arxiv << 'EOF'
SHOW TABLES;
DESC pdf_assets;
DESC chat_logs;
SELECT COUNT(*) FROM information_schema.TABLES 
WHERE TABLE_SCHEMA='agentic_arxiv';
EOF
```

应看到 **7 张表**。

---

## API 端点一览

### 对话 & 会话

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/chat` | 发送消息，Agent 自主决策 |
| `GET` | `/sessions` | 列出所有会话 |
| `GET` | `/sessions/{sid}/papers` | 获取 session 论文列表 |

### PDF 操作

| 方法 | 端点 | 说明 |
|---|---|---|
| `POST` | `/pdf/download` | 下载论文 PDF |
| `POST` | `/pdf/translate/async` | 异步翻译 PDF |
| `GET` | `/pdf/assets` | 列出所有 PDF 缓存 |
| `GET` | `/pdf/view/raw/{paper_id}` | 浏览器查看原始 PDF |
| `GET` | `/pdf/view/translated/{paper_id}` | 浏览器查看翻译 PDF |
| `DELETE` | `/pdf/assets/{paper_id}` | 删除 PDF |
| `DELETE` | `/translate/assets/{paper_id}` | 删除翻译 |

### 日志

| 方法 | 端点 | 说明 |
|---|---|---|
| `GET` | `/logs/sessions` | 会话列表（消息计数） |
| `GET` | `/logs/sessions/{sid}/messages` | 某会话消息时间线 |
| `GET` | `/logs/messages/{msg_id}/steps` | 某消息的 Agent 步骤 |

### 实时事件

| 方法 | 端点 | 说明 |
|---|---|---|
| `GET` | `/events?session_id={sid}` | SSE 事件流（翻译进度、Agent 步骤） |

---

## 前端功能

| 页面 | 功能 |
|---|---|
| 📝 **对话** | 与 Agent 自然交互，实时看到 Agent 思考过程（Thought/Action/Observation） |
| 📚 **论文** | 当前 session 检索到的论文列表，支持批量下载/翻译 |
| 💾 **缓存** | PDF 及翻译文件管理，实时翻译进度条 |
| 📊 **日志** | 按会话和消息查看 Agent 执行链路 |
| ⚙️ **设置** | 会话管理、Agent 模式切换、SSE 连接状态 |

---

## 常见问题

### Q: 如何切换 Agent 模式？

**前端**：进入 **设置** → 选择 Agent Type → 刷新

**代码**：编辑 `.env`：
```env
AGENT_TYPE=regex  # 改为 mcp 或 skill_cli
```

### Q: 翻译为什么很慢？

- `pdf2zh` 是异步任务，不会阻塞 Agent
- 实际翻译在后台线程执行
- 前端通过 SSE 实时接收进度，可以继续聊天

### Q: 如何增加新工具？

1. 在 `tools/` 下创建新文件 `your_tool.py`
2. 实现 `register_tool(name, description, parameters, handler)`
3. 在 `tools/arxiv_tool.py` 等地 import 注册
4. Agent 自动发现（通过 `registry.list_tools()`）

### Q: 如何调整 LLM 参数？

编辑 `config.py`：
```python
@dataclass(frozen=True)
class Settings:
    antigravity_base_url: str = os.getenv("LLM_BASE_URL", ...)
    antigravity_api_key: str = os.getenv("LLM_API_KEY", ...)
    models: LLMModels = LLMModels()
```

Agent 循环参数在 `agents/base_agent.py::run()`：
```python
response = self.llm_client.chat_completions(
    model=agent_model,
    temperature=0.1,       # ← 改这里
    max_tokens=1000,       # ← 或这里
    stream=False,
)
```

### Q: 如何开启调试日志？

改 `config.py` 或环境变量：
```python
# models/db.py
engine = create_engine(
    settings.mysql_uri,
    echo=True,  # SQL 日志
)
```

---

## 文件结构

```
AgenticArxiv/                    # Python 后端
├── api/                         # FastAPI 应用
│   ├── app.py                   # 应用入口 + lifespan 初始化
│   └── endpoints.py             # 路由定义
├── agents/                      # Agent 核心
│   ├── base_agent.py            # 通用执行循环 + SSE + 日志
│   ├── agent_engine.py          # ReActAgent 实现
│   ├── prompt_templates.py      # Prompt 模板
│   └── context_manager.py       # 上下文管理
├── mcp_protocol/                # MCP 方案
│   ├── server.py                # MCP 服务器
│   └── mcp_agent.py             # MCPAgent 实现
├── skill_cli/                   # Skill/CLI 方案
│   ├── SKILL.md                 # 工具文档（LLM 读这个）
│   ├── skill_agent.py           # SkillAgent 实现
│   ├── skill_prompt.py          # Skill Prompt
│   └── tool_cli.py              # CLI 子进程入口
├── tools/                       # 工具实现
│   ├── tool_registry.py         # 工具注册表
│   ├── arxiv_tool.py            # arXiv 搜索
│   ├── pdf_download_tool.py     # PDF 下载
│   ├── pdf_translate_tool.py    # PDF 翻译
│   └── cache_status_tool.py     # 缓存查询
├── models/                      # 数据层
│   ├── db.py                    # SQLAlchemy 引擎 + init_db()
│   ├── orm.py                   # ORM 定义（7 张表）
│   ├── store.py                 # 业务逻辑
│   └── schemas.py               # Pydantic 模型
├── services/                    # 服务层
│   ├── log_service.py           # 日志记录
│   ├── runtime.py               # 翻译 Runner + Event Bus
│   └── event_bus.py             # SSE 事件管理
├── utils/                       # 工具函数
│   ├── llm_client.py            # LLM 客户端
│   └── logger.py                # 日志配置
├── config.py                    # 环境变量 + Settings
├── main.py                      # 命令行调试入口
└── requirements.txt             # Python 依赖

AgenticArxivWeb/                 # Vue 3 前端
├── src/
│   ├── components/              # Vue 组件
│   │   ├── ChatPanel.vue        # 对话面板
│   │   ├── PapersPanel.vue      # 论文列表
│   │   ├── AssetsPanel.vue      # 缓存管理
│   │   ├── LogsPanel.vue        # 日志查看
│   │   ├── SettingsPanel.vue    # 设置面板
│   │   └── Sidebar.vue          # 侧边栏
│   ├── stores/                  # Pinia 状态
│   │   └── appStore.ts
│   ├── api/                     # API 客户端
│   │   ├── client.ts            # axios 实例
│   │   ├── sse.ts               # SSE 管理
│   │   └── types.ts             # 类型定义
│   ├── App.vue                  # 主组件
│   └── main.ts                  # 入口
├── vite.config.ts               # Vite 配置
└── package.json

Makefile                         # 便捷命令
└── bin/                         # 启动脚本
    ├── start.sh
    └── shutdown.sh
```

---

## 本地开发

### 仅启动后端

```bash
cd AgenticArxiv
source ../.venv/bin/activate
uvicorn api.app:app --reload --port 8000
```

### 仅启动前端

```bash
cd AgenticArxivWeb
npm run dev -- --port 5173
```

### 运行测试

```bash
cd AgenticArxiv
pytest tests/
```

---

## 扩展开发

### 增加新 Agent 方案

1. 继承 `BaseAgent`
2. 实现 5 个抽象方法
3. 在 `api/endpoints.py` 注册选择逻辑

### 增加新工具

1. 在 `tools/new_tool.py` 实现
2. 调用 `register_tool()`
3. BaseAgent 自动发现

### 数据库表扩展

1. 在 `models/orm.py` 定义新 ORM 类
2. 启动时自动创建
