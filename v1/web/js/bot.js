// ===== Emoji 数据（优先 Windows/WebView2 可渲染的单码点表情，避免 ZWJ/Unicode15+ 空白方框）=====
const EMOJI_NORMAL_BOT = [
    '🤖', '💻', '📚', '🦉', '🐱', '🧠', '📝', '🔬', '🎨', '🌍', '🛡️', '📊',
    '🦊', '🐶', '🐼', '🦁', '⭐', '🔥', '💡', '🎯', '🚀', '⚡', '🎵', '📡',
];
const EMOJI_ABSTRACT_BOT = [
    '🗿', '🤡', '👹', '👻', '👁️', '🦷', '🧱', '🐸', '💀', '🎭', '🌙', '👽',
    '🤪', '😈', '🎃', '☠️', '🦇', '🐙', '🔮', '💩', '🧟', '🥴', '🤯', '😵',
];
const EMOJI_USER = [
    '😎', '👤', '👨', '👩', '👾', '🦸', '🧙', '🦄', '🐉', '🗿', '🙂', '🤠',
    '😀', '😊', '🤓', '🥳', '👋', '✌️', '🖐️', '🦋', '🌸', '🎮', '👍', '☝️',
];

let emojiPickerTarget = null;  // 'bot' 或 'user'
let emojiPickerCallback = null;
let localTokenCount = 0;

// ===== 机器人管理 =====

async function loadBots() {
    const resultStr = await pywebview.api.get_bots();
    const result = JSON.parse(resultStr);
    if (result.ok) {
        renderBotDropdown(result.bots, result.active_bot_id);
    }
}

function renderBotDropdown(bots, activeBotId) {
    const dropdown = document.getElementById('bot-dropdown');
    if (!dropdown) return;
    dropdown.innerHTML = '';

    for (const bot of bots) {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'dropdown-item' + (bot.id === activeBotId ? ' active' : '');
        item.innerHTML = `<span class="bot-avatar-small">${bot.avatar || '🤖'}</span> ${escapeHtml(bot.name)}`;
        item.addEventListener('click', async (e) => {
            e.stopPropagation();
            await switchBot(bot.id);
            hideBotDropdown();
        });
        dropdown.appendChild(item);
    }
}

function setBotSelectorLocked(locked) {
    const selector = document.getElementById('bot-selector');
    if (!selector) return;
    selector.classList.toggle('bot-selector-locked', !!locked);
    const arrow = selector.querySelector('.dropdown-arrow');
    if (arrow) arrow.classList.toggle('hidden', !!locked);
}

function updateBotSelectorLockState() {
    let locked = !!currentSessionId;
    if (!locked && typeof mainSidebarTab !== 'undefined' && mainSidebarTab === 'private') {
        locked = typeof sidebarView !== 'undefined' && sidebarView !== 'bots';
    }
    if (!locked && typeof mainSidebarTab !== 'undefined' && mainSidebarTab === 'group') {
        locked = !!currentSessionId || (typeof sidebarView !== 'undefined' && sidebarView === 'group-sessions');
    }
    setBotSelectorLocked(locked);
}

async function switchBot(botId) {
    // 停止当前生成（如果有）
    if (isGenerating) {
        pywebview.api.stop_generation();
        setGenerating(false);
    }
    const resultStr = await pywebview.api.switch_bot(botId);
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (result.msg && typeof showToast === 'function') showToast(result.msg);
        return;
    }
    chatMessages.innerHTML = '';
    conversationHistory = [];
    currentSessionId = null;
    // 清理队列、专家模式和残留的流式消息
    messageQueue = [];
    renderQueue();
    if (typeof resetExpertMode === 'function') resetExpertMode();
    if (typeof resetCouncilMode === 'function') resetCouncilMode();
    if (typeof updateGroupComposerUI === 'function') updateGroupComposerUI();
    const streamingMsg = document.getElementById('streaming-msg');
    if (streamingMsg) streamingMsg.remove();
    await refreshConfig();
    updateBotDisplay();
    await loadBots();
    await loadSessions();
    if (typeof updateBotSelectorLockState === 'function') updateBotSelectorLockState();
    await refreshContextUsage();
}

/** DeepSeek 回复模式文案（非 DeepSeek 返回 null） */
function getDeepSeekReplyMode(bot, profile) {
    if (!profile || profile.provider !== 'deepseek') return null;
    if (bot.thinking_enabled) {
        const depth = bot.thinking_depth === 'max' ? '加深 max' : '标准 high';
        return {
            kind: 'thinking',
            label: '思考',
            title: `思考模式 · ${depth}（先思维链后正文）`
        };
    }
    return {
        kind: 'fast',
        label: '快速',
        title: '快速模式（无思维链，使用 Temperature）'
    };
}

function formatReplyModeStatus(bot, profile) {
    const mode = getDeepSeekReplyMode(bot, profile);
    if (!mode) return '-';
    if (mode.kind === 'thinking') {
        const depth = bot.thinking_depth === 'max' ? '加深 (max)' : '标准 (high)';
        return `思考模式 · ${depth}`;
    }
    return '快速模式';
}

