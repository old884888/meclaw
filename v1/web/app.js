// ===== 全局状态 =====
let conversationHistory = [];
let isGenerating = false;
let currentWorkingDir = null;
let cachedConfig = null;
let currentSessionId = null;
let currentPreviewContent = '';
let currentPreviewPath = '';
let pendingOperations = [];
let currentThinkingEl = null;
let isThinking = false;
let pendingAttachments = [];

// ===== DOM 引用 =====
const configModal = document.getElementById('config-modal');
const chatContainer = document.getElementById('chat-container');
const chatMessages = document.getElementById('chat-messages');
const msgInput = document.getElementById('msg-input');
const btnSend = document.getElementById('btn-send');
const btnStop = document.getElementById('btn-stop');
const btnSettings = document.getElementById('btn-settings');
const btnSave = document.getElementById('btn-save');
const btnTest = document.getElementById('btn-test');
const testResult = document.getElementById('test-result');
const btnOpenFolder = document.getElementById('btn-open-folder');
const sidebar = document.getElementById('sidebar');
const fileTree = document.getElementById('file-tree');
const resizeHandle = document.getElementById('resize-handle');
const filePreview = document.getElementById('file-preview');
const previewFilename = document.getElementById('preview-filename');
const previewTruncateMsg = document.getElementById('preview-truncate-msg');
const previewClose = document.getElementById('preview-close');
const btnCopyContent = document.getElementById('btn-copy-content');
const btnSendToAI = document.getElementById('btn-send-to-ai');
const sidebarModelName = document.getElementById('sidebar-model-name');
const confirmModal = document.getElementById('confirm-modal');
const confirmBody = document.getElementById('confirm-body');
const confirmAccept = document.getElementById('confirm-accept');
const confirmReject = document.getElementById('confirm-reject');
const rollbackModal = document.getElementById('rollback-modal');
const rollbackBody = document.getElementById('rollback-body');
const rollbackCancel = document.getElementById('rollback-cancel');
const rollbackConfirm = document.getElementById('rollback-confirm');
const compressModal = document.getElementById('compress-modal');
const compressProgressEl = document.getElementById('compress-progress');
const compressProgressStepsEl = document.getElementById('compress-progress-steps');

const COMPRESS_STEP_LABELS = {
    summary: '生成会话摘要',
    save: '保存到当前会话',
    memory: '整理长期记忆',
};

let compressInProgress = false;
let compressStepIds = [];
let compressHideTimer = null;

// ===== 初始化 =====
window.addEventListener('pywebviewready', async () => {
    // Phase 1: 加载配置（必须成功）
    try {
        const configStr = await pywebview.api.get_config();
        cachedConfig = JSON.parse(configStr);
    } catch (e) {
        console.error('[MeClaw] 配置加载失败:', e);
        showConfigModal();
        return;
    }

    applyTheme(cachedConfig.theme || 'dark');
    const profile = getActiveProfile(cachedConfig);
    if (!profile.base_url || !profile.api_key || !profile.model) {
        showConfigModal();
        if (typeof pushSettingsView === 'function') pushSettingsView('providers');
    }
    updateBotDisplay();
    if (typeof applyEditorWordWrapFromConfig === 'function') {
        applyEditorWordWrapFromConfig();
    }

    // Phase 2: 逐一初始化各模块，各自 try-catch 防止级联失败
    async function safeInit(name, fn) {
        try { await fn(); } catch (e) { console.error('[MeClaw] ' + name + ' 初始化失败:', e); }
    }

    await safeInit('refreshComposerToolbar', () => {
        if (typeof refreshComposerToolbar === 'function') return refreshComposerToolbar();
    });
    await safeInit('loadBots', loadBots);
    await safeInit('loadSessions', loadSessions);

    initSessionSearch();
    if (typeof initGroupUI === 'function') initGroupUI();
    if (typeof loadGroups === 'function') safeInit('loadGroups', loadGroups);
    if (typeof updateBotSelectorLockState === 'function') updateBotSelectorLockState();
    await safeInit('refreshContextUsage', refreshContextUsage);
    updateSidebarToggleUI();
    await safeInit('refreshReceiveDirUI', refreshReceiveDirUI);
    if (typeof initCodeLayout === 'function') initCodeLayout();
    if (typeof initSettingsNavigation === 'function') initSettingsNavigation();
    if (typeof initBotManagementUI === 'function') initBotManagementUI();
});

