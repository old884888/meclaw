const state = {
  config: null,
  providers: [],
  bots: [],
  sessions: [],
  selectedBotId: null,
  currentSessionId: null,
  currentMessages: [],
  hasRequiredSetup: false,
  screen: "home",
  screenTransitioning: false,
  arrangeMode: false,
  orderDirty: false,
  dragBotId: null,
  ws: null,
  wsReady: false,
  activeGenerationId: null,
  streamingBuffer: "",
  streamingEl: null,
  streamingWrap: null,
  streamingCopyBtn: null,
  generationVersion: null,
  generationPhase: null,
  generationWaitTimer: null,
  generationStopTimer: null,
  streamingReasoningBuffer: "",
  reasoningVisibleForGeneration: true,
  chatStickToBottom: true,
  streamingMdTimer: null,
  sessionSwitching: false,
  openMsgMenu: null,
  currentTab: "providers",
  tabSwitching: false,
  editingProviderId: null,
  botEditor: {
    soul: "",
    soulSource: "",
    constraints: "",
    constraintsSource: "",
  },
  brainStatus: null,
  brainStatusLoading: false,
  expandedBrainKey: null,
  lastBrainTraceBySession: {},
  lastCacheUsageBySession: {},
  memoryBrowser: {
    botId: null,
    tab: "l1",
    items: [],
    total: 0,
    profile: "",
    loading: false,
    tabSwitching: false,
    searchQuery: "",
    sessionFilter: null,
    searchResults: null,
  },
};

const AVATAR_OPTIONS = [
  "🤖", "😀", "😎", "🧠", "💡", "🔮", "✨", "🦊", "🐱", "🐶",
  "🐼", "🦁", "🐯", "🐸", "🦄", "🐲", "👽", "👾", "🎭", "🧙",
  "💻", "🔬", "🎓", "📚", "📝", "💬", "🎯", "🚀", "⚡", "🔥",
  "🌟", "🌈", "🎨", "🎵", "💼", "🛠️",
];

