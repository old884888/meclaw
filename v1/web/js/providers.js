// ===== 供应商（API Profiles）设置 =====

let settingsViewStack = ['hub'];
let editingProviderId = null;
let editingModelId = null;
let providerDraft = null;

const SETTINGS_VIEWS = {
    hub: { title: '⚙ 设置', subtitle: '选择要调整的类别', footer: false },
    providers: { title: '🔌 供应商', subtitle: '管理 API 连接与模型', footer: false },
    'provider-detail': { title: '编辑供应商', subtitle: '', footer: false },
    appearance: { title: '🎨 外观', subtitle: '主题、头像和字号', footer: true, section: 'appearance' },
    memory: { title: '🧠 记忆', subtitle: '检索、写入和自动压缩', footer: true, section: 'memory' },
    developer: { title: '⚙ 开发者', subtitle: '联网、技能、文件目录和日志', footer: true, section: 'developer' },
};

function newProviderId() {
    return 'p_' + Date.now();
}

function newModelId() {
    return 'm_' + Math.random().toString(36).slice(2, 10);
}

function defaultProvider() {
    return {
        id: newProviderId(),
        name: '新供应商',
        base_url: '',
        api_key: '',
        model: '',
        provider: 'generic',
        enabled: true,
        temperature: 0.7,
        max_tokens: 4096,
        max_context: 65536,
        balance: {
            enabled: false,
            path: '/user/balance',
            json_path: 'balance_infos[0].total_balance',
            last_value: '',
        },
        models: [],
    };
}

function defaultModel(name) {
    const provider = providerDraft?.provider || document.getElementById('pv-provider')?.value || 'generic';
    const capabilities = ['tools'];
    if (provider === 'deepseek' || provider === 'anthropic') capabilities.push('reasoning');
    return {
        id: newModelId(),
        name: name || '',
        input: ['text'],
        output: ['text'],
        capabilities,
    };
}

function ensureProfileShape(p) {
    if (!p.balance) {
        p.balance = { enabled: false, path: '/user/balance', json_path: 'balance_infos[0].total_balance', last_value: '' };
    }
    if (!Array.isArray(p.models)) {
        p.models = p.model ? [defaultModel(p.model)] : [];
    }
    if (p.enabled === undefined) p.enabled = true;
    return p;
}

function getProviderById(id) {
    return (cachedConfig?.api_profiles || []).find(p => p.id === id) || null;
}

function pushSettingsView(view) {
    settingsViewStack.push(view);
    showSettingsView(view);
}

function popSettingsView() {
    if (settingsViewStack.length <= 1) return;
    settingsViewStack.pop();
    showSettingsView(settingsViewStack[settingsViewStack.length - 1]);
}

function resetSettingsNavigation() {
    settingsViewStack = ['hub'];
    showSettingsView('hub');
}

function showSettingsView(view) {
    document.querySelectorAll('.settings-view').forEach(el => el.classList.add('hidden'));
    const meta = SETTINGS_VIEWS[view] || SETTINGS_VIEWS.hub;
    const panelId = meta.section ? 'settings-view-general' : 'settings-view-' + view;
    const panel = document.getElementById(panelId);
    if (panel) panel.classList.remove('hidden');

    const titleEl = document.getElementById('settings-title');
    const subEl = document.getElementById('settings-subtitle');
    const backBtn = document.getElementById('settings-back');
    const footer = document.getElementById('config-footer-general');
    document.querySelectorAll('[data-settings-section]').forEach(section => {
        const shouldShow = !meta.section || section.dataset.settingsSection === meta.section;
        section.classList.toggle('hidden', !shouldShow);
    });

    if (titleEl) {
        if (view === 'provider-detail' && providerDraft) {
            titleEl.textContent = providerDraft.name || '编辑供应商';
        } else {
            titleEl.textContent = meta.title;
        }
    }
    if (subEl) subEl.textContent = meta.subtitle;
    if (backBtn) backBtn.classList.toggle('hidden', view === 'hub');
    if (footer) footer.classList.toggle('hidden', !meta.footer);
}

