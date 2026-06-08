# OpenManus Frontend

LuminAgent 前端 — React 19 + Ant Design 6，连接 OpenManus 后端 FastAPI 服务。

## 快速开始

```bash
# 1. 启动后端 (需要先启动)
cd ../OpenManus && python web_server.py   # → http://localhost:8000

# 2. 启动前端
cd openmanus-frontend
npm install
npm start                                  # → http://localhost:3000
```

## 文件结构

```
src/
├── index.js                  # React 入口，挂载到 DOM
├── App.js                    # 路由配置 (React Router v6)
├── App.css                   # 全局样式
├── api/
│   └── index.js              # API Helper (agentApi, skillApi, toolApi)
├── layout/
│   └── MainLayout.js         # 主布局 — Sider 侧边栏 + Header + Content
└── pages/
    ├── Chat.js               # 💬 Agent 对话 — 核心页面
    │                           SSE 流式接收，支持 Agent/Plan/普通 三种模式
    │                           Python 代码编辑器弹窗
    │                           搜索结果浮窗 → 二级 Drawer 详情
    │                           Plan Card 步骤进度展示
    ├── ScheduledTasks.js     # ⏰ 定时任务管理
    │                           任务列表 / 新建(cron表达式+快捷预设) / 执行历史
    ├── MemoryManager.js      # 🧠 记忆管理
    │                           记忆列表 / 新建(Markdown) / 详情查看
    │                           四种类型: user / project / feedback / reference
    ├── Skills.js             # 📦 技能管理
    │                           上方: 可用工具列表 (从 GET / 动态加载)
    │                           下方: 用户自定义技能 CRUD + 从 URL 加载
    ├── Tools.js              # 🔧 工具管理 (基础 CRUD 表格)
    ├── MultiAgent.js         # 👥 多 Agent 协同
    ├── ApiTest.js            # 🔌 API 测试页面
    ├── Dashboard.js          # 📊 仪表盘
    └── EmailTestPage.jsx     # 📧 邮件测试页
```

## 页面说明

| 页面 | 路由 | 说明 |
|---|---|---|
| Agent 对话 | `/chat` (默认首页 `/`) | 核心交互页面。三种模式：Plan → 先计划后执行、Agent → 意图分析+工具路由、普通 → 纯 LLM 对话 |
| 多 Agent 协同 | `/multi-agent` | 多 Agent 协作 |
| 定时任务 | `/scheduled-tasks` | Cron 定时任务 CRUD + 执行历史 |
| API 测试 | `/api-test` | 调试后端 API |
| 记忆管理 | `/memory` | 持久化记忆文件 CRUD |
| 工具管理 | `/tools` | 底层工具列表 |
| 技能管理 | `/skills` | 工具列表 + 用户自定义技能 |
| 仪表盘 | `/dashboard` | 概览页 |

## 侧边栏菜单

菜单定义在 `layout/MainLayout.js` 的 `menuItems` 数组中，路由在 `App.js` 中注册：

```
💬 Agent对话       ← 默认首页
👥 多Agent协同
⏰ 定时任务
🔌 API测试
🧠 记忆管理
🔧 工具管理
📦 技能管理
📊 仪表盘
```

添加新页面时需同时修改 `App.js`(路由) 和 `MainLayout.js`(菜单)。

## SSE 事件处理

Chat 页面使用原生 `fetch` + `ReadableStream` 手动解析 SSE，处理以下事件类型：

| event type | 更新到 msg 的哪个字段 |
|---|---|
| `text` | `msg.content` — 流式追加 |
| `status` | `msg.stageText` |
| `tool_call` | `msg.toolCalls` — 追加工具调用标签 |
| `tool_result` | `msg.toolResult` — 绿色执行结果面板 |
| `search_result` | `msg.searchResults` — 搜索结果列表 |
| `plan_created` | `msg.plan` — Plan Card 步骤卡片 |
| `step_start` / `step_completed` / `step_error` | `msg.plan.steps[].status` |
| `error` | `msg.content` — 追加错误信息 |

## 消息状态结构

```javascript
{
  id: number,                 // Date.now() 时间戳
  role: 'user' | 'assistant',
  content: string,            // 累加的文本内容
  // 以下为 assistant 消息可选字段:
  searchResults: [...],       // 搜索结果
  stageText: string,          // 当前阶段状态
  toolCalls: [...],           // 工具调用标签
  toolResult: string,         // 工具执行结果原文
  plan: {                     // Plan 模式计划卡片
    plan_id, title,
    steps: [{text, status}]   // status: not_started | in_progress | completed | error
  }
}
```

## API 配置

前端默认连接 `http://127.0.0.1:8000`，通过环境变量覆盖：

```bash
REACT_APP_API_BASE_URL=http://your-host:8000 npm start
```

所有页面使用原生 `fetch()` 直接调用，`api/index.js` 为早期封装（部分页面未使用）。

## 技术栈

- React 19
- Ant Design 6
- React Router 7
- Create React App (react-scripts 5)