function genId(prefix = "g") {
  if (window.crypto && window.crypto.randomUUID) {
    return `${prefix}_${window.crypto.randomUUID()}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  let data = {};
  try {
    data = await res.json();
  } catch {
    throw new Error(`请求失败: HTTP ${res.status}`);
  }
  if (!res.ok || data.ok === false) {
    const detail = data.detail;
    const detailText = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((x) => x.msg || x).join("; ") : "";
    throw new Error(data.msg || detailText || data.message || `请求失败: HTTP ${res.status}`);
  }
  return data;
}

let toastTimer = null;

function showToast(message, kind = "info", durationMs = 7000) {
  const text = String(message || "").trim();
  if (!text) return;
  const toast = document.getElementById("app-toast");
  if (!toast) return;
  toast.className = `app-toast app-toast-${kind}`;
  toast.textContent = text;
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), durationMs);
}

function setProviderCardStatus(card, message, kind = "info") {
  if (!card) return;
  let status = card.querySelector(".provider-test-status");
  if (!status) {
    status = document.createElement("div");
    status.className = "provider-test-status";
    const summary = card.querySelector(".provider-card-summary");
    const actions = card.querySelector(".provider-card-actions");
    if (summary && actions) summary.insertBefore(status, actions);
    else if (actions) card.insertBefore(status, actions);
    else card.appendChild(status);
  }
  status.className = `provider-test-status provider-test-status-${kind}`;
  status.textContent = message;
}

function currentBot() {
  return state.bots.find((b) => b.id === state.selectedBotId) || null;
}

function providerById(id) {
  return state.providers.find((p) => p.id === id) || null;
}

function providerModels(p) {
  if (!p) return [];
  if (Array.isArray(p.models) && p.models.length) {
    return p.models.map((m) => String(m || "").trim()).filter(Boolean);
  }
  if (p.model) return [String(p.model).trim()];
  return [];
}

function providerOptimizations(p) {
  if (!p) return [];
  if (Array.isArray(p.optimizations)) {
    return p.optimizations.map((x) => String(x || "").trim().toLowerCase()).filter(Boolean);
  }
  return [];
}

function providerOptimizationsLabel(p) {
  const opts = providerOptimizations(p);
  if (!opts.length) return "无";
  return opts.join("、");
}

function setProviderOptimizations(values) {
  const opts = [...new Set((values || []).map((v) => String(v).trim().toLowerCase()).filter(Boolean))];
  const picker = document.getElementById("provider-optimizations");
  if (!picker) return;
  picker.querySelectorAll(".opt-pill").forEach((btn) => {
    const val = btn.dataset.opt || "";
    if (!val) btn.classList.toggle("active", !opts.length);
    else btn.classList.toggle("active", opts.includes(val));
  });
}

function readProviderOptimizations() {
  const picker = document.getElementById("provider-optimizations");
  if (!picker) return [];
  return [...picker.querySelectorAll(".opt-pill.active")]
    .map((btn) => (btn.dataset.opt || "").trim().toLowerCase())
    .filter(Boolean);
}

function providerModelsLabel(p) {
  const models = providerModels(p);
  if (!models.length) return "-";
  if (models.length <= 2) return models.join("、");
  return `${models[0]} 等 ${models.length} 个`;
}

function parseModelsText(text) {
  return String(text || "")
    .split(/[\n\r,，;；]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((v, i, arr) => arr.indexOf(v) === i);
}

function botCanChat(bot) {
  if (!bot) return false;
  if (typeof bot.chat_ready === "boolean") return bot.chat_ready;
  const p = providerById(bot.profile_id);
  if (!p) return false;
  return !!(p.enabled !== false && p.has_api_key && p.base_url && p.model);
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function brainStatusLabel(bot) {
  if (!bot) return "";
  if (bot.chat_ready) return bot.provider_name ? `大脑 · ${bot.provider_name}` : "已配置大脑";
  return bot.brain_message || "未配置大脑";
}

function botConfigSummaryLabel(bot) {
  if (!bot) return "";
  const ef = bot.effective_brains || {};
  const mem = ef.memory_token_budget ?? state.config?.memory_token_budget ?? 800;
  const persona = ef.persona_token_budget ?? state.config?.persona_token_budget ?? 400;
  const cog = ef.cognitive_token_budget ?? state.config?.cognitive_token_budget ?? 300;
  const bgModel = (bot.background_model || "").trim();
  const bgText = bgModel ? `后台 ${bgModel}` : "后台继承主模型";
  return `${bgText} · 预算 M/P/C ${mem}/${persona}/${cog}`;
}

function botHasBrainOverrides(bot) {
  if (!bot) return false;
  if ((bot.background_model || "").trim()) return true;
  const brains = bot.brains || {};
  return Object.keys(brains).some((k) => brains[k] !== undefined && brains[k] !== null && brains[k] !== "");
}

function setScreen(name) {
  state.screen = name;
  document.getElementById("view-home").classList.toggle("hidden", name !== "home");
  document.getElementById("view-chat-workspace").classList.toggle("hidden", name !== "chat");
  document.getElementById("btn-back-home").classList.toggle("hidden", name !== "chat");
  document.getElementById("btn-arrange").classList.toggle("hidden", name !== "home");
  updateTitle();
}

async function showModal(modal) {
  if (!modal || !modal.classList.contains("hidden")) return;
  if (modal.dataset.animating === "1") return;
  modal.dataset.animating = "1";
  try {
    if (!window.AnimEngine || AnimEngine.prefersReducedMotion()) {
      modal.classList.remove("hidden");
      return;
    }
    await AnimEngine.run("A05", modal, "enter");
  } finally {
    modal.dataset.animating = "0";
  }
}

async function hideModal(modal) {
  if (!modal || modal.classList.contains("hidden")) return;
  if (modal.dataset.animating === "1") return;
  modal.dataset.animating = "1";
  try {
    if (!window.AnimEngine || AnimEngine.prefersReducedMotion()) {
      modal.classList.add("hidden");
      return;
    }
    await AnimEngine.run("A05", modal, "exit");
  } finally {
    modal.dataset.animating = "0";
  }
}

async function runButtonTapAnim(buttonEl) {
  if (!buttonEl || !window.AnimEngine || AnimEngine.prefersReducedMotion()) return;
  await AnimEngine.run("A06", buttonEl, "tap").catch(() => {});
}

async function animateScreenChange(targetScreen) {
  if (targetScreen === state.screen) return;
  const home = document.getElementById("view-home");
  const chat = document.getElementById("view-chat-workspace");
  const forward = targetScreen === "chat";
  const fromEl = forward ? home : chat;
  const toEl = forward ? chat : home;
  const direction = forward ? "forward" : "back";

  state.screen = targetScreen;
  document.getElementById("btn-back-home").classList.toggle("hidden", targetScreen !== "chat");
  document.getElementById("btn-arrange").classList.toggle("hidden", targetScreen !== "home");
  updateTitle();

  if (!window.AnimEngine || AnimEngine.prefersReducedMotion()) {
    setScreen(targetScreen);
    return;
  }

  const shell = document.querySelector(".app-shell");
  shell?.classList.add("is-screen-transitioning");
  try {
    await Promise.all([
      AnimEngine.run("A04", fromEl, "exit", { direction }),
      AnimEngine.run("A04", toEl, "enter", { direction }),
    ]);
  } finally {
    shell?.classList.remove("is-screen-transitioning");
  }
}

function updateTitle() {
  const el = document.getElementById("current-title");
  if (state.screen === "home") {
    el.textContent = state.arrangeMode ? "整理 Bot 顺序" : "选择 Bot";
    return;
  }
  const bot = currentBot();
  if (!bot) {
    el.textContent = "Chat · 本地对话";
    return;
  }
  if (!state.currentSessionId) {
    el.textContent = `${bot.avatar || "🤖"} ${bot.name} · 会话`;
    return;
  }
  const session = state.sessions.find((s) => s.id === state.currentSessionId);
  el.textContent = `${bot.avatar || "🤖"} ${bot.name} · ${session?.title || "新对话"}`;
}

function updateUsageHint() {
  const el = document.getElementById("usage-hint");
  if (!el) return;
  const msgCount = state.currentMessages.length;
  const parts = [`约 ${msgCount} 条消息`];
  const status = state.brainStatus;
  const trace = state.currentSessionId ? state.lastBrainTraceBySession[state.currentSessionId] : null;
  const ctx = status?.context;
  const mem = status?.memory;
  const ratio = ctx?.ratio ?? trace?.context_ratio;
  if (ratio != null && Number.isFinite(Number(ratio))) {
    parts.push(`上下文 ${Math.round(Number(ratio) * 100)}%`);
  }
  const tier = ctx?.compact_tier ?? trace?.compact_tier;
  if (tier != null) parts.push(`Tier${tier}`);
  const recall = mem?.last_recall_count ?? trace?.memory?.recall_count;
  if (recall != null && Number(recall) > 0) parts.push(`记忆召回 ${recall}`);
  // Cache hit rate (shown only when provider supports it)
  const cacheInfo = ctx?.cache ?? (state.currentSessionId ? state.lastCacheUsageBySession[state.currentSessionId] : null);
  if (cacheInfo?.supported && cacheInfo.hit_rate != null) {
    parts.push(`缓存命中 ${cacheInfo.hit_rate}%`);
  }
  const bg = formatBackgroundHint(status?.background_jobs);
  if (bg) parts.push(bg);
  el.textContent = parts.join(" · ");
}

function formatContextPct(ratio) {
  const n = Number(ratio);
  if (!Number.isFinite(n) || n <= 0) return "0%";
  return `${Math.round(n * 100)}%`;
}

function formatTierLabel(tier) {
  const n = Number(tier) || 0;
  return `Tier ${n}`;
}

function formatBackgroundHint(jobs) {
  if (!jobs) return "";
  const running = ["l1_extraction", "tier3_summary", "learner"].filter((k) => jobs[k]?.status === "running");
  if (running.length) return "后台运行中";
  return "";
}

function brainDotClass(brain) {
  if (!brain?.enabled) return "brain-dot-disabled";
  if (brain.status === "error" || brain.status === "failed") return "brain-dot-error";
  if (brain.status === "warn") return "brain-dot-warn";
  if (brain.active) return "brain-dot-active";
  return "brain-dot-idle";
}

function isBrainStatusHomeIdle() {
  return !state.selectedBotId;
}

function brainStatusCapsuleLabel(status) {
  if (state.brainStatusLoading && state.selectedBotId) return "同步中…";
  if (!status) return isBrainStatusHomeIdle() ? "大脑空闲" : "加载状态…";
  const health = status.health || {};
  const mem = status.memory || {};
  const ctx = status.context || {};
  if (health.status === "idle" && isBrainStatusHomeIdle()) {
    return health.label || "大脑空闲";
  }
  if (health.status === "idle" && state.selectedBotId) {
    return "同步中…";
  }
  const parts = [health.label || "状态"];
  if (mem.enabled !== false && mem.last_recall_count > 0) {
    parts.push(`记忆${mem.last_recall_count}`);
  } else if (mem.l1_count > 0 && (health.status === "ok" || health.status === "standby")) {
    parts.push(`L1 ${mem.l1_count}`);
  }
  if (ctx.ratio > 0) parts.push(`上下文${formatContextPct(ctx.ratio)}`);
  const bg = formatBackgroundHint(status.background_jobs);
  if (bg) parts.push(bg);
  return parts.join(" · ");
}

function resolveBrainHealthVisual(status) {
  if (!state.selectedBotId) return "idle";
  const raw = status?.health?.status;
  if (!raw || raw === "idle") return state.brainStatusLoading ? "idle" : "standby";
  return raw === "ok" ? "ok" : raw;
}

function renderBrainStatusCapsule() {
  const btn = document.getElementById("btn-brain-status");
  const label = document.getElementById("brain-status-label");
  if (!btn || !label) return;
  btn.classList.remove("hidden");
  const healthStatus = resolveBrainHealthVisual(state.brainStatus);
  btn.classList.remove("brain-status-idle", "brain-status-standby", "brain-status-ok", "brain-status-warn", "brain-status-error");
  btn.classList.add(`brain-status-${healthStatus === "ok" ? "ok" : healthStatus}`);
  label.textContent = brainStatusCapsuleLabel(state.brainStatus);
  btn.disabled = state.brainStatusLoading;
}

function mergeBrainTrace(sessionId, trace) {
  if (!sessionId || !trace) return;
  state.lastBrainTraceBySession[sessionId] = { ...(state.lastBrainTraceBySession[sessionId] || {}), ...trace };
  if (state.brainStatus && state.currentSessionId === sessionId) {
    state.brainStatus = {
      ...state.brainStatus,
      turn_trace: state.lastBrainTraceBySession[sessionId],
      context: {
        ...(state.brainStatus.context || {}),
        ratio: trace.context_ratio ?? state.brainStatus.context?.ratio,
        compact_tier: trace.compact_tier ?? state.brainStatus.context?.compact_tier,
      },
      memory: {
        ...(state.brainStatus.memory || {}),
        last_recall_count: trace.memory?.recall_count ?? state.brainStatus.memory?.last_recall_count,
      },
    };
  }
  updateUsageHint();
  renderBrainStatusCapsule();
  if (!document.getElementById("brain-status-modal")?.classList.contains("hidden")) {
    renderBrainStatusModal();
  }
}

async function loadBrainStatus(options = {}) {
  const { silent = false } = options;
  const btn = document.getElementById("btn-brain-status");
  if (!silent) state.brainStatusLoading = true;
  renderBrainStatusCapsule();
  try {
    if (isBrainStatusHomeIdle()) {
      state.brainStatus = {
        health: { status: "idle", label: "大脑空闲", message: "未进入 Bot 工作区" },
      };
      renderBrainStatusCapsule();
      updateUsageHint();
      if (!document.getElementById("brain-status-modal")?.classList.contains("hidden")) {
        renderBrainStatusModal();
      }
      return;
    }
    const q = state.currentSessionId ? `?session_id=${encodeURIComponent(state.currentSessionId)}` : "";
    const data = await api(`/api/bots/${encodeURIComponent(state.selectedBotId)}/brain/status${q}`);
    if (!data.status) {
      throw new Error("状态接口未返回数据，请重启 MNEMOS 服务");
    }
    state.brainStatus = data.status;
    if (state.currentSessionId && state.brainStatus?.turn_trace) {
      state.lastBrainTraceBySession[state.currentSessionId] = state.brainStatus.turn_trace;
    }
    renderBrainStatusCapsule();
    updateUsageHint();
    if (!document.getElementById("brain-status-modal")?.classList.contains("hidden")) {
      renderBrainStatusModal();
    }
  } catch (err) {
    if (state.selectedBotId) {
      const bot = currentBot();
      const staleBackend = /404|not found/i.test(String(err.message || ""));
      state.brainStatus = {
        health: {
          status: "error",
          label: "状态同步失败",
          message: staleBackend
            ? "大脑状态接口不存在，8766 端口可能仍在跑旧后端。请关闭旧 MNEMOS 窗口/进程后重新运行 启动MNEMOS.bat"
            : (err.message || "无法获取大脑状态"),
        },
        bot: {
          id: state.selectedBotId,
          name: bot?.name || "",
          chat_ready: !!bot?.chat_ready,
          provider_name: bot?.provider_name || "",
        },
      };
      renderBrainStatusCapsule();
      if (!document.getElementById("brain-status-modal")?.classList.contains("hidden")) {
        renderBrainStatusModal();
      }
    }
    if (!silent) onErr(err);
    else if (btn) btn.classList.add("brain-status-error");
  } finally {
    state.brainStatusLoading = false;
    renderBrainStatusCapsule();
  }
}

function jobStatusLabel(status) {
  const map = {
    idle: "空闲",
    standby: "已就绪",
    ok: "正常",
    warn: "注意",
    running: "运行中",
    success: "已完成",
    failed: "失败",
    disabled: "已关闭",
    ready: "就绪",
    error: "异常",
  };
  return map[status] || status || "—";
}

function jobStatusClass(status) {
  if (status === "running") return "bs-pill-running";
  if (status === "success" || status === "ready") return "bs-pill-ok";
  if (status === "failed" || status === "error") return "bs-pill-error";
  if (status === "disabled") return "bs-pill-disabled";
  return "bs-pill-idle";
}

function healthHeroClass(status) {
  return `bs-hero-${status || "idle"}`;
}

function brainIcon(key) {
  return ({ executor: "⚡", persona: "🎭", memory: "💾", cognitive: "🧩", learner: "📡" })[key] || "🧠";
}

function brainLabel(key) {
  return ({ executor: "执行脑", persona: "右脑", memory: "记忆脑", cognitive: "左脑", learner: "学习脑" })[key] || key;
}

const BS_BRAIN_COLORS = {
  executor: "#007aff",
  persona: "#ff2d55",
  memory: "#00a86b",
  cognitive: "#ff9500",
  learner: "#9c27b0",
};

function brainWaterPct(used, budget) {
  const u = Math.max(0, Number(used) || 0);
  const b = Number(budget) || 0;
  if (b > 0) return Math.min(100, Math.round((u / b) * 100));
  if (!u) return 0;
  return Math.min(88, Math.max(14, Math.round(u / 12)));
}

function renderBsBrainWaterTank(key, b) {
  const used = Number(b.tokens_used) || 0;
  const budget = Number(b.budget) || 0;
  const enabled = b.enabled !== false;
  const pct = brainWaterPct(used, budget);
  const over = budget > 0 && used > budget;
  const color = BS_BRAIN_COLORS[key] || "#6366f1";
  const active = !!b.active;
  const usageText = budget > 0 ? `${used}/${budget}` : (used ? `${used} tok` : "—");
  const waveClass = active && pct > 0 ? " bs-brain-water-wave" : "";
  const levelClass = [
    "bs-brain-water",
    waveClass,
    over ? " is-over" : "",
    !enabled ? " is-disabled" : "",
  ].filter(Boolean).join(" ");
  return `<div class="bs-brain-tank" style="--brain-color:${color};--water-pct:${pct}" title="Token 用量 ${usageText}">
    <div class="${levelClass}" aria-hidden="true"></div>
    <span class="bs-brain-tank-label">${escapeHtml(usageText)}</span>
  </div>`;
}

function renderBsBrainCard(key, b) {
  const expanded = state.expandedBrainKey === key;
  const cardClass = [
    "bs-brain-card",
    brainDotClass(b).replace("brain-dot-", "bs-brain-"),
    expanded ? "is-expanded" : "",
  ].filter(Boolean).join(" ");
  const stateLabel = !b.enabled ? "已关闭" : b.active ? "本轮激活" : "待命";
  return `<button type="button" class="${cardClass}" data-brain-key="${key}" aria-expanded="${expanded ? "true" : "false"}" aria-label="${escapeHtml(brainLabel(key))} ${escapeHtml(stateLabel)}">
    <div class="bs-brain-card-top">
      <span class="bs-brain-emoji">${brainIcon(key)}</span>
      <span class="bs-brain-dot ${brainDotClass(b)}"></span>
    </div>
    <strong>${brainLabel(key)}</strong>
    <span class="bs-brain-state">${escapeHtml(stateLabel)}</span>
    ${renderBsBrainWaterTank(key, b)}
  </button>`;
}

function renderBsBrainDetailPanel(key, status) {
  if (!key) return "";
  const b = (status.brains || {})[key] || {};
  const trace = status.turn_trace || {};
  const mem = status.memory || {};
  const jobs = status.background_jobs || {};
  const cfg = state.config || {};
  const rows = [];

  if (key === "executor") {
    rows.push(["职责", "组装 Soul + 约束，作为 stable system 前缀"]);
    rows.push(["本轮注入", `${Number(b.tokens_used) || 0} tok（system 基础）`]);
    rows.push(["主模型", status.bot?.executor_model || "—"]);
  } else if (key === "persona") {
    rows.push(["职责", "L3 用户画像摘要，并入 stable 前缀"]);
    rows.push(["预算 / 用量", b.budget ? `${b.tokens_used || 0} / ${b.budget} tok` : `${b.tokens_used || 0} tok`]);
    rows.push(["L3 画像", mem.l3_available ? "已生成，可查看" : "尚未生成"]);
  } else if (key === "memory") {
    const strategy = cfg.memory_retrieval_strategy || "hybrid";
    rows.push(["职责", "检索 L1/L2 相关记忆，注入动态上下文"]);
    rows.push(["预算 / 用量", b.budget ? `${b.tokens_used || 0} / ${b.budget} tok` : `${b.tokens_used || 0} tok`]);
    rows.push(["召回", `${trace.memory?.recall_count ?? mem.last_recall_count ?? 0} 条 · 策略 ${strategy}`]);
    if (trace.memory?.cross_session) rows.push(["路由", "跨会话召回"]);
    if (trace.memory?.l0_deep_recall) rows.push(["路由", "L0 深召回"]);
  } else if (key === "cognitive") {
    rows.push(["职责", "规划/分析块，仅在识别到认知意图时激活"]);
    rows.push(["预算 / 用量", b.budget ? `${b.tokens_used || 0} / ${b.budget} tok` : `${b.tokens_used || 0} tok`]);
    rows.push(["本轮", b.active ? "已注入左脑块" : "未触发（非规划类问题）"]);
  } else if (key === "learner") {
    const job = jobs.learner || {};
    rows.push(["职责", "后台收集学习信号，定时写入知识"]);
    rows.push(["状态", jobStatusLabel(job.status || b.status || "disabled")]);
    rows.push(["计划", cfg.learner_schedule || "0 3 * * *"]);
    if (job.pending_signals) rows.push(["待处理信号", `${job.pending_signals} 条`]);
  }

  const recallDebug = Array.isArray(trace.memory?.recall) ? trace.memory.recall.slice(0, 3) : [];
  const recallSnippets = recallDebug.length && key === "memory"
    ? `<div class="bs-brain-detail-recall">
        <div class="bs-brain-detail-sub">Top 召回片段</div>
        ${recallDebug.map((d) => `<div class="bs-brain-detail-snippet">${escapeHtml(`${d.layer || "L1"} · ${d.type || "记忆"} · 相关度 ${d.hybrid_score ?? "—"}`)}</div>`).join("")}
      </div>`
    : "";

  const actions = [];
  if (key === "memory") {
    actions.push('<button type="button" class="btn btn-ghost btn-sm" data-memory-tab="l1">打开记忆库</button>');
  }
  if (key === "persona" && mem.l3_available) {
    actions.push('<button type="button" class="btn btn-ghost btn-sm" data-memory-tab="l3">查看 L3 画像</button>');
  }

  return `<div class="bs-brain-detail" data-brain-detail="${key}">
    <div class="bs-brain-detail-head">
      <span>${brainIcon(key)} ${brainLabel(key)}</span>
      <button type="button" class="btn btn-ghost btn-sm bs-brain-detail-close" data-brain-close aria-label="收起">收起</button>
    </div>
    <div class="bs-brain-detail-rows">
      ${rows.map(([k, v]) => `<div class="bs-brain-detail-row"><span>${escapeHtml(k)}</span><b>${escapeHtml(String(v))}</b></div>`).join("")}
    </div>
    ${recallSnippets}
    ${actions.length ? `<div class="bs-brain-detail-actions">${actions.join("")}</div>` : ""}
  </div>`;
}

function formatTokenK(n) {
  const v = Number(n) || 0;
  if (v >= 10000) return `${(v / 1000).toFixed(1)}k`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return String(v);
}

function renderBsGauge(pct, label, sublabel = "") {
  const n = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
  const tierColor = n >= 95 ? "#ef4444" : n >= 80 ? "#f59e0b" : n >= 60 ? "#3b82f6" : "#10b981";
  return `<div class="bs-gauge" style="--pct:${n};--gauge-color:${tierColor}">
    <div class="bs-gauge-ring" aria-hidden="true"></div>
    <div class="bs-gauge-center">
      <span class="bs-gauge-value">${n}%</span>
      <span class="bs-gauge-label">${escapeHtml(label)}</span>
      ${sublabel ? `<span class="bs-gauge-sub">${escapeHtml(sublabel)}</span>` : ""}
    </div>
  </div>`;
}

function renderBsMetric(icon, label, value, sub = "", accent = "") {
  return `<div class="bs-metric${accent ? ` bs-metric-${accent}` : ""}">
    <span class="bs-metric-icon" aria-hidden="true">${icon}</span>
    <div class="bs-metric-body">
      <span class="bs-metric-value">${escapeHtml(value)}</span>
      <span class="bs-metric-label">${escapeHtml(label)}</span>
      ${sub ? `<span class="bs-metric-sub">${escapeHtml(sub)}</span>` : ""}
    </div>
  </div>`;
}

function renderBsLayerBars(mem) {
  const layers = [
    { key: "l0", label: "L0 证据", count: mem.l0_count ?? 0, color: "#6366f1" },
    { key: "l1", label: "L1 原子", count: mem.l1_count ?? 0, color: "#8b5cf6" },
    { key: "l2", label: "L2 摘要", count: mem.l2_count ?? 0, color: "#a855f7" },
    { key: "l3", label: "L3 画像", count: mem.l3_available ? 1 : 0, color: "#d946ef", isBool: true },
  ];
  const max = Math.max(1, ...layers.map((l) => (l.isBool ? 0 : l.count)));
  return layers.map((layer) => {
    const pct = layer.isBool ? (layer.count ? 100 : 8) : Math.max(6, Math.round((layer.count / max) * 100));
    const countText = layer.isBool ? (mem.l3_available ? "已配置" : "未配置") : String(layer.count);
    return `<button type="button" class="bs-layer-row bs-layer-btn" data-memory-tab="${layer.key}" title="查看${layer.label}">
      <span class="bs-layer-name">${layer.label}</span>
      <div class="bs-layer-track"><div class="bs-layer-fill" style="width:${pct}%;background:${layer.color}"></div></div>
      <span class="bs-layer-count">${countText}</span>
    </button>`;
  }).join("");
}

function renderBsCacheSection(cache) {
  if (!cache) return "";
  if (!cache.supported) {
    return `<div class="bs-cache-row bs-cache-unsupported"><span class="bs-cache-icon">⚡</span><span>供应商不支持缓存指标</span></div>`;
  }
  const hitRate = cache.hit_rate != null ? `${cache.hit_rate}%` : "—";
  const accent = cache.hit_rate >= 80 ? "ok" : cache.hit_rate >= 40 ? "warn" : "";
  return `<div class="bs-cache-row">
    <span class="bs-cache-icon">⚡</span>
    <span class="bs-cache-label">Prompt 缓存命中</span>
    <span class="bs-cache-value bs-cache-${accent || "neutral"}">${hitRate}</span>
    <span class="bs-cache-meta">读 ${cache.read ?? 0} · 建 ${cache.create ?? 0} tok</span>
  </div>`;
}

// High-contrast categorical palette (avoid adjacent blue/purple pairs).
const BS_TOKEN_COLORS = {
  system: "#007aff",
  persona: "#ff2d55",
  memory: "#00a86b",
  cognitive: "#ff9500",
  session_summary: "#9c27b0",
};

const BS_TOKEN_LABELS = {
  system: "系统",
  persona: "人格",
  memory: "记忆",
  cognitive: "左脑",
  session_summary: "摘要",
};

function renderBsTokenChart(tokens) {
  const entries = Object.entries(tokens || {}).filter(([, v]) => Number(v) > 0);
  const total = entries.reduce((s, [, v]) => s + Number(v), 0);
  if (!total) {
    return '<p class="brain-status-empty">暂无 token 分布数据</p>';
  }
  const segments = entries.map(([key, val]) => {
    const pct = (Number(val) / total) * 100;
    const color = BS_TOKEN_COLORS[key] || "#94a3b8";
    return `<div class="bs-token-seg" style="flex:${val};background:${color}" title="${BS_TOKEN_LABELS[key] || key}: ${val}"></div>`;
  }).join("");
  const legend = entries.map(([key, val]) => {
    const pct = Math.round((Number(val) / total) * 100);
    const color = BS_TOKEN_COLORS[key] || "#94a3b8";
    return `<span class="bs-token-legend-item"><i style="background:${color}"></i>${BS_TOKEN_LABELS[key] || key} ${formatTokenK(val)} <em>${pct}%</em></span>`;
  }).join("");
  return `<div class="bs-token-stack" role="img" aria-label="Token 分布">${segments}</div>
    <div class="bs-token-legend">${legend}</div>
    <div class="bs-token-total">合计 ${formatTokenK(total)} tokens</div>`;
}

function renderBsTierSteps(tier) {
  const n = Number(tier) || 0;
  return [0, 1, 2, 3].map((t) => {
    const active = t === n;
    const done = t < n;
    return `<div class="bs-tier-step${active ? " is-active" : ""}${done ? " is-done" : ""}">
      <span class="bs-tier-dot"></span>
      <span>T${t}</span>
    </div>`;
  }).join("");
}

function renderBsToggleChip(label, on) {
  return `<span class="bs-chip${on ? " is-on" : ""}">${escapeHtml(label)}</span>`;
}

function renderBrainStatusSection(title, html, extraClass = "") {
  return `<section class="brain-status-section ${extraClass}"><div class="brain-status-section-head"><h4>${escapeHtml(title)}</h4></div><div class="brain-status-section-body">${html}</div></section>`;
}

function renderBrainStatusIdle() {
  const cfg = state.config || {};
  const multiOn = !!cfg.multi_brain_enabled;
  return `
    <div class="bs-hero bs-hero-idle">
      <div class="bs-hero-icon">🧠</div>
      <div class="bs-hero-content">
        <div class="bs-hero-title">大脑空闲</div>
        <div class="bs-hero-msg">尚未进入 Bot 工作区，选择首页 Bot 卡片开始对话后可查看完整状态</div>
      </div>
    </div>
    <div class="bs-metrics-row">
      ${renderBsMetric("🤖", "Bot 数量", String(state.bots?.length || 0), "已创建")}
      ${renderBsMetric("🔗", "AI 超级大脑", multiOn ? "已开启" : "已关闭", multiOn ? "编排生效" : "单脑模式")}
      ${renderBsMetric("💬", "当前会话", "—", "进入 Bot 后可见")}
    </div>
    <div class="bs-idle-hint">
      <span class="bs-idle-hint-icon">💡</span>
      <p>顶栏胶囊会实时摘要健康状态、记忆召回与上下文压力；发送消息后 trace 与后台任务会自动更新。</p>
    </div>`;
}

function renderBrainStatusModal() {
  const body = document.getElementById("brain-status-scroll") || document.getElementById("brain-status-body");
  const subtitle = document.getElementById("brain-status-subtitle");
  if (!body) return;
  const status = state.brainStatus;
  if (!status) {
    body.innerHTML = '<div class="bs-empty-state"><span>📭</span><p>暂无状态数据</p></div>';
    return;
  }

  const health = status.health || {};
  if (isBrainStatusHomeIdle()) {
    if (subtitle) subtitle.textContent = "等待进入 Bot 工作区";
    body.innerHTML = renderBrainStatusIdle();
    return;
  }

  const bot = status.bot || {};
  const brains = status.brains || {};
  const mem = status.memory || {};
  const ctx = status.context || {};
  const jobs = status.background_jobs || {};
  const trace = status.turn_trace || {};
  const liveBot = currentBot();
  const avatar = liveBot?.avatar || "🤖";

  if (subtitle) {
    const parts = [bot.name || "Bot"];
    if (state.currentSessionId) parts.push("会话进行中");
    subtitle.textContent = parts.join(" · ");
  }

  const ctxPct = Math.round((Number(ctx.ratio) || 0) * 100);
  const recall = mem.last_recall_count ?? trace.memory?.recall_count ?? 0;
  const tier = ctx.compact_tier ?? trace.compact_tier ?? 0;

  const brainCards = ["executor", "persona", "memory", "cognitive", "learner"].map((key) => {
    const b = brains[key] || {};
    return renderBsBrainCard(key, b);
  }).join("");

  const brainDetail = renderBsBrainDetailPanel(state.expandedBrainKey, status);

  const jobCard = (title, icon, job) => {
    const j = job || {};
    const st = j.status || "idle";
    return `<div class="bs-job-card ${jobStatusClass(st)}">
      <div class="bs-job-top">
        <span class="bs-job-icon">${icon}</span>
        <span class="bs-job-pill ${jobStatusClass(st)}">${escapeHtml(jobStatusLabel(st))}</span>
      </div>
      <strong>${escapeHtml(title)}</strong>
      ${j.model ? `<span class="bs-job-meta">${escapeHtml(j.model)}</span>` : ""}
      ${j.created_count ? `<span class="bs-job-meta">+${j.created_count} 条原子</span>` : ""}
      ${j.pending_signals ? `<span class="bs-job-meta">${j.pending_signals} 条信号</span>` : ""}
      ${j.last_error ? `<span class="bs-job-error">${escapeHtml(j.last_error)}</span>` : ""}
    </div>`;
  };

  const activated = trace.activated || [];
  const activationChips = ["executor", "persona", "memory", "cognitive"].map((key) => {
    const on = activated.includes(key);
    return `<span class="bs-activation-chip${on ? " is-on" : ""}">${brainIcon(key)} ${brainLabel(key)}</span>`;
  }).join("");

  const indexLabel = { ready: "已就绪", missing: "待重建", error: "异常" }[mem.index_status] || mem.index_status || "—";
  const traceModels = trace.models || {};
  const modelsRow = (traceModels.executor || traceModels.extraction || traceModels.summary || traceModels.background)
    ? `<div class="bs-trace-foot">
        ${traceModels.executor ? `<span>执行 <code>${escapeHtml(traceModels.executor)}</code></span>` : ""}
        ${traceModels.extraction ? `<span>提取 <code>${escapeHtml(traceModels.extraction)}</code></span>` : ""}
        ${traceModels.summary ? `<span>摘要 <code>${escapeHtml(traceModels.summary)}</code></span>` : ""}
        ${!traceModels.extraction && traceModels.background ? `<span>后台 <code>${escapeHtml(traceModels.background)}</code></span>` : ""}
      </div>`
    : "";
  const traceWarnings = Array.isArray(trace.warnings) ? trace.warnings.filter(Boolean) : [];
  const warningsBlock = traceWarnings.length
    ? `<div class="bs-detail-block">
        <div class="bs-detail-label">告警</div>
        <div class="bs-warning-list">
          ${traceWarnings.map((w) => `<div class="bs-warning-item">⚠️ ${escapeHtml(String(w))}</div>`).join("")}
        </div>
      </div>`
    : "";
  const hasTokenTrace = Object.values(trace.tokens || {}).some((v) => Number(v) > 0);
  const memoryOffHint = !mem.retrieval_enabled && !mem.write_enabled
    ? '<p class="bs-memory-hint">记忆检索与写入已在 <strong>设置 → AI 超级大脑</strong> 中关闭。开启后发送消息才会召回/写入 L0–L3。</p>'
    : "";

  const roleModels = bot.model_roles || {};
  const infraRoleRows = ["embedding", "rerank"].map((key) => {
    const r = roleModels[key] || {};
    const label = key === "embedding" ? "Embedding" : "Rerank";
    const value = r.enabled ? (r.model || r.provider || "—") : "未启用";
    return `<div class="bs-model-row"><span>${label}</span><code>${escapeHtml(String(value))}</code></div>`;
  }).join("");

  body.innerHTML = `
    <div class="bs-hero ${healthHeroClass(health.status)}">
      <div class="bs-hero-icon">${health.status === "ok" ? "✅" : health.status === "warn" ? "⚠️" : health.status === "error" ? "❌" : "🧠"}</div>
      <div class="bs-hero-content">
        <div class="bs-hero-title">${escapeHtml(health.label || "状态")}</div>
        <div class="bs-hero-msg">${escapeHtml(health.message || "")}</div>
      </div>
      <div class="bs-hero-badge ${jobStatusClass(health.status === "ok" ? "success" : health.status)}">${escapeHtml(jobStatusLabel(health.status))}</div>
    </div>

    <div class="bs-metrics-row">
      ${renderBsMetric("📊", "上下文压力", `${ctxPct}%`, `${formatTokenK(ctx.estimated_tokens)} / ${formatTokenK(ctx.max_context)}`, ctxPct >= 80 ? "warn" : "ok")}
      ${renderBsMetric("💾", "记忆召回", `${recall} 条`, mem.enabled ? "检索已开" : "记忆关闭", recall > 0 ? "ok" : "")}
      ${renderBsMetric("🗜️", "压缩层级", formatTierLabel(tier), ctx.summary_active ? "摘要生效" : "无运行摘要", tier > 0 ? "warn" : "")}
    </div>

    <div class="bs-bot-card">
      <span class="bs-bot-avatar">${escapeHtml(avatar)}</span>
      <div class="bs-bot-info">
        <strong>${escapeHtml(bot.name || "未命名 Bot")}</strong>
        <span class="bs-bot-provider">${escapeHtml(bot.provider_name || "未绑定供应商")}</span>
        <div class="bs-bot-chips">
          <span class="bs-chip${bot.chat_ready ? " is-on" : " is-error"}">${bot.chat_ready ? "可对话" : "未就绪"}</span>
          <span class="bs-chip${bot.config_source === "bot_override" ? " is-on" : ""}">${bot.config_source === "bot_override" ? "Bot 覆盖" : "全局默认"}</span>
          ${bot.multi_brain_enabled ? '<span class="bs-chip is-on">AI 超级大脑</span>' : '<span class="bs-chip">单脑</span>'}
        </div>
      </div>
      <div class="bs-bot-models">
        <div class="bs-model-row"><span>主模型</span><code>${escapeHtml(bot.executor_model || "—")}</code></div>
        <div class="bs-model-row"><span>提取</span><code>${escapeHtml(bot.extraction_model || bot.background_model || "—")}</code></div>
        <div class="bs-model-row"><span>摘要</span><code>${escapeHtml(bot.summary_model || bot.background_model || "—")}</code></div>
        ${infraRoleRows}
      </div>
    </div>

    ${renderBrainStatusSection("五脑编排", `<div class="bs-brain-grid">${brainCards}</div>${brainDetail}`)}

    <div class="bs-dual-grid">
      ${renderBrainStatusSection("记忆层级", `
        <div class="bs-chip-row">
          ${renderBsToggleChip("记忆", mem.enabled)}
          ${renderBsToggleChip("检索", mem.retrieval_enabled)}
          ${renderBsToggleChip("写入", mem.write_enabled)}
          <span class="bs-chip">索引 ${escapeHtml(indexLabel)}</span>
        </div>
        <div class="bs-layer-chart">${renderBsLayerBars(mem)}</div>
        <div class="bs-memory-actions">
          <button type="button" class="btn btn-ghost btn-sm bs-memory-open-all" data-memory-tab="l1">查看记忆库</button>
        </div>
        ${memoryOffHint}
        ${mem.last_write_at ? `<p class="bs-footnote">最近写入 ${escapeHtml(mem.last_write_at.slice(0, 19).replace("T", " "))}</p>` : ""}
      `, "bs-panel-memory")}

      ${renderBrainStatusSection("上下文", `
        <div class="bs-context-layout">
          ${renderBsGauge(ctxPct, "压力比", formatTierLabel(tier))}
          <div class="bs-context-details">
            <div class="bs-tier-steps">${renderBsTierSteps(tier)}</div>
            <div class="bs-kv-compact"><span>保护区</span><b>${formatTokenK(ctx.protection_zone_tokens)}</b></div>
            <div class="bs-kv-compact"><span>运行摘要</span><b>${ctx.summary_active ? "已激活" : "无"}</b></div>
          </div>
        </div>
        ${renderBsCacheSection(ctx.cache ?? (state.currentSessionId ? state.lastCacheUsageBySession[state.currentSessionId] : null))}
      `, "bs-panel-context")}
    </div>

    ${renderBrainStatusSection("运行详情", `
      <div class="bs-detail-block">
        <div class="bs-detail-label">后台任务</div>
        <div class="bs-job-grid">
          ${jobCard("L1 记忆提取", "🧬", jobs.l1_extraction)}
          ${jobCard("Tier3 运行摘要", "📝", jobs.tier3_summary)}
          ${jobCard("学习脑信号", "📡", jobs.learner)}
        </div>
      </div>
      <div class="bs-detail-block">
        <div class="bs-detail-label">本轮激活</div>
        <div class="bs-activation-row">${activationChips || '<span class="brain-status-empty">发送消息后显示五脑激活情况</span>'}</div>
        <div class="bs-trace-foot">
          <span>压缩 ${escapeHtml(formatTierLabel(trace.compact_tier))}</span>
          <span>压力 ${escapeHtml(formatContextPct(trace.context_ratio))}</span>
          ${trace.memory?.cross_session ? '<span class="bs-chip is-on">跨会话</span>' : ""}
          ${trace.memory?.l0_deep_recall ? '<span class="bs-chip is-on">L0 深召回</span>' : ""}
          ${Number(trace.memory?.top_score) > 0 ? `<span class="bs-chip">召回分 ${escapeHtml(String(trace.memory.top_score))}</span>` : ""}
        </div>
        ${modelsRow}
      </div>
      ${warningsBlock}
      <div class="bs-detail-block">
        <div class="bs-detail-label">Token 分布</div>
        ${hasTokenTrace ? renderBsTokenChart(trace.tokens) : '<p class="brain-status-empty">发送消息后显示各脑区 token 占比</p>'}
      </div>
    `, "bs-panel-runtime")}
    <div class="brain-status-scroll-hint" aria-hidden="true">↓ 向下滚动查看更多</div>
  `;
}

async function openBrainStatusModal() {
  await loadBrainStatus({ silent: true });
  renderBrainStatusModal();
  await showModal(document.getElementById("brain-status-modal"));
  const scroll = document.getElementById("brain-status-scroll");
  if (scroll) scroll.scrollTop = 0;
}

function bindBrainStatusScroll() {
  const modal = document.getElementById("brain-status-modal");
  const scroll = document.getElementById("brain-status-scroll");
  if (!modal || !scroll || modal.dataset.scrollBound === "1") return;
  modal.dataset.scrollBound = "1";
  scroll.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true });
  modal.addEventListener("wheel", (e) => {
    if (modal.classList.contains("hidden")) return;
    const max = scroll.scrollHeight - scroll.clientHeight;
    if (max <= 0) return;
    const next = Math.max(0, Math.min(max, scroll.scrollTop + e.deltaY));
    if (next !== scroll.scrollTop) {
      scroll.scrollTop = next;
      e.preventDefault();
    }
    e.stopPropagation();
  }, { passive: false });
}

async function closeBrainStatusModal() {
  await hideModal(document.getElementById("brain-status-modal"));
}

const MEMORY_TAB_LABELS = { l0: "L0 证据", l1: "L1 原子", l2: "L2 摘要", l3: "L3 画像" };
const MEMORY_TYPE_LABELS = {
  fact: "事实",
  preference: "偏好",
  task: "任务",
  insight: "洞察",
  event: "事件",
};
let memorySearchTimer = null;

function formatMemoryTime(iso) {
  if (!iso) return "—";
  return String(iso).slice(0, 19).replace("T", " ");
}

function memoryLayerBadge(layer, type) {
  const label = MEMORY_TYPE_LABELS[type] || type || layer || "记忆";
  const cls = `memory-badge memory-badge-${(layer || "l1").toLowerCase()}`;
  return `<span class="${cls}">${escapeHtml(String(label).toUpperCase())}</span>`;
}

function renderMemoryMarkdown(text, options = {}) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  if (typeof renderMarkdown === "function") {
    return `<div class="md-body memory-md">${renderMarkdown(raw, { wikiLinks: false, ...options })}</div>`;
  }
  return `<p class="memory-card-body">${escapeHtml(raw)}</p>`;
}

function renderAssistantMessageHtml(text, { asMarkdown = true, isError = false } = {}) {
  const raw = String(text || "");
  if (!raw) return "";
  if (isError || !asMarkdown || typeof renderMarkdown !== "function") {
    return escapeHtml(raw);
  }
  return `<div class="md-body msg-md">${renderMarkdown(raw, { wikiLinks: false })}</div>`;
}

function setAssistantMessageBody(bodyEl, text, { asMarkdown = true, isError = false } = {}) {
  if (!bodyEl) return;
  const html = renderAssistantMessageHtml(text, { asMarkdown, isError });
  if (html.includes("<")) {
    bodyEl.innerHTML = html;
  } else {
    bodyEl.textContent = text || "";
  }
}

const CHAT_SCROLL_STICKY_PX = 96;

function getChatMessagesBox() {
  return document.getElementById("chat-messages");
}

function bindChatScrollGuard() {
  const box = getChatMessagesBox();
  if (!box || box.dataset.scrollBound === "1") return;
  box.dataset.scrollBound = "1";
  box.addEventListener(
    "scroll",
    () => {
      const dist = box.scrollHeight - box.scrollTop - box.clientHeight;
      state.chatStickToBottom = dist <= CHAT_SCROLL_STICKY_PX;
    },
    { passive: true }
  );
}

function maybeScrollChatToBottom(force = false) {
  const box = getChatMessagesBox();
  if (!box) return;
  if (!force && !state.chatStickToBottom) return;
  box.scrollTop = box.scrollHeight;
  if (force) state.chatStickToBottom = true;
}

function clearStreamingMarkdownTimer() {
  if (state.streamingMdTimer) {
    clearTimeout(state.streamingMdTimer);
    state.streamingMdTimer = null;
  }
}

function flushStreamingMarkdownUpdate(bodyEl) {
  clearStreamingMarkdownTimer();
  if (!bodyEl) return;
  setAssistantMessageBody(bodyEl, state.streamingBuffer, { asMarkdown: true });
}

function scheduleStreamingMarkdownUpdate(bodyEl) {
  if (!bodyEl) return;
  if (state.streamingMdTimer) return;
  state.streamingMdTimer = setTimeout(() => {
    state.streamingMdTimer = null;
    setAssistantMessageBody(bodyEl, state.streamingBuffer, { asMarkdown: true });
    maybeScrollChatToBottom();
  }, 100);
}

function createStreamingMessageBody(row) {
  const body = document.createElement("div");
  body.className = "msg-body";
  const cursor = document.createElement("span");
  cursor.className = "cursor";
  cursor.textContent = "▌";
  row.appendChild(body);
  row.appendChild(cursor);
  return body;
}

function renderMemoryBrowserEmpty(tab) {
  const hints = {
    l0: "发送消息后，每轮对话会写入 L0 证据。",
    l1: "后台 L1 提取任务会从对话中生成原子记忆。",
    l2: "会话运行摘要（Tier3）写入后在此显示。",
    l3: "学习脑会逐步构建用户画像，写入 L3。",
  };
  return `<div class="memory-browser-empty">
    <span>📭</span>
    <p>暂无${escapeHtml(MEMORY_TAB_LABELS[tab] || tab)}</p>
    <small>${escapeHtml(hints[tab] || "继续对话以积累记忆。")}</small>
  </div>`;
}

function renderMemoryBrowserSearchResults() {
  const hits = state.memoryBrowser.searchResults;
  if (!hits) return "";
  if (!hits.length) {
    return `<div class="memory-browser-empty"><span>🔍</span><p>未找到匹配记忆</p><small>试试更短或更通用的关键词</small></div>`;
  }
  return hits.map((h) => `
    <article class="memory-card memory-card-search">
      <div class="memory-card-head">
        ${memoryLayerBadge(h.layer, h.type)}
        <span class="memory-card-meta">${escapeHtml(h.session_id || "跨会话")}</span>
      </div>
      <div class="memory-card-body">${renderMemoryMarkdown(h.snippet || "")}</div>
    </article>
  `).join("");
}

function renderMemoryBrowserL0(items) {
  if (!items.length) return renderMemoryBrowserEmpty("l0");
  const groups = new Map();
  for (const item of items) {
    const sid = item.session_id || "unknown";
    if (!groups.has(sid)) groups.set(sid, []);
    groups.get(sid).push(item);
  }
  return [...groups.entries()].map(([sid, rows]) => `
    <section class="memory-group">
      <header class="memory-group-head">
        <strong>${escapeHtml(sid.slice(0, 8))}…</strong>
        <span>${rows.length} 条证据</span>
      </header>
      ${rows.map((item) => `
        <article class="memory-card">
          <div class="memory-card-head">
            <span class="memory-card-meta">${formatMemoryTime(item.created_at)}</span>
            <span class="memory-card-meta">${item.message_count || 0} 条消息</span>
          </div>
          <div class="memory-card-body">${renderMemoryMarkdown(item.preview || "")}</div>
        </article>
      `).join("")}
    </section>
  `).join("");
}

function renderMemoryBrowserL1(items) {
  if (!items.length) return renderMemoryBrowserEmpty("l1");
  return items.map((item) => `
    <article class="memory-card memory-card-l1" data-atom-id="${escapeHtml(item.id || "")}">
      <div class="memory-card-head">
        ${memoryLayerBadge("l1", item.type)}
        <span class="memory-card-meta">${formatMemoryTime(item.created_at)}</span>
        <button type="button" class="btn btn-ghost btn-xs memory-delete-btn" data-delete-l1="${escapeHtml(item.id || "")}" title="删除">🗑</button>
      </div>
      <div class="memory-card-body">${renderMemoryMarkdown(item.content || "")}</div>
      ${item.session_id ? `<p class="memory-card-foot">会话 ${escapeHtml(item.session_id.slice(0, 12))}…</p>` : ""}
    </article>
  `).join("");
}

function renderMemoryBrowserL2(items) {
  if (!items.length) return renderMemoryBrowserEmpty("l2");
  return items.map((item) => `
    <button type="button" class="memory-card memory-card-l2 memory-session-link" data-session-id="${escapeHtml(item.session_id || "")}">
      <div class="memory-card-head">
        <strong>${escapeHtml(item.title || item.session_id || "会话")}</strong>
        <span class="memory-card-meta">${formatMemoryTime(item.updated_at)}</span>
      </div>
      <div class="memory-card-body">${renderMemoryMarkdown(item.summary || "")}</div>
      <span class="memory-card-foot">点击切换到此会话 →</span>
    </button>
  `).join("");
}

function renderMemoryBrowserL3(profile) {
  const text = (profile || "").trim();
  if (!text) return renderMemoryBrowserEmpty("l3");
  return `<article class="memory-card memory-card-l3">
    <div class="memory-card-head"><span class="memory-badge memory-badge-l3">L3 画像</span><span class="memory-card-meta">只读</span></div>
    <div class="memory-profile">${renderMemoryMarkdown(text)}</div>
  </article>`;
}

function renderMemoryBrowserBody() {
  const scroll = document.getElementById("memory-browser-scroll");
  if (!scroll) return;
  const mb = state.memoryBrowser;
  if (mb.loading) {
    scroll.innerHTML = '<p class="memory-browser-loading">加载中…</p>';
    return;
  }
  if (mb.searchQuery && mb.searchQuery.length >= 2) {
    scroll.innerHTML = renderMemoryBrowserSearchResults();
    return;
  }
  const tab = mb.tab || "l1";
  if (tab === "l0") scroll.innerHTML = renderMemoryBrowserL0(mb.items || []);
  else if (tab === "l1") scroll.innerHTML = renderMemoryBrowserL1(mb.items || []);
  else if (tab === "l2") scroll.innerHTML = renderMemoryBrowserL2(mb.items || []);
  else scroll.innerHTML = renderMemoryBrowserL3(mb.profile || "");
}

function syncMemoryBrowserTabs() {
  document.querySelectorAll(".memory-tab[data-tab]").forEach((el) => {
    el.classList.toggle("active", el.dataset.tab === state.memoryBrowser.tab);
  });
  const search = document.getElementById("memory-browser-search-input");
  if (search && document.activeElement !== search) {
    search.value = state.memoryBrowser.searchQuery || "";
  }
}

async function animateMemoryTabScroll(action) {
  const scroll = document.getElementById("memory-browser-scroll");
  if (!scroll || !window.AnimEngine || AnimEngine.prefersReducedMotion()) return;
  await AnimEngine.run("A07", scroll, action);
  // A07 exit hides the element; keep the scroll slot mounted for tab switches.
  if (action === "exit") {
    scroll.classList.remove("hidden");
    scroll.classList.remove("is-tab-animating");
    scroll.style.opacity = "";
    scroll.style.transform = "";
    scroll.style.transition = "";
    scroll.style.willChange = "";
  }
}

async function loadMemoryTab(tab, opts = {}) {
  const botId = state.memoryBrowser.botId || state.selectedBotId;
  if (!botId) {
    showToast("请先选择一个 Bot", "warn");
    return;
  }
  if (state.memoryBrowser.tabSwitching) return;

  const sameTab = tab === state.memoryBrowser.tab && !state.memoryBrowser.searchQuery && !opts.force;
  if (sameTab) return;

  const shouldAnim = !opts.skipAnim && tab !== state.memoryBrowser.tab;
  const scroll = document.getElementById("memory-browser-scroll");

  if (shouldAnim) {
    state.memoryBrowser.tabSwitching = true;
    try {
      await animateMemoryTabScroll("exit");
    } catch {
      /* fall through to content swap */
    }
  }

  state.memoryBrowser.tab = tab;
  state.memoryBrowser.loading = true;
  if (!opts.keepSearch) {
    state.memoryBrowser.searchQuery = "";
    state.memoryBrowser.searchResults = null;
  }
  syncMemoryBrowserTabs();
  renderMemoryBrowserBody();
  if (scroll) scroll.scrollTop = 0;

  try {
    const enc = encodeURIComponent(botId);
    if (tab === "l0") {
      const q = state.memoryBrowser.sessionFilter
        ? `?session_id=${encodeURIComponent(state.memoryBrowser.sessionFilter)}&limit=50`
        : "?limit=50";
      const data = await api(`/api/bots/${enc}/memory/l0${q}`);
      state.memoryBrowser.items = data.items || [];
      state.memoryBrowser.total = data.total ?? state.memoryBrowser.items.length;
    } else if (tab === "l1") {
      const data = await api(`/api/bots/${enc}/memory/l1?limit=100`);
      state.memoryBrowser.items = data.items || [];
      state.memoryBrowser.total = data.total ?? state.memoryBrowser.items.length;
    } else if (tab === "l2") {
      const data = await api(`/api/bots/${enc}/memory/l2?limit=30`);
      state.memoryBrowser.items = data.items || [];
      state.memoryBrowser.total = state.memoryBrowser.items.length;
    } else {
      const data = await api(`/api/bots/${enc}/memory/l3`);
      state.memoryBrowser.profile = data.profile || "";
      state.memoryBrowser.items = [];
      state.memoryBrowser.total = data.profile ? 1 : 0;
    }
  } catch (err) {
    const staleBackend = /404|not found/i.test(String(err.message || ""));
    showToast(
      staleBackend
        ? "记忆库接口不存在，8766 可能仍在跑旧后端。请关闭旧 MNEMOS 窗口/进程后重新运行 启动MNEMOS.bat"
        : (err.message || "加载记忆失败"),
      "error",
      staleBackend ? 9000 : 7000,
    );
    state.memoryBrowser.items = [];
    state.memoryBrowser.total = 0;
  } finally {
    state.memoryBrowser.loading = false;
    renderMemoryBrowserBody();
    if (shouldAnim) {
      try {
        await animateMemoryTabScroll("enter");
      } catch {
        /* content already visible */
      }
      state.memoryBrowser.tabSwitching = false;
    }
  }
}

async function searchMemoryNow(query) {
  const botId = state.memoryBrowser.botId || state.selectedBotId;
  if (!botId || !query || query.length < 2) {
    state.memoryBrowser.searchResults = null;
    renderMemoryBrowserBody();
    return;
  }
  state.memoryBrowser.loading = true;
  renderMemoryBrowserBody();
  try {
    const enc = encodeURIComponent(botId);
    const data = await api(`/api/bots/${enc}/memory/search?q=${encodeURIComponent(query)}&limit=20`);
    state.memoryBrowser.searchResults = data.items || [];
  } catch (err) {
    const staleBackend = /404|not found/i.test(String(err.message || ""));
    showToast(
      staleBackend
        ? "记忆搜索接口不存在，请重启 8766 后端（启动MNEMOS.bat）"
        : (err.message || "搜索失败"),
      "error",
    );
    state.memoryBrowser.searchResults = [];
  } finally {
    state.memoryBrowser.loading = false;
    renderMemoryBrowserBody();
  }
}

function scheduleMemorySearch(query) {
  clearTimeout(memorySearchTimer);
  state.memoryBrowser.searchQuery = query;
  if (!query || query.length < 2) {
    state.memoryBrowser.searchResults = null;
    renderMemoryBrowserBody();
    return;
  }
  memorySearchTimer = setTimeout(() => searchMemoryNow(query).catch(onErr), 350);
}

async function deleteMemoryL1(atomId) {
  if (!atomId) return;
  if (!confirm("确定删除这条 L1 原子记忆？删除后无法恢复。")) return;
  const botId = state.memoryBrowser.botId || state.selectedBotId;
  if (!botId) return;
  try {
    await api(`/api/bots/${encodeURIComponent(botId)}/memory/l1/${encodeURIComponent(atomId)}`, "DELETE");
    showToast("已删除 L1 原子", "info", 3000);
    await loadMemoryTab("l1", { keepSearch: true, skipAnim: true });
    await loadBrainStatus({ silent: true });
    renderBrainStatusModal();
  } catch (err) {
    showToast(err.message || "删除失败", "error");
  }
}

async function openMemoryBrowser(opts = {}) {
  const botId = opts.botId || state.selectedBotId;
  if (!botId) {
    showToast("请先进入一个 Bot 工作区", "warn");
    return;
  }
  const memoryModal = document.getElementById("memory-browser-modal");
  if (memoryModal?.dataset.animating === "1") return;

  const bot = state.bots.find((b) => b.id === botId);
  state.memoryBrowser.botId = botId;
  state.memoryBrowser.tab = opts.tab || "l1";
  state.memoryBrowser.sessionFilter = opts.sessionFilter || null;
  state.memoryBrowser.searchQuery = "";
  state.memoryBrowser.searchResults = null;
  const title = document.getElementById("memory-browser-title");
  const subtitle = document.getElementById("memory-browser-subtitle");
  if (title) title.textContent = `${bot?.name || "Bot"} · 记忆库`;
  if (subtitle) {
    const filterHint = state.memoryBrowser.sessionFilter ? " · 当前会话 L0" : "";
    subtitle.textContent = `L0–L3 分层记忆${filterHint}`;
  }
  syncMemoryBrowserTabs();

  // Close brain-status first so memory browser gets a clean A05 enter (avoids stacked overlays).
  const brainStatusModal = document.getElementById("brain-status-modal");
  if (brainStatusModal && !brainStatusModal.classList.contains("hidden")) {
    await hideModal(brainStatusModal);
  }
  await showModal(memoryModal);
  const scroll = document.getElementById("memory-browser-scroll");
  if (scroll) scroll.scrollTop = 0;
  await loadMemoryTab(state.memoryBrowser.tab, { skipAnim: true });
}

async function closeMemoryBrowser() {
  await hideModal(document.getElementById("memory-browser-modal"));
}

function bindMemoryBrowserScroll() {
  const modal = document.getElementById("memory-browser-modal");
  const scroll = document.getElementById("memory-browser-scroll");
  if (!modal || !scroll || modal.dataset.scrollBound === "1") return;
  modal.dataset.scrollBound = "1";
  scroll.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true });
  modal.addEventListener("wheel", (e) => {
    if (modal.classList.contains("hidden")) return;
    const max = scroll.scrollHeight - scroll.clientHeight;
    if (max <= 0) return;
    const next = Math.max(0, Math.min(max, scroll.scrollTop + e.deltaY));
    if (next !== scroll.scrollTop) {
      scroll.scrollTop = next;
      e.preventDefault();
    }
    e.stopPropagation();
  }, { passive: false });
}

function bindMemoryBrowserEvents() {
  document.getElementById("btn-close-memory-browser")?.addEventListener("click", () => {
    closeMemoryBrowser().catch(onErr);
  });
  document.querySelectorAll(".memory-tab[data-tab]").forEach((el) => {
    el.addEventListener("click", () => {
      const tab = el.dataset.tab;
      if (tab === state.memoryBrowser.tab && !state.memoryBrowser.searchQuery) return;
      if (state.memoryBrowser.tabSwitching) return;
      if (tab !== "l0") state.memoryBrowser.sessionFilter = null;
      runButtonTapAnim(el)
        .then(() => loadMemoryTab(tab))
        .catch(onErr);
    });
  });
  document.getElementById("memory-browser-search-input")?.addEventListener("input", (ev) => {
    scheduleMemorySearch(ev.target.value.trim());
  });
  document.getElementById("memory-browser-scroll")?.addEventListener("click", (ev) => {
    const delBtn = ev.target.closest("[data-delete-l1]");
    if (delBtn) {
      ev.preventDefault();
      ev.stopPropagation();
      deleteMemoryL1(delBtn.dataset.deleteL1).catch(onErr);
      return;
    }
    const sessionBtn = ev.target.closest(".memory-session-link[data-session-id]");
    if (sessionBtn) {
      const sid = sessionBtn.dataset.sessionId;
      if (!sid) return;
      closeMemoryBrowser()
        .then(() => switchSession(sid))
        .catch(onErr);
    }
  });
}

function bindBrainStatusMemoryLinks() {
  const scroll = document.getElementById("brain-status-scroll");
  if (!scroll || scroll.dataset.memoryBound === "1") return;
  scroll.dataset.memoryBound = "1";
  scroll.addEventListener("click", (ev) => {
    const btn = ev.target.closest("[data-memory-tab]");
    if (!btn) return;
    ev.preventDefault();
    const tab = btn.dataset.memoryTab || "l1";
    const sessionFilter = tab === "l0" && state.currentSessionId ? state.currentSessionId : null;
    runButtonTapAnim(btn)
      .then(() => openMemoryBrowser({ tab, sessionFilter }))
      .catch(onErr);
  });
}

function bindBrainStatusBrainCards() {
  const scroll = document.getElementById("brain-status-scroll");
  if (!scroll || scroll.dataset.brainCardsBound === "1") return;
  scroll.dataset.brainCardsBound = "1";
  scroll.addEventListener("click", (ev) => {
    const closeBtn = ev.target.closest("[data-brain-close]");
    if (closeBtn) {
      ev.preventDefault();
      state.expandedBrainKey = null;
      renderBrainStatusModal();
      return;
    }
    const card = ev.target.closest("[data-brain-key]");
    if (!card || card.closest(".bs-brain-detail")) return;
    ev.preventDefault();
    const key = card.dataset.brainKey;
    state.expandedBrainKey = state.expandedBrainKey === key ? null : key;
    renderBrainStatusModal();
    if (state.expandedBrainKey) {
      const detail = scroll.querySelector(`[data-brain-detail="${state.expandedBrainKey}"]`);
      detail?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  });
}

function updateChatAvailabilityHint() {
  const hint = document.getElementById("setup-hint");
  const sendBtn = document.getElementById("btn-send");
  const bot = currentBot();
  let msg = "";
  if (!bot) {
    msg = "请先选择一个 Bot。";
  } else if (!botCanChat(bot)) {
    msg = bot.brain_message || "当前 Bot 未绑定可用供应商，请先编辑 Bot 并绑定大脑。";
  } else if (!state.currentSessionId) {
    msg = "请先在左侧创建或打开一个会话。";
  }
  if (msg) {
    hint.classList.remove("hidden");
    hint.textContent = msg;
    sendBtn.disabled = true;
  } else {
    hint.classList.add("hidden");
    sendBtn.disabled = false;
  }
}

function clearGenerationWaitTimer() {
  if (state.generationWaitTimer) {
    clearTimeout(state.generationWaitTimer);
    state.generationWaitTimer = null;
  }
}

function clearGenerationStopTimer() {
  if (state.generationStopTimer) {
    clearTimeout(state.generationStopTimer);
    state.generationStopTimer = null;
  }
}

function scheduleGenerationStopFallback() {
  clearGenerationStopTimer();
  state.generationStopTimer = setTimeout(() => {
    if (!state.activeGenerationId) return;
    abortGenerationUi({
      resync: true,
      toast: true,
      reason: "停止超时，已解除发送锁定",
    }).catch(onErr);
  }, 12000);
}

function resetGenerationStreamingState() {
  clearGenerationWaitTimer();
  clearGenerationStopTimer();
  clearStreamingMarkdownTimer();
  state.generationPhase = null;
  state.streamingEl = null;
  state.streamingWrap = null;
  state.streamingCopyBtn = null;
  state.streamingBuffer = "";
  state.streamingReasoningBuffer = "";
  state.reasoningVisibleForGeneration = true;
}

function isWsOpen() {
  return !!(state.ws && state.wsReady && state.ws.readyState === WebSocket.OPEN);
}

function removeStreamingDom() {
  if (state.streamingWrap?.parentNode) {
    state.streamingWrap.parentNode.removeChild(state.streamingWrap);
  }
  document.querySelectorAll("#chat-messages .msg-wrap.is-streaming").forEach((el) => {
    el.remove();
  });
}

async function syncSessionMessages() {
  if (!state.currentSessionId) return;
  const data = await api(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/switch`, "POST", {});
  state.currentMessages = data.messages || [];
}