function initSettingsNavigation() {
    document.querySelectorAll('[data-settings-view]').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.settingsView;
            if (view === 'bots') {
                if (typeof hideConfigModal === 'function') hideConfigModal();
                if (typeof showBotManager === 'function') showBotManager();
                return;
            }
            if ((view === 'appearance' || view === 'memory' || view === 'developer')
                && typeof populateGeneralSettings === 'function') {
                populateGeneralSettings();
            }
            if (view === 'providers') renderProvidersList();
            pushSettingsView(view);
        });
    });

    document.getElementById('settings-back')?.addEventListener('click', () => {
        if (settingsViewStack[settingsViewStack.length - 1] === 'provider-detail') {
            providerDraft = null;
            editingProviderId = null;
        }
        popSettingsView();
        if (settingsViewStack[settingsViewStack.length - 1] === 'providers') {
            renderProvidersList();
        }
    });

    document.getElementById('btn-add-provider')?.addEventListener('click', () => {
        openProviderDetail(null);
    });

    document.querySelectorAll('.provider-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchProviderTab(tab.dataset.providerTab);
        });
    });

    document.getElementById('pv-provider')?.addEventListener('change', updateProviderOptimizationHint);
    document.getElementById('pv-balance-enabled')?.addEventListener('change', toggleBalanceFields);
    document.getElementById('pv-toggle-key')?.addEventListener('click', () => {
        const inp = document.getElementById('pv-api-key');
        if (!inp) return;
        inp.type = inp.type === 'password' ? 'text' : 'password';
    });
    document.getElementById('pv-default-model')?.addEventListener('change', onDefaultModelSelectChange);
    document.getElementById('btn-save-provider')?.addEventListener('click', saveProviderDetail);
    document.getElementById('btn-delete-provider')?.addEventListener('click', deleteCurrentProvider);
    document.getElementById('btn-test-provider')?.addEventListener('click', testCurrentProvider);
    document.getElementById('btn-query-balance')?.addEventListener('click', queryProviderBalance);
    document.getElementById('btn-add-provider-model')?.addEventListener('click', () => showModelEditModal(null));

    document.getElementById('model-edit-close')?.addEventListener('click', hideModelEditModal);
    document.getElementById('model-edit-cancel')?.addEventListener('click', hideModelEditModal);
    document.getElementById('model-edit-save')?.addEventListener('click', saveModelEdit);

    document.getElementById('model-edit-modal')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.cap-toggle');
        if (!btn) return;
        const group = btn.closest('.cap-toggle-group');
        const multi = group?.dataset.capGroup === 'capabilities';
        if (multi) {
            btn.classList.toggle('active');
        } else {
            group.querySelectorAll('.cap-toggle').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }
    });
}

function renderProvidersList() {
    const list = document.getElementById('providers-list');
    if (!list || !cachedConfig) return;
    list.innerHTML = '';
    const profiles = cachedConfig.api_profiles || [];
    const bot = getActiveBot(cachedConfig);
    const activeId = bot.profile_id || '';

    for (const p of profiles) {
        ensureProfileShape(p);
        const item = document.createElement('div');
        const disabled = p.enabled === false;
        item.className = 'provider-card' + (p.id === activeId ? ' active' : '') + (disabled ? ' disabled' : '');
        const badge = p.provider === 'deepseek' ? '<span class="provider-badge">DeepSeek</span>'
            : p.provider === 'anthropic' ? '<span class="provider-badge provider-badge--anthropic">Anthropic</span>'
            : '';
        const modelCount = (p.models || []).length;
        const balance = p.balance?.last_value ? `<span class="provider-balance-chip">¥${escapeHtml(p.balance.last_value)}</span>` : '';
        item.innerHTML = `
            <div class="provider-card-main">
                <div class="provider-card-name">${escapeHtml(p.name || '未命名')}${badge}${balance}</div>
                <div class="provider-card-meta">${escapeHtml(p.model || '未设默认模型')} · ${modelCount} 个模型</div>
            </div>
        `;
        item.addEventListener('click', async (e) => {
            if (e.target.closest('.provider-use-btn')) return;
            openProviderDetail(p.id);
        });
        const useBtn = document.createElement('button');
        useBtn.type = 'button';
        useBtn.className = 'provider-use-btn btn-secondary btn-sm';
        useBtn.textContent = p.id === activeId ? '使用中' : '使用';
        useBtn.disabled = disabled || p.id === activeId;
        useBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const r = JSON.parse(await pywebview.api.switch_profile(p.id));
            if (r.ok) {
                await refreshConfig();
                renderProvidersList();
                updateModelDisplay();
                if (typeof showToast === 'function') showToast(r.msg);
            } else alert(r.msg);
        });
        item.appendChild(useBtn);
        list.appendChild(item);
    }
}

