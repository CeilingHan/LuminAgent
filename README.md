# LuminAgent — 多模态科研AI助手

基于 OpenManus 构建的多模态科研辅助 Agent，支持 Web 交互、工具路由、Plan Mode、定时任务、记忆管理和可扩展技能系统。

## 架构

```
LuminAgent/
├── openmanus-frontend/          React 19 + Ant Design 6 前端
├── OpenManus/
│   ├── web_server.py            FastAPI 主服务 (所有 REST/SSE 端点)
│   ├── main.py                  CLI Agent 入口
│   ├── run_flow.py              CLI Flow 入口
│   ├── app/
│   │   ├── agent/               ReAct Agent 层
│   │   │   ├── base.py          BaseAgent — 基础循环
│   │   │   ├── react.py         ReActAgent — think() + act()
│   │   │   ├── toolcall.py      ToolCallAgent — LLM 工具调用 + 执行
│   │   │   └── manus.py         Manus Agent — 完整工具集
│   │   ├── tool/                原子工具层 (Tools)
│   │   │   ├── python_execute.py    Python 代码执行
│   │   │   ├── web_search.py        多引擎搜索 (Google→Baidu→DuckDuckGo→Bing)
│   │   │   ├── browser_use_tool.py  浏览器自动化
│   │   │   ├── str_replace_editor.py 文件读写编辑
│   │   │   ├── bash.py              Shell 命令执行
│   │   │   ├── planning.py          计划管理
│   │   │   ├── terminate.py         任务结束
│   │   │   ├── research_tools.py    PDF 论文分析
│   │   │   ├── research_pipeline.py 全流程科研流水线
│   │   │   └── intent_analyzer.py   意图分析 → 工具选择
│   │   ├── flow/                Plan-then-Execute 工作流层
│   │   │   ├── base.py          BaseFlow
│   │   │   ├── planning.py      PlanningFlow — 计划→步骤执行→总结
│   │   │   └── flow_factory.py  FlowFactory
│   │   ├── memory_manager.py    持久化记忆系统 (4 层架构)
│   │   ├── scheduler.py         定时任务调度 (cron-based)
│   │   ├── skill_manager.py     技能管理 (用户自定义工作流)
│   │   ├── schema.py            数据模型
│   │   ├── llm.py               LLM 客户端
│   │   ├── config.py            配置加载
│   │   └── prompt/              Prompt 模板
│   ├── config/config.toml       全局配置
│   └── data/                    持久化数据
│       ├── memory/               记忆文件 (*.md)
│       │   └── MEMORY.md         记忆索引
│       ├── skills/               技能文件 (*.md)
│       └── task_results/         定时任务执行记录
├── docker-compose.yml           Milvus + etcd + minio
└── README.md
```

## 核心概念

### Tools (工具) vs Skills (技能)

| 维度 | Tools | Skills |
|---|---|---|
| **是什么** | 原子 API/函数调用 | Prompt 模板 + 工具编排 |
| **谁来创建** | 开发者写 Python 代码 | **用户**通过前端或 Markdown 文件 |
| **粒度** | `web_search`、`python_execute`、`bash` | "文献综述"、"代码审计"、"实验设计" |
| **存储位置** | `app/tool/*.py` (代码注册) | `data/skills/*.md` (文件即技能) |
| **类比** | 瑞士军刀的单件工具 | 食谱 (告诉你怎么用工具做一道菜) |
| **可否从 GitHub 加载** | 否 (需要 pip install) | ✅ 下载 .md 即可用 |

```
┌──────────────────────────────────────────────────┐
│               Skills (技能) — "怎么做"              │
│                                                    │
│  ┌─ "文献综述" ──────────────────────────────┐    │
│  │ 触发: 用户说"调研"、"文献综述"              │    │
│  │ 工具: web_search + python_execute + LLM    │    │
│  │ 系统提示: "你是文献综述专家，请按照..."     │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌─ "代码审计" ──────────────────────────────┐    │
│  │ 触发: 用户说"审计"、"review代码"           │    │
│  │ 工具: bash + python_execute + LLM          │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
├──────────────────────────────────────────────────┤
│               Tools (工具) — "能做什么"              │
│                                                    │
│  web_search ─ python_execute ─ bash ─ browser     │
│  str_replace_editor ─ terminate ─ planning         │
│  research_tools ─ crawl4ai                         │
└──────────────────────────────────────────────────┘
```