function updateBotDisplay() {
    const bot = getActiveBot(cachedConfig);
    const profile = getActiveProfile(cachedConfig);
    const avatarEl = document.getElementById('current-bot-avatar');
    const nameEl = document.getElementById('current-bot-name');
    const badgeEl = document.getElementById('current-bot-mode-badge');
    if (avatarEl) avatarEl.textContent = bot.avatar || '🤖';
    if (nameEl) nameEl.textContent = bot.name || '默认助手';
    if (badgeEl) {
        const mode = getDeepSeekReplyMode(bot, profile);
        if (mode) {
            badgeEl.textContent = mode.label;
            badgeEl.title = mode.title;
            badgeEl.className = 'bot-mode-badge bot-mode-' + mode.kind;
        } else {
            badgeEl.textContent = '';
            badgeEl.className = 'bot-mode-badge hidden';
        }
    }
    updateModelDisplay();
    if (typeof refreshComposerToolbar === 'function') {
        refreshComposerToolbar();
    }
    if (typeof updateHeaderBotManageVisibility === 'function') {
        updateHeaderBotManageVisibility();
    }
}

function isBotDropdownOpen() {
    const dropdown = document.getElementById('bot-dropdown');
    return dropdown && !dropdown.classList.contains('hidden');
}

function showBotDropdown() {
    const dropdown = document.getElementById('bot-dropdown');
    if (!dropdown) return;
    const btn = document.getElementById('bot-selector');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    dropdown.style.top = (rect.bottom + 4) + 'px';
    dropdown.style.left = rect.left + 'px';
    dropdown.classList.remove('hidden');
}

function hideBotDropdown() {
    const dropdown = document.getElementById('bot-dropdown');
    if (dropdown) dropdown.classList.add('hidden');
}

function toggleBotDropdown() {
    if (isBotDropdownOpen()) hideBotDropdown();
    else showBotDropdown();
}

// ===== 机器人管理弹窗 =====

async function showBotManager() {
    hideBotDropdown();
    const modal = document.getElementById('bot-manager-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    try {
        const resultStr = await pywebview.api.get_bots();
        const result = JSON.parse(resultStr);
        if (result.ok) {
            renderBotManagerList(result.bots, result.active_bot_id);
            return;
        }
    } catch (_) {}
    if (cachedConfig?.bots) {
        renderBotManagerList(cachedConfig.bots, cachedConfig.active_bot_id || '');
    }
}

function hideBotManager() {
    document.getElementById('bot-manager-modal')?.classList.add('hidden');
}

function updateHeaderBotManageVisibility() {
    const btn = document.getElementById('btn-manage-bots-header');
    if (!btn) return;
    const isCode = document.getElementById('main-content')?.dataset.mode === 'code';
    btn.classList.toggle('hidden', isCode);
}

function initBotManagementUI() {
    const headerBtn = document.getElementById('btn-manage-bots-header');
    headerBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        showBotManager();
    });

    document.getElementById('btn-bot-manager-close')?.addEventListener('click', hideBotManager);
    document.getElementById('btn-add-bot')?.addEventListener('click', () => showBotEditModal(null));

    const managerModal = document.getElementById('bot-manager-modal');
    managerModal?.addEventListener('click', (e) => {
        if (e.target === managerModal) hideBotManager();
    });
    document.getElementById('bot-manager-panel')?.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    const dropdown = document.getElementById('bot-dropdown');
    dropdown?.addEventListener('click', (e) => e.stopPropagation());

    updateHeaderBotManageVisibility();
}

function renderBotManagerList(bots, activeBotId) {
    const list = document.getElementById('bot-list');
    list.innerHTML = '';

    for (const bot of bots) {
        const item = document.createElement('div');
        const profile = (cachedConfig.api_profiles || []).find(p => p.id === bot.profile_id);
        const modelName = bot.model || (profile ? profile.model : '') || '';
        const providerName = profile ? profile.name : '';
        const profileLabel = modelName
            ? escapeHtml(`${providerName} / ${modelName}`)
            : escapeHtml(providerName || bot.profile_id || '未关联');
        const meta = bot.id === activeBotId
            ? `${profileLabel} · <span class="in-use">使用中</span>`
            : profileLabel;
        item.className = 'bot-list-item';
        item.innerHTML = `
            <div class="bot-list-avatar">${bot.avatar || '🤖'}</div>
            <div class="bot-list-info">
                <div class="bot-list-name">${escapeHtml(bot.name)}</div>
                <div class="bot-list-meta">${meta}</div>
            </div>
            <div class="bot-list-actions">
                <button class="btn-icon edit" title="编辑">✏️</button>
                <button class="btn-icon delete" title="删除">🗑️</button>
            </div>
        `;

        item.querySelector('.edit').addEventListener('click', () => {
            showBotEditModal(bot);
        });

        item.querySelector('.delete').addEventListener('click', async () => {
            if (bots.length <= 1) return alert('至少保留一个机器人');
            if (!confirm(`删除机器人「${bot.name}」？`)) return;
            const resultStr = await pywebview.api.delete_bot(bot.id);
            const result = JSON.parse(resultStr);
            if (result.ok) {
                await refreshConfig();
                updateBotDisplay();
                await loadBots();
                showBotManager(); // 刷新列表
            } else {
                alert(result.msg);
            }
        });

        list.appendChild(item);
    }
}

// ===== 机器人编辑弹窗 =====