async function abortGenerationUi(options = {}) {
  const { resync = false, toast = false, reason = "连接已断开，回复未完成" } = options;
  const wasGenerating = !!state.activeGenerationId || !!state.streamingWrap;
  removeStreamingDom();
  resetGenerationStreamingState();
  state.activeGenerationId = null;
  state.generationVersion = null;
  setGenerating(false);
  if (resync && state.currentSessionId) {
    try {
      await syncSessionMessages();
    } catch (err) {
      console.error(err);
    }
  }
  renderMessages();
  updateUsageHint();
  if (toast && wasGenerating) {
    showToast(`${reason}。可点消息旁 ⋯ → 重新生成`, "warn", 7000);
  }
}

async function ensureReadyToSend() {
  if (state.activeGenerationId && !isWsOpen()) {
    await abortGenerationUi({
      resync: true,
      toast: true,
      reason: "上次回复因服务中断已取消",
    });
  }
  if (state.activeGenerationId) {
    showToast("请等待当前回复结束", "info");
    return false;
  }
  if (!state.currentSessionId) {
    return false;
  }
  try {
    await ensureWS();
  } catch (err) {
    showToast(err.message || "无法连接服务器，请确认 MNEMOS 已启动", "error");
    return false;
  }
  if (!isWsOpen()) {
    showToast("无法连接服务器，请确认 MNEMOS 已启动", "error");
    return false;
  }
  return true;
}