### Memory (记忆) — 四层架构

参考 Claude Code 设计，基于 Markdown 文件 + YAML frontmatter：

| 层级 | 内容 | 加载时机 |
|---|---|---|
| **热层** | MEMORY.md 索引 | 每次 session (始终在上下文) |
| **温层** | `memory/*.md` 主题文件 | LLM 按关键词检索，最多加载 5 个 |
| **冷层** | `data/sessions/*.json` | 关键词搜索访问 |
| **向量层** | Milvus (可选) | 语义相似度搜索 fallback |

四种记忆类型：

| 类型 | 用途 | 示例 |
|---|---|---|
| `user` | 用户身份/偏好 | 研究方向、常⽤工具、编程语言偏好 |
| `project` | 项目上下文 | 项目目标、架构决策、当前进展 |
| `feedback` | 用户反馈 | 确认的方法、纠正过的错误 |
| `reference` | 外部资源 | 论文 DOI、工具链接、数据集地址 |

### Plan Mode — 计划驱动执行

```
用户输入 → LLM 生成计划 (3-7步) → 逐步执行 (每步走工具分发) → LLM 总结
         SSE: plan_created       SSE: step_start/completed    SSE: text
```

### Agent Mode — 工具路由

```
用户输入 → intent_analyzer 选择工具 → 工具执行 → LLM 合成回答
         → web_search / python_execute / browser_use / str_replace_editor / chat
```

## 快速开始

### 1. 启动后端

```bash
cd OpenManus

# 安装依赖 (使用 uv)
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

# 可选: 启动 Milvus (向量记忆)
docker-compose up -d

# 启动服务
python web_server.py
# → http://localhost:8000
```

### 2. 启动前端

```bash
cd openmanus-frontend
npm install
npm start
# → http://localhost:3000
```

### 3. 配置 LLM

编辑 `OpenManus/config/config.toml`：

```toml
[llm]
model = "qwen-max"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "your-api-key"
max_tokens = 4096
temperature = 0.0
```

## API 端点

### 对话与执行

| 端点 | 方法 | 说明 |
|---|---|---|
| `/` | GET | Agent 状态 + 可用工具列表 |
| `/agent/stream` | POST | Agent 模式 (SSE) — 意图分析 → 工具分发 → LLM 回答 |
| `/plan/stream` | POST | Plan 模式 (SSE) — 计划生成 → 逐步执行 → 总结 |
| `/execute/python` | POST | Python 代码直接执行 (SSE) |
| `/execute/stream` | POST | 纯文本 LLM 对话 (SSE) |
| `/research/pipeline` | POST | 科研全流程流水线 (SSE) |
| `/upload` | POST | 文件上传 |

### 记忆管理

| 端点 | 方法 | 说明 |
|---|---|---|
| `/memory` | GET | 列出所有记忆 |
| `/memory` | POST | 创建/更新记忆 `{name, type, description, content}` |
| `/memory/{name}` | GET | 读取单个记忆全文 |
| `/memory/{name}` | DELETE | 删除记忆 |
| `/memory/search` | POST | 关键词搜索记忆 `{query, limit}` |

### 定时任务

| 端点 | 方法 | 说明 |
|---|---|---|
| `/scheduler/jobs` | GET | 列出所有任务 |
| `/scheduler/jobs` | POST | 创建任务 `{name, cron, prompt, mode}` |
| `/scheduler/jobs/{id}` | PUT | 启用/停用任务 |
| `/scheduler/jobs/{id}` | DELETE | 删除任务 |
| `/scheduler/jobs/{id}/history` | GET | 查看任务执行历史 |

### 技能管理

| 端点 | 方法 | 说明 |
|---|---|---|
| `/skills` | GET | 列出所有技能 |
| `/skills` | POST | 创建技能 `{name, description, prompt, tools, triggers}` |
| `/skills/{name}` | GET | 读取单个技能 |
| `/skills/{name}` | DELETE | 删除技能 |
| `/skills/load` | POST | 从 URL 加载技能 `{url}` |

## SSE 事件类型

所有流式端点使用标准 SSE (`text/event-stream`) 协议：