/** 从状态面板等入口：直接编辑当前激活的 Bot */
function editActiveBot() {
    if (!cachedConfig) return;
    const bots = cachedConfig.bots || [];
    const activeId = cachedConfig.active_bot_id;
    const bot = bots.find(b => b.id === activeId) || getActiveBot(cachedConfig);
    if (!bot || !bot.id) {
        alert('未找到当前机器人');
        return;
    }
    showBotEditModal(bot);
}

function showBotEditModal(bot) {
    const isNew = !bot || !bot.id;
    document.getElementById('bot-edit-title').textContent = isNew ? '添加机器人' : '编辑机器人';
    document.getElementById('bot-edit-id').value = bot ? (bot.id || '') : '';
    document.getElementById('bot-edit-name').value = bot ? (bot.name || '') : '';
    document.getElementById('bot-edit-avatar').textContent = bot ? (bot.avatar || '🤖') : '🤖';
    document.getElementById('bot-edit-temp').value = bot && bot.temperature != null ? bot.temperature : '';
    document.getElementById('bot-edit-max').value = bot && bot.max_tokens != null ? bot.max_tokens : '';
    document.getElementById('bot-edit-max-context').value = bot && bot.max_context != null ? bot.max_context : '';
    document.getElementById('bot-edit-soul').value = bot ? (bot.soul_folder || '') : '';

    // 渲染模型选择下拉（按供应商分组）
    const select = document.getElementById('bot-edit-profile');
    select.innerHTML = '';
    const profiles = cachedConfig.api_profiles || [];
    const botModel = bot ? (bot.model || '') : '';

    // 自定义模型输入框：只有当 bot 的 model 不在任何下拉选项中时才填充
    const allKnownModels = [];
    for (const p of profiles) {
        if (p.enabled === false) continue;
        if (p.model) allKnownModels.push(p.model);
        for (const m of (p.models || [])) {
            const mName = m.name || m.id || '';
            if (mName && !allKnownModels.includes(mName)) allKnownModels.push(mName);
        }
    }
    document.getElementById('bot-edit-model').value = (bot && botModel && !allKnownModels.includes(botModel)) ? botModel : '';

    for (const p of profiles) {
        if (p.enabled === false) continue;
        const models = p.models || [];
        const defaultModel = p.model || '';

        // 收集该供应商下所有可选模型（去重）
        const modelNames = [];
        if (defaultModel && !modelNames.includes(defaultModel)) modelNames.push(defaultModel);
        for (const m of models) {
            const mName = m.name || m.id || '';
            if (mName && !modelNames.includes(mName)) modelNames.push(mName);
        }

        const group = document.createElement('optgroup');
        group.label = p.name;

        if (modelNames.length === 0) {
            // 没有模型列表，显示供应商名 + 默认模型
            const opt = document.createElement('option');
            opt.value = `${p.id}::${defaultModel}`;
            opt.textContent = defaultModel || '(未配置模型)';
            if (bot && bot.profile_id === p.id && !botModel) opt.selected = true;
            group.appendChild(opt);
            // 如果 bot 有自定义模型名
            if (bot && bot.profile_id === p.id && botModel && botModel !== defaultModel) {
                const customOpt = document.createElement('option');
                customOpt.value = `${p.id}::${botModel}`;
                customOpt.textContent = `${botModel}（自定义）`;
                customOpt.selected = true;
                group.appendChild(customOpt);
            }
        } else {
            for (const mName of modelNames) {
                const opt = document.createElement('option');
                opt.value = `${p.id}::${mName}`;
                opt.textContent = mName;
                // 匹配逻辑：bot 的 profile_id 匹配且 model 匹配（或 bot 无 model 覆盖且是默认模型）
                const isSelected = bot && bot.profile_id === p.id
                    && (botModel === mName || (!botModel && mName === defaultModel));
                if (isSelected) opt.selected = true;
                group.appendChild(opt);
            }
            // 如果 bot 的自定义模型名不在列表中，补充为额外选项并选中
            if (bot && bot.profile_id === p.id && botModel && !modelNames.includes(botModel)) {
                const opt = document.createElement('option');
                opt.value = `${p.id}::${botModel}`;
                opt.textContent = `${botModel}（自定义）`;
                opt.selected = true;
                group.appendChild(opt);
            }
        }
        select.appendChild(group);
    }

    // 深度思考的初始值
    const thinkingEnabled = bot ? (bot.thinking_enabled || false) : false;
    const thinkingDepth = bot ? (bot.thinking_depth || 'high') : 'high';

    // 设置 toggle 按钮状态
    setToggleValue('thinking-enabled', thinkingEnabled ? 'true' : 'false');
    setToggleValue('thinking-depth', thinkingDepth);

    // 解析当前选中值的辅助函数
    function parseModelSelect(val) {
        const parts = (val || '').split('::');
        return { profileId: parts[0] || '', model: parts[1] || '' };
    }

    // 根据 provider 显示/隐藏 DeepSeek 模式设置
    const currentVal = parseModelSelect(select.value);
    const profile = profiles.find(p => p.id === currentVal.profileId);
    updateProviderSettings(profile ? profile.provider : 'generic');
    updateThinkingUI();

    // 模型选择下拉变化时联动
    select.onchange = () => {
        const { profileId: pid } = parseModelSelect(select.value);
        const prof = profiles.find(p => p.id === pid);
        updateProviderSettings(prof ? prof.provider : 'generic');
    };
    const tag = document.getElementById('bot-edit-provider-tag');
    if (tag) tag.classList.remove('hidden');

    // 清空灵魂预览
    const preview = document.getElementById('soul-preview');
    preview.innerHTML = '';
    preview.classList.add('hidden');

    // 如果有 soul_folder，预览
    if (bot && bot.soul_folder) {
        previewSoulFolder(bot.soul_folder);
    }

    // 技能：全局 / 自定义
    const useGlobal = bot ? (bot.skills_use_global !== false) : true;
    setToggleValue('skills-source', useGlobal ? 'global' : 'custom');
    const customSkills = bot ? (bot.enabled_skills || []) : [];
    renderSkillList('bot-skill-list', 'bot-skill-empty', customSkills);
    updateBotSkillsUI();

    const memCustom = bot && (
        bot.memory_enabled !== null && bot.memory_enabled !== undefined
        || bot.memory_write_enabled !== null && bot.memory_write_enabled !== undefined
    );
    setToggleValue('memory-source', memCustom ? 'custom' : 'global');
    const memOn = !bot || bot.memory_enabled !== false;
    setToggleValue('bot-memory-enabled', memOn ? 'true' : 'false');
    const memWrite = !bot || bot.memory_write_enabled !== false;
    setToggleValue('bot-memory-write-enabled', memWrite ? 'true' : 'false');
    updateBotMemoryUI();

    const autoCustom = bot && (
        bot.memory_auto_extract !== null && bot.memory_auto_extract !== undefined
        || bot.memory_extract_threshold_pct !== null && bot.memory_extract_threshold_pct !== undefined
    );
    setToggleValue('auto-compress-source', autoCustom ? 'custom' : 'global');
    const botAutoOn = bot && bot.memory_auto_extract === true;
    setToggleValue('bot-memory-auto-extract', botAutoOn ? 'true' : 'false');
    const botPct = (bot && bot.memory_extract_threshold_pct != null)
        ? bot.memory_extract_threshold_pct
        : (cachedConfig.memory_extract_threshold_pct ?? 85);
    const botThr = document.getElementById('bot-auto-compress-threshold');
    const botThrVal = document.getElementById('bot-auto-compress-threshold-val');
    if (botThr) {
        botThr.value = botPct;
        if (botThrVal) botThrVal.textContent = botPct + '%';
    }
    updateBotAutoCompressUI();

    const detailCustom = bot && bot.compress_summary_detail != null && bot.compress_summary_detail !== '';
    setToggleValue('compress-detail-source', detailCustom ? 'custom' : 'global');
    const detailSel = document.getElementById('bot-compress-summary-detail');
    if (detailSel) {
        detailSel.value = (bot && bot.compress_summary_detail)
            || cachedConfig.compress_summary_detail
            || 'standard';
    }
    updateBotCompressDetailUI();

    document.getElementById('bot-edit-modal').classList.remove('hidden');
}

