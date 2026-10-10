// ===== 配置管理 =====

function getActiveBot(config) {
    const bots = config.bots || [];
    const activeId = config.active_bot_id || '';
    return bots.find(b => b.id === activeId) || bots[0] || {};
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme || 'dark');
}

function getActiveProfile(config) {
    const bot = getActiveBot(config);
    const profileId = bot.profile_id || '';
    const profiles = config.api_profiles || [];
    return profiles.find(p => p.id === profileId) || profiles[0] || {};
}

function getProfileModelConfig(profile, modelName) {
    if (!profile) return null;
    const name = modelName || profile.model || '';
    const models = profile.models || [];
    return models.find(m => m.name === name) || null;
}

function modelSupportsCapability(profile, capability, modelName) {
    const modelCfg = getProfileModelConfig(profile, modelName);
    if (!modelCfg) {
        // 旧配置没有 models[] 时保持兼容：DeepSeek 默认认为支持推理，工具由技能自行控制。
        if (capability === 'reasoning') return profile?.provider === 'deepseek';
        if (capability === 'tools') return true;
        return false;
    }
    return (modelCfg.capabilities || []).includes(capability);
}

async function refreshConfig() {
    const configStr = await pywebview.api.get_config();
    cachedConfig = JSON.parse(configStr);
    updateModelDisplay();
    if (typeof applyEditorWordWrapFromConfig === 'function') {
        applyEditorWordWrapFromConfig();
    }
}

function updateModelDisplay() {
    if (!cachedConfig) return;
    const profile = getActiveProfile(cachedConfig);
    sidebarModelName.textContent = profile.name || profile.model || '-';
}

// ===== Config Modal =====
function populateGeneralSettings() {
    if (!cachedConfig) return;
    document.getElementById('cfg-user-avatar').textContent = cachedConfig.user_avatar || '😎';
    document.getElementById('cfg-user-font-size').value = cachedConfig.user_font_size || 14;
    document.getElementById('cfg-bot-font-size').value = cachedConfig.bot_font_size || 14;
    document.getElementById('cfg-thinking-font-size').value = cachedConfig.thinking_font_size || 12;
    document.getElementById('cfg-theme').value = cachedConfig.theme || 'dark';
    // API 日志开关
    const apiLogEnabled = cachedConfig.api_log_enabled !== false; // 默认开启
    document.querySelectorAll('[data-field="api-log-enabled"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(apiLogEnabled));
    });
    const wordWrap = cachedConfig.editor_word_wrap !== false;
    document.querySelectorAll('[data-field="editor-word-wrap"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(wordWrap));
    });
    const memEnabled = cachedConfig.memory_enabled !== false;
    document.querySelectorAll('[data-field="memory-enabled"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(memEnabled));
    });
    const memWrite = cachedConfig.memory_write_enabled !== false;
    document.querySelectorAll('[data-field="memory-write-enabled"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(memWrite));
    });
    const budgetEl = document.getElementById('cfg-memory-token-budget');
    if (budgetEl) budgetEl.value = cachedConfig.memory_token_budget ?? 1200;
    const autoExtract = cachedConfig.memory_auto_extract === true;
    document.querySelectorAll('[data-field="memory-auto-extract"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(autoExtract));
    });
    const thresholdEl = document.getElementById('cfg-auto-compress-threshold');
    const thresholdVal = document.getElementById('cfg-auto-compress-threshold-val');
    const pct = cachedConfig.memory_extract_threshold_pct ?? 85;
    if (thresholdEl) {
        thresholdEl.value = pct;
        if (thresholdVal) thresholdVal.textContent = pct + '%';
    }
    const detailEl = document.getElementById('cfg-compress-summary-detail');
    if (detailEl) {
        detailEl.value = cachedConfig.compress_summary_detail || 'standard';
    }
    // 整理模型选择器
    const organizerEnabled = cachedConfig.memory_organizer_enabled === true;
    document.querySelectorAll('[data-field="organizer-enabled"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(organizerEnabled));
    });
    const organizerSection = document.getElementById('organizer-model-section');
    if (organizerSection) organizerSection.style.display = organizerEnabled ? '' : 'none';
    renderOrganizerProfileSelect();
    // 整理模型思考模式
    const orgThinking = cachedConfig.organizer_thinking_enabled === true;
    document.querySelectorAll('[data-field="organizer-thinking"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(orgThinking));
    });
    const depthRow = document.getElementById('organizer-thinking-depth-row');
    if (depthRow) depthRow.style.display = orgThinking ? '' : 'none';
    const orgDepth = cachedConfig.organizer_thinking_depth || 'high';
    document.querySelectorAll('[data-field="organizer-thinking-depth"]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === orgDepth);
    });
    const providerEl = document.getElementById('cfg-web-search-provider');
    const keyEl = document.getElementById('cfg-web-search-api-key');
    if (providerEl) providerEl.value = cachedConfig.web_search_provider || 'duckduckgo';
    if (keyEl) keyEl.value = cachedConfig.web_search_api_key || '';
    const maxRoundsEl = document.getElementById('cfg-web-search-max-rounds');
    const maxQueriesEl = document.getElementById('cfg-web-search-max-queries');
    if (maxRoundsEl) maxRoundsEl.value = cachedConfig.web_search_max_rounds ?? 3;
    if (maxQueriesEl) maxQueriesEl.value = cachedConfig.web_search_max_queries_per_round ?? 3;
    testResult.classList.add('hidden');
    if (typeof renderSkillList === 'function') {
        renderSkillList('cfg-skill-list', 'cfg-skill-empty', cachedConfig.enabled_skills || []);
    }
}