function reasoningSettingsForBot(bot = currentBot()) {
  return {
    enabled: !!bot?.reasoning_enabled,
    visible: bot?.reasoning_visible !== false,
    level: bot?.reasoning_level || "off",
  };
}

function appendReasoningBlock(row, text, { open = false } = {}) {
  if (!text) return null;
  let block = row.querySelector(".msg-reasoning");
  if (!block) {
    block = document.createElement("details");
    block.className = "msg-reasoning";
    const summary = document.createElement("summary");
    summary.className = "msg-reasoning-summary";
    summary.textContent = "思考过程";
    const body = document.createElement("div");
    body.className = "msg-reasoning-body";
    block.appendChild(summary);
    block.appendChild(body);
    const anchor = row.querySelector(".msg-body") || row.querySelector(".content") || row.firstChild;
    if (anchor) row.insertBefore(block, anchor);
    else row.appendChild(block);
  }
  if (open) block.open = true;
  const body = block.querySelector(".msg-reasoning-body");
  if (body) body.textContent = text;
  return body;
}

function ensureStreamingReasoningBody(row, { open = true } = {}) {
  if (!state.reasoningVisibleForGeneration) return null;
  let block = row.querySelector(".msg-reasoning");
  if (!block) {
    block = document.createElement("details");
    block.className = "msg-reasoning is-live";
    if (open) block.open = true;
    const summary = document.createElement("summary");
    summary.className = "msg-reasoning-summary";
    summary.textContent = "思考过程";
    const body = document.createElement("div");
    body.className = "msg-reasoning-body";
    block.appendChild(summary);
    block.appendChild(body);
    const anchor = row.querySelector(".msg-body") || row.querySelector(".content");
    if (anchor) row.insertBefore(block, anchor);
    else row.prepend(block);
  } else if (open) {
    block.open = true;
  }
  return block.querySelector(".msg-reasoning-body");
}

function setGenerationStatusLabel(text) {
  const el = state.streamingEl?.querySelector(".msg-waiting-status");
  if (el) el.textContent = text;
}

function setGenerationPhase(phase) {
  state.generationPhase = phase;
  if (phase === "retrieving") {
    setGenerationStatusLabel("正在检索记忆…");
  } else if (phase === "waiting") {
    setGenerationStatusLabel("正在准备…");
  }
}

function beginGenerationUi() {
  clearGenerationWaitTimer();
  state.chatStickToBottom = true;
  const rs = reasoningSettingsForBot();
  state.reasoningVisibleForGeneration = rs.visible;
  ensureWaitingBubble();
  state.generationWaitTimer = setTimeout(() => {
    if (state.generationPhase === "waiting" || state.generationPhase === "retrieving") {
      setGenerationStatusLabel("仍在等待模型响应…");
    }
  }, 8000);
}

function clearMessages() {
  const box = document.getElementById("chat-messages");
  box.innerHTML = "";
  resetGenerationStreamingState();
}

async function copyMessageText(text, btn) {
  const content = String(text || "");
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
    if (btn) {
      btn.textContent = "已复制";
      btn.classList.add("copied");
      setTimeout(() => {
        btn.textContent = "复制";
        btn.classList.remove("copied");
      }, 1500);
    }
  } catch {
    showToast("复制失败", "error");
  }
}

function findLastUserMessageIndex() {
  for (let i = state.currentMessages.length - 1; i >= 0; i -= 1) {
    if (state.currentMessages[i].role === "user") return i;
  }
  return -1;
}

function canRegenerateFromUser(msg, index) {
  if (msg.role !== "user" || index !== findLastUserMessageIndex()) return false;
  if (state.activeGenerationId && isWsOpen()) return false;
  return true;
}

function canEditUserMessage(msg, index) {
  return canRegenerateFromUser(msg, index);
}

function getAssistantVersionInfo(msg) {
  const versions = msg?.versions;
  if (!versions?.length) return null;
  const index = Number.isInteger(msg.version_index) ? msg.version_index : versions.length - 1;
  return { index, total: versions.length, current: index + 1 };
}

function getAssistantDisplayContent(msg) {
  const versions = msg?.versions;
  if (!versions?.length) return msg.content || "";
  const index = Number.isInteger(msg.version_index) ? msg.version_index : versions.length - 1;
  return versions[index]?.content ?? msg.content ?? "";
}

function getAssistantReasoning(msg) {
  const versions = msg?.versions;
  if (!versions?.length) return msg.reasoning || "";
  const index = Number.isInteger(msg.version_index) ? msg.version_index : versions.length - 1;
  return versions[index]?.reasoning ?? msg.reasoning ?? "";
}

function closeMsgMenus(exceptMenu = null) {
  document.querySelectorAll(".msg-menu-pop").forEach((pop) => {
    if (exceptMenu && pop === exceptMenu) return;
    pop.classList.add("hidden");
  });
  if (!exceptMenu) state.openMsgMenu = null;
}

function createMessageToolbar(msg, index) {
  const toolbar = document.createElement("div");
  toolbar.className = "msg-toolbar";

  const copyText = msg.role === "assistant" ? getAssistantDisplayContent(msg) : (msg.content || "");
  const copyBtn = createMessageCopyButton(copyText);
  toolbar.appendChild(copyBtn);

  if (msg.role === "user") {
    const menu = document.createElement("div");
    menu.className = "msg-menu";
    const menuBtn = document.createElement("button");
    menuBtn.type = "button";
    menuBtn.className = "msg-menu-btn";
    menuBtn.setAttribute("aria-label", "更多操作");
    menuBtn.textContent = "⋯";
    const pop = document.createElement("div");
    pop.className = "msg-menu-pop hidden";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "msg-menu-item";
    editBtn.textContent = "修改";
    editBtn.disabled = !canEditUserMessage(msg, index);
    if (!editBtn.disabled) {
      editBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        closeMsgMenus();
        startUserMessageEdit(index);
      });
    }
    pop.appendChild(editBtn);

    const regenBtn = document.createElement("button");
    regenBtn.type = "button";
    regenBtn.className = "msg-menu-item";
    regenBtn.textContent = "重新生成";
    regenBtn.disabled = !canRegenerateFromUser(msg, index);
    if (!regenBtn.disabled) {
      regenBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        closeMsgMenus();
        regenerateFromUserMessage(index).catch(onErr);
      });
    }
    pop.appendChild(regenBtn);

    menuBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const willOpen = pop.classList.contains("hidden");
      closeMsgMenus();
      if (willOpen) {
        pop.classList.remove("hidden");
        state.openMsgMenu = pop;
      }
    });
    menu.appendChild(menuBtn);
    menu.appendChild(pop);
    toolbar.appendChild(menu);
  }

  return toolbar;
}

function renderAssistantVersionNav(wrap, msg, index) {
  const info = getAssistantVersionInfo(msg);
  if (!info || info.total <= 1) {
    wrap.querySelector(".msg-version-nav")?.remove();
    return;
  }

  let nav = wrap.querySelector(".msg-version-nav");
  if (!nav) {
    nav = document.createElement("div");
    nav.className = "msg-version-nav";
    nav.innerHTML = `
      <button type="button" class="msg-version-btn" data-act="prev" aria-label="上一版本">‹</button>
      <span class="msg-version-label"></span>
      <button type="button" class="msg-version-btn" data-act="next" aria-label="下一版本">›</button>
    `;
    wrap.querySelector(".msg")?.prepend(nav);
    nav.querySelector('[data-act="prev"]').addEventListener("click", () => switchAssistantVersion(index, -1));
    nav.querySelector('[data-act="next"]').addEventListener("click", () => switchAssistantVersion(index, 1));
  }

  const label = nav.querySelector(".msg-version-label");
  if (label) label.textContent = `${info.current}/${info.total}`;
  nav.querySelector('[data-act="prev"]').disabled = info.index <= 0;
  nav.querySelector('[data-act="next"]').disabled = info.index >= info.total - 1;
}

function switchAssistantVersion(msgIndex, delta) {
  const msg = state.currentMessages[msgIndex];
  const info = getAssistantVersionInfo(msg);
  if (!info) return;
  const next = info.index + delta;
  if (next < 0 || next >= info.total) return;
  msg.version_index = next;
  msg.content = msg.versions[next].content || "";
  renderMessages();
}

function startUserMessageEdit(msgIndex) {
  const msg = state.currentMessages[msgIndex];
  if (!canEditUserMessage(msg, msgIndex)) return;

  const wrap = document.querySelector(`.msg-wrap[data-msg-index="${msgIndex}"]`);
  if (!wrap || wrap.classList.contains("is-editing")) return;

  wrap.classList.add("is-editing");
  const bubble = wrap.querySelector(".msg.user");
  if (!bubble) return;

  const textarea = document.createElement("textarea");
  textarea.className = "msg-edit-input";
  textarea.value = msg.content || "";
  textarea.rows = Math.min(8, Math.max(3, (msg.content || "").split("\n").length + 1));

  const actions = document.createElement("div");
  actions.className = "msg-edit-actions";
  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn btn-secondary btn-sm";
  cancelBtn.textContent = "取消";
  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-primary btn-sm";
  saveBtn.textContent = "重新发送";

  cancelBtn.addEventListener("click", () => renderMessages());
  saveBtn.addEventListener("click", () => {
    editAndResendUserMessage(msgIndex, textarea.value).catch(onErr);
  });
  textarea.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      renderMessages();
    }
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      editAndResendUserMessage(msgIndex, textarea.value).catch(onErr);
    }
  });

  actions.appendChild(cancelBtn);
  actions.appendChild(saveBtn);
  bubble.replaceWith(textarea);
  wrap.querySelector(".msg-toolbar")?.replaceWith(actions);
  textarea.focus();
  textarea.select();
}

async function regenerateFromUserMessage(msgIndex) {
  const msg = state.currentMessages[msgIndex];
  if (!msg) return;
  await editAndResendUserMessage(msgIndex, msg.content || "");
}

async function editAndResendUserMessage(msgIndex, newContent) {
  const text = String(newContent || "").trim();
  if (!text) {
    showToast("消息不能为空", "warn");
    return;
  }
  if (!canRegenerateFromUser(state.currentMessages[msgIndex], msgIndex)) {
    showToast("只能对最后一条用户消息重新生成", "warn");
    return;
  }
  if (!(await ensureReadyToSend())) return;

  const nextMsg = state.currentMessages[msgIndex + 1];
  let priorTotal = 0;
  if (nextMsg?.role === "assistant") {
    priorTotal = nextMsg.versions?.length || 1;
  }

  state.currentMessages[msgIndex].content = text;
  if (nextMsg?.role === "assistant") {
    state.currentMessages.splice(msgIndex + 1);
  }

  state.generationVersion = { current: priorTotal + 1, total: priorTotal + 1 };
  renderMessages();

  const generationId = genId("g");
  state.activeGenerationId = generationId;
  setGenerating(true);
  beginGenerationUi();
  try {
    state.ws.send(
      JSON.stringify({
        event: "send",
        generation_id: generationId,
        session_id: state.currentSessionId,
        content: text,
        edit_last_user: true,
      })
    );
  } catch (err) {
    await abortGenerationUi({ resync: true, toast: false });
    showToast(err.message || "发送失败", "error");
    throw err;
  }
}