function updateBotMemoryUI() {
    const wrap = document.getElementById('bot-memory-custom');
    if (!wrap) return;
    const useCustom = getBotToggleValue('memory-source') === 'custom';
    wrap.classList.toggle('hidden', !useCustom);
}

function updateBotAutoCompressUI() {
    const wrap = document.getElementById('bot-auto-compress-custom');
    if (!wrap) return;
    const useCustom = getBotToggleValue('auto-compress-source') === 'custom';
    wrap.classList.toggle('hidden', !useCustom);
}

function updateBotCompressDetailUI() {
    const wrap = document.getElementById('bot-compress-detail-custom');
    if (!wrap) return;
    const useCustom = getBotToggleValue('compress-detail-source') === 'custom';
    wrap.classList.toggle('hidden', !useCustom);
}

function openCompressModal() {
    if (window.compressInProgress) return;
    const modal = document.getElementById('compress-modal');
    if (modal) {
        modal.classList.remove('hidden');
        const level = typeof resolveDefaultCompressDetail === 'function'
            ? resolveDefaultCompressDetail()
            : 'standard';
        if (typeof setCompressDetailInModal === 'function') {
            setCompressDetailInModal(level);
        }
    }
}

function hideBotEditModal() {
    document.getElementById('bot-edit-modal').classList.add('hidden');
}

function collectEnabledSkillIds(listId) {
    const ids = [];
    document.querySelectorAll(`#${listId} .skill-checkbox:checked`).forEach(cb => {
        ids.push(cb.dataset.id);
    });
    return ids;
}

async function renderSkillList(listId, emptyId, enabledSkills, options = {}) {
    const list = document.getElementById(listId);
    const empty = document.getElementById(emptyId);
    if (!list || !empty) return;
    list.innerHTML = '';

    let skills = [];
    try {
        const resultStr = await pywebview.api.get_skills();
        const result = JSON.parse(resultStr);
        if (result.ok) skills = result.skills;
    } catch (e) {}

    if (!skills.length) {
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');

    for (const skill of skills) {
        const enabled = enabledSkills.includes(skill.id);
        const item = document.createElement('div');
        item.className = 'skill-item' + (enabled ? ' active' : '');
        item.innerHTML = `
            <input type="checkbox" class="skill-checkbox" data-id="${escapeHtml(skill.id)}" ${enabled ? 'checked' : ''}>
            <div class="skill-info">
                <div class="skill-name">${skill.icon || '🔧'} ${escapeHtml(skill.name)} <span class="skill-version">v${escapeHtml(skill.version || '1.0')}</span></div>
                <div class="skill-desc">${escapeHtml(skill.description || '')}</div>
            </div>
        `;
        const notifyChange = () => {
            if (options.onChange) options.onChange(collectEnabledSkillIds(listId));
        };
        item.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT') return;
            const cb = item.querySelector('.skill-checkbox');
            cb.checked = !cb.checked;
            item.classList.toggle('active', cb.checked);
            notifyChange();
        });
        item.querySelector('.skill-checkbox').addEventListener('change', (e) => {
            item.classList.toggle('active', e.target.checked);
            notifyChange();
        });
        list.appendChild(item);
    }
}