function openProviderDetail(profileId) {
    if (profileId) {
        const src = getProviderById(profileId);
        if (!src) return;
        editingProviderId = profileId;
        providerDraft = JSON.parse(JSON.stringify(ensureProfileShape(src)));
    } else {
        editingProviderId = null;
        providerDraft = defaultProvider();
    }
    fillProviderDetailForm(providerDraft);
    switchProviderTab('config');
    pushSettingsView('provider-detail');
}

function switchProviderTab(tab) {
    document.querySelectorAll('.provider-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.providerTab === tab);
    });
    document.getElementById('provider-tab-config')?.classList.toggle('hidden', tab !== 'config');
    document.getElementById('provider-tab-models')?.classList.toggle('hidden', tab !== 'models');
    if (tab === 'models') renderProviderModelsList();
}

function fillProviderDetailForm(p) {
    document.getElementById('pv-name').value = p.name || '';
    document.getElementById('pv-base-url').value = p.base_url || '';
    document.getElementById('pv-api-key').value = p.api_key || '';
    document.getElementById('pv-provider').value = p.provider || 'generic';
    document.getElementById('pv-enabled').checked = p.enabled !== false;
    document.getElementById('pv-balance-enabled').checked = !!p.balance?.enabled;
    document.getElementById('pv-balance-path').value = p.balance?.path || '/user/balance';
    document.getElementById('pv-balance-json-path').value = p.balance?.json_path || 'balance_infos[0].total_balance';
    document.getElementById('pv-balance-value').textContent = p.balance?.last_value || '—';
    updateDefaultModelSelect(p);
    updateProviderOptimizationHint();
    toggleBalanceFields();
    const testEl = document.getElementById('provider-test-result');
    if (testEl) testEl.classList.add('hidden');
    const titleEl = document.getElementById('settings-title');
    if (titleEl) titleEl.textContent = p.name || '编辑供应商';
}

function updateDefaultModelSelect(p) {
    const sel = document.getElementById('pv-default-model');
    const custom = document.getElementById('pv-default-model-custom');
    if (!sel) return;
    const models = p.models || [];
    const current = p.model || '';
    const inList = models.some(m => m.name === current);
    sel.innerHTML = '';
    for (const m of models) {
        const opt = document.createElement('option');
        opt.value = m.name;
        opt.textContent = m.name;
        sel.appendChild(opt);
    }
    const customOpt = document.createElement('option');
    customOpt.value = '__custom__';
    customOpt.textContent = '自定义…';
    sel.appendChild(customOpt);
    if (inList) {
        sel.value = current;
        custom.classList.add('hidden');
        custom.value = '';
    } else if (current) {
        sel.value = '__custom__';
        custom.classList.remove('hidden');
        custom.value = current;
    } else if (models.length) {
        sel.value = models[0].name;
        custom.classList.add('hidden');
    } else {
        sel.value = '__custom__';
        custom.classList.remove('hidden');
    }
}

function onDefaultModelSelectChange() {
    const sel = document.getElementById('pv-default-model');
    const custom = document.getElementById('pv-default-model-custom');
    if (!sel || !custom) return;
    if (sel.value === '__custom__') {
        custom.classList.remove('hidden');
    } else {
        custom.classList.add('hidden');
        custom.value = sel.value;
    }
}

function readProviderDetailForm() {
    if (!providerDraft) return null;
    const sel = document.getElementById('pv-default-model');
    const custom = document.getElementById('pv-default-model-custom');
    let model = '';
    if (sel?.value === '__custom__') {
        model = custom?.value.trim() || '';
    } else {
        model = sel?.value || '';
    }
    providerDraft.name = document.getElementById('pv-name').value.trim() || '未命名';
    providerDraft.base_url = document.getElementById('pv-base-url').value.trim();
    providerDraft.api_key = document.getElementById('pv-api-key').value.trim();
    providerDraft.model = model;
    providerDraft.provider = document.getElementById('pv-provider').value || 'generic';
    providerDraft.enabled = document.getElementById('pv-enabled').checked;
    providerDraft.balance = {
        enabled: document.getElementById('pv-balance-enabled').checked,
        path: document.getElementById('pv-balance-path').value.trim() || '/user/balance',
        json_path: document.getElementById('pv-balance-json-path').value.trim() || 'balance_infos[0].total_balance',
        last_value: providerDraft.balance?.last_value || '',
    };
    return providerDraft;
}