function createMessageCopyButton(text) {
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "msg-copy";
  copyBtn.textContent = "复制";
  copyBtn.addEventListener("click", () => copyMessageText(text, copyBtn));
  return copyBtn;
}

function buildMessageRow(msg, index) {
  const wrap = document.createElement("div");
  wrap.className = `msg-wrap ${msg.role === "user" ? "user" : "assistant"}`;
  wrap.dataset.msgIndex = String(index);
  if (msg.id) wrap.dataset.msgId = msg.id;

  const bubble = document.createElement("div");
  bubble.className = `msg ${msg.role === "user" ? "user" : "assistant"}`;
  if (msg.status === "error") bubble.classList.add("error");

  if (msg.role === "assistant") {
    const reasoning = getAssistantReasoning(msg);
    if (reasoning) {
      appendReasoningBlock(bubble, reasoning, { open: false });
    }
    const body = document.createElement("div");
    body.className = "msg-body";
    setAssistantMessageBody(body, getAssistantDisplayContent(msg), {
      isError: msg.status === "error",
    });
    bubble.appendChild(body);
    wrap.appendChild(bubble);
    renderAssistantVersionNav(wrap, msg, index);
  } else {
    bubble.textContent = msg.content || "";
    wrap.appendChild(bubble);
  }
  wrap.appendChild(createMessageToolbar(msg, index));
  return wrap;
}

function renderMessages() {
  closeMsgMenus();
  clearMessages();
  const box = document.getElementById("chat-messages");
  for (let i = 0; i < state.currentMessages.length; i += 1) {
    box.appendChild(buildMessageRow(state.currentMessages[i], i));
  }
  maybeScrollChatToBottom(true);
  updateUsageHint();
}

function setGenerating(flag) {
  document.getElementById("btn-stop").classList.toggle("hidden", !flag);
  const sendBtn = document.getElementById("btn-send");
  if (flag) sendBtn.disabled = true;
  else updateChatAvailabilityHint();
}

function buildSessionItem(session) {
  const card = document.createElement("div");
  card.className = "item session-item" + (session.id === state.currentSessionId ? " active" : "");
  card.dataset.sessionId = session.id || "";
  card.innerHTML = `
    <div class="session-item-body" data-act="open">
      <div class="session-item-head">
        <div class="item-title">${escapeHtml(session.title || "新对话")}</div>
        <div class="session-item-actions">
          <button type="button" class="session-item-action-btn" data-act="edit" title="重命名" aria-label="重命名">✎</button>
          <button type="button" class="session-item-action-btn is-danger" data-act="delete" title="删除" aria-label="删除">×</button>
        </div>
      </div>
      <div class="item-sub">${escapeHtml(session.updated_at || "")} · ${session.message_count || 0} 条</div>
    </div>
  `;
  card.querySelector('[data-act="open"]').addEventListener("click", () => switchSession(session.id).catch(onErr));
  card.querySelector('[data-act="edit"]').addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    startSessionRename(card, session.id);
  });
  card.querySelector('[data-act="delete"]').addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    deleteSessionItem(session.id).catch(onErr);
  });
  return card;
}

function startSessionRename(card, sessionId) {
  const session = state.sessions.find((s) => s.id === sessionId);
  if (!session || card.classList.contains("is-renaming")) return;

  const titleEl = card.querySelector(".item-title");
  const actions = card.querySelector(".session-item-actions");
  if (!titleEl) return;

  card.classList.add("is-renaming");
  if (actions) actions.hidden = true;

  const input = document.createElement("input");
  input.type = "text";
  input.className = "session-item-rename-input";
  input.value = session.title || "新对话";
  input.maxLength = 80;
  input.setAttribute("aria-label", "会话名称");

  const restoreTitle = (text) => {
    const div = document.createElement("div");
    div.className = "item-title";
    div.textContent = text;
    if (input.isConnected) input.replaceWith(div);
    if (actions) actions.hidden = false;
    card.classList.remove("is-renaming");
  };

  titleEl.replaceWith(input);
  input.focus();
  input.select();

  let saving = false;
  const onBlur = () => commit(true);
  const commit = async (save) => {
    if (saving) return;
    saving = true;
    input.removeEventListener("blur", onBlur);
    const next = input.value.trim();
    const current = session.title || "新对话";
    if (!save || !next || next === current) {
      restoreTitle(current);
      saving = false;
      return;
    }
    try {
      await api(`/api/sessions/${encodeURIComponent(sessionId)}`, "PUT", { title: next });
      session.title = next;
      await loadSessions(state.selectedBotId);
      renderSessionList();
      updateTitle();
    } catch (err) {
      restoreTitle(current);
      onErr(err);
    }
    saving = false;
  };

  input.addEventListener("keydown", (ev) => {
    ev.stopPropagation();
    if (ev.key === "Enter") {
      ev.preventDefault();
      commit(true);
    }
    if (ev.key === "Escape") {
      ev.preventDefault();
      commit(false);
    }
  });
  input.addEventListener("click", (ev) => ev.stopPropagation());
  input.addEventListener("blur", onBlur);
}

function renderSessionList(options = {}) {
  const { animateId = null } = options;
  const list = document.getElementById("sidebar-list");
  list.innerHTML = "";
  if (!state.sessions.length) {
    const empty = document.createElement("div");
    empty.className = "item";
    empty.innerHTML = `<div class="item-title">还没有会话</div><div class="item-sub">点击上方「+ 新建对话」</div>`;
    list.appendChild(empty);
    return;
  }
  for (const s of state.sessions) {
    const card = buildSessionItem(s);
    list.appendChild(card);
    if (animateId && s.id === animateId && window.AnimEngine) {
      AnimEngine.run("A03", card, "enter", { variant: "list" }).catch(() => {});
    }
  }
}

async function animateItemExit(selector, variant) {
  const el = document.querySelector(selector);
  if (!el || !window.AnimEngine) return;
  await AnimEngine.run("A03", el, "exit", { variant });
}

function syncSessionActiveState() {
  document.querySelectorAll(".session-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.sessionId === state.currentSessionId);
  });
}

function buildBotTile(bot, index) {
  const tile = document.createElement("div");
  tile.className = "bot-tile" + (botCanChat(bot) ? "" : " bot-tile-unready");
  const hasOverrides = botHasBrainOverrides(bot);
  tile.dataset.botId = bot.id;
  tile.style.setProperty("--jiggle-delay", `${(index % 6) * 0.04}s`);
  if (state.arrangeMode) tile.setAttribute("draggable", "true");

  tile.innerHTML = `
    <button type="button" class="bot-tile-main" data-act="enter">
      <span class="bot-tile-avatar">${escapeHtml(bot.avatar || "🤖")}</span>
      <span class="bot-tile-name">${escapeHtml(bot.name || "未命名")}</span>
      <span class="bot-tile-status">${escapeHtml(brainStatusLabel(bot))}</span>
      <span class="bot-tile-meta">${escapeHtml(botConfigSummaryLabel(bot))}</span>
      <span class="bot-tile-brain-badge ${hasOverrides ? "is-custom" : "is-default"}">${hasOverrides ? "已覆盖" : "默认"}</span>
    </button>
    <div class="bot-tile-actions">
      <button type="button" class="btn btn-ghost btn-sm" data-act="edit">编辑</button>
      <button type="button" class="btn btn-ghost btn-sm bot-tile-delete" data-act="delete">删除</button>
    </div>
  `;

  tile.querySelector('[data-act="enter"]').addEventListener("click", () => {
    if (state.arrangeMode) return;
    enterBotWorkspace(bot.id).catch(onErr);
  });
  tile.querySelector('[data-act="edit"]').addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (state.arrangeMode) {
      showToast("请先点击「完成」退出整理模式", "info");
      return;
    }
    openBotEditor(bot.id).catch(onErr);
  });
  tile.querySelector('[data-act="delete"]').addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (state.arrangeMode) return;
    deleteBot(bot.id).catch(onErr);
  });

  tile.addEventListener("dragstart", (ev) => {
    if (!state.arrangeMode) {
      ev.preventDefault();
      return;
    }
    state.dragBotId = bot.id;
    ev.dataTransfer.effectAllowed = "move";
    tile.classList.add("is-dragging");
  });
  tile.addEventListener("dragend", () => {
    state.dragBotId = null;
    tile.classList.remove("is-dragging");
    document.querySelectorAll(".bot-tile.is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
  });
  tile.addEventListener("dragover", (ev) => {
    if (!state.arrangeMode || !state.dragBotId || state.dragBotId === bot.id) return;
    ev.preventDefault();
    tile.classList.add("is-drop-target");
  });
  tile.addEventListener("dragleave", () => tile.classList.remove("is-drop-target"));
  tile.addEventListener("drop", (ev) => {
    ev.preventDefault();
    tile.classList.remove("is-drop-target");
    reorderBots(state.dragBotId, bot.id);
  });

  return tile;
}

function reorderBots(fromId, toId) {
  if (!fromId || !toId || fromId === toId) return;
  const fromIdx = state.bots.findIndex((b) => b.id === fromId);
  const toIdx = state.bots.findIndex((b) => b.id === toId);
  if (fromIdx < 0 || toIdx < 0) return;
  const next = [...state.bots];
  const [item] = next.splice(fromIdx, 1);
  next.splice(toIdx, 0, item);
  state.bots = next;
  state.orderDirty = true;
  renderLauncher();
}

function renderLauncher(options = {}) {
  const { animateId = null } = options;
  const grid = document.getElementById("launcher-grid");
  grid.classList.toggle("arrange-mode", state.arrangeMode);
  grid.innerHTML = "";

  state.bots.forEach((bot, index) => {
    const tile = buildBotTile(bot, index);
    grid.appendChild(tile);
    if (animateId && bot.id === animateId && window.AnimEngine) {
      AnimEngine.run("A03", tile, "enter", { variant: "card" }).catch(() => {});
    }
  });

  const addTile = document.createElement("button");
  addTile.type = "button";
  addTile.className = "bot-tile bot-tile-add";
  addTile.innerHTML = `<span class="bot-tile-add-icon">+</span><span class="bot-tile-add-label">新建 Bot</span>`;
  addTile.addEventListener("click", () => {
    if (state.arrangeMode) {
      showToast("请先点击「完成」退出整理模式", "info");
      return;
    }
    openBotEditor(null).catch(onErr);
  });
  grid.appendChild(addTile);

  document.getElementById("btn-arrange").textContent = state.arrangeMode ? "完成" : "整理";
  document.getElementById("launcher-hint").textContent = state.arrangeMode
    ? "拖动 Bot 卡片调整顺序，完成后点击「完成」保存"
    : "点击 Bot 进入对话 · 编辑可配置人格与大脑 · 右上角「整理」可拖动排序";
  updateTitle();
}

async function toggleArrangeMode() {
  if (!state.arrangeMode) {
    state.arrangeMode = true;
    renderLauncher();
    return;
  }
  state.arrangeMode = false;
  if (state.orderDirty) {
    await api("/api/bots/reorder", "POST", { order: state.bots.map((b) => b.id) });
    state.orderDirty = false;
    await loadBootstrap();
  }
  renderLauncher();
}

async function loadBootstrap(options = {}) {
  const data = await api("/api/bootstrap");
  state.config = data.config;
  state.providers = data.providers || [];
  state.bots = data.bots || [];
  state.hasRequiredSetup = !!data.has_required_setup;
  if (state.selectedBotId && !state.bots.some((b) => b.id === state.selectedBotId)) {
    state.selectedBotId = null;
  }
  if (state.screen === "chat" && state.selectedBotId) {
    await loadSessions(state.selectedBotId);
  }
  if (state.screen === "home") renderLauncher(options);
  else renderSessionList();
  updateTitle();
  updateChatAvailabilityHint();
  renderProviderTab();
  fillEditorProviderOptions();
  renderBrainsSettings();
  await loadBrainStatus({ silent: true });
}

function renderBrainsSettings() {
  const cfg = state.config || {};
  const brains = cfg.brains || {};
  const setCheck = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.checked = !!val;
  };
  const setNum = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = String(val ?? "");
  };
  const setSel = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = String(val ?? "");
  };
  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = String(val ?? "");
  };
  setCheck("cfg-multi-brain-enabled", cfg.multi_brain_enabled);
  setCheck("cfg-brain-trace-enabled", cfg.brain_trace_enabled);
  setCheck("cfg-brain-persona", brains.persona_enabled !== false);
  setCheck("cfg-brain-memory", brains.memory_enabled !== false);
  setCheck("cfg-brain-cognitive", brains.cognitive_enabled !== false);
  setCheck("cfg-brain-learner", brains.learner_enabled || cfg.learner_enabled);
  setCheck("cfg-memory-retrieval", cfg.memory_retrieval_enabled !== false);
  setCheck("cfg-memory-write", cfg.memory_write_enabled !== false);
  setCheck("cfg-l1-every-turn", cfg.l1_extract_every_turn !== false);
  setSel("cfg-memory-retrieval-strategy", cfg.memory_retrieval_strategy ?? "hybrid");
  setSel("cfg-knowledge-retrieval-strategy", cfg.knowledge_retrieval_strategy ?? "hybrid");
  setNum("cfg-memory-budget", cfg.memory_token_budget ?? 800);
  setNum("cfg-persona-budget", cfg.persona_token_budget ?? 400);
  setNum("cfg-cognitive-budget", cfg.cognitive_token_budget ?? 300);
  setNum("cfg-l2-every", cfg.l2_update_every_n_turns ?? 5);
  setNum("cfg-l3-every", cfg.l3_update_every_n_atoms ?? 5);
  setNum("cfg-protection-zone", cfg.protection_zone_tokens ?? 8000);
  setNum("cfg-tier1", cfg.compaction_tier1_pct ?? 60);
  setNum("cfg-tier2", cfg.compaction_tier2_pct ?? 80);
  setNum("cfg-tier3", cfg.compaction_tier3_pct ?? 95);
  setNum("cfg-summary-max", cfg.summary_max_length ?? 2000);
  setText("cfg-learner-schedule", cfg.learner_schedule ?? "0 3 * * *");
}

async function saveBrainsSettings(ev) {
  ev.preventDefault();
  const readCheck = (id) => !!document.getElementById(id)?.checked;
  const readNum = (id, fallback) => {
    const n = Number.parseInt(document.getElementById(id)?.value || "", 10);
    return Number.isFinite(n) ? n : fallback;
  };
  const readStr = (id, fallback) => {
    const v = (document.getElementById(id)?.value || "").trim();
    return v || fallback;
  };
  const payload = {
    multi_brain_enabled: readCheck("cfg-multi-brain-enabled"),
    brain_trace_enabled: readCheck("cfg-brain-trace-enabled"),
    brains: {
      persona_enabled: readCheck("cfg-brain-persona"),
      memory_enabled: readCheck("cfg-brain-memory"),
      cognitive_enabled: readCheck("cfg-brain-cognitive"),
      learner_enabled: readCheck("cfg-brain-learner"),
    },
    memory_retrieval_enabled: readCheck("cfg-memory-retrieval"),
    memory_write_enabled: readCheck("cfg-memory-write"),
    l1_extract_every_turn: readCheck("cfg-l1-every-turn"),
    learner_enabled: readCheck("cfg-brain-learner"),
    memory_retrieval_strategy: readStr("cfg-memory-retrieval-strategy", "hybrid"),
    knowledge_retrieval_strategy: readStr("cfg-knowledge-retrieval-strategy", "hybrid"),
    memory_token_budget: readNum("cfg-memory-budget", 800),
    persona_token_budget: readNum("cfg-persona-budget", 400),
    cognitive_token_budget: readNum("cfg-cognitive-budget", 300),
    l2_update_every_n_turns: readNum("cfg-l2-every", 5),
    l3_update_every_n_atoms: readNum("cfg-l3-every", 5),
    protection_zone_tokens: readNum("cfg-protection-zone", 8000),
    compaction_tier1_pct: readNum("cfg-tier1", 60),
    compaction_tier2_pct: readNum("cfg-tier2", 80),
    compaction_tier3_pct: readNum("cfg-tier3", 95),
    summary_max_length: readNum("cfg-summary-max", 2000),
    learner_schedule: readStr("cfg-learner-schedule", "0 3 * * *"),
  };
  const res = await api("/api/config", "PUT", payload);
  state.config = res.config;
  renderBrainsSettings();
  showToast("AI 超级大脑设置已保存", "success");
  await loadBrainStatus({ silent: true });
}

async function loadSessions(botId) {
  const data = await api(`/api/sessions?bot_id=${encodeURIComponent(botId)}`);
  state.sessions = data.sessions || [];
}

async function enterBotWorkspace(botId) {
  if (state.screenTransitioning) return;
  const bot = state.bots.find((b) => b.id === botId);
  if (!bot) return;
  if (!botCanChat(bot)) {
    showToast(bot.brain_message || "请先编辑 Bot 并绑定可用供应商", "error");
    openBotEditor(botId).catch(onErr);
    return;
  }
  state.screenTransitioning = true;
  try {
    state.selectedBotId = botId;
    state.currentSessionId = null;
    state.currentMessages = [];
    state.brainStatus = null;
    state.brainStatusLoading = true;
    renderBrainStatusCapsule();
    await loadSessions(botId);
    renderSessionList();
    renderMessages();
    updateChatAvailabilityHint();
    await loadBrainStatus({ silent: true });
    await animateScreenChange("chat");
  } finally {
    state.screenTransitioning = false;
  }
}

function backToHome() {
  if (state.screenTransitioning) return;
  if (state.activeGenerationId && isWsOpen()) {
    showToast("请等待当前回复结束", "info");
    return;
  }
  state.screenTransitioning = true;
  (async () => {
    try {
      if (state.activeGenerationId) {
        await abortGenerationUi({ resync: false, toast: false });
      }
      state.selectedBotId = null;
      state.currentSessionId = null;
      state.currentMessages = [];
      state.sessions = [];
      renderLauncher();
      renderMessages();
      await loadBrainStatus({ silent: true });
      await animateScreenChange("home");
    } finally {
      state.screenTransitioning = false;
    }
  })().catch(onErr);
}

async function animateChatSessionSwitch(action) {
  const panel = document.getElementById("view-chat");
  if (!panel || !window.AnimEngine) return;
  await AnimEngine.run("A08", panel, action);
}

async function switchSession(sessionId, options = {}) {
  if (!sessionId) return;
  if (sessionId === state.currentSessionId && !options.force) {
    syncSessionActiveState();
    return;
  }
  if (state.sessionSwitching) return;
  if (state.activeGenerationId && isWsOpen()) {
    showToast("请等待当前回复结束", "info");
    return;
  }
  if (state.activeGenerationId) {
    await abortGenerationUi({ resync: true, toast: false });
  }

  const skipAnim = options.skipAnim || options.skipRender;
  const canAnim = !skipAnim && window.AnimEngine && !AnimEngine.prefersReducedMotion();
  state.sessionSwitching = true;
  try {
    if (canAnim) await animateChatSessionSwitch("exit");

    const data = await api(`/api/sessions/${encodeURIComponent(sessionId)}/switch`, "POST", {});
    state.currentSessionId = sessionId;
    state.currentMessages = data.messages || [];
    state.chatStickToBottom = true;
    updateTitle();
    if (options.skipRender) syncSessionActiveState();
    else renderSessionList();
    renderMessages();
    updateChatAvailabilityHint();

    if (canAnim) await animateChatSessionSwitch("enter");

    await loadBrainStatus({ silent: true });
  } finally {
    state.sessionSwitching = false;
  }
}