function openSkillsDir() {
    pywebview.api.open_skills_dir();
}

function updateBotSkillsUI() {
    const useGlobal = getBotToggleValue('skills-source') !== 'custom';
    const hint = document.getElementById('bot-skills-global-hint');
    const wrap = document.getElementById('bot-skill-custom-wrap');
    if (hint) hint.classList.toggle('hidden', !useGlobal);
    if (wrap) wrap.classList.toggle('hidden', useGlobal);
}

function getBotToggleValue(field) {
    const active = document.querySelector(
        `#bot-edit-modal .toggle-btn[data-field="${field}"].active`
    );
    return active ? active.dataset.value : '';
}

function updateProviderSettings(provider) {
    const thinkingSection = document.getElementById('thinking-section');
    const tag = document.getElementById('bot-edit-provider-tag');
    if (provider === 'deepseek') {
        thinkingSection.classList.remove('hidden');
        if (tag) {
            tag.textContent = 'DeepSeek';
            tag.className = 'provider-tag provider-tag--deepseek';
        }
    } else if (provider === 'anthropic') {
        thinkingSection.classList.add('hidden');
        if (tag) {
            tag.textContent = 'Anthropic';
            tag.className = 'provider-tag provider-tag--anthropic';
        }
    } else {
        thinkingSection.classList.add('hidden');
        if (tag) {
            tag.textContent = '通用';
            tag.className = 'provider-tag';
        }
    }
    updateThinkingUI();
}

function setToggleValue(field, value) {
    const btns = document.querySelectorAll(`.toggle-btn[data-field="${field}"]`);
    btns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === value);
    });
}

function getToggleValue(field) {
    const active = document.querySelector(`.toggle-btn[data-field="${field}"].active`);
    return active ? active.dataset.value : '';
}

function updateThinkingUI() {
    const enabled = getToggleValue('thinking-enabled') === 'true';
    const depthRow = document.getElementById('thinking-depth-row');
    const tempWarning = document.getElementById('thinking-temp-warning');
    const hintFast = document.getElementById('thinking-mode-hint-fast');
    const hintThink = document.getElementById('thinking-mode-hint-think');
    const tempInput = document.getElementById('bot-edit-temp');
    if (enabled) {
        depthRow.classList.remove('hidden');
        tempWarning.classList.remove('hidden');
        if (hintFast) hintFast.classList.add('hidden');
        if (hintThink) hintThink.classList.remove('hidden');
        tempInput.disabled = true;
        tempInput.style.opacity = '0.4';
    } else {
        depthRow.classList.add('hidden');
        tempWarning.classList.add('hidden');
        if (hintFast) hintFast.classList.remove('hidden');
        if (hintThink) hintThink.classList.add('hidden');
        tempInput.disabled = false;
        tempInput.style.opacity = '';
    }
}

// Toggle 按钮点击事件（事件委托）
document.getElementById('bot-edit-modal').addEventListener('click', (e) => {
    const btn = e.target.closest('.toggle-btn');
    if (!btn) return;
    const field = btn.dataset.field;
    const value = btn.dataset.value;
    setToggleValue(field, value);
    if (field === 'thinking-enabled' || field === 'thinking-depth') {
        updateThinkingUI();
    }
    if (field === 'skills-source') {
        updateBotSkillsUI();
    }
    if (field === 'memory-source') {
        updateBotMemoryUI();
    }
    if (field === 'auto-compress-source') {
        updateBotAutoCompressUI();
    }
    if (field === 'compress-detail-source') {
        updateBotCompressDetailUI();
    }
});

const botThrRange = document.getElementById('bot-auto-compress-threshold');
const botThrVal = document.getElementById('bot-auto-compress-threshold-val');
if (botThrRange && botThrVal) {
    botThrRange.addEventListener('input', () => {
        botThrVal.textContent = botThrRange.value + '%';
    });
}