async function refreshReceiveDirUI() {
    const rd = await pywebview.api.get_receive_dir();
    const input = document.getElementById('cfg-receive-dir');
    if (input) input.value = rd || '';
    try {
        const layoutStr = await pywebview.api.get_receive_layout();
        const layout = JSON.parse(layoutStr);
        const hint = document.getElementById('cfg-receive-layout-hint');
        if (hint && layout.ok && layout.pattern) {
            hint.textContent = `各对话文件保存在：${layout.pattern}`;
        }
    } catch (_) {}
}

// ===== 配置面板事件 =====
document.getElementById('config-close').addEventListener('click', hideConfigModal);

btnSettings.addEventListener('click', async () => {
    await refreshConfig();
    await refreshReceiveDirUI();
    showConfigModal();
});

btnSave.addEventListener('click', async () => {
    cachedConfig.user_avatar = document.getElementById('cfg-user-avatar').textContent || '😎';
    cachedConfig.user_font_size = parseInt(document.getElementById('cfg-user-font-size').value) || 14;
    cachedConfig.bot_font_size = parseInt(document.getElementById('cfg-bot-font-size').value) || 14;
    cachedConfig.thinking_font_size = parseInt(document.getElementById('cfg-thinking-font-size').value) || 12;
    cachedConfig.theme = document.getElementById('cfg-theme').value || 'dark';
    // API 日志开关
    const apiLogBtn = document.querySelector('[data-field="api-log-enabled"].active');
    cachedConfig.api_log_enabled = apiLogBtn ? apiLogBtn.dataset.value === 'true' : true;
    if (typeof collectEnabledSkillIds === 'function') {
        cachedConfig.enabled_skills = collectEnabledSkillIds('cfg-skill-list');
    }
    const wrapBtn = document.querySelector('[data-field="editor-word-wrap"].active');
    cachedConfig.editor_word_wrap = wrapBtn ? wrapBtn.dataset.value === 'true' : true;
    const memEnabledBtn = document.querySelector('[data-field="memory-enabled"].active');
    cachedConfig.memory_enabled = memEnabledBtn ? memEnabledBtn.dataset.value === 'true' : true;
    const memWriteBtn = document.querySelector('[data-field="memory-write-enabled"].active');
    cachedConfig.memory_write_enabled = memWriteBtn ? memWriteBtn.dataset.value === 'true' : true;
    const budgetEl = document.getElementById('cfg-memory-token-budget');
    if (budgetEl) {
        const v = parseInt(budgetEl.value, 10);
        cachedConfig.memory_token_budget = Number.isFinite(v) ? v : 1200;
    }
    const autoExtractBtn = document.querySelector('[data-field="memory-auto-extract"].active');
    cachedConfig.memory_auto_extract = autoExtractBtn ? autoExtractBtn.dataset.value === 'true' : false;
    const thresholdEl = document.getElementById('cfg-auto-compress-threshold');
    if (thresholdEl) {
        cachedConfig.memory_extract_threshold_pct = parseInt(thresholdEl.value, 10) || 85;
    }
    const detailEl = document.getElementById('cfg-compress-summary-detail');
    if (detailEl) {
        cachedConfig.compress_summary_detail = detailEl.value || 'standard';
    }
    // 整理模型设置
    const organizerBtn = document.querySelector('[data-field="organizer-enabled"].active');
    cachedConfig.memory_organizer_enabled = organizerBtn ? organizerBtn.dataset.value === 'true' : false;
    const organizerSelect = document.getElementById('cfg-organizer-profile');
    if (organizerSelect && organizerSelect.value) {
        const [pid, model] = organizerSelect.value.split('::');
        cachedConfig.memory_organizer_profile_id = pid || '';
        cachedConfig._organizer_model = model || '';
    } else {
        cachedConfig.memory_organizer_profile_id = '';
        cachedConfig._organizer_model = '';
    }
    const orgThinkingBtn = document.querySelector('[data-field="organizer-thinking"].active');
    cachedConfig.organizer_thinking_enabled = orgThinkingBtn ? orgThinkingBtn.dataset.value === 'true' : false;
    const orgDepthBtn = document.querySelector('[data-field="organizer-thinking-depth"].active');
    cachedConfig.organizer_thinking_depth = orgDepthBtn ? orgDepthBtn.dataset.value : 'high';
    const providerEl = document.getElementById('cfg-web-search-provider');
    const keyEl = document.getElementById('cfg-web-search-api-key');
    if (providerEl) cachedConfig.web_search_provider = providerEl.value || 'duckduckgo';
    if (keyEl) cachedConfig.web_search_api_key = keyEl.value.trim();
    const maxRoundsEl = document.getElementById('cfg-web-search-max-rounds');
    const maxQueriesEl = document.getElementById('cfg-web-search-max-queries');
    if (maxRoundsEl) {
        cachedConfig.web_search_max_rounds = Math.max(1, Math.min(5, parseInt(maxRoundsEl.value, 10) || 3));
    }
    if (maxQueriesEl) {
        cachedConfig.web_search_max_queries_per_round = Math.max(1, Math.min(8, parseInt(maxQueriesEl.value, 10) || 3));
    }
    applyTheme(cachedConfig.theme);
    if (typeof applyEditorWordWrapFromConfig === 'function') {
        applyEditorWordWrapFromConfig();
    }
    const result = JSON.parse(await pywebview.api.save_config(JSON.stringify(cachedConfig)));
    if (result.ok) {
        hideConfigModal();
        if (typeof refreshComposerToolbar === 'function') {
            await refreshComposerToolbar();
        }
    }
});