async function createSession() {
  if (!state.selectedBotId) return;
  const data = await api("/api/sessions", "POST", { bot_id: state.selectedBotId });
  const newId = data.session.id;
  await loadSessions(state.selectedBotId);
  renderSessionList({ animateId: newId });
  await switchSession(newId, { skipRender: true, skipAnim: true });
  await loadBrainStatus({ silent: true });
}

async function deleteSessionItem(sessionId) {
  if (!confirm("确定删除该会话？删除后无法恢复。")) return;
  const card = document.querySelector(`.session-item[data-session-id="${CSS.escape(sessionId)}"]`);
  try {
    if (card && window.AnimEngine) {
      await AnimEngine.run("A03", card, "exit", { variant: "list" });
    } else if (card) {
      card.remove();
    }
    await api(`/api/sessions/${encodeURIComponent(sessionId)}`, "DELETE");
    if (state.currentSessionId === sessionId) {
      state.currentSessionId = null;
      state.currentMessages = [];
      renderMessages();
      updateTitle();
    }
    await loadSessions(state.selectedBotId);
    if (!state.sessions.length) renderSessionList();
    updateChatAvailabilityHint();
  } catch (err) {
    await loadSessions(state.selectedBotId);
    renderSessionList();
    onErr(err);
  }
}

async function ensureWS() {
  if (isWsOpen()) return;
  if (state.ws) {
    try {
      state.ws.onclose = null;
      state.ws.onerror = null;
      state.ws.onmessage = null;
      state.ws.close();
    } catch {
      /* ignore */
    }
    state.ws = null;
    state.wsReady = false;
  }
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${protocol}://${location.host}/ws/chat`);
  state.ws.onopen = () => { state.wsReady = true; };
  state.ws.onclose = () => {
    const wasGenerating = !!state.activeGenerationId || !!state.streamingWrap;
    state.wsReady = false;
    state.ws = null;
    if (wasGenerating) {
      abortGenerationUi({
        resync: true,
        toast: true,
        reason: "连接已断开，回复未完成",
      }).catch(onErr);
    }
  };
  state.ws.onerror = () => {
    state.wsReady = false;
  };
  state.ws.onmessage = (ev) => {
    try { handleWsEvent(JSON.parse(ev.data)); } catch (e) { console.error(e); }
  };
  await new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error("WebSocket 连接超时")), 6000);
    state.ws.addEventListener("open", () => { clearTimeout(t); resolve(); }, { once: true });
    state.ws.addEventListener("error", () => { clearTimeout(t); reject(new Error("WebSocket 连接失败")); }, { once: true });
  });
}

function ensureWaitingBubble() {
  if (state.streamingEl) return state.streamingEl;
  const box = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "msg-wrap assistant is-streaming is-waiting";
  const row = document.createElement("div");
  row.className = "msg assistant msg-waiting";

  if (state.generationVersion?.total > 1) {
    const nav = document.createElement("div");
    nav.className = "msg-version-nav is-live";
    nav.innerHTML = `<span class="msg-version-label">${state.generationVersion.current}/${state.generationVersion.total}</span>`;
    row.appendChild(nav);
  }

  const status = document.createElement("div");
  status.className = "msg-waiting-status";
  status.textContent = "正在准备…";

  const dots = document.createElement("span");
  dots.className = "msg-waiting-dots";
  dots.setAttribute("aria-hidden", "true");
  dots.innerHTML = "<span></span><span></span><span></span>";

  row.appendChild(status);
  row.appendChild(dots);
  wrap.appendChild(row);
  wrap.appendChild(createMessageCopyButton(""));
  wrap.lastElementChild.style.visibility = "hidden";
  wrap.lastElementChild.disabled = true;
  box.appendChild(wrap);
  maybeScrollChatToBottom(true);
  state.streamingWrap = wrap;
  state.streamingEl = row;
  state.streamingCopyBtn = wrap.querySelector(".msg-copy");
  state.streamingBuffer = "";
  state.generationPhase = "waiting";
  return row;
}

function upgradeWaitingToStreaming(row) {
  clearGenerationWaitTimer();
  state.generationPhase = "streaming";
  row.classList.remove("msg-waiting");
  row.querySelector(".msg-waiting-status")?.remove();
  row.querySelector(".msg-waiting-dots")?.remove();
  state.streamingWrap?.classList.remove("is-waiting");

  if (state.generationVersion?.total > 1 && !row.querySelector(".msg-version-nav")) {
    const nav = document.createElement("div");
    nav.className = "msg-version-nav is-live";
    nav.innerHTML = `<span class="msg-version-label">${state.generationVersion.current}/${state.generationVersion.total}</span>`;
    row.prepend(nav);
  }

  const body = createStreamingMessageBody(row);
  setAssistantMessageBody(body, state.streamingBuffer || "", { asMarkdown: true });
  return row;
}

function ensureStreamingBubble() {
  if (state.streamingEl) {
    if (state.generationPhase !== "streaming") {
      return upgradeWaitingToStreaming(state.streamingEl);
    }
    if (state.streamingEl.querySelector(".msg-body")) {
      return state.streamingEl;
    }
  }
  const box = document.getElementById("chat-messages");
  const wrap = document.createElement("div");
  wrap.className = "msg-wrap assistant is-streaming";
  const row = document.createElement("div");
  row.className = "msg assistant";

  if (state.generationVersion?.total > 1) {
    const nav = document.createElement("div");
    nav.className = "msg-version-nav is-live";
    nav.innerHTML = `<span class="msg-version-label">${state.generationVersion.current}/${state.generationVersion.total}</span>`;
    row.appendChild(nav);
  }

  const body = createStreamingMessageBody(row);
  wrap.appendChild(row);
  wrap.appendChild(createMessageCopyButton(""));
  wrap.lastElementChild.style.visibility = "hidden";
  wrap.lastElementChild.disabled = true;
  box.appendChild(wrap);
  maybeScrollChatToBottom(true);
  state.streamingWrap = wrap;
  state.streamingEl = row;
  state.streamingCopyBtn = wrap.querySelector(".msg-copy");
  state.streamingBuffer = "";
  state.generationPhase = "streaming";
  return row;
}

function updateStreamingVersionLabel() {
  if (!state.streamingEl || !state.generationVersion || state.generationVersion.total <= 1) return;
  let nav = state.streamingEl.querySelector(".msg-version-nav");
  if (!nav) {
    nav = document.createElement("div");
    nav.className = "msg-version-nav is-live";
    nav.innerHTML = `<span class="msg-version-label"></span>`;
    state.streamingEl.prepend(nav);
  }
  const label = nav.querySelector(".msg-version-label");
  if (label) label.textContent = `${state.generationVersion.current}/${state.generationVersion.total}`;
}

function finalizeStreamingBubble(text, isError = false) {
  const row = state.streamingEl || ensureStreamingBubble();
  const content = text || "";
  if (state.streamingReasoningBuffer && state.reasoningVisibleForGeneration) {
    appendReasoningBlock(row, state.streamingReasoningBuffer, { open: false });
    row.querySelector(".msg-reasoning")?.classList.remove("is-live");
  }
  const body = row.querySelector(".msg-body") || row.querySelector(".content");
  clearStreamingMarkdownTimer();
  if (body) {
    setAssistantMessageBody(body, content, { isError });
  }
  row.querySelector(".cursor")?.remove();
  if (isError) row.classList.add("error");
  if (state.streamingCopyBtn) {
    state.streamingCopyBtn.disabled = !content;
    state.streamingCopyBtn.style.visibility = content ? "visible" : "hidden";
    state.streamingCopyBtn.replaceWith(createMessageCopyButton(content));
    state.streamingCopyBtn = state.streamingWrap?.querySelector(".msg-copy") || null;
  }
  state.streamingWrap?.classList.remove("is-streaming", "is-waiting");
  clearGenerationWaitTimer();
  state.generationPhase = null;
}

function handleWsEvent(payload) {
  const gid = payload.generation_id || "";
  if (state.activeGenerationId && gid && gid !== state.activeGenerationId) return;
  if (payload.event === "reasoning_token") {
    const row = ensureStreamingBubble();
    state.streamingReasoningBuffer += payload.text || "";
    if (state.reasoningVisibleForGeneration) {
      if (state.generationPhase !== "streaming") {
        setGenerationPhase("streaming");
      }
      const body = ensureStreamingReasoningBody(row, { open: true });
      if (body) body.textContent = state.streamingReasoningBuffer;
      setGenerationStatusLabel("正在思考…");
    }
    maybeScrollChatToBottom();
    return;
  }
  if (payload.event === "token") {
    const row = ensureStreamingBubble();
    state.streamingBuffer += payload.text || "";
    const body = row.querySelector(".msg-body") || row.querySelector(".content");
    scheduleStreamingMarkdownUpdate(body);
    if (payload.version_total > 1) {
      state.generationVersion = {
        current: payload.version_current || state.generationVersion?.current || 1,
        total: payload.version_total,
      };
      updateStreamingVersionLabel();
    }
    maybeScrollChatToBottom();
    return;
  }
  if (payload.event === "brain_trace") {
    mergeBrainTrace(state.currentSessionId, payload.trace || {});
    if (state.activeGenerationId && state.generationPhase !== "streaming") {
      setGenerationPhase("retrieving");
    }
    return;
  }
  if (payload.event === "cache_usage") {
    const sid = payload.session_id || state.currentSessionId;
    if (sid) {
      state.lastCacheUsageBySession[sid] = {
        read: payload.cache_read,
        create: payload.cache_create,
        hit_rate: payload.hit_rate,
        supported: payload.supported,
      };
      if (sid === state.currentSessionId) {
        // Merge into brainStatus.context.cache so status panel stays in sync
        if (state.brainStatus) {
          state.brainStatus = {
            ...state.brainStatus,
            context: {
              ...(state.brainStatus.context || {}),
              cache: {
                read: payload.cache_read,
                create: payload.cache_create,
                hit_rate: payload.hit_rate,
                supported: payload.supported,
              },
            },
          };
        }
        updateUsageHint();
        if (!document.getElementById("brain-status-modal")?.classList.contains("hidden")) {
          renderBrainStatusModal();
        }
      }
    }
    return;
  }
  if (payload.event === "done" || payload.event === "stopped") {
    const msg = payload.message || {};
    if (!msg.reasoning && state.streamingReasoningBuffer) {
      msg.reasoning = state.streamingReasoningBuffer;
    }
    finalizeStreamingBubble(msg.content || state.streamingBuffer, false);
    state.currentMessages.push(msg);
    state.generationVersion = null;
    resetGenerationStreamingState();
    state.activeGenerationId = null;
    setGenerating(false);
    renderMessages();
    updateUsageHint();
    loadSessions(state.selectedBotId).then(renderSessionList);
    loadBrainStatus({ silent: true });
    return;
  }
  if (payload.event === "error") {
    const text = payload.message || "请求失败";
    const content = `❌ ${text}`;
    if (state.streamingEl) finalizeStreamingBubble(content, true);
    else {
      document.getElementById("chat-messages").appendChild(
        buildMessageRow({ role: "assistant", content, status: "error" }, state.currentMessages.length)
      );
    }
    if (payload.assistant_message) state.currentMessages.push(payload.assistant_message);
    state.generationVersion = null;
    resetGenerationStreamingState();
    state.activeGenerationId = null;
    setGenerating(false);
    renderMessages();
    updateUsageHint();
    loadSessions(state.selectedBotId).then(renderSessionList);
    loadBrainStatus({ silent: true });
  }
}

function syncComposerInputHeight(inputEl = null) {
  const input = inputEl || document.getElementById("msg-input");
  if (!input) return;
  const maxHeight = 220;
  input.style.height = "auto";
  const next = Math.min(input.scrollHeight, maxHeight);
  input.style.height = `${Math.max(next, 78)}px`;
  input.style.overflowY = input.scrollHeight > maxHeight ? "auto" : "hidden";
}

async function sendMessage() {
  const input = document.getElementById("msg-input");
  const text = (input.value || "").trim();
  if (!text) return;
  if (!(await ensureReadyToSend())) {
    if (!state.currentSessionId) showToast("请先创建或打开会话", "warn");
    return;
  }
  const generationId = genId("g");
  state.activeGenerationId = generationId;
  state.currentMessages.push({ id: genId("m"), role: "user", content: text, created_at: new Date().toISOString() });
  renderMessages();
  input.value = "";
  syncComposerInputHeight(input);
  setGenerating(true);
  beginGenerationUi();
  try {
    state.ws.send(JSON.stringify({ event: "send", generation_id: generationId, session_id: state.currentSessionId, content: text }));
  } catch (err) {
    state.currentMessages.pop();
    await abortGenerationUi({ resync: true, toast: false });
    showToast(err.message || "发送失败", "error");
  }
}

function stopMessage() {
  if (!state.activeGenerationId || !state.wsReady) return;
  state.ws.send(JSON.stringify({ event: "stop", generation_id: state.activeGenerationId }));
  scheduleGenerationStopFallback();
}

async function loadDataInfo() {
  const data = await api("/api/system/data-info");
  const el = document.getElementById("data-dir-path");
  if (el) el.textContent = data.data_dir || "-";
  const backupEl = document.getElementById("history-backup-generations");
  if (backupEl) backupEl.textContent = String(data.history_backup_generations ?? 3);
}

async function switchTab(name, options = {}) {
  const instant = !!options.instant;
  const target = ["providers", "brains", "data"].includes(name) ? name : "providers";
  document.querySelectorAll(".tab[data-tab]").forEach((el) => {
    el.classList.toggle("active", el.dataset.tab === target);
  });

  const providersEl = document.getElementById("tab-providers");
  const brainsEl = document.getElementById("tab-brains");
  const dataEl = document.getElementById("tab-data");
  const tabMap = { providers: providersEl, brains: brainsEl, data: dataEl };
  const fromKey = state.currentTab || "providers";
  const fromEl = tabMap[fromKey] || providersEl;
  const toEl = tabMap[target] || providersEl;

  const noAnim =
    instant
    || !window.AnimEngine
    || AnimEngine.prefersReducedMotion()
    || !fromEl
    || !toEl
    || fromEl === toEl
    || state.tabSwitching;

  if (noAnim) {
    providersEl.classList.toggle("hidden", target !== "providers");
    if (brainsEl) brainsEl.classList.toggle("hidden", target !== "brains");
    dataEl.classList.toggle("hidden", target !== "data");
    state.currentTab = target;
    if (target === "data") loadDataInfo().catch(onErr);
    if (target === "brains") renderBrainsSettings();
    return;
  }

  state.tabSwitching = true;
  try {
    if (!fromEl.classList.contains("hidden")) {
      await AnimEngine.run("A07", fromEl, "exit");
    } else {
      fromEl.classList.add("hidden");
    }
    toEl.classList.remove("hidden");
    await AnimEngine.run("A07", toEl, "enter");
    state.currentTab = target;
    if (target === "data") loadDataInfo().catch(onErr);
    if (target === "brains") renderBrainsSettings();
  } finally {
    state.tabSwitching = false;
  }
}

function renderProviderTab() {
  const box = document.getElementById("providers-list");
  const countEl = document.getElementById("providers-count");
  const providersTab = document.getElementById("tab-providers");
  if (providersTab) {
    providersTab.classList.remove("is-tab-animating");
    providersTab.style.pointerEvents = "";
  }
  box.innerHTML = "";
  if (countEl) countEl.textContent = `${state.providers.length} 个`;

  if (!state.providers.length) {
    box.innerHTML = `<div class="provider-empty">还没有供应商。点击「新建供应商」添加第一个大脑配置。</div>`;
    return;
  }

  for (const p of state.providers) {
    const card = document.createElement("div");
    card.className = "card provider-card";
    card.dataset.providerId = p.id;
    card.innerHTML = `
      <div class="provider-card-summary">
        <div class="provider-card-head">
          <div>
            <div class="provider-card-name">${escapeHtml(p.name || "未命名")}</div>
            <div class="provider-card-type">${escapeHtml(p.provider || "generic")}</div>
          </div>
        </div>
        <div class="provider-card-meta">
          <div><span class="meta-label">模型</span><span class="meta-value">${escapeHtml(providerModelsLabel(p))}</span></div>
          <div><span class="meta-label">优化</span><span class="meta-value">${escapeHtml(providerOptimizationsLabel(p))}</span></div>
          <div><span class="meta-label">URL</span><span class="meta-value">${escapeHtml(p.base_url || "-")}</span></div>
          <div><span class="meta-label">Key</span><span class="meta-value">${escapeHtml(p.api_key || "未设置")}</span></div>
        </div>
        <div class="row provider-card-actions">
          <button type="button" class="btn btn-secondary" data-act="edit">编辑</button>
          <button type="button" class="btn btn-secondary" data-act="test">测试</button>
          <button type="button" class="btn btn-ghost provider-card-delete" data-act="delete">删除</button>
        </div>
      </div>
      <div class="provider-card-editor" aria-hidden="true">
        <div class="provider-card-editor-inner"></div>
      </div>
    `;
    box.appendChild(card);
  }
}

function bindProviderListEvents() {
  const box = document.getElementById("providers-list");
  if (!box || box.dataset.bound === "1") return;
  box.dataset.bound = "1";
  box.addEventListener("click", (ev) => {
    const actEl = ev.target.closest("[data-act]");
    if (!actEl) return;
    const card = actEl.closest(".provider-card");
    if (!card) return;
    const providerId = card.dataset.providerId;
    if (!providerId) return;
    const act = actEl.dataset.act;
    ev.preventDefault();
    ev.stopPropagation();
    if (act === "edit") {
      const p = providerById(providerId);
      if (p) toggleProviderCardEditor(p, card).catch(onErr);
      return;
    }
    if (act === "test") {
      testProvider(providerId, actEl, card).catch(onErr);
      return;
    }
    if (act === "delete") {
      deleteProvider(providerId).catch(onErr);
    }
  });
}

function mountProviderFormHome() {
  const section = document.querySelector(".provider-form-section");
  const form = document.getElementById("provider-form");
  if (section && form && form.parentElement !== section) {
    section.appendChild(form);
  }
}

function buildProviderModelEntryRow(value = "") {
  const row = document.createElement("div");
  row.className = "model-entry-row";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "model-entry-input";
  input.placeholder = "模型 ID，如 deepseek-v4-flash";
  input.value = value;
  input.required = true;
  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-ghost btn-sm model-entry-remove";
  removeBtn.setAttribute("aria-label", "删除模型");
  removeBtn.textContent = "✕";
  removeBtn.addEventListener("click", () => removeProviderModelEntry(row));
  input.addEventListener("input", syncProviderModelRemoveButtons);
  row.appendChild(input);
  row.appendChild(removeBtn);
  return row;
}

function syncProviderModelRemoveButtons() {
  const rows = document.querySelectorAll("#provider-models-list .model-entry-row");
  rows.forEach((row) => {
    const btn = row.querySelector(".model-entry-remove");
    if (btn) btn.disabled = rows.length <= 1;
  });
}

function renderProviderModelEntries(models = []) {
  const list = document.getElementById("provider-models-list");
  if (!list) return;
  const values = (Array.isArray(models) ? models : [])
    .map((m) => String(m || "").trim())
    .filter(Boolean);
  if (!values.length) values.push("");
  list.innerHTML = "";
  values.forEach((value) => list.appendChild(buildProviderModelEntryRow(value)));
  syncProviderModelRemoveButtons();
}

function addProviderModelEntry(value = "") {
  const list = document.getElementById("provider-models-list");
  if (!list) return;
  list.appendChild(buildProviderModelEntryRow(value));
  syncProviderModelRemoveButtons();
  list.lastElementChild?.querySelector(".model-entry-input")?.focus();
}