async function saveBot() {
    const id = document.getElementById('bot-edit-id').value;
    const name = document.getElementById('bot-edit-name').value.trim() || '未命名';
    const avatar = document.getElementById('bot-edit-avatar').textContent || '🤖';
    const selectVal = document.getElementById('bot-edit-profile').value;
    const [profileId, selectedModel] = selectVal.split('::');
    const soulFolder = document.getElementById('bot-edit-soul').value.trim();
    const modelOverride = document.getElementById('bot-edit-model').value.trim();
    const model = modelOverride || selectedModel || '';
    const tempStr = document.getElementById('bot-edit-temp').value.trim();
    const maxStr = document.getElementById('bot-edit-max').value.trim();
    const maxContextStr = document.getElementById('bot-edit-max-context').value.trim();

    // 深度思考
    const thinkingEnabled = getToggleValue('thinking-enabled') === 'true';
    const thinkingDepth = getToggleValue('thinking-depth') || 'high';

    const skillsUseGlobal = getBotToggleValue('skills-source') !== 'custom';
    const enabledSkills = skillsUseGlobal
        ? []
        : collectEnabledSkillIds('bot-skill-list');

    const bots = cachedConfig.bots || [];
    const existing = bots.find(b => b.id === id) || {};

    const memoryCustom = getBotToggleValue('memory-source') === 'custom';
    let memory_enabled = null;
    let memory_write_enabled = null;
    if (memoryCustom) {
        memory_enabled = getBotToggleValue('bot-memory-enabled') === 'true';
        memory_write_enabled = getBotToggleValue('bot-memory-write-enabled') === 'true';
    }

    const autoCompressCustom = getBotToggleValue('auto-compress-source') === 'custom';
    let memory_auto_extract = null;
    let memory_extract_threshold_pct = null;
    if (autoCompressCustom) {
        memory_auto_extract = getBotToggleValue('bot-memory-auto-extract') === 'true';
        const thrEl = document.getElementById('bot-auto-compress-threshold');
        memory_extract_threshold_pct = thrEl ? parseInt(thrEl.value, 10) || 85 : 85;
    }

    const compressDetailCustom = getBotToggleValue('compress-detail-source') === 'custom';
    let compress_summary_detail = null;
    if (compressDetailCustom) {
        const detailSel = document.getElementById('bot-compress-summary-detail');
        compress_summary_detail = detailSel ? detailSel.value || 'standard' : 'standard';
    }

    const bot = {
        ...existing,
        id: id,
        name: name,
        avatar: avatar,
        profile_id: profileId,
        soul_folder: soulFolder,
        model: model || '',
        temperature: tempStr ? parseFloat(tempStr) : null,
        max_tokens: maxStr ? parseInt(maxStr) : null,
        max_context: maxContextStr ? parseInt(maxContextStr) : null,
        thinking_enabled: thinkingEnabled,
        thinking_depth: thinkingDepth,
        skills_use_global: skillsUseGlobal,
        enabled_skills: enabledSkills,
        memory_enabled,
        memory_write_enabled,
        memory_auto_extract,
        memory_extract_threshold_pct,
        compress_summary_detail,
    };

    const resultStr = await pywebview.api.save_bot(JSON.stringify(bot));
    const result = JSON.parse(resultStr);
    if (result.ok) {
        hideBotEditModal();
        await refreshConfig();
        updateBotDisplay();
        await loadBots();
        if (!document.getElementById('status-panel').classList.contains('hidden')) {
            await refreshStatusPanel();
        }
        // 如果管理弹窗开着，刷新列表
        if (!document.getElementById('bot-manager-modal').classList.contains('hidden')) {
            showBotManager();
        }
    } else {
        alert(result.msg);
    }
}

async function clearBotMemory() {
    const botName = document.getElementById('bot-edit-name').value.trim() || '当前机器人';
    if (!confirm(`⚠️ 第 1 次确认：确定要清空「${botName}」的全部记忆吗？\n\n此操作将删除该 Bot 的所有记忆条目、收藏、文档和索引。`)) return;
    if (!confirm(`⚠️ 第 2 次确认：此操作不可撤销！\n\n「${botName}」的所有记忆数据将被永久删除。是否继续？`)) return;
    if (!confirm(`🔴 最终确认：这是最后一次机会！\n\n点击「确定」将立即删除「${botName}」的全部记忆。`)) return;
    try {
        const resultStr = await pywebview.api.clear_bot_memory();
        const result = JSON.parse(resultStr);
        if (result.ok) {
            alert('✅ 记忆已清空');
            if (typeof refreshMemoryPanel === 'function') {
                await refreshMemoryPanel();
            }
        } else {
            alert('❌ ' + (result.msg || '清空失败'));
        }
    } catch (e) {
        alert('❌ 清空记忆失败：' + e.message);
    }
}

async function browseSoulFolder() {
    const current = document.getElementById('bot-edit-soul')?.value?.trim() || '';
    const resultStr = await pywebview.api.select_soul_folder(current);
    const result = JSON.parse(resultStr);
    if (result.ok) {
        document.getElementById('bot-edit-soul').value = result.path;
        previewSoulFolder(result.path);
    }
}

async function previewSoulFolder(path) {
    const preview = document.getElementById('soul-preview');
    if (!path) {
        preview.innerHTML = '';
        preview.classList.add('hidden');
        return;
    }
    const resultStr = await pywebview.api.preview_soul_folder(path);
    const result = JSON.parse(resultStr);
    if (result.ok && result.items) {
        preview.classList.remove('hidden');
        preview.innerHTML = result.items.map(item => {
            const badge = item.type === 'dir' ? '目录' : 'MD';
            const status = item.type === 'dir' ? `${item.count} 个文件` : '已加载';
            return `<div class="soul-preview-item"><span class="soul-preview-badge">${badge}</span><span class="soul-preview-name">${escapeHtml(item.name)}</span><span class="status">${status}</span></div>`;
        }).join('');
    } else {
        preview.classList.remove('hidden');
        preview.innerHTML = `<div class="soul-preview-item"><span class="soul-preview-badge warn">!</span><span class="soul-preview-name">${escapeHtml(result.msg || '无法预览')}</span></div>`;
    }
}

// ===== Emoji 选择 =====

