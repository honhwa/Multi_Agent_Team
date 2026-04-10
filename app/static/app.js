const ReactRuntime = window.React;
const ReactDomRuntime = window.ReactDOM;
const htmRuntime = window.htm;

if (!ReactRuntime || !ReactDomRuntime || !htmRuntime) {
  const root = document.getElementById("root");
  if (root) {
    root.innerHTML = `
      <div style="padding:24px;font:14px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;color:#1f2328;">
        前端资源加载失败。请刷新页面；如果问题持续，请检查 /static/vendor 下的本地脚本是否可访问。
      </div>
    `;
  }
  throw new Error("Local frontend vendor scripts are unavailable.");
}

const { useEffect, useMemo, useRef, useState } = ReactRuntime;
const { createRoot } = ReactDomRuntime;
const html = htmRuntime.bind(ReactRuntime.createElement);

const SESSION_STORAGE_KEY = "vintage_programmer.session_id";
const STARTER_PROMPTS = [
  "帮我疏通这个仓库的主链路",
  "检查当前工作区并给我一个重构计划",
  "把这个页面改得更像 Codex",
];
const DEFAULT_SETTINGS = {
  model: "",
  max_output_tokens: 128000,
  max_context_turns: 2000,
  enable_tools: true,
  response_style: "normal",
};

function createMessage(role, text, options = {}) {
  return {
    id: options.id || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    text,
    pending: Boolean(options.pending),
    error: Boolean(options.error),
    createdAt: options.createdAt || "",
  };
}

function createLog(type, text) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    text,
    createdAt: new Date().toISOString(),
  };
}

function formatTime(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function parseSseChunk(chunk) {
  const lines = String(chunk || "").split("\n");
  let event = "message";
  const dataLines = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim() || "message";
      return;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  });
  if (!dataLines.length) return null;
  try {
    return { event, payload: JSON.parse(dataLines.join("\n")) };
  } catch {
    return { event, payload: { raw: dataLines.join("\n") } };
  }
}

function roleLabel(role) {
  if (role === "user") return "You";
  if (role === "assistant") return "Vintage Programmer";
  return "System";
}

function pushLogWithLimit(setter, type, text) {
  setter((prev) => [createLog(type, text), ...prev].slice(0, 24));
}

function fileNameFromHealth(health) {
  const label = String(((health || {}).runtime_status || {}).workspace_label || "").trim();
  if (label) return label;
  const path = String((health && health.workspace_root) || "").trim();
  if (!path) return "workspace";
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || "workspace";
}

function extractSessionMessages(data) {
  const turns = Array.isArray(data.turns) ? data.turns : [];
  return turns.map((turn) =>
    createMessage(
      String(turn.role || "").toLowerCase() === "user" ? "user" : "assistant",
      String(turn.text || ""),
      {
        createdAt: String(turn.created_at || ""),
      },
    ),
  );
}

function starterPromptChips(setDraft, handleSend) {
  return STARTER_PROMPTS.map((text) =>
    html`
      <button
        key=${text}
        className="starter-chip"
        type="button"
        onClick=${() => {
          setDraft(text);
          setTimeout(() => handleSend(text), 0);
        }}
      >
        ${text}
      </button>
    `,
  );
}

