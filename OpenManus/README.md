# LuminAgent 后端

基于 [OpenManus](https://github.com/FoundationAgents/OpenManus) 框架构建。保留了 OpenManus 的 Agent 层、工具基类、Flow 编排和配置系统，在此之上扩展了 Web 服务、记忆、调度、技能管理等能力。

## 复用 vs 新增

### 复用自 OpenManus（框架层）

| 模块 | 文件 | 用途 |
|---|---|---|
| Agent 层 | `app/agent/base.py`, `react.py`, `toolcall.py`, `manus.py` | ReAct 循环、LLM 工具调用 |
| 工具基类 | `app/tool/base.py`, `tool_collection.py` | `BaseTool` 抽象、`ToolCollection` 容器 |
| 部分工具 | `browser_use_tool.py`, `bash.py`, `str_replace_editor.py`, `planning.py`, `terminate.py` | 浏览器、Shell、文件编辑、计划管理 |
| Flow 层 | `app/flow/base.py`, `planning.py`, `flow_factory.py` | Plan-then-Execute 工作流 |
| 配置 | `app/config.py`, `config/config.toml` | Pydantic 配置加载 |
| LLM 客户端 | `app/llm.py` | OpenAI 兼容客户端 + token 计数 |
| Schema | `app/schema.py` | Message、Memory、AgentState |
| MCP 协议 | `app/mcp/` | MCP 服务端 |
| Prompt | `app/prompt/` | 系统提示模板 |
| Sandbox | `app/sandbox/` | Daytona 沙盒 |
| 科研工具 | `app/tool/research_tools.py`, `research_pipeline.py`, `crawl4ai.py`, `pptx_tool.py` | PDF 解析、爬虫、PPT 生成 |

### LuminAgent 新增（应用层）

| 模块 | 文件 | 说明 |
|---|---|---|
| **Web 服务** | `web_server.py` | FastAPI + SSE streaming，所有 REST 端点 |
| **工具路由** | `app/tool/intent_analyzer.py` | LLM 意图分析 → 5 工具智能分发 |
| **工具路由** | `app/prompt/intent_analysic.py` | 意图分析系统提示 |
| **搜索增强** | `app/tool/web_search.py` (修改) | 委托给 intent_analyzer |
| **记忆系统** | `app/memory_manager.py` | Markdown + YAML frontmatter，4 层架构 |
| **技能系统** | `app/skill_manager.py` | 用户自定义技能，文件即技能，URL 加载 |
| **定时任务** | `app/scheduler.py` | APScheduler cron 调度 + 持久化 |
| **Python 执行** | `app/tool/python_execute.py` (修改) | 增加 `__name__ == "__main__"` 支持 |

## 架构

```
web_server.py  ← 用户入口 (FastAPI + SSE)
     │
     ├─ /agent/stream    意图分析 → 工具分发 → LLM 合成
     ├─ /plan/stream     计划生成 → 逐步执行 → 总结
     ├─ /execute/python  直接 Python 执行
     ├─ /memory/*        记忆 CRUD
     ├─ /skills/*        技能 CRUD + URL 加载
     ├─ /scheduler/*     定时任务 CRUD
     └─ /research/pipeline  科研全流程流水线
```

## 核心概念

### Tools (工具) vs Skills (技能)

Tools 是底层原子能力（Python 函数调用），Skills 是上层编排模板（Prompt + 工作流），用户通过 Markdown 文件定义。

| 维度 | Tools | Skills |
|---|---|---|
| 是什么 | 原子 API/函数调用 | Prompt 模板 + 工具编排 |
| 谁创建 | 开发者写 Python 代码 | **用户**通过前端或 Markdown |
| 存储 | `app/tool/*.py` | `data/skills/*.md` |
| 类比 | 瑞士军刀的单件工具 | 食谱 |
| 可否从 GitHub 加载 | 否 | ✅ 下载 .md 即用 |

### Memory — 四层架构

参考 Claude Code 设计，基于文件系统 + YAML frontmatter：

| 层 | 存储 | 加载时机 |
|---|---|---|
| 热层 | `data/memory/MEMORY.md` 索引 | 每次 session |
| 温层 | `data/memory/*.md` 主题文件 | 关键词检索，最多 5 个 |
| 冷层 | `data/sessions/*.json` | 搜索访问 |
| 向量层 | Milvus (可选) | 语义检索 fallback |

四种记忆类型：`user`(用户偏好)、`project`(项目上下文)、`feedback`(用户反馈)、`reference`(外部资源)。

### Plan Mode

```
用户输入 → LLM 生成计划(3-7步) → 逐步执行(每步走工具分发) → LLM 总结
         SSE: plan_created       SSE: step_start/completed    SSE: text
```

### Agent Mode

```
用户输入 → intent_analyzer 选择工具 → 工具执行 → LLM 合成回答
         → web_search / python_execute / browser_use / str_replace_editor / chat
```

## 快速开始

```bash
# 安装依赖
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt

# 配置 (复制示例文件后填入 API key)
cp config/config.example.toml config/config.toml

# 启动
python web_server.py    # → http://localhost:8000
```

配置示例 (`config/config.toml`)：

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
| `/agent/stream` | POST | Agent 模式 (SSE) |
| `/plan/stream` | POST | Plan 模式 (SSE) |
| `/execute/python` | POST | Python 代码直接执行 (SSE) |
| `/execute/stream` | POST | 纯文本 LLM 对话 (SSE) |
| `/research/pipeline` | POST | 科研全流程流水线 (SSE) |
| `/upload` | POST | 文件上传 |

### 记忆 / 技能 / 定时任务

| 端点 | 方法 | 说明 |
|---|---|---|
| `/memory` | GET/POST | 记忆列表/创建 |
| `/memory/{name}` | GET/DELETE | 记忆读取/删除 |
| `/memory/search` | POST | 关键词搜索 |
| `/skills` | GET/POST | 技能列表/创建 |
| `/skills/{name}` | GET/DELETE | 技能读取/删除 |
| `/skills/load` | POST | 从 URL 加载技能 |
| `/scheduler/jobs` | GET/POST | 定时任务列表/创建 |
| `/scheduler/jobs/{id}` | PUT/DELETE | 启用停用/删除 |
| `/scheduler/jobs/{id}/history` | GET | 执行历史 |

## SSE 事件类型

| event type | 携带字段 | 说明 |
|---|---|---|
| `text` | `content` | LLM 文本增量 |
| `status` | `content` | 状态消息 |
| `tool_call` | `tools`, `args` | 工具调用通知 |
| `tool_result` | `content` | 工具执行结果 |
| `search_result` | `query`, `results` | 搜索结果 |
| `plan_created` | `plan_id`, `title`, `steps` | 计划生成 |
| `step_start` / `step_completed` | `step_index` | 步骤进度 |
| `step_error` | `step_index`, `error` | 步骤失败 |
| `done` | — | 流结束 |
| `error` | `content` | 错误消息 |

## 创建自定义 Skill

**方法 1 — 前端创建**: 侧边栏 → 技能管理 → 新建技能 → 填写表单 → 保存

**方法 2 — 从 URL 加载**: 技能管理 → 从URL加载 → 输入 GitHub Raw URL → 加载

**方法 3 — 手动创建文件**，放在 `data/skills/*.md`：

```markdown
---
name: literature-review
description: 文献综述
tools: [web_search, python_execute]
trigger_keywords: [文献综述, 调研, 研究现状, literature review]
---

# 文献综述技能

## 执行步骤
1. 用 web_search 搜索相关论文（中英文，至少 5 篇）
2. 提取核心贡献和方法
3. 按子领域分类整理
4. 生成 Markdown 综述报告
```

## 项目进展

| 模块 | 状态 |
|---|---|
| Agent 对话 | ✅ |
| Plan Mode | ✅ |
| Python 执行 | ✅ |
| 网络搜索 | ✅ |
| 定时任务 | ✅ |
| 记忆系统 | ✅ Phase 1 |
| 技能系统 | ✅ Phase 1 |
| Memory 检索/自动捕获 | 🔄 Phase 2-3 |
| RAG 文档检索 | 🔄 计划中 |

## 技术栈

Python 3.12 + FastAPI + SSE · 通义千问 (DashScope) · APScheduler · LangSmith · Playwright + browser-use · pdfplumber + PyMuPDF

## 致谢

本项目基于 [OpenManus](https://github.com/FoundationAgents/OpenManus) 构建。感谢 MetaGPT 社区和 OpenManus 贡献者。

## 许可证

MIT License