async function saveProviderDetail() {
    const draft = readProviderDetailForm();
    if (!draft) return;
    if (!draft.base_url || !draft.api_key) {
        alert('Base URL 和 API Key 为必填项');
        return;
    }
    if (!draft.model) {
        alert('请设置默认模型（在模型 Tab 添加或自定义）');
        return;
    }
    await persistProviderDraft(draft);
    providerDraft = JSON.parse(JSON.stringify(draft));
    if (typeof showToast === 'function') showToast('供应商已保存');
    renderProvidersList();
    updateModelDisplay();
}

async function deleteCurrentProvider() {
    const profiles = cachedConfig?.api_profiles || [];
    if (profiles.length <= 1) {
        alert('至少保留一个供应商');
        return;
    }
    if (!confirm(`删除供应商「${providerDraft?.name || ''}」？`)) return;
    const id = editingProviderId;
    cachedConfig.api_profiles = profiles.filter(p => p.id !== id);
    const bot = getActiveBot(cachedConfig);
    if (bot.profile_id === id) {
        const bots = cachedConfig.bots || [];
        const activeBot = bots.find(b => b.id === cachedConfig.active_bot_id);
        if (activeBot) activeBot.profile_id = cachedConfig.api_profiles[0].id;
    }
    await pywebview.api.save_config(JSON.stringify(cachedConfig));
    providerDraft = null;
    editingProviderId = null;
    popSettingsView();
    renderProvidersList();
}

async function persistProviderDraft(draft) {
    if (!cachedConfig.api_profiles) cachedConfig.api_profiles = [];
    if (editingProviderId) {
        const idx = cachedConfig.api_profiles.findIndex(p => p.id === editingProviderId);
        if (idx >= 0) cachedConfig.api_profiles[idx] = draft;
    } else {
        cachedConfig.api_profiles.push(draft);
        editingProviderId = draft.id;
    }
    const result = JSON.parse(await pywebview.api.save_config(JSON.stringify(cachedConfig)));
    if (!result.ok) throw new Error(result.msg || '保存失败');
}

async function testCurrentProvider() {
    const draft = readProviderDetailForm();
    if (!draft?.base_url || !draft?.api_key || !draft?.model) {
        alert('请先填写 URL、Key 和默认模型');
        return;
    }
    const btn = document.getElementById('btn-test-provider');
    const resultEl = document.getElementById('provider-test-result');
    if (btn) { btn.disabled = true; btn.textContent = '测试中…'; }
    if (resultEl) resultEl.classList.add('hidden');
    await persistProviderDraft(draft);
    const bot = getActiveBot(cachedConfig);
    if (bot.profile_id !== draft.id) {
        await pywebview.api.switch_profile(draft.id);
        await refreshConfig();
    }
    const result = JSON.parse(await pywebview.api.test_connection());
    if (resultEl) {
        resultEl.textContent = result.msg;
        resultEl.className = 'test-result ' + (result.ok ? 'success' : 'error');
        resultEl.classList.remove('hidden');
    }
    if (btn) { btn.disabled = false; btn.textContent = '测试连接'; }
}

async function queryProviderBalance() {
    const draft = readProviderDetailForm();
    if (!draft) return;
    if (!draft.balance?.enabled) {
        alert('请先开启「获取账户余额」');
        return;
    }
    await persistProviderDraft(draft);
    const btn = document.getElementById('btn-query-balance');
    if (btn) { btn.disabled = true; btn.textContent = '查询中…'; }
    const result = JSON.parse(await pywebview.api.fetch_profile_balance(draft.id));
    const valEl = document.getElementById('pv-balance-value');
    if (result.ok) {
        if (valEl) valEl.textContent = result.value;
        if (providerDraft?.balance) providerDraft.balance.last_value = result.value;
        if (typeof showToast === 'function') showToast('余额：' + result.value);
    } else {
        alert(result.msg || '查询失败');
    }
    if (btn) { btn.disabled = false; btn.textContent = '查询余额'; }
    await refreshConfig();
}

function updateProviderOptimizationHint() {
    const provider = document.getElementById('pv-provider')?.value;
    const hint = document.getElementById('pv-provider-hint');
    if (!hint) return;
    if (provider === 'deepseek') {
        hint.textContent = '已启用：深度思考 / 联网搜索 / 流式推理';
        hint.classList.remove('hidden');
    } else if (provider === 'anthropic') {
        hint.textContent = '已启用：Anthropic Messages API 格式（x-api-key 认证）';
        hint.classList.remove('hidden');
    } else {
        hint.classList.add('hidden');
    }
}

function toggleBalanceFields() {
    const on = document.getElementById('pv-balance-enabled')?.checked;
    document.getElementById('pv-balance-fields')?.classList.toggle('hidden', !on);
}