function App() {
  const [health, setHealth] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [sessionAgentState, setSessionAgentState] = useState({});
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [drawerView, setDrawerView] = useState("");
  const [logs, setLogs] = useState([]);
  const [lastResponse, setLastResponse] = useState(null);
  const [pendingUploads, setPendingUploads] = useState([]);
  const [chatSettings, setChatSettings] = useState(DEFAULT_SETTINGS);
  const [modelTouched, setModelTouched] = useState(false);
  const [lastError, setLastError] = useState("");
  const [toolTimeline, setToolTimeline] = useState([]);
  const [stageTimeline, setStageTimeline] = useState([]);
  const [draftingPendingMessageId, setDraftingPendingMessageId] = useState("");
  const fileInputRef = useRef(null);
  const chatListRef = useRef(null);

  useEffect(() => {
    const stored = window.localStorage.getItem(SESSION_STORAGE_KEY) || "";
    if (stored) setSessionId(stored);
  }, []);

  useEffect(() => {
    if (!sessionId) {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }, [sessionId]);

  useEffect(() => {
    if (!health || modelTouched) return;
    setChatSettings((prev) => ({
      ...prev,
      model: String(prev.model || health.default_model || "").trim(),
    }));
  }, [health, modelTouched]);

  useEffect(() => {
    if (!chatListRef.current) return;
    chatListRef.current.scrollTop = chatListRef.current.scrollHeight;
  }, [messages, drawerView]);

  useEffect(() => {
    async function boot() {
      await refreshHealth();
      await refreshSessions();
      const stored = window.localStorage.getItem(SESSION_STORAGE_KEY) || "";
      if (stored) {
        await loadSession(stored, { silentNotFound: true });
      }
    }
    boot();
  }, []);

  async function refreshHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error(`health ${res.status}`);
      const data = await res.json();
      setHealth(data);
      return data;
    } catch (err) {
      const detail = String(err.message || err);
      setLastError(detail);
      pushLogWithLimit(setLogs, "error", `刷新状态失败：${detail}`);
      return null;
    }
  }

  async function refreshSessions() {
    try {
      const res = await fetch("/api/sessions?limit=80");
      if (!res.ok) throw new Error(`sessions ${res.status}`);
      const data = await res.json();
      const list = Array.isArray(data.sessions) ? data.sessions : [];
      setSessions(list);
      return list;
    } catch (err) {
      const detail = String(err.message || err);
      setLastError(detail);
      pushLogWithLimit(setLogs, "error", `刷新线程失败：${detail}`);
      return [];
    }
  }

  async function createSession() {
    const res = await fetch("/api/session/new", { method: "POST" });
    if (!res.ok) throw new Error(`create session ${res.status}`);
    const data = await res.json();
    const sid = String(data.session_id || "").trim();
    if (!sid) throw new Error("session id missing");
    setSessionId(sid);
    setMessages([]);
    setLastResponse(null);
    setSessionAgentState({});
    setToolTimeline([]);
    setStageTimeline([]);
    await refreshSessions();
    pushLogWithLimit(setLogs, "system", `已创建新线程 ${sid.slice(0, 8)}`);
    return sid;
  }

  async function loadSession(targetSessionId, options = {}) {
    const sid = String(targetSessionId || "").trim();
    if (!sid) return false;
    setLoadingSession(true);
    try {
      const res = await fetch(`/api/session/${encodeURIComponent(sid)}?max_turns=120`);
      if (!res.ok) {
        if (res.status === 404 && options.silentNotFound) return false;
        throw new Error(`session ${res.status}`);
      }
      const data = await res.json();
      setMessages(extractSessionMessages(data));
      setSessionAgentState((data && data.agent_state) || {});
      setSessionId(sid);
      setLastResponse(null);
      setToolTimeline([]);
      setStageTimeline([]);
      pushLogWithLimit(setLogs, "system", `已载入线程 ${sid.slice(0, 8)}`);
      return true;
    } catch (err) {
      const detail = String(err.message || err);
      setLastError(detail);
      pushLogWithLimit(setLogs, "error", `载入线程失败：${detail}`);
      return false;
    } finally {
      setLoadingSession(false);
    }
  }

  async function handleNewSession() {
    try {
      await createSession();
    } catch (err) {
      const detail = String(err.message || err);
      setLastError(detail);
      pushLogWithLimit(setLogs, "error", `新线程失败：${detail}`);
    }
  }

  async function uploadFiles(files) {
    const uploaded = [];
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/upload", {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        let detail = `upload ${res.status}`;
        try {
          const payload = await res.json();
          if (payload.detail) detail = String(payload.detail);
        } catch {
          // ignore parse errors
        }
        throw new Error(`${file.name}: ${detail}`);
      }
      uploaded.push(await res.json());
    }
    return uploaded;
  }

  async function handleSelectFiles(event) {
    const files = Array.from(event.currentTarget.files || []);
    if (!files.length) return;
    try {
      const uploaded = await uploadFiles(files);
      setPendingUploads((prev) => [...prev, ...uploaded]);
      pushLogWithLimit(setLogs, "system", `已添加 ${uploaded.length} 个附件`);
    } catch (err) {
      const detail = String(err.message || err);
      setLastError(detail);
      pushLogWithLimit(setLogs, "error", `附件上传失败：${detail}`);
    } finally {
      event.currentTarget.value = "";
    }
  }

  function removeUpload(fileId) {
    setPendingUploads((prev) => prev.filter((item) => item.id !== fileId));
  }

  async function handleSend(overrideText) {
    const messageText = String(overrideText != null ? overrideText : draft).trim();
    if (!messageText || sending) return;

    setSending(true);
    setLastError("");
    setDrawerView("run");
    setToolTimeline([]);
    setStageTimeline([]);

    let sid = sessionId;
    let pendingMessage = null;
    try {
      if (!sid) sid = await createSession();

      const userMessage = createMessage("user", messageText);
      pendingMessage = createMessage("assistant", "正在准备上下文...", { pending: true });
      setDraftingPendingMessageId(pendingMessage.id);
      setMessages((prev) => [...prev, userMessage, pendingMessage]);
      if (overrideText == null) setDraft("");

      const body = {
        session_id: sid,
        message: messageText,
        attachment_ids: pendingUploads.map((item) => item.id),
        settings: {
          ...chatSettings,
          model: String(chatSettings.model || (health && health.default_model) || "").trim(),
        },
      };

      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok || !res.body) {
        throw new Error(`stream ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalPayload = null;

      const replacePendingText = (text) => {
        setMessages((prev) =>
          prev.map((item) =>
            item.id === pendingMessage.id
              ? {
                  ...item,
                  text,
                }
              : item,
          ),
        );
      };

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

        let splitIndex = buffer.indexOf("\n\n");
        while (splitIndex >= 0) {
          const chunk = buffer.slice(0, splitIndex);
          buffer = buffer.slice(splitIndex + 2);
          const parsed = parseSseChunk(chunk);
          if (parsed) {
            const { event, payload } = parsed;
            if (event === "stage") {
              const detail = String(payload.detail || payload.label || payload.code || "处理中...");
              replacePendingText(detail);
              setStageTimeline((prev) => [
                {
                  id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                  phase: String(payload.phase || payload.code || ""),
                  label: String(payload.label || payload.phase || payload.code || "stage"),
                  status: String(payload.status || "running"),
                  detail,
                },
                ...prev,
              ].slice(0, 20));
              pushLogWithLimit(setLogs, "stage", detail);
            } else if (event === "trace") {
              const detail = String(payload.message || payload.raw || "");
              if (detail) pushLogWithLimit(setLogs, "trace", detail);
            } else if (event === "tool") {
              const item = payload.item || {};
              const name = String(item.name || "tool");
              const summary = String(payload.summary || item.summary || item.output_preview || "工具调用");
              setToolTimeline((prev) => [item, ...prev].slice(0, 24));
              pushLogWithLimit(setLogs, "tool", `${name}: ${summary}`);
            } else if (event === "final") {
              finalPayload = payload.response || null;
            } else if (event === "error") {
              throw new Error(String(payload.detail || "stream error"));
            }
          }
          splitIndex = buffer.indexOf("\n\n");
        }

        if (done) break;
      }

      if (!finalPayload) throw new Error("missing final payload");

      setMessages((prev) =>
        prev.map((item) =>
          item.id === pendingMessage.id
            ? createMessage("assistant", String(finalPayload.text || "(empty response)"))
            : item,
        ),
      );
      setLastResponse(finalPayload);
      setPendingUploads([]);
      setDrawerView("run");
      setSessionAgentState({
        agent_id: finalPayload.agent_id || "vintage_programmer",
        current_goal: String((((finalPayload.inspector || {}).run_state || {}).goal) || messageText),
        phase: String((((finalPayload.inspector || {}).run_state || {}).phase) || "report"),
        last_run_id: String(finalPayload.run_id || ""),
        last_model: String(finalPayload.effective_model || ""),
        tool_count: Array.isArray(finalPayload.tool_events) ? finalPayload.tool_events.length : 0,
        tool_names: Array.isArray(finalPayload.tool_events) ? finalPayload.tool_events.map((item) => item.name) : [],
        evidence_status: String((((finalPayload.inspector || {}).evidence || {}).status) || "not_needed"),
      });
      pushLogWithLimit(
        setLogs,
        "response",
        `收到回复，工具 ${Array.isArray(finalPayload.tool_events) ? finalPayload.tool_events.length : 0} 次`,
      );
      await Promise.all([refreshSessions(), refreshHealth()]);
    } catch (err) {
      const detail = String(err.message || err);
      setLastError(detail);
      pushLogWithLimit(setLogs, "error", `发送失败：${detail}`);
      setMessages((prev) => {
        const next = prev.filter((item) => !(pendingMessage && item.id === pendingMessage.id));
        next.push(createMessage("system", `请求失败：${detail}`, { error: true }));
        return next;
      });
    } finally {
      setDraftingPendingMessageId("");
      setSending(false);
    }
  }

  function handleComposerKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  const workspaceLabel = fileNameFromHealth(health);
  const runtimeStatus = (health && health.runtime_status) || {};
  const lastInspector = (lastResponse && lastResponse.inspector) || {};
  const runState = lastInspector.run_state || {};
  const evidence = lastInspector.evidence || {};
  const agentInfo = lastInspector.agent || (health && health.agent) || {};
  const activeToolTimeline = Array.isArray(lastInspector.tool_timeline) && lastInspector.tool_timeline.length
    ? lastInspector.tool_timeline
    : toolTimeline;
  const tokenUsage = (lastResponse && lastResponse.token_usage) || {};
  const activeModel = String((lastResponse && lastResponse.effective_model) || chatSettings.model || (health && health.default_model) || "").trim();
  const statusPills = useMemo(
    () => [
      `mode:${runtimeStatus.execution_mode || "host"}`,
      runtimeStatus.auth_ready ? `auth:${runtimeStatus.auth_mode || "ready"}` : "auth:missing",
      `agent:${agentInfo.title || "Vintage Programmer"}`,
      `model:${activeModel || "-"}`,
      `branch:${runtimeStatus.git_branch || "-"}`,
    ],
    [runtimeStatus, agentInfo, activeModel],
  );

  return html`
    <div className="workstation-shell" id="appShell">
      <aside className="thread-rail" id="threadSidebar">
        <div className="rail-brand">
          <div className="brand-mark">VP</div>
          <div>
            <div className="brand-title">Vintage Programmer</div>
            <div className="brand-sub">${workspaceLabel}</div>
          </div>
        </div>

        <div className="rail-actions">
          <button className="solid-btn" type="button" onClick=${handleNewSession} disabled=${loadingSession || sending}>新线程</button>
          <button className="ghost-btn" type="button" onClick=${refreshSessions} disabled=${loadingSession || sending}>刷新</button>
        </div>

        <div className="thread-list">
          ${sessions.length
            ? sessions.map(
                (item) => html`
                  <button
                    key=${item.session_id}
                    className=${`thread-row ${item.session_id === sessionId ? "active" : ""}`}
                    type="button"
                    onClick=${() => loadSession(item.session_id)}
                    disabled=${loadingSession || sending}
                  >
                    <div className="thread-row-title">${item.title || "新线程"}</div>
                    <div className="thread-row-preview">${item.preview || "暂无预览"}</div>
                    <div className="thread-row-meta">${formatTime(item.updated_at)} · ${item.turn_count || 0} 轮</div>
                  </button>
                `,
              )
            : html`<div className="thread-empty">还没有线程，先开始一轮工作。</div>`}
        </div>
      </aside>

      <main className="main-pane" id="chatPane">
        <div className="main-head">
          <div>
            <div className="main-head-kicker">${agentInfo.title || "Vintage Programmer"}</div>
            <div className="main-head-title">${sessionId ? (sessions.find((item) => item.session_id === sessionId)?.title || "新线程") : "开始构建"}</div>
          </div>
          <div className="head-actions">
            <button className=${`mini-btn ${drawerView === "run" ? "active" : ""}`} type="button" onClick=${() => setDrawerView(drawerView === "run" ? "" : "run")}>Run Details</button>
            <button className=${`mini-btn ${drawerView === "tools" ? "active" : ""}`} type="button" onClick=${() => setDrawerView(drawerView === "tools" ? "" : "tools")}>Tools</button>
            <button className=${`mini-btn ${drawerView === "session" ? "active" : ""}`} type="button" onClick=${() => setDrawerView(drawerView === "session" ? "" : "session")}>Session</button>
            <button className=${`mini-btn ${drawerView === "settings" ? "active" : ""}`} type="button" onClick=${() => setDrawerView(drawerView === "settings" ? "" : "settings")}>Settings</button>
          </div>
        </div>

        <section className="chat-scroll" id="messageList" ref=${chatListRef}>
          <div className="reading-column">
            ${messages.length
              ? messages.map(
                  (item) => html`
                    <article key=${item.id} className=${`message-block role-${item.role} ${item.pending ? "pending" : ""} ${item.error ? "error" : ""}`}>
                      <div className="message-block-head">
                        <span className="message-role">${roleLabel(item.role)}</span>
                        ${item.createdAt ? html`<span className="message-time">${formatTime(item.createdAt)}</span>` : null}
                      </div>
                      <div className="message-block-body">${item.text}</div>
                    </article>
                  `,
                )
              : html`
                  <section className="empty-panel">
                    <div className="empty-kicker">Single-Agent Workstation</div>
                    <h1 className="empty-title">输入框始终在底部，线程在左边，细节通过抽屉展开。</h1>
                    <p className="empty-copy">
                      这里默认只有一个主 agent：<strong>vintage_programmer</strong>。它按 explore、plan、execute、verify、report 这条主线工作。
                    </p>
                    <div className="starter-list">${starterPromptChips(setDraft, handleSend)}</div>
                  </section>
                `}
          </div>
        </section>

        <div className=${`surface-drawer ${drawerView ? "open" : ""}`} id="detailDrawer">
          ${drawerView === "run"
            ? html`
                <div className="drawer-head">
                  <div className="drawer-title">Run Details</div>
                  <button className="drawer-close" type="button" onClick=${() => setDrawerView("")}>关闭</button>
                </div>
                <div className="drawer-grid">
                  <div className="drawer-card">
                    <div className="drawer-card-title">当前状态</div>
                    <div className="meta-line">goal: ${runState.goal || sessionAgentState.current_goal || "-"}</div>
                    <div className="meta-line">phase: ${runState.phase || sessionAgentState.phase || "idle"}</div>
                    <div className="meta-line">network: ${runState.network_mode || (((agentInfo || {}).network || {}).mode) || "explicit_tools"}</div>
                  </div>
                  <div className="drawer-card">
                    <div className="drawer-card-title">证据</div>
                    <div className="meta-line">status: ${evidence.status || sessionAgentState.evidence_status || "not_needed"}</div>
                    <div className="meta-line">required: ${String(Boolean(evidence.required))}</div>
                    <div className="meta-line">${evidence.warning || "当前无额外警告。"}</div>
                  </div>
                  <div className="drawer-card wide">
                    <div className="drawer-card-title">阶段时间线</div>
                    <div className="timeline-list">
                      ${stageTimeline.length
                        ? stageTimeline.map(
                            (item) => html`
                              <div key=${item.id} className="timeline-row">
                                <span className="timeline-phase">${item.phase || item.label}</span>
                                <span className="timeline-status">${item.status}</span>
                                <span className="timeline-detail">${item.detail}</span>
                              </div>
                            `,
                          )
                        : html`<div className="empty-inline">本轮还没有阶段记录。</div>`}
                    </div>
                  </div>
                </div>
              `
            : null}

          ${drawerView === "tools"
            ? html`
                <div className="drawer-head">
                  <div className="drawer-title">Tools</div>
                  <button className="drawer-close" type="button" onClick=${() => setDrawerView("")}>关闭</button>
                </div>
                <div className="drawer-grid">
                  <div className="drawer-card wide">
                    <div className="drawer-card-title">工具时间线</div>
                    <div className="timeline-list">
                      ${activeToolTimeline.length
                        ? activeToolTimeline.map(
                            (item, index) => html`
                              <div key=${`${item.name || "tool"}-${index}`} className="tool-row">
                                <div className="tool-row-name">${item.name || "tool"}</div>
                                <div className="tool-row-summary">${item.summary || item.output_preview || "无摘要"}</div>
                                <div className="tool-row-meta">${item.status || "ok"} · ${(item.source_refs || []).join(" · ") || "no refs"}</div>
                              </div>
                            `,
                          )
                        : html`<div className="empty-inline">这一轮没有工具调用。</div>`}
                    </div>
                  </div>
                </div>
              `
            : null}

          ${drawerView === "session"
            ? html`
                <div className="drawer-head">
                  <div className="drawer-title">Session</div>
                  <button className="drawer-close" type="button" onClick=${() => setDrawerView("")}>关闭</button>
                </div>
                <div className="drawer-grid">
                  <div className="drawer-card">
                    <div className="drawer-card-title">线程</div>
                    <div className="meta-line">session: ${sessionId || "(未创建)"}</div>
                    <div className="meta-line">turns: ${messages.length}</div>
                    <div className="meta-line">uploads: ${pendingUploads.length}</div>
                  </div>
                  <div className="drawer-card">
                    <div className="drawer-card-title">Agent State</div>
                    <div className="meta-line">goal: ${sessionAgentState.current_goal || "-"}</div>
                    <div className="meta-line">phase: ${sessionAgentState.phase || "idle"}</div>
                    <div className="meta-line">evidence: ${sessionAgentState.evidence_status || "not_needed"}</div>
                    <div className="meta-line">last model: ${sessionAgentState.last_model || "-"}</div>
                  </div>
                  <div className="drawer-card wide">
                    <div className="drawer-card-title">Recent Logs</div>
                    <div className="timeline-list">
                      ${logs.length
                        ? logs.map(
                            (item) => html`
                              <div key=${item.id} className=${`log-row tone-${item.type}`}>
                                <span className="timeline-detail">${item.text}</span>
                              </div>
                            `,
                          )
                        : html`<div className="empty-inline">暂无额外日志。</div>`}
                    </div>
                  </div>
                </div>
              `
            : null}

          ${drawerView === "settings"
            ? html`
                <div className="drawer-head" id="settingsModal">
                  <div className="drawer-title">Settings</div>
                  <button className="drawer-close" type="button" onClick=${() => setDrawerView("")}>关闭</button>
                </div>
                <div className="drawer-grid">
                  <div className="drawer-card">
                    <div className="drawer-card-title">模型</div>
                    <input
                      className="drawer-input"
                      type="text"
                      value=${chatSettings.model}
                      onInput=${(event) => {
                        setModelTouched(true);
                        setChatSettings((prev) => ({ ...prev, model: event.currentTarget.value }));
                      }}
                      placeholder=${(health && health.default_model) || "模型名"}
                      disabled=${sending}
                    />
                  </div>
                  <div className="drawer-card">
                    <div className="drawer-card-title">响应风格</div>
                    <select
                      className="drawer-input"
                      value=${chatSettings.response_style}
                      onChange=${(event) => setChatSettings((prev) => ({ ...prev, response_style: event.currentTarget.value }))}
                      disabled=${sending}
                    >
                      <option value="short">简短</option>
                      <option value="normal">正常</option>
                      <option value="long">详细</option>
                    </select>
                  </div>
                  <div className="drawer-card">
                    <div className="drawer-card-title">输出上限</div>
                    <input
                      className="drawer-input"
                      type="number"
                      value=${chatSettings.max_output_tokens}
                      onInput=${(event) => setChatSettings((prev) => ({ ...prev, max_output_tokens: Number(event.currentTarget.value || 0) || 1024 }))}
                      disabled=${sending}
                    />
                  </div>
                  <div className="drawer-card">
                    <div className="drawer-card-title">上下文轮数</div>
                    <input
                      className="drawer-input"
                      type="number"
                      value=${chatSettings.max_context_turns}
                      onInput=${(event) => setChatSettings((prev) => ({ ...prev, max_context_turns: Number(event.currentTarget.value || 0) || 20 }))}
                      disabled=${sending}
                    />
                  </div>
                </div>
              `
            : null}
        </div>

        <section className="composer-shell" id="composerShell">
          ${pendingUploads.length
            ? html`
                <div className="attachment-strip">
                  ${pendingUploads.map(
                    (item) => html`
                      <div key=${item.id} className="attachment-chip">
                        <span>${item.name}</span>
                        <button type="button" onClick=${() => removeUpload(item.id)}>×</button>
                      </div>
                    `,
                  )}
                </div>
              `
            : null}

          <div className="composer-controls">
            <button className="icon-btn" type="button" onClick=${() => fileInputRef.current && fileInputRef.current.click()} disabled=${sending}>+</button>
            <select
              value=${chatSettings.response_style}
              onChange=${(event) => setChatSettings((prev) => ({ ...prev, response_style: event.currentTarget.value }))}
              disabled=${sending}
            >
              <option value="short">简短</option>
              <option value="normal">正常</option>
              <option value="long">详细</option>
            </select>
            <label className="tool-toggle">
              <input
                type="checkbox"
                checked=${chatSettings.enable_tools}
                onChange=${(event) => setChatSettings((prev) => ({ ...prev, enable_tools: event.currentTarget.checked }))}
                disabled=${sending}
              />
              工具
            </label>
          </div>

          <div className="composer-frame">
            <textarea
              value=${draft}
              onInput=${(event) => setDraft(event.currentTarget.value)}
              onKeyDown=${handleComposerKeyDown}
              placeholder="给 Vintage Programmer 一个清晰任务。Enter 发送，Shift+Enter 换行。"
              disabled=${sending}
            ></textarea>
            <button className="send-btn" type="button" onClick=${() => handleSend()} disabled=${sending || !draft.trim()}>
              ${sending ? "运行中" : "发送"}
            </button>
          </div>
          <input ref=${fileInputRef} type="file" multiple hidden onChange=${handleSelectFiles} />
        </section>

        <footer className="status-bar" id="statusBar">
          <div className="status-left">
            ${statusPills.map((item) => html`<span key=${item} className="status-pill">${item}</span>`)}
          </div>
          <div className="status-right">
            <span>${runtimeStatus.permission_summary || "permissions: unknown"}</span>
            ${lastError ? html`<span className="status-error">${lastError}</span>` : null}
          </div>
        </footer>
      </main>
    </div>
  `;
}

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root");
}

createRoot(root).render(html`<${App} />`);
