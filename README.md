# LuminAgent — 多模态科研AI助手

基于 [OpenManus](https://github.com/FoundationAgents/OpenManus) 构建的多模态科研辅助 Agent。

## 快速开始

```bash
# 1. 后端
cd OpenManus
cp config/config.example.toml config/config.toml   # 编辑填入 API key
python web_server.py                                # → http://localhost:8000

# 2. 前端
cd openmanus-frontend
npm install && npm start                            # → http://localhost:3000
```

## 项目结构

```
LuminAgent/
├── OpenManus/              后端 (基于 OpenManus 框架扩展)
│   ├── web_server.py           FastAPI 主服务 (LuminAgent 新增)
│   ├── app/                    应用核心
│   │   ├── agent/              Agent 层 (复用 OpenManus)
│   │   ├── tool/               工具层 (复用 + 扩展)
│   │   ├── flow/               Plan-then-Execute (复用 OpenManus)
│   │   ├── memory_manager.py   记忆系统 (LuminAgent 新增)
│   │   ├── scheduler.py        定时任务 (LuminAgent 新增)
│   │   ├── skill_manager.py    技能管理 (LuminAgent 新增)
│   │   └── ...
│   └── data/                   运行时数据 (LuminAgent 新增)
├── openmanus-frontend/      React 前端 (LuminAgent 新增)
└── README.md
```

## 文档

- [OpenManus/README.md](OpenManus/README.md) — 详细架构、API、模块说明
- [openmanus-frontend/README.md](openmanus-frontend/README.md) — 前端文件结构和组件说明

## 许可证

MIT License — 基于 OpenManus (MIT) 构建
