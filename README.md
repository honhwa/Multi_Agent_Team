# Multi_Agent_Robot

![Mat Multi_Agent_Robot logo](docs/assets/brand/mat-logo-horizontal.jpg)

[English README](README.en.md)

## 核心定位（最终版）

`Multi_Agent_Robot` 现在采用 **极简主核架构**：

- 一个稳定 Kernel（启动、上下文、状态）
- 一个 LLM 中央调度器（`app/kernel/llm_router.py`）
- 12 个完全独立的 Agent 插件（`app/agents/*_agent`）

目标是：**层级最少、代码最少、维护最简单、单 Agent 故障不影响全局**。

## 一眼看懂底层逻辑

只有 5 步：

1. 前端请求进入 `POST /api/chat`
2. `LLMRouter` 读取 12 个 Agent 的 `manifest.json`
3. LLM 生成最短执行步骤（1~4 步）
4. 对应 Agent 执行 `handle_task`
5. 汇总返回，并写入会话

如果云端 LLM 暂时不可用：系统自动进入本地稳态回复，不报红、不崩溃。

## 独立 Agent 列表（12）

1. worker_agent
2. researcher_agent
3. planner_agent
4. critic_agent
5. executor_agent
6. summarizer_agent
7. coder_agent
8. reviewer_agent
9. coordinator_agent
10. tool_user_agent
11. office_specialist_agent
12. navigator_agent

每个 Agent 目录只包含：

- `agent.py`：统一入口 `handle_task`
- `manifest.json`：能力描述与版本

## 目录（简化视角）

```text
app/
├── agents/                 # 12 independent agents
├── kernel/
│   ├── host.py             # stable kernel host
│   └── llm_router.py       # central LLM router
├── api/
└── main.py                 # FastAPI endpoints
```

## 快速启动

```bash
git clone https://github.com/jonhncatt/Multi_Agent_Robot.git
cd Multi_Agent_Robot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./run.sh
```

访问：<http://127.0.0.1:8080>

## 关键 API

- `POST /api/chat`：走 LLM 中央调度 + 独立 Agent 执行
- `POST /api/chat/stream`：流式返回
- `GET /api/agents`：查看已加载 Agent
- `POST /api/agents/{name}/reload`：热重载单 Agent
- `GET /api/health`：平台健康状态

## 现在删掉了什么（为简单而删）

- 旧的复杂 chat 主链路（`_process_chat_request`）已删除
- 重复的路由包装文件已删除（`app/api/routes/chat.py`、`app/api/routes/agents.py`）
- `main.py` 无用 import 与历史分支已清理

## LLM 环境变量（通用）

```env
OFFICETOOL_LLM_PROVIDER=openai
OFFICETOOL_LLM_AUTH_MODE=auto
OFFICETOOL_LLM_API_KEY=<YOUR_API_KEY>
OFFICETOOL_LLM_BASE_URL=https://api.openai.com/v1
OFFICETOOL_LLM_MODEL=gpt-5.1-chat
OFFICETOOL_ROUTER_MODEL=gpt-4o-mini
```

说明：

- 支持 OpenAI-compatible 与 Codex auth。
- 若未配置可用凭据，`/api/chat` 无法返回真实模型结果。

## 开发说明

- 新增/替换 Agent：只改 `app/agents/<name>_agent/`。
- Agent 热插拔：修改后调用 `POST /api/agents/{name}/reload`。
- 不需要改 Kernel 主链路，即可演进单个 Agent。

## 计划调整（简洁版）

1. 只继续保留一条主链路：`/api/chat -> llm_router -> agents`
2. 每次改动优先删代码，而不是加抽象层
3. Agent 只做单一职责，避免再回到“工业级巨型框架”
