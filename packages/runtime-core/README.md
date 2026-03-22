# runtime-core

统一底层运行时。

承接内容：
- auth / provider
- storage / session / upload
- module manifest / loader / supervisor
- shadow / promote / rollback
- attachment parsing 与 document cache
- capability loader（能力模块加载）
- KernelHost
- Blackboard

说明：
- 这里不承接具体 office 角色和工具。
- 它负责把 `agent-core` 和 `capability-modules` 粘起来。
- 当前已支持按顺序加载多个 capability modules，并把它们交给上层做 registry / tools 装配。
- 当前还开始承接：
  - `KernelHost`：主核入口
  - `Blackboard`：请求级共享状态
  - `ToolExecutionBus`：按 `ToolModule` 路由具体工具执行