function getCurrentPickerAvatar(target) {
    if (target === 'user') {
        const el = document.getElementById('cfg-user-avatar');
        return el ? el.textContent.trim() : '';
    }
    if (target === 'bot-header' && cachedConfig) {
        return getActiveBot(cachedConfig).avatar || '🤖';
    }
    const el = document.getElementById('bot-edit-avatar');
    return el ? el.textContent.trim() : '🤖';
}

function showEmojiPicker(target, callback) {
    emojiPickerTarget = target;
    emojiPickerCallback = callback;
    renderEmojiPicker(target, getCurrentPickerAvatar(target));
    document.getElementById('emoji-picker-modal').classList.remove('hidden');
}

function openUserEmojiPicker() {
    showEmojiPicker('user', (emoji) => {
        const el = document.getElementById('cfg-user-avatar');
        if (el) el.textContent = emoji;
    });
}

function openBotEmojiPicker() {
    showEmojiPicker('bot', (emoji) => {
        const el = document.getElementById('bot-edit-avatar');
        if (el) el.textContent = emoji;
    });
}

/** 顶栏：更换当前 Bot 头像（保存到 config） */
async function openActiveBotEmojiPicker() {
    if (!cachedConfig) return;
    const bot = getActiveBot(cachedConfig);
    showEmojiPicker('bot-header', async (emoji) => {
        try {
            const payload = { ...bot, avatar: emoji };
            const resultStr = await pywebview.api.save_bot(JSON.stringify(payload));
            const result = JSON.parse(resultStr);
            if (result.ok) {
                await refreshConfig();
                updateBotDisplay();
                await loadBots();
            } else {
                alert(result.msg || '保存失败');
            }
        } catch (e) {
            alert('保存头像失败');
        }
    });
}

function initAvatarPickers() {
    const headerAvatar = document.getElementById('current-bot-avatar');
    if (headerAvatar) {
        headerAvatar.addEventListener('click', (e) => {
            e.stopPropagation();
            openActiveBotEmojiPicker();
        });
    }
    const userAvatar = document.getElementById('cfg-user-avatar');
    if (userAvatar) {
        userAvatar.addEventListener('click', () => openUserEmojiPicker());
    }
}

initAvatarPickers();

function hideEmojiPicker() {
    document.getElementById('emoji-picker-modal').classList.add('hidden');
    emojiPickerTarget = null;
    emojiPickerCallback = null;
}

function createEmojiOption(emoji, currentEmoji) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'emoji-option' + (emoji === currentEmoji ? ' selected' : '');
    btn.title = emoji;
    btn.setAttribute('aria-label', `选择头像 ${emoji}`);
    const span = document.createElement('span');
    span.className = 'emoji-char';
    span.textContent = emoji;
    btn.appendChild(span);
    btn.addEventListener('click', () => selectEmoji(emoji));
    return btn;
}

function renderEmojiPicker(target, currentEmoji = '') {
    const normalGrid = document.getElementById('emoji-normal');
    const abstractGrid = document.getElementById('emoji-abstract');
    const abstractSection = abstractGrid?.parentElement;
    if (!normalGrid || !abstractGrid) return;

    normalGrid.innerHTML = '';
    abstractGrid.innerHTML = '';

    const isUser = target === 'user';
    const normalEmojis = filterRenderableEmojis(
        isUser ? EMOJI_USER : EMOJI_NORMAL_BOT
    );
    const abstractEmojis = isUser
        ? []
        : filterRenderableEmojis(EMOJI_ABSTRACT_BOT);

    if (abstractSection) abstractSection.style.display = '';

    for (const emoji of normalEmojis) {
        normalGrid.appendChild(createEmojiOption(emoji, currentEmoji));
    }

    if (abstractEmojis.length > 0) {
        for (const emoji of abstractEmojis) {
            abstractGrid.appendChild(createEmojiOption(emoji, currentEmoji));
        }
    } else if (abstractSection) {
        abstractSection.style.display = 'none';
    }
}

function selectEmoji(emoji) {
    if (emojiPickerCallback) {
        emojiPickerCallback(emoji);
    }
    hideEmojiPicker();
}

// ===== 上下文进度条 =====

let isContextFull = false;

function updateContextState(percentage) {
    isContextFull = percentage >= 100;
    const sendBtn = document.getElementById('btn-send');
    if (sendBtn) {
        sendBtn.disabled = isContextFull;
        sendBtn.style.opacity = isContextFull ? '0.4' : '';
        sendBtn.style.cursor = isContextFull ? 'not-allowed' : '';
    }
}

function updateContextBarIncremental(delta) {
    localTokenCount += delta;
    const bot = getActiveBot(cachedConfig);
    const profile = getActiveProfile(cachedConfig);
    const maxContext = bot.max_context || profile.max_context || 65536;
    const percentage = Math.min(100, (localTokenCount / maxContext) * 100);
    updateContextState(percentage);
}

async function refreshContextUsage() {
    try {
        const resultStr = await pywebview.api.get_context_usage();
        const usage = JSON.parse(resultStr);
        localTokenCount = usage.total_used;
        updateContextState(usage.percentage);
        return usage;
    } catch (e) {
        return null;
    }
}

async function compressContext() {
    openCompressModal();
}

// ===== 状态面板 =====