function renderOrganizerProfileSelect() {
    const select = document.getElementById('cfg-organizer-profile');
    if (!select) return;
    select.innerHTML = '';
    const profiles = cachedConfig.api_profiles || [];
    const currentPid = cachedConfig.memory_organizer_profile_id || '';
    const currentBotId = cachedConfig.memory_organizer_bot_id || '';

    // 空选项（使用当前对话模型）
    const emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = '（使用当前对话模型）';
    select.appendChild(emptyOpt);

    for (const p of profiles) {
        if (p.enabled === false) continue;
        const models = p.models || [];
        const defaultModel = p.model || '';
        const modelNames = [];
        if (defaultModel && !modelNames.includes(defaultModel)) modelNames.push(defaultModel);
        for (const m of models) {
            const mName = m.name || m.id || '';
            if (mName && !modelNames.includes(mName)) modelNames.push(mName);
        }

        const group = document.createElement('optgroup');
        group.label = p.name;

        if (modelNames.length === 0) {
            const opt = document.createElement('option');
            opt.value = `${p.id}::${defaultModel}`;
            opt.textContent = defaultModel || '(未配置模型)';
            if (p.id === currentPid && !currentBotId) opt.selected = true;
            group.appendChild(opt);
        } else {
            for (const mName of modelNames) {
                const opt = document.createElement('option');
                opt.value = `${p.id}::${mName}`;
                opt.textContent = mName;
                if (p.id === currentPid && (cachedConfig._organizer_model === mName || (!cachedConfig._organizer_model && mName === defaultModel))) {
                    opt.selected = true;
                }
                group.appendChild(opt);
            }
        }
        select.appendChild(group);
    }
}

function showConfigModal() {
    if (typeof refreshReceiveDirUI === 'function') {
        refreshReceiveDirUI();
    }
    if (typeof resetSettingsNavigation === 'function') {
        resetSettingsNavigation();
    }
    configModal.classList.remove('hidden');
}

function hideConfigModal() {
    configModal.classList.add('hidden');
    if (typeof resetSettingsNavigation === 'function') {
        resetSettingsNavigation();
    }
}

function showTestResult(msg, ok) {
    if (!testResult) return;
    testResult.textContent = msg;
    testResult.className = 'test-result ' + (ok ? 'success' : 'error');
    testResult.classList.remove('hidden');
}