function removeProviderModelEntry(row) {
  const list = document.getElementById("provider-models-list");
  if (!list || !row) return;
  if (list.querySelectorAll(".model-entry-row").length <= 1) return;
  row.remove();
  syncProviderModelRemoveButtons();
}

function readProviderModelEntries() {
  return [...document.querySelectorAll("#provider-models-list .model-entry-input")]
    .map((el) => el.value.trim())
    .filter(Boolean)
    .filter((v, i, arr) => arr.indexOf(v) === i);
}

async function closeProviderCardEditor(options = {}) {
  const animate = options.animate !== false;
  const card = document.querySelector(`.provider-card[data-provider-id="${state.editingProviderId}"]`);
  if (!card) {
    state.editingProviderId = null;
    mountProviderFormHome();
    return;
  }
  const editor = card.querySelector(".provider-card-editor");
  const editBtn = card.querySelector('[data-act="edit"]');
  card.classList.remove("is-editing");
  if (editor) editor.setAttribute("aria-hidden", "true");
  if (editBtn) editBtn.textContent = "编辑";
  if (animate && window.AnimEngine && !AnimEngine.prefersReducedMotion() && editor) {
    await AnimEngine.waitTransition(editor, "grid-template-rows", 340);
  }
  state.editingProviderId = null;
  mountProviderFormHome();
  document.getElementById("provider-form")?.classList.add("hidden");
}

async function openProviderCardEditor(p, card) {
  const form = document.getElementById("provider-form");
  const slot = card?.querySelector(".provider-card-editor-inner");
  if (!form || !slot || !card) return;

  hideCreateProviderForm({ keepFormHidden: true });
  await closeProviderCardEditor({ animate: false });
  document.querySelectorAll(".provider-card.is-editing").forEach((el) => {
    el.classList.remove("is-editing");
    const btn = el.querySelector('[data-act="edit"]');
    if (btn) btn.textContent = "编辑";
    el.querySelector(".provider-card-editor")?.setAttribute("aria-hidden", "true");
  });

  fillProviderForm(p);
  form.classList.remove("hidden");
  slot.appendChild(form);
  state.editingProviderId = p.id;
  card.offsetHeight;
  card.classList.add("is-editing");
  card.querySelector(".provider-card-editor")?.setAttribute("aria-hidden", "false");
  card.querySelector('[data-act="edit"]').textContent = "收起";
  form.querySelector("#provider-name")?.focus();
}

async function toggleProviderCardEditor(p, card) {
  if (state.editingProviderId === p.id && card.classList.contains("is-editing")) {
    clearProviderForm();
    await closeProviderCardEditor();
    return;
  }
  await openProviderCardEditor(p, card);
}

function hideCreateProviderForm(options = {}) {
  const form = document.getElementById("provider-form");
  const btn = document.getElementById("btn-show-provider-form");
  const title = document.getElementById("provider-form-title");
  if (!options.keepFormHidden) mountProviderFormHome();
  form?.classList.add("hidden");
  btn?.classList.remove("hidden");
  if (title) title.textContent = "供应商配置";
}

function fillProviderForm(p) {
  document.getElementById("provider-id").value = p.id || "";
  document.getElementById("provider-name").value = p.name || "";
  document.getElementById("provider-base-url").value = p.base_url || "";
  document.getElementById("provider-api-key").value = "";
  renderProviderModelEntries(providerModels(p));
  let providerType = p.provider || "generic";
  let opts = providerOptimizations(p);
  if (providerType === "deepseek") {
    providerType = "generic";
    if (!opts.includes("deepseek")) opts = ["deepseek", ...opts];
  }
  document.getElementById("provider-type").value = providerType === "anthropic" ? "anthropic" : "generic";
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val == null ? "" : String(val);
  };
  setVal("provider-max-context", p.max_context ?? 65536);
  setVal("provider-temperature", p.temperature);
  setVal("provider-max-tokens", p.max_tokens ?? 4096);
  const enabledEl = document.getElementById("provider-enabled");
  if (enabledEl) enabledEl.checked = p.enabled !== false;
  setProviderOptimizations(opts);
}

function clearProviderForm() {
  ["provider-id", "provider-name", "provider-base-url", "provider-api-key", "provider-temperature"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  renderProviderModelEntries([]);
  document.getElementById("provider-type").value = "generic";
  const mc = document.getElementById("provider-max-context");
  if (mc) mc.value = "65536";
  const mt = document.getElementById("provider-max-tokens");
  if (mt) mt.value = "4096";
  const en = document.getElementById("provider-enabled");
  if (en) en.checked = true;
  setProviderOptimizations([]);
}

function showProviderForm(mode = "create") {
  closeProviderCardEditor({ animate: false }).catch(() => {});
  mountProviderFormHome();
  const form = document.getElementById("provider-form");
  const btn = document.getElementById("btn-show-provider-form");
  const title = document.getElementById("provider-form-title");
  if (!form) return;
  form.classList.remove("hidden");
  if (btn) btn.classList.add("hidden");
  if (title) title.textContent = mode === "edit" ? "编辑供应商" : "新建供应商";
  form.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function hideProviderForm() {
  hideCreateProviderForm();
  closeProviderCardEditor({ animate: false }).catch(() => {});
}

function bindOptimizationPicker() {
  const picker = document.getElementById("provider-optimizations");
  if (!picker || picker.dataset.bound === "1") return;
  picker.dataset.bound = "1";
  picker.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".opt-pill");
    if (!btn) return;
    const val = (btn.dataset.opt || "").trim().toLowerCase();
    if (!val) {
      setProviderOptimizations([]);
      return;
    }
    const current = readProviderOptimizations();
    const next = current.includes(val) ? current.filter((x) => x !== val) : [...current, val];
    setProviderOptimizations(next);
  });
}

async function saveProviderForm(ev) {
  ev.preventDefault();
  const id = document.getElementById("provider-id").value.trim();
  const models = readProviderModelEntries();
  const maxContext = parseNullableInt(document.getElementById("provider-max-context")?.value);
  const maxTokens = parseNullableInt(document.getElementById("provider-max-tokens")?.value);
  const temperature = parseNullableNumber(document.getElementById("provider-temperature")?.value);
  const payload = {
    name: document.getElementById("provider-name").value.trim(),
    base_url: document.getElementById("provider-base-url").value.trim(),
    api_key: document.getElementById("provider-api-key").value.trim(),
    models,
    model: models[0] || "",
    provider: document.getElementById("provider-type").value,
    optimizations: readProviderOptimizations(),
    enabled: !!document.getElementById("provider-enabled")?.checked,
    max_context: maxContext == null ? 65536 : maxContext,
    max_tokens: maxTokens,
    temperature,
  };
  if (!payload.name || !payload.base_url || !models.length) {
    alert("请填写名称、Base URL，并至少添加一个模型");
    return;
  }
  let res;
  if (id) res = await api(`/api/providers/${encodeURIComponent(id)}`, "PUT", payload);
  else res = await api("/api/providers", "POST", payload);
  const savedModels = providerModels(res?.provider);
  clearProviderForm();
  state.editingProviderId = null;
  hideProviderForm();
  await loadBootstrap();
  if (savedModels.length !== models.length) {
    showToast(`保存异常：提交了 ${models.length} 个模型，但只写入了 ${savedModels.length} 个。8766 端口可能仍在跑旧后端，请关闭旧窗口/进程后重新启动。`, "error", 9000);
    return;
  }
  showToast(`供应商已保存（${savedModels.length} 个模型）`, "success");
}

async function testProvider(providerId, btn, card) {
  const label = btn?.textContent || "测试";
  setProviderCardStatus(card, "正在测试连接…", "info");
  showToast("正在测试供应商连接…", "info", 4000);
  if (btn) {
    btn.disabled = true;
    btn.textContent = "测试中…";
  }
  try {
    const res = await api(`/api/providers/${encodeURIComponent(providerId)}/test`, "POST", {});
    const msg = res.msg || (res.success ? "连接成功" : "连接失败");
    setProviderCardStatus(card, msg, res.success ? "success" : "error");
    showToast(msg, res.success ? "success" : "error", 8000);
  } catch (err) {
    const msg = err.message || "连接测试失败";
    setProviderCardStatus(card, msg, "error");
    showToast(msg, "error", 8000);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = label;
    }
  }
}

async function deleteProvider(providerId) {
  if (!confirm("确定删除该供应商？")) return;
  await api(`/api/providers/${encodeURIComponent(providerId)}`, "DELETE");
  await loadBootstrap();
}

function fillEditorProviderOptions(selectedId = "") {
  const sel = document.getElementById("editor-bot-profile");
  if (!sel) return;
  sel.innerHTML = '<option value="">未绑定</option>';
  for (const p of state.providers) {
    const opt = document.createElement("option");
    opt.value = p.id;
    const count = providerModels(p).length;
    opt.textContent = count
      ? `${p.name || p.id}（${count} 个模型）`
      : `${p.name || p.id}（未配置模型）`;
    sel.appendChild(opt);
  }
  sel.value = selectedId || "";
}

function fillEditorModelOptions(profileId, selectedModel = "") {
  const wrap = document.getElementById("editor-bot-model-wrap");
  const sel = document.getElementById("editor-bot-model");
  if (!wrap || !sel) return;

  const p = providerById(profileId);
  const models = providerModels(p);
  if (!profileId || !models.length) {
    wrap.classList.add("hidden");
    sel.innerHTML = '<option value="">请先绑定供应商</option>';
    sel.value = "";
    sel.disabled = true;
    return;
  }

  wrap.classList.remove("hidden");
  sel.disabled = false;
  sel.innerHTML = "";
  for (const model of models) {
    const opt = document.createElement("option");
    opt.value = model;
    opt.textContent = model;
    sel.appendChild(opt);
  }
  if (selectedModel && models.includes(selectedModel)) sel.value = selectedModel;
  else sel.value = models[0];
}

function fillEditorBackgroundModelOptions(profileId, selectedModel = "") {
  const wrap = document.getElementById("editor-bot-background-model-wrap");
  const sel = document.getElementById("editor-bot-background-model");
  if (!wrap || !sel) return;

  const p = providerById(profileId);
  const models = providerModels(p);
  if (!profileId || !models.length) {
    wrap.classList.add("hidden");
    sel.innerHTML = '<option value="">继承主模型</option>';
    sel.value = "";
    sel.disabled = true;
    return;
  }

  wrap.classList.remove("hidden");
  sel.disabled = false;
  sel.innerHTML = "";
  const inherit = document.createElement("option");
  inherit.value = "";
  inherit.textContent = "继承主模型";
  sel.appendChild(inherit);
  for (const model of models) {
    const opt = document.createElement("option");
    opt.value = model;
    opt.textContent = model;
    sel.appendChild(opt);
  }
  if (selectedModel && models.includes(selectedModel)) sel.value = selectedModel;
  else sel.value = "";
}

function fillEditorRoleModelOptions(profileId, selectedModel = "", selectId = "", wrapId = "") {
  const wrap = document.getElementById(wrapId);
  const sel = document.getElementById(selectId);
  if (!wrap || !sel) return;

  const p = providerById(profileId);
  const models = providerModels(p);
  if (!profileId || !models.length) {
    wrap.classList.add("hidden");
    sel.innerHTML = '<option value="">留空继承</option>';
    sel.value = "";
    sel.disabled = true;
    return;
  }

  wrap.classList.remove("hidden");
  sel.disabled = false;
  sel.innerHTML = "";
  const inherit = document.createElement("option");
  inherit.value = "";
  inherit.textContent = "留空继承";
  sel.appendChild(inherit);
  for (const model of models) {
    const opt = document.createElement("option");
    opt.value = model;
    opt.textContent = model;
    sel.appendChild(opt);
  }
  if (selectedModel && models.includes(selectedModel)) sel.value = selectedModel;
  else sel.value = "";
}

function fillEditorModelRoles(profileId, modelRoles = {}) {
  const roles = modelRoles || {};
  fillEditorRoleModelOptions(
    profileId,
    roles.extraction?.model || "",
    "editor-role-extraction-model",
    "editor-role-extraction-wrap",
  );
  fillEditorRoleModelOptions(
    profileId,
    roles.summary?.model || "",
    "editor-role-summary-model",
    "editor-role-summary-wrap",
  );
}

function applyEditorBrainPlaceholders() {
  const defaults = (state.config || {}).brains || {};
  const setPlaceholder = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.placeholder = value == null ? "留空继承" : `继承默认：${value}`;
  };
  setPlaceholder("editor-brain-memory-budget", state.config?.memory_token_budget ?? 800);
  setPlaceholder("editor-brain-persona-budget", state.config?.persona_token_budget ?? 400);
  setPlaceholder("editor-brain-cognitive-budget", state.config?.cognitive_token_budget ?? 300);
  setPlaceholder("editor-brain-protection-zone", state.config?.protection_zone_tokens ?? 8000);
  setPlaceholder("editor-brain-tier1", state.config?.compaction_tier1_pct ?? 60);
  setPlaceholder("editor-brain-tier2", state.config?.compaction_tier2_pct ?? 80);
  setPlaceholder("editor-brain-tier3", state.config?.compaction_tier3_pct ?? 95);
  setPlaceholder("editor-brain-summary-max", state.config?.summary_max_length ?? 2000);
  const setSelectHint = (id, key, globalVal) => {
    const el = document.getElementById(id);
    if (!el) return;
    const raw = defaults[key] !== undefined ? defaults[key] : globalVal;
    const hint = raw === false ? "继承全局（当前默认：关闭）" : "继承全局（当前默认：启用）";
    if (el.options.length) el.options[0].textContent = hint;
  };
  setSelectHint("editor-brain-persona", "persona_enabled");
  setSelectHint("editor-brain-memory", "memory_enabled");
  setSelectHint("editor-brain-cognitive", "cognitive_enabled");
  setSelectHint("editor-brain-learner", "learner_enabled");
  setSelectHint("editor-brain-memory-retrieval", "memory_retrieval_enabled", state.config?.memory_retrieval_enabled !== false);
  setSelectHint("editor-brain-memory-write", "memory_write_enabled", state.config?.memory_write_enabled !== false);
  setSelectHint("editor-brain-l1-every-turn", "l1_extract_every_turn", state.config?.l1_extract_every_turn !== false);
}

function writeBotBrainsToEditor(brains = {}) {
  const setSwitch = (id, val) => {
    const el = document.getElementById(id);
    if (!el) return;
    if (typeof val === "boolean") el.value = val ? "true" : "false";
    else el.value = "";
  };
  const setBudget = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val == null ? "" : String(val);
  };
  setSwitch("editor-brain-persona", brains.persona_enabled);
  setSwitch("editor-brain-memory", brains.memory_enabled);
  setSwitch("editor-brain-cognitive", brains.cognitive_enabled);
  setSwitch("editor-brain-learner", brains.learner_enabled);
  setSwitch("editor-brain-memory-retrieval", brains.memory_retrieval_enabled);
  setSwitch("editor-brain-memory-write", brains.memory_write_enabled);
  setSwitch("editor-brain-l1-every-turn", brains.l1_extract_every_turn);
  setBudget("editor-brain-memory-budget", brains.memory_token_budget);
  setBudget("editor-brain-persona-budget", brains.persona_token_budget);
  setBudget("editor-brain-cognitive-budget", brains.cognitive_token_budget);
  setBudget("editor-brain-protection-zone", brains.protection_zone_tokens);
  setBudget("editor-brain-tier1", brains.compaction_tier1_pct);
  setBudget("editor-brain-tier2", brains.compaction_tier2_pct);
  setBudget("editor-brain-tier3", brains.compaction_tier3_pct);
  setBudget("editor-brain-summary-max", brains.summary_max_length);
  fillEditorModelRoles(
    document.getElementById("editor-bot-profile")?.value || "",
    brains.model_roles || {},
  );
}

function renderEditorBrainsDefaults(bot = null) {
  const el = document.getElementById("editor-brains-defaults");
  if (!el) return;
  const cfg = state.config || {};
  const effective = bot?.effective_brains || {};
  const gMem = cfg.memory_token_budget ?? 800;
  const gPersona = cfg.persona_token_budget ?? 400;
  const gCog = cfg.cognitive_token_budget ?? 300;
  const eMem = effective.memory_token_budget ?? gMem;
  const ePersona = effective.persona_token_budget ?? gPersona;
  const eCog = effective.cognitive_token_budget ?? gCog;
  el.textContent = `平台默认：记忆 ${gMem} / 人格 ${gPersona} / 左脑 ${gCog}；当前 Bot 生效：记忆 ${eMem} / 人格 ${ePersona} / 左脑 ${eCog}`;
}

function readBotBrainsFromEditor() {
  const out = {};
  const readSwitch = (id, key) => {
    const v = document.getElementById(id)?.value;
    if (v === "true") out[key] = true;
    else if (v === "false") out[key] = false;
  };
  const readBudget = (id, key) => {
    const val = parseNullableInt(document.getElementById(id)?.value);
    if (val != null) out[key] = val;
  };
  readSwitch("editor-brain-persona", "persona_enabled");
  readSwitch("editor-brain-memory", "memory_enabled");
  readSwitch("editor-brain-cognitive", "cognitive_enabled");
  readSwitch("editor-brain-learner", "learner_enabled");
  readSwitch("editor-brain-memory-retrieval", "memory_retrieval_enabled");
  readSwitch("editor-brain-memory-write", "memory_write_enabled");
  readSwitch("editor-brain-l1-every-turn", "l1_extract_every_turn");
  readBudget("editor-brain-memory-budget", "memory_token_budget");
  readBudget("editor-brain-persona-budget", "persona_token_budget");
  readBudget("editor-brain-cognitive-budget", "cognitive_token_budget");
  readBudget("editor-brain-protection-zone", "protection_zone_tokens");
  readBudget("editor-brain-tier1", "compaction_tier1_pct");
  readBudget("editor-brain-tier2", "compaction_tier2_pct");
  readBudget("editor-brain-tier3", "compaction_tier3_pct");
  readBudget("editor-brain-summary-max", "summary_max_length");
  const profileId = document.getElementById("editor-bot-profile")?.value?.trim() || "";
  const extractionModel = document.getElementById("editor-role-extraction-model")?.value?.trim() || "";
  const summaryModel = document.getElementById("editor-role-summary-model")?.value?.trim() || "";
  const modelRoles = {};
  if (extractionModel) modelRoles.extraction = { profile_id: profileId, model: extractionModel };
  if (summaryModel) modelRoles.summary = { profile_id: profileId, model: summaryModel };
  if (Object.keys(modelRoles).length) out.model_roles = modelRoles;
  return out;
}

function updateEditorMaxContext(profileId) {
  const el = document.getElementById("editor-bot-max-context");
  if (!el) return;
  const pid = (profileId || "").trim();
  const profile = pid ? (state.providers || []).find((p) => p.id === pid) : null;
  if (!profile) {
    el.textContent = "—（未绑定供应商，默认 65536）";
    return;
  }
  const mc = Number.parseInt(profile.max_context, 10);
  const value = Number.isFinite(mc) && mc > 0 ? mc : 65536;
  el.textContent = `${value.toLocaleString()} token`;
}