btnTest.addEventListener('click', async () => {
    btnTest.disabled = true;
    btnTest.textContent = '测试中...';
    testResult.classList.add('hidden');
    const result = JSON.parse(await pywebview.api.test_connection());
    showTestResult(result.msg, result.ok);
    btnTest.disabled = false;
    btnTest.textContent = '测试当前配置';
});

// 设置面板 Toggle 按钮点击事件（事件委托）
configModal.addEventListener('click', (e) => {
    const btn = e.target.closest('.toggle-btn');
    if (!btn) return;
    const field = btn.dataset.field;
    const value = btn.dataset.value;
    // 更新同组按钮状态
    document.querySelectorAll(`.toggle-btn[data-field="${field}"]`).forEach(b => {
        b.classList.toggle('active', b.dataset.value === value);
    });
    // 整理模型开关联动
    if (field === 'organizer-enabled') {
        const section = document.getElementById('organizer-model-section');
        if (section) section.style.display = value === 'true' ? '' : 'none';
    }
    if (field === 'organizer-thinking') {
        const depthRow = document.getElementById('organizer-thinking-depth-row');
        if (depthRow) depthRow.style.display = value === 'true' ? '' : 'none';
    }
});

// 对话文件目录
document.getElementById('btn-browse-receive-dir').addEventListener('click', async () => {
    const resultStr = await pywebview.api.select_receive_dir();
    const result = JSON.parse(resultStr);
    if (result.ok) {
        await refreshReceiveDirUI();
    }
});

document.getElementById('btn-open-receive-dir').addEventListener('click', async () => {
    await pywebview.api.open_receive_dir();
});

document.getElementById('btn-open-session-files').addEventListener('click', async () => {
    const resultStr = await pywebview.api.open_session_files_dir();
    const result = JSON.parse(resultStr);
    if (!result.ok && result.msg) {
        alert(result.msg);
    }
});

document.addEventListener('mousedown', (e) => {
    if (e.target.closest('#bot-dropdown') || e.target.closest('#bot-selector')) return;
    hideBotDropdown();
});

// 压缩上下文（由状态面板「压缩上下文」或下方确认弹窗触发）

function setCompressBusy(busy) {
    compressInProgress = busy;
    window.compressInProgress = busy;
    const confirmBtn = document.getElementById('compress-confirm');
    const statusBtn = document.querySelector('.btn-compress-status');
    if (confirmBtn) confirmBtn.disabled = busy;
    if (statusBtn) statusBtn.disabled = busy;
}

function initCompressProgressSteps(includeMemory) {
    compressStepIds = includeMemory
        ? ['summary', 'save', 'memory']
        : ['summary', 'save'];
    if (!compressProgressStepsEl) return;
    compressProgressStepsEl.innerHTML = '';
    compressStepIds.forEach((id) => {
        const li = document.createElement('li');
        li.className = 'compress-progress-step';
        li.dataset.step = id;
        li.innerHTML = `<span class="compress-progress-step-icon">○</span><span class="compress-progress-step-label">${COMPRESS_STEP_LABELS[id]}</span>`;
        compressProgressStepsEl.appendChild(li);
    });
}