| event type | 携带字段 | 说明 |
|---|---|---|
| `text` | `content` | LLM 生成的文本增量 |
| `status` | `content` | 状态消息 (意图分析、工具执行进度) |
| `tool_call` | `tools`, `args` | 意图分析选择的工具和参数 |
| `tool_result` | `content` | 工具执行结果 |
| `search_result` | `query`, `results` | 网络搜索结果 |
| `plan_created` | `plan_id`, `title`, `steps` | 计划已生成 |
| `step_start` | `step_index`, `step_text` | 步骤开始执行 |
| `step_completed` | `step_index` | 步骤执行完成 |
| `step_error` | `step_index`, `error` | 步骤执行失败 |
| `done` | — | 流结束 |
| `error` | `content` | 错误消息 |

## 创建自定义 Skill

### 方法 1: 前端创建

1. 点击侧边栏「📦 技能管理」
2. 点击「新建技能」
3. 填写名称、描述、选用的工具、触发关键词、系统提示词
4. 保存

### 方法 2: 从 GitHub/URL 加载

1. 在技能管理页面点击「从URL加载」
2. 输入原始文件 URL：
   ```
   https://raw.githubusercontent.com/user/repo/main/skills/my-skill.md
   ```
3. 点击加载 → 自动解析并注册

### 方法 3: 手动创建 Markdown 文件

在 `OpenManus/data/skills/` 目录下创建 `.md` 文件，格式：

```markdown
---
name: literature-review
description: 文献综述 — 搜索、整理、总结研究论文
tools: [web_search, python_execute]
trigger_keywords: [文献综述, 调研, 研究现状, literature review, survey]
---

# 文献综述技能

## 执行步骤
1. 用 web_search 搜索相关论文（中文 + 英文，至少 5 篇）
2. 提取每篇论文的核心贡献、方法和局限性
3. 按子领域分类整理
4. 生成 Markdown 格式的综述报告，包含标题、作者、链接

## 输出格式
### [子领域名称]
- **论文**: [论文标题](链接) — 核心贡献
- **方法**: 使用的关键技术
- **评价**: 优点与不足
```

**Skill 文件规范**:
- 文件名: `{name}.md` (英文 slug)
- Frontmatter: `name`, `description` (用于检索), `tools` (可选工具列表), `trigger_keywords` (触发词)
- Body: Markdown 格式的系统提示，注入到 Agent 的 system prompt 中

**工作流程**:
1. Agent 收到用户输入时，检查是否匹配任何 skill 的 `trigger_keywords`
2. 如果匹配，将匹配的 skill 内容注入到 system prompt
3. Agent 按照 skill 定义的步骤执行任务

## 项目进展

| 模块 | 状态 | 说明 |
|---|---|---|
| Agent 对话 | ✅ 完成 | 意图分析 + 工具路由 + 流式回答 |
| Plan Mode | ✅ 完成 | 计划生成 → 逐步执行 → 总结 |
| Python 执行 | ✅ 完成 | 直接代码执行 + 前端编辑器 |
| 网络搜索 | ✅ 完成 | 4 引擎回退 + 搜索结果浮窗 |
| 定时任务 | ✅ 完成 | Cron 调度 + 持久化 + 执行历史 |
| 记忆系统 | ✅ Phase 1 | 文件 CRUD + 索引 + Agent 上下文注入 |
| 技能系统 | ✅ Phase 1 | 文件 CRUD + URL 加载 + 触发匹配 |
| Memory 检索 | 🔄 Phase 2 | LLM 相关性选择 + Milvus fallback |
| Memory 自动捕获 | 🔄 Phase 3 | Session 后自动提取 + 合并去重 |
| 多 Agent 协同 | ⚠️ 基础 | PlanningFlow 存在，未接入 Web |
| RAG 文档检索 | 🔄 计划中 | Milvus 向量检索 + 文档索引 |
| 图表可视化 | 🔄 计划中 | matplotlib/plotly 渲染到前端 |

## 技术栈

- **后端**: Python 3.12 + FastAPI + SSE streaming
- **LLM**: 阿里云通义千问 (DashScope) — 兼容 OpenAI API
- **前端**: React 19 + Ant Design 6 + React Router 7
- **搜索**: Google / Baidu / DuckDuckGo / Bing (多引擎回退)
- **调度**: APScheduler (cron 表达式)
- **向量检索**: Milvus 2.4 (可选)
- **追踪**: LangSmith
- **浏览器自动化**: Playwright + browser-use
- **PDF 处理**: pdfplumber + PyMuPDF

## 许可证

MIT License
