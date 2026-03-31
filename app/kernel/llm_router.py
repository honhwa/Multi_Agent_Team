from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from app.config import load_config
from app.openai_auth import OpenAIAuthManager


class LLMRouter:
    """
    极简中央调度器：
    - discover_agents: 扫描 app/agents/*_agent
    - route: 用单一 LLM 产生执行步骤
    - execute: 顺序/并行执行步骤
    - reload_single_agent: 热重载单 Agent
    """

    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel
        self._config = load_config()
        self._auth_manager = OpenAIAuthManager(self._config)
        self.model = str(os.environ.get("OFFICETOOL_ROUTER_MODEL") or "gpt-4o-mini").strip()
        timeout_raw = str(os.environ.get("OFFICETOOL_AGENT_STEP_TIMEOUT_SEC") or "25").strip()
        try:
            timeout_val = int(timeout_raw)
        except Exception:
            timeout_val = 25
        self.step_timeout_sec = max(5, min(120, timeout_val))
        self.client = self._build_client()
        self._last_llm_error = ""
        self.agents: dict[str, Any] = {}
        self.manifests: dict[str, dict[str, Any]] = {}
        self._discover_lock = asyncio.Lock()
        self._reload_lock = asyncio.Lock()

    def _build_client(self) -> AsyncOpenAI | None:
        resolved = self._auth_manager.resolve()
        if resolved.mode != "api_key" or not resolved.available:
            return None
        api_key = str(resolved.api_key or "").strip()
        if not api_key:
            return None
        base_url = str(
            os.environ.get("OFFICETOOL_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or self._config.openai_base_url
            or ""
        ).strip()
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        try:
            return AsyncOpenAI(**kwargs)
        except Exception:
            return None

    def _looks_like_greeting(self, text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        markers = {
            "hi",
            "hello",
            "hey",
            "你好",
            "您好",
            "在吗",
            "在不在",
            "早上好",
            "下午好",
            "晚上好",
        }
        if lowered in markers:
            return True
        if len(lowered) <= 6 and any(item in lowered for item in markers):
            return True
        return False

    def _strip_internal_markers(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        lines: list[str] = []
        for line in raw.splitlines():
            normalized = str(line or "").strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if "任务已接收" in normalized:
                continue
            if "当前进入稳态执行模式" in normalized:
                continue
            if "请对上一结果做精炼复核" in normalized:
                continue
            if lowered.startswith("[worker_agent]") or lowered.startswith("[reviewer_agent]"):
                normalized = re.sub(r"^\[[a-z_]+\]\s*", "", normalized, flags=re.IGNORECASE).strip()
            normalized = re.sub(r"^(worker|reviewer|planner|coder|agent)[\s_-]*agent[:：]?\s*", "", normalized, flags=re.IGNORECASE)
            if normalized:
                lines.append(normalized)
        if lines:
            return "\n".join(lines).strip()
        return raw

    def _normalize_task_text(self, text: Any) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        if len(normalized) > 1200:
            normalized = normalized[:1200].rstrip()
        return normalized

    def _extract_previous_output(self, context: Any | None = None) -> str:
        if not isinstance(context, dict):
            return ""
        prev = list(context.get("previous_results") or [])
        for item in reversed(prev):
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "") != "success":
                continue
            cleaned = self._strip_internal_markers(str(item.get("result") or ""))
            if cleaned:
                return cleaned
        return ""

    def _normalize_plan(self, plan: dict[str, Any], *, user_query: str) -> dict[str, Any]:
        normalized_steps: list[dict[str, str]] = []
        for raw in list(plan.get("steps") or []):
            if not isinstance(raw, dict):
                continue
            agent = str(raw.get("agent") or "").strip().lower()
            task = self._normalize_task_text(raw.get("task"))
            if not task:
                continue
            if agent not in self.agents:
                candidates = self._manifest_name_candidates(agent)
                agent = next((item for item in candidates if item in self.agents), "")
            if not agent:
                continue
            normalized_steps.append({"agent": agent, "task": task})
            if len(normalized_steps) >= 4:
                break

        if not normalized_steps:
            return self._fallback_plan(user_query)

        return {
            "plan": str(plan.get("plan") or "llm_router_plan"),
            "parallel": bool(plan.get("parallel", False)),
            "steps": normalized_steps,
        }

    async def _complete_text(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        for _attempt in range(2):
            if self.client is None:
                self.client = self._build_client()
            if self.client is None:
                return None
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = str(resp.choices[0].message.content or "").strip()
                return text or None
            except Exception as exc:
                self._last_llm_error = str(exc)
                self.client = None
                continue
        return None

    def _agent_offline_fallback(self, agent_name: str, task: str, context: Any | None = None) -> str:
        text = str(task or "").strip()
        lowered = text.lower()
        if self._looks_like_greeting(text):
            return "你好，我在。告诉我你现在要完成什么，我直接给你可执行结果。"
        if agent_name == "reviewer_agent":
            previous = self._extract_previous_output(context)
            if previous:
                return previous
            return "我已完成复核。你给我一个更具体目标，我会直接输出最终可执行答案。"
        if agent_name == "planner_agent" or any(item in lowered for item in ("计划", "规划", "plan", "roadmap")):
            return (
                "建议三步推进：\n"
                "1. 先定义目标与完成标准。\n"
                "2. 再拆分为可执行子任务并安排优先级。\n"
                "3. 最后逐项验证结果并留出复盘动作。"
            )
        if agent_name == "researcher_agent" or any(item in lowered for item in ("调研", "research", "资料", "检索")):
            return (
                "我会按“范围定义 -> 信息收集 -> 结论归纳”的顺序输出结果。"
            )
        return f"已收到你的任务：{text}。我会直接给出简洁、可执行的结果。"

    @property
    def agents_dir(self) -> Path:
        return (Path(__file__).resolve().parent.parent / "agents").resolve()

    def list_agents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in sorted(self.manifests.keys()):
            manifest = dict(self.manifests.get(name) or {})
            rows.append(
                {
                    "name": name,
                    "version": str(manifest.get("version") or "1.0"),
                    "description": str(manifest.get("description") or ""),
                    "capabilities": list(manifest.get("capabilities") or []),
                    "loaded": name in self.agents,
                }
            )
        return rows

    def _derive_class_name(self, folder_name: str) -> str:
        base = str(folder_name or "").strip().lower()
        if base.endswith("_agent"):
            base = base[: -len("_agent")]
        camel = "".join(part.capitalize() for part in base.split("_") if part)
        return f"{camel}Agent" if camel else "Agent"

    def _manifest_name_candidates(self, name: str) -> list[str]:
        raw = str(name or "").strip().lower()
        if not raw:
            return []
        candidates = [raw]
        if raw.endswith("_agent"):
            candidates.append(raw[: -len("_agent")])
        else:
            candidates.append(f"{raw}_agent")
        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            if item and item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    async def discover_agents(self, force: bool = False) -> dict[str, Any]:
        async with self._discover_lock:
            if self.agents and not force:
                return {"ok": True, "loaded": sorted(self.agents.keys()), "count": len(self.agents), "cached": True}

            loaded: list[str] = []
            manifests: dict[str, dict[str, Any]] = {}
            agents: dict[str, Any] = {}
            if not self.agents_dir.exists():
                return {"ok": True, "loaded": [], "count": 0, "warning": f"Agents dir not found: {self.agents_dir}"}

            for agent_dir in sorted(self.agents_dir.iterdir(), key=lambda p: p.name):
                if not agent_dir.is_dir():
                    continue
                if not agent_dir.name.endswith("_agent"):
                    continue
                manifest_path = agent_dir / "manifest.json"
                if not manifest_path.exists():
                    continue

                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest_name = str(manifest.get("name") or agent_dir.name).strip().lower()
                    if not manifest_name:
                        manifest_name = agent_dir.name
                    manifest["name"] = manifest_name
                    module_path = f"app.agents.{agent_dir.name}.agent"
                    mod = importlib.import_module(module_path)
                    class_name = str(manifest.get("entry_class") or "").strip() or self._derive_class_name(agent_dir.name)
                    agent_cls = getattr(mod, class_name)
                    try:
                        instance = agent_cls(kernel=self.kernel)
                    except TypeError:
                        instance = agent_cls()
                    manifests[manifest_name] = manifest
                    agents[manifest_name] = instance
                    loaded.append(manifest_name)
                except Exception as exc:
                    print(f"[LLMRouter] skip broken agent {agent_dir.name}: {exc}")

            self.manifests = manifests
            self.agents = agents
            return {"ok": True, "loaded": sorted(loaded), "count": len(loaded), "cached": False}

    async def reload_single_agent(self, name: str) -> dict[str, Any]:
        async with self._reload_lock:
            await self.discover_agents(force=False)
            candidates = self._manifest_name_candidates(name)
            target = ""
            for item in candidates:
                if item in self.manifests:
                    target = item
                    break
            if not target:
                return {"ok": False, "error": f"Agent not found: {name}"}

            agent_dir = self.agents_dir / target
            if not agent_dir.is_dir():
                return {"ok": False, "error": f"Agent directory not found: {target}"}
            manifest_path = agent_dir / "manifest.json"
            if not manifest_path.exists():
                return {"ok": False, "error": f"Manifest missing: {target}/manifest.json"}

            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_name = str(manifest.get("name") or target).strip().lower() or target
                module_path = f"app.agents.{agent_dir.name}.agent"
                mod = importlib.import_module(module_path)
                mod = importlib.reload(mod)
                class_name = str(manifest.get("entry_class") or "").strip() or self._derive_class_name(agent_dir.name)
                agent_cls = getattr(mod, class_name)
                try:
                    instance = agent_cls(kernel=self.kernel)
                except TypeError:
                    instance = agent_cls()
                self.manifests[manifest_name] = manifest
                self.agents[manifest_name] = instance
                return {"ok": True, "name": manifest_name, "version": str(manifest.get("version") or "1.0")}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

    async def _json_completion(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 900) -> dict[str, Any]:
        raw = await self._complete_text(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not raw:
            return {"ok": False, "error": "llm unavailable"}
        try:
            payload = raw
            if payload.startswith("```"):
                payload = payload.strip("`")
                if payload.lower().startswith("json"):
                    payload = payload[4:].strip()
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
            return {"ok": False, "error": "invalid json object"}
        except Exception:
            return {"ok": False, "error": "invalid json content"}

    def _fallback_plan(self, user_query: str) -> dict[str, Any]:
        text = self._normalize_task_text(user_query).lower()
        if self._looks_like_greeting(text):
            return {
                "plan": "fallback_greeting",
                "parallel": False,
                "steps": [{"agent": "worker_agent", "task": self._normalize_task_text(user_query)}],
            }
        first = "worker_agent"
        if any(key in text for key in ("research", "调研", "资料", "web", "查找", "检索")):
            first = "researcher_agent"
        elif any(key in text for key in ("计划", "规划", "plan", "roadmap", "里程碑")):
            first = "planner_agent"
        elif any(key in text for key in ("代码", "bug", "修复", "refactor", "python", "ts", "js")):
            first = "coder_agent"
        elif any(key in text for key in ("总结", "摘要", "summary")):
            first = "summarizer_agent"

        second = "reviewer_agent"
        if first == "reviewer_agent":
            second = "worker_agent"
        return {
            "plan": "fallback_router",
            "parallel": False,
            "steps": [
                {"agent": first, "task": self._normalize_task_text(user_query)},
                {"agent": second, "task": "请对上一结果做精炼复核，输出最终可执行答复。"},
            ],
        }

    async def route(self, user_query: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        await self.discover_agents(force=False)
        if not self.agents:
            return {"plan": "fallback_no_agents", "parallel": False, "steps": []}

        agent_lines = []
        for name in sorted(self.manifests.keys()):
            meta = self.manifests.get(name) or {}
            desc = str(meta.get("description") or "")
            capabilities = ", ".join(str(item) for item in list(meta.get("capabilities") or [])[:6])
            agent_lines.append(f"- {name}: {desc}; capabilities={capabilities}")
        agents_info = "\n".join(agent_lines)
        history_hint = ""
        if history:
            recent = [str(item.get("text") or "") for item in history[-3:] if isinstance(item, dict)]
            if recent:
                history_hint = "\n最近上下文：" + " | ".join(recent)

        system_prompt = (
            "你是多 Agent 系统的唯一中央调度器。"
            "目标是最少步骤、最清晰分工。"
            "只返回 JSON，不要解释。"
        )
        user_prompt = (
            f"可用 Agent:\n{agents_info}\n\n"
            f"用户问题：{user_query}{history_hint}\n\n"
            "返回格式必须是：\n"
            "{\n"
            '  "plan": "一句话调度思路",\n'
            '  "parallel": false,\n'
            '  "steps": [\n'
            '    {"agent": "agent_name", "task": "具体任务"}\n'
            "  ]\n"
            "}\n"
            "要求：steps 1~4 步；agent 必须来自可用列表。"
        )
        candidate = await self._json_completion(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.25)
        if not bool(candidate.get("ok", True)) or not isinstance(candidate.get("steps"), list):
            return self._fallback_plan(user_query)
        return self._normalize_plan(candidate, user_query=user_query)

    async def _run_step(self, step: dict[str, Any], *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        name = str(step.get("agent") or "").strip().lower()
        task = self._normalize_task_text(step.get("task"))
        if name not in self.agents:
            return {"agent": name, "status": "failed", "error": "Agent not found"}
        agent = self.agents[name]
        try:
            result = await agent.handle_task({"query": task, "context": context or {"router": "llm_router"}})
            if isinstance(result, dict):
                return {"agent": name, "status": "success", **result}
            return {"agent": name, "status": "success", "result": str(result)}
        except Exception as exc:
            return {"agent": name, "status": "failed", "error": str(exc)}

    async def _run_step_with_timeout(self, step: dict[str, Any], *, context: dict[str, Any] | None = None) -> dict[str, Any]:
        agent_name = str(step.get("agent") or "").strip().lower()
        try:
            return await asyncio.wait_for(
                self._run_step(step, context=context),
                timeout=float(self.step_timeout_sec),
            )
        except asyncio.TimeoutError:
            return {
                "agent": agent_name,
                "status": "failed",
                "error": f"step timeout ({self.step_timeout_sec}s)",
            }

    async def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        steps = [item for item in list(plan.get("steps") or []) if isinstance(item, dict)]
        if not steps:
            return {"plan": str(plan.get("plan") or "empty"), "results": []}

        if bool(plan.get("parallel")):
            tasks = [
                self._run_step_with_timeout(
                    step,
                    context={
                        "router": "llm_router",
                        "mode": "parallel",
                        "step_index": idx,
                        "previous_results": [],
                    },
                )
                for idx, step in enumerate(steps, start=1)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            normalized: list[dict[str, Any]] = []
            for item in results:
                if isinstance(item, Exception):
                    normalized.append({"status": "failed", "error": str(item)})
                else:
                    normalized.append(dict(item))
            return {"plan": str(plan.get("plan") or "parallel"), "results": normalized}

        output: list[dict[str, Any]] = []
        for idx, step in enumerate(steps, start=1):
            output.append(
                await self._run_step_with_timeout(
                    step,
                    context={
                        "router": "llm_router",
                        "mode": "sequential",
                        "step_index": idx,
                        "previous_results": list(output)[-6:],
                        "plan": str(plan.get("plan") or ""),
                    },
                )
            )
        return {"plan": str(plan.get("plan") or "sequential"), "results": output}

    async def agent_reason(
        self,
        *,
        agent_name: str,
        agent_description: str,
        capabilities: list[str],
        task: str,
        context: Any | None = None,
    ) -> str:
        system_prompt = (
            f"你现在扮演 {agent_name}。\n"
            f"角色说明：{agent_description}\n"
            f"能力：{', '.join(capabilities)}\n"
            "输出要简洁、可执行、避免空话。"
        )
        user_prompt = f"任务：{task}\n上下文：{json.dumps(context or {}, ensure_ascii=False)}"
        text = await self._complete_text(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        if text:
            return text
        return self._agent_offline_fallback(agent_name, task, context)

    async def summarize(
        self,
        *,
        user_query: str,
        plan: dict[str, Any],
        execution: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        results = list(execution.get("results") or [])
        if not results:
            return "当前没有可执行结果，请检查 Agent 加载状态。"

        system_prompt = (
            "你是最终答复生成器。基于多 Agent 结果，输出简洁明确的最终答复。"
            "结构：先结论，再关键要点。"
        )
        user_prompt = (
            f"用户问题：{user_query}\n"
            f"调度计划：{json.dumps(plan, ensure_ascii=False)}\n"
            f"执行结果：{json.dumps(results, ensure_ascii=False)}\n"
        )
        text = await self._complete_text(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=1200,
        )
        if text:
            return text

        for item in reversed(results):
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "") != "success":
                continue
            cleaned = self._strip_internal_markers(str(item.get("result") or ""))
            if cleaned:
                return cleaned
        if self._looks_like_greeting(user_query):
            return "你好，我在。告诉我你想先做什么，我直接帮你完成。"
        return "已完成执行。给我一个更具体目标，我会直接返回最终答案。"
