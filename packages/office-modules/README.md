# office-modules

office 领域能力包。

承接内容：
- tools
- roles
- agent module
- output module
- memory module
- prompts / profiles
- workflows
- manifest.json

说明：
- 这是 capability modules（能力模块）层。
- 多 agent 不会被削弱，而是作为可装载能力的一部分迁到这里。
- 当前具体 office role 实现已经开始从 `app/agents/*` 迁入这里，`app/agents/*` 只保留兼容导出层。
- 当前默认导出：
  - `Office Agent Module`
  - `Workspace Tool Module`
  - `File Tool Module`
  - `Web Tool Module`
  - `Write Tool Module`
  - `Session Tool Module`
  - `Output Module`
  - `Overlay Memory Module`
- 当前工具模块已经不是纯展示分组：
  - 主核会通过 `ToolExecutionBus` 把具体工具调用路由到对应 `ToolModule`
  - `Blackboard` 和前端运行轨迹也会显示实际命中的 `ToolModule`