function updateEditorBrainStatus(profileId) {
  const box = document.getElementById("editor-brain-status");
  const modelSel = document.getElementById("editor-bot-model");
  const bgModelSel = document.getElementById("editor-bot-background-model");
  const selectedModel = modelSel?.disabled ? "" : (modelSel?.value || "").trim();
  const selectedBgModel = bgModelSel?.disabled ? "" : (bgModelSel?.value || "").trim();
  if (!state.providers.length) {
    box.className = "brain-status brain-status-warn";
    box.textContent = "还没有供应商。请先去设置新增供应商，再回来绑定大脑。";
    return;
  }
  if (!profileId) {
    box.className = "brain-status brain-status-warn";
    box.textContent = "当前 Bot 尚未绑定大脑。";
    return;
  }
  const p = providerById(profileId);
  if (!p) {
    box.className = "brain-status brain-status-error";
    box.textContent = "绑定的供应商不存在，请重新选择。";
    return;
  }
  const models = providerModels(p);
  const baseReady = !!(p.enabled !== false && p.has_api_key && p.base_url && models.length);
  if (!baseReady) {
    box.className = "brain-status brain-status-warn";
    box.textContent = `供应商「${p.name || p.id}」配置不完整，请前往设置补全 API Key / URL / 模型列表。`;
    return;
  }
  if (!selectedModel) {
    box.className = "brain-status brain-status-warn";
    box.textContent = `已绑定 ${p.name || p.id}，请选择要使用的模型。`;
    return;
  }
  box.className = "brain-status brain-status-ok";
  box.textContent = selectedBgModel
    ? `已绑定：${p.name || p.id} · 主模型 ${selectedModel} · 后台 ${selectedBgModel}`
    : `已绑定：${p.name || p.id} · 主模型 ${selectedModel} · 后台继承主模型`;
}

function updateEditorAvatarPreview() {
  const input = document.getElementById("editor-bot-avatar");
  const preview = document.getElementById("editor-bot-avatar-preview");
  const label = document.getElementById("editor-bot-avatar-label");
  const avatar = (input?.value || "").trim() || "🤖";
  if (preview) preview.textContent = avatar;
  if (label) label.textContent = "当前头像";
  document.querySelectorAll(".avatar-option").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.avatar === avatar);
  });
}

function setAvatarLibraryExpanded(expanded) {
  const lib = document.getElementById("editor-avatar-library");
  const btn = document.getElementById("btn-toggle-avatar-library");
  if (!lib || !btn) return;
  lib.classList.toggle("hidden", !expanded);
  btn.setAttribute("aria-expanded", expanded ? "true" : "false");
  btn.textContent = expanded ? "收起头像库" : "展开头像库";
}

function renderAvatarPicker() {
  const grid = document.getElementById("editor-avatar-grid");
  if (!grid || grid.childElementCount) return;
  for (const emoji of AVATAR_OPTIONS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "avatar-option";
    btn.dataset.avatar = emoji;
    btn.textContent = emoji;
    btn.title = emoji;
    btn.addEventListener("click", () => {
      document.getElementById("editor-bot-avatar").value = emoji;
      updateEditorAvatarPreview();
    });
    grid.appendChild(btn);
  }
}

function setEditorFileSource(kind, label) {
  const el = document.getElementById(kind === "soul" ? "editor-soul-source" : "editor-constraints-source");
  if (el) el.textContent = label || "未选择文件";
}

function resetBotEditorDraft() {
  state.botEditor = {
    soul: "",
    soulSource: "",
    constraints: "",
    constraintsSource: "",
  };
  setEditorFileSource("soul", "未选择文件");
  setEditorFileSource("constraints", "未选择文件");
  const soulLib = document.getElementById("editor-soul-library");
  const constraintsLib = document.getElementById("editor-constraints-library");
  if (soulLib) soulLib.value = "";
  if (constraintsLib) constraintsLib.value = "";
  const soulFile = document.getElementById("editor-soul-file");
  const constraintsFile = document.getElementById("editor-constraints-file");
  if (soulFile) soulFile.value = "";
  if (constraintsFile) constraintsFile.value = "";
}

async function loadSoulLibraryOptions(excludeBotId = "") {
  try {
    const [soulData, constraintsData] = await Promise.all([
      api("/api/soul-files?kind=soul"),
      api("/api/soul-files?kind=constraints"),
    ]);
    const soulSel = document.getElementById("editor-soul-library");
    const constraintsSel = document.getElementById("editor-constraints-library");
    if (soulSel) {
      soulSel.innerHTML = '<option value="">从已有 Soul 选择…</option>';
      for (const item of soulData.files || []) {
        if (item.bot_id === excludeBotId) continue;
        const opt = document.createElement("option");
        opt.value = item.bot_id;
        opt.textContent = `${item.label} · ${item.relative_path}`;
        soulSel.appendChild(opt);
      }
    }
    if (constraintsSel) {
      constraintsSel.innerHTML = '<option value="">从已有 Constraints 选择…</option>';
      for (const item of constraintsData.files || []) {
        if (item.bot_id === excludeBotId) continue;
        const opt = document.createElement("option");
        opt.value = item.bot_id;
        opt.textContent = `${item.label} · ${item.relative_path}`;
        constraintsSel.appendChild(opt);
      }
    }
  } catch (err) {
    console.warn("loadSoulLibraryOptions failed", err);
    showToast("无法加载已有 Soul 列表，可直接选择本地文件", "info");
  }
}

function readLocalTextFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.readAsText(file, "UTF-8");
  });
}

async function pickLocalSoulFile(file) {
  if (!file) return;
  const text = await readLocalTextFile(file);
  state.botEditor.soul = text;
  state.botEditor.soulSource = file.name;
  setEditorFileSource("soul", `本地文件：${file.name}`);
}

async function pickLocalConstraintsFile(file) {
  if (!file) return;
  const text = await readLocalTextFile(file);
  state.botEditor.constraints = text;
  state.botEditor.constraintsSource = file.name;
  setEditorFileSource("constraints", `本地文件：${file.name}`);
}

async function selectLibrarySoul(botId) {
  if (!botId) return;
  const data = await api(`/api/bots/${encodeURIComponent(botId)}/soul`);
  state.botEditor.soul = data.soul || "";
  state.botEditor.soulSource = `souls/${botId}/soul.md`;
  setEditorFileSource("soul", `已有文件：souls/${botId}/soul.md`);
}

async function selectLibraryConstraints(botId) {
  if (!botId) return;
  const data = await api(`/api/bots/${encodeURIComponent(botId)}/soul`);
  state.botEditor.constraints = data.constraints || "";
  if (!state.botEditor.constraints) {
    showToast("该 Bot 没有 constraints 文件", "info");
    setEditorFileSource("constraints", "未选择文件");
    return;
  }
  state.botEditor.constraintsSource = `souls/${botId}/constraints.md`;
  setEditorFileSource("constraints", `已有文件：souls/${botId}/constraints.md`);
}

async function openBotEditor(botId) {
  const modal = document.getElementById("bot-editor-modal");
  if (!modal) {
    showToast("无法打开编辑弹窗，请刷新页面", "error");
    return;
  }

  try {
    document.getElementById("bot-editor-title").textContent = botId ? "编辑 Bot" : "新建 Bot";
    document.getElementById("editor-bot-id").value = botId || "";
    fillEditorProviderOptions();
    applyEditorBrainPlaceholders();
    resetBotEditorDraft();

    const bot = botId ? state.bots.find((b) => b.id === botId) : null;
    if (bot) {
      document.getElementById("editor-bot-name").value = bot.name || "";
      document.getElementById("editor-bot-avatar").value = bot.avatar || "🤖";
      document.getElementById("editor-bot-profile").value = bot.profile_id || "";
      document.getElementById("editor-bot-temperature").value = bot.temperature == null ? "" : String(bot.temperature);
      document.getElementById("editor-bot-max-tokens").value = bot.max_tokens == null ? "" : String(bot.max_tokens);
      fillEditorProviderOptions(bot.profile_id || "");
      fillEditorModelOptions(bot.profile_id || "", bot.model || "");
      fillEditorBackgroundModelOptions(bot.profile_id || "", bot.background_model || "");
      document.getElementById("editor-bot-reasoning-enabled").checked = !!bot.reasoning_enabled;
      document.getElementById("editor-bot-reasoning-level").value = bot.reasoning_level || "off";
      document.getElementById("editor-bot-reasoning-visible").checked = bot.reasoning_visible !== false;
      writeBotBrainsToEditor(bot.brains || {});
      renderEditorBrainsDefaults(bot);
      state.botEditor.soulSource = `souls/${botId}/soul.md`;
      setEditorFileSource("soul", `当前：souls/${botId}/soul.md`);
      updateEditorBrainStatus(bot.profile_id || "");
      updateEditorMaxContext(bot.profile_id || "");
    } else {
      document.getElementById("editor-bot-name").value = "";
      document.getElementById("editor-bot-avatar").value = "🤖";
      document.getElementById("editor-bot-profile").value = "";
      document.getElementById("editor-bot-temperature").value = "";
      document.getElementById("editor-bot-max-tokens").value = "";
      fillEditorProviderOptions("");
      fillEditorModelOptions("", "");
      fillEditorBackgroundModelOptions("", "");
      document.getElementById("editor-bot-reasoning-enabled").checked = false;
      document.getElementById("editor-bot-reasoning-level").value = "off";
      document.getElementById("editor-bot-reasoning-visible").checked = true;
      writeBotBrainsToEditor({});
      renderEditorBrainsDefaults(null);
      updateEditorBrainStatus("");
      updateEditorMaxContext("");
    }

    updateEditorAvatarPreview();
    setAvatarLibraryExpanded(false);
  } catch (err) {
    console.error("openBotEditor setup failed", err);
    showToast("加载编辑表单时出错，仍可尝试编辑", "error");
  }

  await showModal(modal);

  await loadSoulLibraryOptions(botId || "");

  if (botId) {
    try {
      const soulData = await api(`/api/bots/${encodeURIComponent(botId)}/soul`);
      state.botEditor.soul = soulData.soul || "";
      state.botEditor.constraints = soulData.constraints || "";
      state.botEditor.constraintsSource = soulData.constraints ? `souls/${botId}/constraints.md` : "";
      setEditorFileSource(
        "constraints",
        soulData.constraints ? `当前：souls/${botId}/constraints.md` : "未选择文件"
      );
    } catch (err) {
      console.warn("load bot soul failed", err);
      showToast("无法加载 Soul 内容，可直接选择本地文件", "error");
    }
  }
}

async function closeBotEditor() {
  await hideModal(document.getElementById("bot-editor-modal"));
}

async function cancelBotEditor() {
  await runButtonTapAnim(document.getElementById("btn-cancel-bot-editor"));
  await closeBotEditor();
}

async function openSettingsModal(tab = "providers") {
  const modal = document.getElementById("settings-modal");
  modal?.classList.remove("is-modal-animating");
  document.querySelectorAll(".tab-content.is-tab-animating").forEach((el) => {
    el.classList.remove("is-tab-animating");
    el.style.pointerEvents = "";
  });
  await showModal(modal);
  await switchTab(tab, { instant: true });
}

async function openHelpModal() {
  await showModal(document.getElementById("help-modal"));
}

async function closeHelpModal() {
  await hideModal(document.getElementById("help-modal"));
}

async function closeSettingsModal() {
  clearProviderForm();
  state.editingProviderId = null;
  hideProviderForm();
  await hideModal(document.getElementById("settings-modal"));
}

async function saveBotEditor(ev) {
  ev.preventDefault();
  await runButtonTapAnim(ev.submitter);
  const id = document.getElementById("editor-bot-id").value.trim();
  const payload = {
    name: document.getElementById("editor-bot-name").value.trim(),
    avatar: document.getElementById("editor-bot-avatar").value.trim() || "🤖",
    profile_id: document.getElementById("editor-bot-profile").value || "",
    model: document.getElementById("editor-bot-model").value.trim(),
    background_model: document.getElementById("editor-bot-background-model")?.value?.trim() || "",
    temperature: parseNullableNumber(document.getElementById("editor-bot-temperature").value),
    max_tokens: parseNullableInt(document.getElementById("editor-bot-max-tokens").value),
    reasoning_enabled: !!document.getElementById("editor-bot-reasoning-enabled")?.checked,
    reasoning_level: document.getElementById("editor-bot-reasoning-level")?.value || "off",
    reasoning_visible: document.getElementById("editor-bot-reasoning-visible")?.checked !== false,
    brains: readBotBrainsFromEditor(),
  };
  const soul = state.botEditor.soul;
  const constraints = state.botEditor.constraints;

  if (!payload.name) {
    alert("请填写 Bot 名称");
    return;
  }
  if (payload.reasoning_enabled && (!payload.reasoning_level || payload.reasoning_level === "off")) {
    payload.reasoning_level = "medium";
  }
  if (payload.profile_id && !payload.model) {
    alert("请选择要使用的模型");
    return;
  }
  if (payload.profile_id) {
    const models = providerModels(providerById(payload.profile_id));
    if (models.length && !models.includes(payload.model)) {
      alert("所选模型不在供应商列表中，请重新选择");
      return;
    }
    if (payload.background_model && models.length && !models.includes(payload.background_model)) {
      alert("后台模型不在供应商列表中，请重新选择");
      return;
    }
  }

  let botId = id;
  if (id) {
    await api(`/api/bots/${encodeURIComponent(id)}`, "PUT", payload);
  } else {
    const res = await api("/api/bots", "POST", payload);
    botId = res.bot.id;
  }
  const shouldSaveSoul = id || state.botEditor.soulSource || state.botEditor.constraintsSource;
  if (shouldSaveSoul) {
    await api(`/api/bots/${encodeURIComponent(botId)}/soul`, "PUT", { soul, constraints });
  }

  await closeBotEditor();
  await loadBootstrap(id ? {} : { animateId: botId });
  await loadBrainStatus({ silent: true });
  showToast(id ? "Bot 已更新" : "Bot 已创建", "success");
}

async function deleteBot(botId) {
  if (state.arrangeMode) {
    showToast("请先点击「完成」退出整理模式", "info");
    return;
  }
  if (!confirm("确定删除该 Bot？")) return;
  await animateItemExit(`.bot-tile[data-bot-id="${CSS.escape(botId)}"]`, "card");
  await api(`/api/bots/${encodeURIComponent(botId)}`, "DELETE");
  if (state.selectedBotId === botId) backToHome();
  await loadBootstrap();
}

function parseNullableNumber(v) {
  const x = String(v || "").trim();
  if (!x) return null;
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function parseNullableInt(v) {
  const x = String(v || "").trim();
  if (!x) return null;
  const n = Number.parseInt(x, 10);
  return Number.isFinite(n) ? n : null;
}

function bindEditorEvents() {
  const pairs = [
    ["btn-close-bot-editor", () => closeBotEditor().catch(onErr)],
    ["btn-cancel-bot-editor", () => cancelBotEditor().catch(onErr)],
    ["btn-toggle-avatar-library", () => {
      const expanded = document.getElementById("btn-toggle-avatar-library")?.getAttribute("aria-expanded") === "true";
      setAvatarLibraryExpanded(!expanded);
    }],
    ["btn-pick-soul-file", () => document.getElementById("editor-soul-file")?.click()],
    ["btn-pick-constraints-file", () => document.getElementById("editor-constraints-file")?.click()],
  ];
  for (const [id, handler] of pairs) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", handler);
  }

  document.getElementById("bot-editor-form")?.addEventListener("submit", (e) => saveBotEditor(e).catch(onErr));
  document.getElementById("editor-bot-profile")?.addEventListener("change", (ev) => {
    fillEditorModelOptions(ev.target.value);
    fillEditorBackgroundModelOptions(ev.target.value);
    fillEditorModelRoles(ev.target.value, readBotBrainsFromEditor().model_roles || {});
    updateEditorBrainStatus(ev.target.value);
    updateEditorMaxContext(ev.target.value);
  });
  document.getElementById("editor-bot-model")?.addEventListener("change", () => {
    updateEditorBrainStatus(document.getElementById("editor-bot-profile")?.value || "");
  });
  document.getElementById("editor-bot-background-model")?.addEventListener("change", () => {
    updateEditorBrainStatus(document.getElementById("editor-bot-profile")?.value || "");
  });
  document.getElementById("editor-soul-file")?.addEventListener("change", (ev) => {
    pickLocalSoulFile(ev.target.files?.[0]).catch(onErr);
  });
  document.getElementById("editor-constraints-file")?.addEventListener("change", (ev) => {
    pickLocalConstraintsFile(ev.target.files?.[0]).catch(onErr);
  });
  document.getElementById("editor-soul-library")?.addEventListener("change", (ev) => {
    const id = ev.target.value;
    if (id) selectLibrarySoul(id).catch(onErr);
  });
  document.getElementById("editor-constraints-library")?.addEventListener("change", (ev) => {
    const id = ev.target.value;
    if (id) selectLibraryConstraints(id).catch(onErr);
  });
}

function bindEvents() {
  document.getElementById("btn-arrange").addEventListener("click", () => toggleArrangeMode().catch(onErr));
  document.getElementById("btn-back-home").addEventListener("click", backToHome);
  document.getElementById("btn-new-session").addEventListener("click", () => createSession().catch(onErr));
  document.getElementById("btn-send").addEventListener("click", () => sendMessage().catch(onErr));
  document.getElementById("btn-stop").addEventListener("click", stopMessage);
  const msgInput = document.getElementById("msg-input");
  msgInput?.addEventListener("input", () => syncComposerInputHeight(msgInput));
  msgInput?.addEventListener("focus", () => syncComposerInputHeight(msgInput));
  msgInput?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendMessage().catch(onErr);
    }
  });

  document.getElementById("btn-open-settings").addEventListener("click", () => {
    openSettingsModal("providers").catch(onErr);
    loadBootstrap().catch(onErr);
  });
  document.getElementById("btn-open-help")?.addEventListener("click", () => {
    openHelpModal().catch(onErr);
  });
  document.getElementById("btn-brain-status")?.addEventListener("click", () => {
    openBrainStatusModal().catch(onErr);
  });
  document.getElementById("btn-close-brain-status")?.addEventListener("click", () => {
    closeBrainStatusModal().catch(onErr);
  });
  document.getElementById("btn-close-help")?.addEventListener("click", () => {
    closeHelpModal().catch(onErr);
  });
  document.getElementById("btn-close-settings").addEventListener("click", () => {
    closeSettingsModal().catch(onErr);
  });
  document.getElementById("btn-open-settings-from-editor")?.addEventListener("click", () => {
    openSettingsModal("providers").catch(onErr);
  });
  document.getElementById("btn-export-data")?.addEventListener("click", () => {
    window.location.href = "/api/system/export";
  });
  document.getElementById("brains-form")?.addEventListener("submit", (e) => saveBrainsSettings(e).catch(onErr));

  bindEditorEvents();
  bindProviderListEvents();

  document.querySelectorAll(".tab[data-tab]").forEach((el) => {
    el.addEventListener("click", () => {
      runButtonTapAnim(el).catch(() => {});
      switchTab(el.dataset.tab).catch(onErr);
    });
  });
  document.getElementById("provider-form").addEventListener("submit", (e) => saveProviderForm(e).catch(onErr));
  document.getElementById("btn-show-provider-form").addEventListener("click", () => {
    clearProviderForm();
    showProviderForm("create");
  });
  document.getElementById("btn-provider-cancel").addEventListener("click", () => {
    clearProviderForm();
    hideProviderForm();
  });
  document.getElementById("btn-provider-clear").addEventListener("click", clearProviderForm);
  document.getElementById("btn-add-provider-model").addEventListener("click", () => addProviderModelEntry(""));
  bindOptimizationPicker();
  renderProviderModelEntries([]);
}

function onErr(err) {
  console.error(err);
  alert(err.message || String(err));
  state.activeGenerationId = null;
  setGenerating(false);
}

async function init() {
  bindEvents();
  syncComposerInputHeight();
  bindBrainStatusScroll();
  bindBrainStatusMemoryLinks();
  bindBrainStatusBrainCards();
  bindMemoryBrowserScroll();
  bindMemoryBrowserEvents();
  renderAvatarPicker();
  bindChatScrollGuard();
  document.addEventListener("click", () => {
    closeMsgMenus();
  });
  await loadBootstrap();
  setScreen("home");
  renderLauncher();
  renderMessages();
  updateTitle();
  updateUsageHint();
  updateChatAvailabilityHint();
}

init().catch(onErr);