async function refreshStatusPanel() {
    // Bot 状态
    const bot = getActiveBot(cachedConfig);
    const profile = getActiveProfile(cachedConfig);
    const botAvatarEl = document.getElementById('status-bot-avatar');
    const botNameEl = document.getElementById('status-bot-name');
    if (botAvatarEl) botAvatarEl.textContent = bot.avatar || '🤖';
    if (botNameEl) botNameEl.textContent = bot.name || '-';

    const apiEl = document.getElementById('status-api-name');
    const modelEl = document.getElementById('status-model-name');
    const apiName = profile.name || '-';
    const modelName = profile.model || '-';
    if (apiEl) {
        apiEl.textContent = apiName;
        apiEl.title = apiName;
    }
    if (modelEl) {
        modelEl.textContent = modelName;
        modelEl.title = modelName;
    }

    const thinkingEl = document.getElementById('status-thinking');
    if (thinkingEl) {
        thinkingEl.textContent = formatReplyModeStatus(bot, profile);
    }

    // 上下文
    try {
        const resultStr = await pywebview.api.get_context_usage();
        const usage = JSON.parse(resultStr);
        renderStatusPanel(usage);
        if (typeof refreshMemoryPanel === 'function') {
            await refreshMemoryPanel();
        }
    } catch (e) {}
}

function renderStatusPanel(usage) {
    document.getElementById('status-ctx-max').textContent = usage.max_context.toLocaleString();
    const usedEl = document.getElementById('status-ctx-used');
    if (usedEl) {
        usedEl.innerHTML = `${usage.total_used.toLocaleString()}<span class="status-ctx-pct">${usage.percentage}%</span>`;
    }
    document.getElementById('status-ctx-remaining').textContent = usage.remaining.toLocaleString();

    // 容量条
    const bar = document.getElementById('status-context-bar');
    bar.style.width = Math.min(100, usage.percentage) + '%';
    bar.className = 'status-context-bar';
    if (usage.percentage >= 100) bar.classList.add('level-full');
    else if (usage.percentage >= 60) bar.classList.add('level-high');
    else if (usage.percentage >= 40) bar.classList.add('level-mid');
    else bar.classList.add('level-low');
    const percentEl = document.getElementById('status-context-percent');
    const pct = Math.round(usage.percentage);
    if (percentEl) {
        percentEl.textContent = pct + '%';
        percentEl.className = 'status-percent-badge';
        if (usage.percentage >= 100) percentEl.classList.add('level-full');
        else if (usage.percentage >= 60) percentEl.classList.add('level-high');
        else if (usage.percentage >= 40) percentEl.classList.add('level-mid');
        else percentEl.classList.add('level-low');
    }

    // 占用明细
    const breakdown = usage.breakdown;
    const total = usage.total_used || 1;

    document.getElementById('status-breakdown-system').style.width = (breakdown.system / total * 100) + '%';
    document.getElementById('status-breakdown-system-val').textContent = breakdown.system.toLocaleString();

    document.getElementById('status-breakdown-summary').style.width = (breakdown.summary / total * 100) + '%';
    document.getElementById('status-breakdown-summary-val').textContent = breakdown.summary.toLocaleString();

    document.getElementById('status-breakdown-messages').style.width = (breakdown.messages / total * 100) + '%';
    document.getElementById('status-breakdown-messages-val').textContent = breakdown.messages.toLocaleString();

    // 建议
    const advice = document.getElementById('status-advice');
    const adviceText = document.getElementById('status-advice-text');
    if (usage.percentage >= 100) {
        advice.classList.remove('hidden');
        advice.className = 'status-advice danger';
        adviceText.textContent = '❌ 上下文已满，无法发送新消息';
    } else if (usage.percentage >= 80) {
        advice.classList.remove('hidden');
        advice.className = 'status-advice warning';
        adviceText.textContent = '⚠️ 上下文即将用完，建议压缩';
    } else if (usage.percentage >= 60) {
        advice.classList.remove('hidden');
        advice.className = 'status-advice';
        adviceText.textContent = '上下文偏多，可考虑压缩';
    } else {
        advice.classList.add('hidden');
    }
}

// ===== API 日志 =====

const MAX_LOG_ENTRIES = 100;
let logEntries = [];

function onLog(msg) {
    // 检查 API 日志开关
    if (cachedConfig && cachedConfig.api_log_enabled === false) return;
    const time = new Date().toLocaleTimeString();
    const entry = `[${time}] ${msg}`;
    logEntries.push(entry);
    if (logEntries.length > MAX_LOG_ENTRIES) {
        logEntries.shift();
    }
    const list = document.getElementById('status-log-list');
    if (!list) return;
    const div = document.createElement('div');
    div.className = 'status-log-entry';
    div.textContent = entry;
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
}

function copyLogs() {
    const text = logEntries.join('\n');
    navigator.clipboard.writeText(text).then(() => {
        onLog('日志已复制到剪贴板');
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        onLog('日志已复制到剪贴板');
    });
}

function clearLogs() {
    logEntries = [];
    const list = document.getElementById('status-log-list');
    if (list) list.innerHTML = '';
}

// 供 HTML onclick 与顶栏按钮调用
window.showBotManager = showBotManager;
window.hideBotManager = hideBotManager;
window.showBotEditModal = showBotEditModal;
window.hideBotEditModal = hideBotEditModal;
window.editActiveBot = editActiveBot;
window.clearBotMemory = clearBotMemory;