function setCompressStepState(stepId, state) {
    if (!compressProgressStepsEl) return;
    const el = compressProgressStepsEl.querySelector(`[data-step="${stepId}"]`);
    if (!el) return;
    el.classList.remove('is-active', 'is-done', 'is-error');
    if (state) el.classList.add(state);
    const icon = el.querySelector('.compress-progress-step-icon');
    if (!icon) return;
    if (state === 'is-active') icon.textContent = '●';
    else if (state === 'is-done') icon.textContent = '✓';
    else if (state === 'is-error') icon.textContent = '✕';
    else icon.textContent = '○';
}

function showCompressProgressPanel(includeMemory) {
    clearTimeout(compressHideTimer);
    if (!compressProgressEl) return;
    initCompressProgressSteps(includeMemory);
    compressProgressEl.classList.remove('hidden', 'is-done', 'is-error');
    const title = compressProgressEl.querySelector('.compress-progress-title');
    if (title) title.textContent = '🗜 压缩中…';
}

function hideCompressProgressPanel(delayMs) {
    clearTimeout(compressHideTimer);
    if (!compressProgressEl) return;
    const hide = () => {
        compressProgressEl.classList.add('hidden');
        compressProgressEl.classList.remove('is-done', 'is-error');
        if (compressProgressStepsEl) compressProgressStepsEl.innerHTML = '';
    };
    if (delayMs > 0) {
        compressHideTimer = setTimeout(hide, delayMs);
    } else {
        hide();
    }
}

function onCompressProgress(payload) {
    if (!payload || !payload.phase) return;
    const phase = payload.phase;

    if (phase === 'start') {
        let includeMemory = false;
        try {
            const detail = typeof payload.detail === 'string'
                ? JSON.parse(payload.detail)
                : (payload.detail || {});
            includeMemory = !!detail.memory;
        } catch (_) {
            includeMemory = false;
        }
        setCompressBusy(true);
        showCompressProgressPanel(includeMemory);
        return;
    }

    if (phase === 'done') {
        compressStepIds.forEach((id) => setCompressStepState(id, 'is-done'));
        if (compressProgressEl) {
            compressProgressEl.classList.add('is-done');
            const title = compressProgressEl.querySelector('.compress-progress-title');
            if (title) title.textContent = '✓ 压缩完成';
        }
        compressHideTimer = setTimeout(() => hideCompressProgressPanel(0), 800);
        return;
    }

    if (phase === 'error') {
        const failed = payload.detail || 'summary';
        const failedIdx = compressStepIds.indexOf(failed);
        compressStepIds.forEach((id, idx) => {
            if (idx < failedIdx) setCompressStepState(id, 'is-done');
            else if (idx === failedIdx) setCompressStepState(id, 'is-error');
        });
        if (compressProgressEl) {
            compressProgressEl.classList.add('is-error');
            const title = compressProgressEl.querySelector('.compress-progress-title');
            if (title) title.textContent = '✕ 压缩失败';
        }
        setTimeout(() => {
            hideCompressProgressPanel(0);
            setCompressBusy(false);
        }, 1500);
        return;
    }

    if (!compressStepIds.includes(phase)) return;
    const idx = compressStepIds.indexOf(phase);
    compressStepIds.forEach((id, i) => {
        if (i < idx) setCompressStepState(id, 'is-done');
        else if (i === idx) setCompressStepState(id, 'is-active');
    });
}

function resolveDefaultCompressDetail() {
    if (!cachedConfig) return 'standard';
    const bot = typeof getActiveBot === 'function' ? getActiveBot(cachedConfig) : null;
    if (bot && bot.compress_summary_detail) {
        return bot.compress_summary_detail;
    }
    return cachedConfig.compress_summary_detail || 'standard';
}

function setCompressDetailInModal(level) {
    document.querySelectorAll('[data-field="compress-detail-level"]').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.value === level);
    });
    const hint = document.getElementById('compress-detail-max-hint');
    if (hint) hint.classList.toggle('hidden', level !== 'max');
}