function renderProviderModelsList() {
    const list = document.getElementById('provider-models-list');
    if (!list || !providerDraft) return;
    list.innerHTML = '';
    const models = providerDraft.models || [];
    if (!models.length) {
        list.innerHTML = '<p class="form-hint">暂无模型，点击下方添加</p>';
        return;
    }
    for (const m of models) {
        const row = document.createElement('div');
        row.className = 'provider-model-item';
        const caps = (m.capabilities || []).map(c => {
            if (c === 'tools') return '🔧';
            if (c === 'reasoning') return '🧠';
            return c;
        }).join(' ');
        const inp = (m.input || ['text']).map(x => x === 'image' ? '🖼' : 'T').join('');
        const out = (m.output || ['text']).map(x => x === 'image' ? '🖼' : 'T').join('');
        row.innerHTML = `
            <div class="provider-model-info">
                <div class="provider-model-name">${escapeHtml(m.name || '未命名')}</div>
                <div class="provider-model-tags"><span>${inp}→${out}</span> ${caps}</div>
            </div>
            <div class="provider-model-actions">
                <button type="button" class="profile-action-btn edit" title="编辑">✎</button>
                <button type="button" class="profile-action-btn delete" title="删除">✕</button>
            </div>
        `;
        row.querySelector('.edit').addEventListener('click', () => showModelEditModal(m.id));
        row.querySelector('.delete').addEventListener('click', () => {
            if (!confirm(`删除模型「${m.name}」？`)) return;
            providerDraft.models = models.filter(x => x.id !== m.id);
            if (providerDraft.model === m.name) {
                providerDraft.model = providerDraft.models[0]?.name || '';
            }
            renderProviderModelsList();
            updateDefaultModelSelect(providerDraft);
        });
        list.appendChild(row);
    }
}

function showModelEditModal(modelId) {
    editingModelId = modelId;
    const modal = document.getElementById('model-edit-modal');
    const title = document.getElementById('model-edit-title');
    let m = null;
    if (modelId && providerDraft) {
        m = (providerDraft.models || []).find(x => x.id === modelId);
    }
    title.textContent = m ? '编辑模型' : '添加模型';
    document.getElementById('me-name').value = m?.name || '';
    setCapGroup('input', m?.input || ['text'], false);
    setCapGroup('output', m?.output || ['text'], false);
    setCapGroup('capabilities', m?.capabilities || defaultModel('').capabilities, true);
    modal.classList.remove('hidden');
}

function hideModelEditModal() {
    document.getElementById('model-edit-modal')?.classList.add('hidden');
    editingModelId = null;
}

function setCapGroup(group, values, multi) {
    const el = document.querySelector(`.cap-toggle-group[data-cap-group="${group}"]`);
    if (!el) return;
    el.querySelectorAll('.cap-toggle').forEach(btn => {
        const on = values.includes(btn.dataset.value);
        btn.classList.toggle('active', multi ? on : (on && values[0] === btn.dataset.value));
    });
    if (!multi) {
        const active = el.querySelector('.cap-toggle.active');
        if (!active) el.querySelector('.cap-toggle')?.classList.add('active');
    }
}

function readCapGroup(group, multi) {
    const el = document.querySelector(`.cap-toggle-group[data-cap-group="${group}"]`);
    if (!el) return multi ? [] : 'text';
    if (multi) {
        return [...el.querySelectorAll('.cap-toggle.active')].map(b => b.dataset.value);
    }
    const active = el.querySelector('.cap-toggle.active');
    return active?.dataset.value || 'text';
}

function saveModelEdit() {
    if (!providerDraft) return;
    const name = document.getElementById('me-name').value.trim();
    if (!name) {
        alert('请填写模型名称');
        return;
    }
    const input = [readCapGroup('input', false)];
    const output = [readCapGroup('output', false)];
    const capabilities = readCapGroup('capabilities', true);
    if (!providerDraft.models) providerDraft.models = [];
    if (editingModelId) {
        const m = providerDraft.models.find(x => x.id === editingModelId);
        if (m) {
            m.name = name;
            m.input = input;
            m.output = output;
            m.capabilities = capabilities;
        }
    } else {
        providerDraft.models.push({ id: newModelId(), name, input, output, capabilities });
    }
    if (!providerDraft.model) providerDraft.model = name;
    hideModelEditModal();
    renderProviderModelsList();
    updateDefaultModelSelect(providerDraft);
}