function getCompressDetailFromModal() {
    const active = document.querySelector('[data-field="compress-detail-level"].active');
    return active ? active.dataset.value : 'standard';
}

function initCompressDetailModalHandlers() {
    const modal = document.getElementById('compress-modal');
    if (!modal || modal.dataset.detailBound === '1') return;
    modal.dataset.detailBound = '1';
    modal.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-field="compress-detail-level"]');
        if (!btn) return;
        setCompressDetailInModal(btn.dataset.value);
    });
}

function syncConversationAfterCompress(messages) {
    if (!Array.isArray(messages) || typeof conversationHistory === 'undefined') return;
    conversationHistory = messages;
    if (typeof chatMessages === 'undefined' || !chatMessages) return;
    chatMessages.querySelectorAll('.message-row').forEach(row => row.remove());
    for (const m of conversationHistory) {
        if (m && m.role && typeof renderMessage === 'function') renderMessage(m, false);
    }
    if (typeof scrollToBottom === 'function') scrollToBottom();
}

async function executeCompress(direction, detailLevel) {
    setCompressBusy(true);
    try {
        const level = detailLevel || getCompressDetailFromModal();
        const resultStr = await pywebview.api.compress_context(direction, level);
        const result = JSON.parse(resultStr);
        if (result.ok) {
            hideCompressProgressPanel(600);
            syncConversationAfterCompress(result.messages);
            addMessage('ai', '✅ ' + result.msg);
            if (typeof refreshContextUsage === 'function') await refreshContextUsage();
            if (typeof refreshStatusPanel === 'function' && !document.getElementById('status-panel').classList.contains('hidden')) {
                await refreshStatusPanel();
            }
        } else {
            hideCompressProgressPanel(1200);
            addMessage('error', '❌ ' + result.msg);
        }
    } catch (e) {
        hideCompressProgressPanel(1200);
        addMessage('error', '❌ 压缩失败: ' + (e.message || e));
    } finally {
        setCompressBusy(false);
    }
}

document.getElementById('compress-cancel').addEventListener('click', () => {
    compressModal.classList.add('hidden');
});

document.getElementById('compress-confirm').addEventListener('click', async () => {
    const direction = document.getElementById('compress-direction').value.trim();
    const detailLevel = getCompressDetailFromModal();
    compressModal.classList.add('hidden');
    document.getElementById('compress-direction').value = '';
    await executeCompress(direction, detailLevel);
});

initCompressDetailModalHandlers();

function onAutoCompress(payload) {
    setCompressBusy(false);
    const data = (payload && typeof payload === 'object') ? payload : { msg: payload };
    const text = data.msg || '';
    syncConversationAfterCompress(data.messages);
    if (text && typeof addMessage === 'function') addMessage('ai', text);
    if (typeof refreshContextUsage === 'function') refreshContextUsage();
    if (typeof refreshStatusPanel === 'function' && !document.getElementById('status-panel').classList.contains('hidden')) {
        refreshStatusPanel();
    }
}

const cfgThresholdRange = document.getElementById('cfg-auto-compress-threshold');
const cfgThresholdVal = document.getElementById('cfg-auto-compress-threshold-val');
if (cfgThresholdRange && cfgThresholdVal) {
    cfgThresholdRange.addEventListener('input', () => {
        cfgThresholdVal.textContent = cfgThresholdRange.value + '%';
    });
}

// ===== 对话事件 =====
btnSend.addEventListener('click', sendMessage);
btnStop.addEventListener('click', stopGeneration);
document.getElementById('btn-expert-mode')?.addEventListener('click', toggleExpertMode);
document.getElementById('btn-council-mode')?.addEventListener('click', toggleCouncilMode);
document.getElementById('council-arbitration-select')?.addEventListener('click', () => submitCouncilArbitration('select'));
document.getElementById('council-arbitration-deepen')?.addEventListener('click', () => submitCouncilArbitration('deepen'));
document.getElementById('council-arbitration-end')?.addEventListener('click', () => submitCouncilArbitration('end'));
document.getElementById('btn-estop')?.addEventListener('click', () => {
    if (typeof emergencyStopGroup === 'function') emergencyStopGroup();
    else stopGeneration();
});
document.getElementById('btn-attach').addEventListener('click', selectAttachments);

msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

msgInput.addEventListener('input', autoResize);

// 新任务按钮
document.getElementById('btn-new-task').addEventListener('click', async () => {
    if (!confirm('将创建新任务，当前对话和文件上下文将清空（工作目录保留）。')) return;
    const resultStr = await pywebview.api.new_task();
    const result = JSON.parse(resultStr);
    if (result.ok) {
        currentSessionId = result.session.id;
        conversationHistory = [];
        chatMessages.innerHTML = '';
        if (typeof read_files !== 'undefined') read_files.clear();
        await loadSessions();
        await refreshContextUsage();
        showToast('新任务已创建');
    }
});

// ===== 侧边栏事件 =====
// Bot 选择器
document.getElementById('bot-selector').addEventListener('click', (e) => {
    e.stopPropagation();
    if (e.target.closest('#current-bot-avatar')) return;
    if (document.getElementById('bot-selector').classList.contains('bot-selector-locked')) return;
    if (typeof toggleBotDropdown === 'function') toggleBotDropdown();
    else showBotDropdown();
});

document.getElementById('sidebar-tab-status')?.addEventListener('click', () => {
    if (typeof setMainSidebarTab === 'function') {
        setMainSidebarTab('status');
    } else {
        document.getElementById('chat-panel')?.classList.add('hidden');
        document.getElementById('group-panel')?.classList.add('hidden');
        document.getElementById('status-panel')?.classList.remove('hidden');
        refreshStatusPanel();
    }
});

const btnSessionBack = document.getElementById('btn-session-back');
if (btnSessionBack) {
    btnSessionBack.addEventListener('click', () => {
        if (typeof backToBotList === 'function') backToBotList();
    });
}

document.getElementById('btn-sidebar-toggle').addEventListener('click', toggleSidebar);
btnOpenFolder.addEventListener('click', openFolder);
document.getElementById('btn-rollback').addEventListener('click', showRollbackModal);
document.getElementById('btn-new-session').addEventListener('click', () => newSession());
document.getElementById('btn-select-mode').addEventListener('click', enterMultiSelectMode);
document.getElementById('btn-select-back').addEventListener('click', exitMultiSelectMode);
document.getElementById('btn-select-all').addEventListener('click', toggleSelectAll);
document.getElementById('btn-select-delete').addEventListener('click', showDeleteSessionsConfirm);
document.getElementById('session-delete-cancel').addEventListener('click', () => {
    document.getElementById('session-delete-modal').classList.add('hidden');
});
document.getElementById('session-delete-confirm').addEventListener('click', confirmDeleteSelectedSessions);

// ===== 模式切换 =====
let currentMode = 'chat';

document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => switchMode(btn.dataset.mode));
});

document.getElementById('code-workdir').addEventListener('click', async () => {
    // 点击工作目录：切换目录
    const resultStr = await pywebview.api.select_folder();
    const result = JSON.parse(resultStr);
    if (result.ok && result.path) {
        await setCodeWorkDir(result.path);
    }
});

async function switchMode(mode) {
    if (mode === currentMode) return;

    // 切到编程模式且无工作目录时，先弹文件夹选择
    if (mode === 'code' && !currentWorkingDir) {
        const resultStr = await pywebview.api.select_folder();
        const result = JSON.parse(resultStr);
        if (!result.ok || !result.path) return; // 用户取消
        currentWorkingDir = result.path;
        await pywebview.api.set_working_dir(result.path);
        await loadFileTree(result.path);
    }

    currentMode = mode;
    document.getElementById('main-content').dataset.mode = mode;

    // 更新按钮高亮
    document.querySelectorAll('.mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
    });

    // 编程模式：显示工作目录、侧边栏显示文件面板、显示预览面板
    const workdirEl = document.getElementById('code-workdir');
    const codeModeBar = document.getElementById('code-mode-bar');
    if (mode === 'code') {
        workdirEl.classList.remove('hidden');
        workdirEl.textContent = currentWorkingDir;
        codeModeBar.classList.remove('hidden');
        openSidebar();
        // 切换侧边栏到文件面板
        document.getElementById('chat-panel').classList.add('hidden');
        document.getElementById('files-panel').classList.remove('hidden');
        document.getElementById('status-panel').classList.add('hidden');
    } else {
        workdirEl.classList.add('hidden');
        codeModeBar.classList.add('hidden');
        // 对话模式：恢复侧边栏到对话面板
        document.getElementById('chat-panel').classList.remove('hidden');
        document.getElementById('files-panel').classList.add('hidden');
    }

    if (typeof onCodeModeChange === 'function') onCodeModeChange(mode);
    if (typeof updateHeaderBotManageVisibility === 'function') updateHeaderBotManageVisibility();

    // 通知后端
    await pywebview.api.switch_mode(mode);
}

async function setCodeWorkDir(path) {
    currentWorkingDir = path;
    await pywebview.api.set_working_dir(path);
    await loadFileTree(path);
    document.getElementById('code-workdir').textContent = path;
}

function switchSidebarTab(tabName) {
    if (tabName === 'status') {
        document.getElementById('sidebar-tab-status')?.click();
        return;
    }
    if (tabName === 'chat' && typeof setMainSidebarTab === 'function') {
        setMainSidebarTab('private', { preserveNav: true });
    }
}

resizeHandle.addEventListener('mousedown', () => {
    isResizing = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const newWidth = Math.min(Math.max(e.clientX, 200), 400);
    sidebar.style.width = newWidth + 'px';
});

document.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
});

// ===== 文件预览事件 =====
previewClose.addEventListener('click', closePreview);
btnCopyContent.addEventListener('click', copyPreviewContent);
btnSendToAI.addEventListener('click', sendFileToAI);

// ===== 文件操作事件 =====
confirmAccept.addEventListener('click', () => {
    confirmModal.classList.add('hidden');
    executeOperations(pendingOperations);
    pendingOperations = [];
});

confirmReject.addEventListener('click', () => {
    confirmModal.classList.add('hidden');
    pendingOperations = [];
});

rollbackCancel.addEventListener('click', () => {
    rollbackModal.classList.add('hidden');
});

rollbackConfirm.addEventListener('click', async () => {
    const selected = rollbackBody.querySelectorAll('.rollback-item.selected');
    for (const item of selected) {
        const backupPath = item.dataset.backupPath;
        const originalPath = item.dataset.originalPath;
        const resultStr = await pywebview.api.restore_backup(backupPath, originalPath);
        const result = JSON.parse(resultStr);
        if (result.ok) {
            addMessage('ai', '✅ ' + result.msg);
        } else {
            addMessage('error', '❌ ' + result.msg);
        }
    }
    rollbackModal.classList.add('hidden');
});

// ===== 附件管理 =====

async function selectAttachments() {
    if (pendingAttachments.length >= 5) {
        alert('最多附加 5 个文件');
        return;
    }
    const resultStr = await pywebview.api.select_attachments();
    const result = JSON.parse(resultStr);
    if (!result.ok || !result.files.length) return;
    const remaining = 5 - pendingAttachments.length;
    const newFiles = result.files.slice(0, remaining);
    pendingAttachments.push(...newFiles);
    renderAttachmentsPreview();
}

function removeAttachment(index) {
    pendingAttachments.splice(index, 1);
    renderAttachmentsPreview();
}

function clearAttachments() {
    pendingAttachments = [];
    renderAttachmentsPreview();
}

function renderAttachmentsPreview() {
    const preview = document.getElementById('attachments-preview');
    if (!pendingAttachments.length) {
        preview.classList.add('hidden');
        preview.innerHTML = '';
        return;
    }
    preview.classList.remove('hidden');
    preview.innerHTML = pendingAttachments.map((a, i) => {
        if (a.is_image && a.base64) {
            return `<div class="attachment-item">
                <img class="attachment-thumb" src="${a.base64}" alt="${escapeHtml(a.name)}">
                <div class="attachment-info">
                    <span class="attachment-name">${escapeHtml(a.name)}</span>
                    <span class="attachment-size">${formatFileSize(a.size)}</span>
                </div>
                <button class="attachment-remove" onclick="removeAttachment(${i})">✕</button>
            </div>`;
        }
        return `<div class="attachment-item">
            <span class="attachment-icon">${getFileIcon(a.name)}</span>
            <div class="attachment-info">
                <span class="attachment-name">${escapeHtml(a.name)}</span>
                <span class="attachment-size">${formatFileSize(a.size)}</span>
            </div>
            <button class="attachment-remove" onclick="removeAttachment(${i})">✕</button>
        </div>`;
    }).join('');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
