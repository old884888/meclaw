// ===== 群聊：侧边栏导航 + 建群弹窗 + @ 成员选择 =====

let mainSidebarTab = 'private'; // 'private' | 'group'
let selectedGroupId = null;
let allGroupsCache = [];
let currentGroupSession = null; // { group_id, member_bot_ids, group_name }
let pendingMentions = []; // [{ id, name, avatar }]
let groupReplySpeaker = null;
let groupReplyQueue = [];
let groupChainState = { remaining_budget: null, budget_max: null, spoken_bot_ids: [] };
let groupReplyHalted = false;
let groupEmptyRetried = false;
const USER_MENTION_ID = '__user__';

async function loadGroups() {
    const resultStr = await pywebview.api.get_groups();
    const result = JSON.parse(resultStr);
    if (!result.ok) return;
    allGroupsCache = result.groups || [];
    if (mainSidebarTab === 'group') {
        renderGroupSidebarNav();
    }
}

function setMainSidebarTab(tab, options = {}) {
    mainSidebarTab = tab;
    const chatTab = document.getElementById('sidebar-tab-chat');
    const groupTab = document.getElementById('sidebar-tab-group');
    const statusTab = document.getElementById('sidebar-tab-status');
    if (chatTab) chatTab.classList.toggle('active', tab === 'private');
    if (groupTab) groupTab.classList.toggle('active', tab === 'group');
    if (statusTab) statusTab.classList.toggle('active', tab === 'status');

    const chatPanel = document.getElementById('chat-panel');
    const groupPanel = document.getElementById('group-panel');
    const statusPanel = document.getElementById('status-panel');
    if (chatPanel) chatPanel.classList.toggle('hidden', tab !== 'private');
    if (groupPanel) groupPanel.classList.toggle('hidden', tab !== 'group');
    if (statusPanel) statusPanel.classList.toggle('hidden', tab !== 'status');

    if (tab === 'private') {
        if (!options.preserveNav && typeof sidebarView !== 'undefined') {
            if (sidebarView === 'groups' || sidebarView === 'group-sessions') {
                sidebarView = 'bots';
            }
        }
        if (typeof loadSessions === 'function') loadSessions();
    } else if (tab === 'group') {
        if (!options.preserveNav) {
            sidebarView = 'groups';
            selectedGroupId = null;
        }
        loadGroups();
    } else if (tab === 'status') {
        if (typeof refreshStatusPanel === 'function') refreshStatusPanel();
    }
    updateGroupComposerUI();
    if (typeof updateBotSelectorLockState === 'function') updateBotSelectorLockState();
}

function renderGroupSidebarNav() {
    const list = document.getElementById('group-session-list');
    if (!list) return;
    const searchInput = document.getElementById('group-session-search');
    if (searchInput && searchInput.value.trim()) return;

    list.innerHTML = '';
    if (sidebarView === 'groups') {
        renderGroupList(list);
    } else if (sidebarView === 'group-sessions') {
        const sessions = (typeof allSessionsCache !== 'undefined' ? allSessionsCache : [])
            .filter(s => s.group_id === selectedGroupId);
        renderGroupSessionList(list, sessions);
    }
    updateGroupNavToolbar();
}

function renderGroupList(container) {
    if (!allGroupsCache.length) {
        const empty = document.createElement('div');
        empty.className = 'session-empty-state';
        empty.innerHTML = `
            <p>还没有群聊</p>
            <button type="button" class="btn-new-session session-empty-cta" id="btn-empty-create-group">创建第一个群</button>`;
        empty.querySelector('#btn-empty-create-group').addEventListener('click', showCreateGroupModal);
        container.appendChild(empty);
        return;
    }
    const sorted = [...allGroupsCache].sort((a, b) => (b.updated_at > a.updated_at ? 1 : -1));
    for (const g of sorted) {
        const item = document.createElement('div');
        item.className = 'bot-list-item group-list-item';
        item.innerHTML = `
            <span class="bot-list-row-avatar">${g.avatar || '👥'}</span>
            <div class="bot-list-row-info">
                <div class="bot-list-row-name">${escapeHtml(g.name || '未命名群')}</div>
                <div class="bot-list-row-meta">${g.member_count || (g.member_bot_ids || []).length} 位成员</div>
            </div>
            <div class="group-item-actions">
                <button type="button" class="group-item-action-btn" data-action="rename" title="重命名">✎</button>
                <button type="button" class="group-item-action-btn danger" data-action="delete" title="删除">✕</button>
            </div>`;
        item.querySelector('[data-action="rename"]').addEventListener('click', (e) => {
            e.stopPropagation();
            showRenameGroupModal(g);
        });
        item.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
            e.stopPropagation();
            confirmDeleteGroup(g);
        });
        item.addEventListener('click', () => enterGroupSessions(g.id));
        container.appendChild(item);
    }
}

function showRenameGroupModal(group) {
    const modal = document.getElementById('group-rename-modal');
    const input = document.getElementById('group-rename-input');
    if (!modal || !input) return;
    input.value = group.name || '';
    input.dataset.groupId = group.id;
    modal.classList.remove('hidden');
    input.focus();
    input.select();
}

function hideRenameGroupModal() {
    document.getElementById('group-rename-modal')?.classList.add('hidden');
}

async function confirmRenameGroup() {
    const input = document.getElementById('group-rename-input');
    if (!input) return;
    const groupId = input.dataset.groupId;
    const newName = input.value.trim();
    if (!newName) {
        if (typeof showToast === 'function') showToast('名称不能为空');
        return;
    }
    const resultStr = await pywebview.api.update_group(groupId, newName, null, null, null);
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (typeof showToast === 'function') showToast(result.msg || '重命名失败');
        return;
    }
    hideRenameGroupModal();
    await loadGroups();
    // 如果当前正在该群对话中，更新头部显示
    if (currentGroupSession && currentGroupSession.group_id === groupId) {
        currentGroupSession.group_name = newName;
        updateGroupHeaderDisplay();
    }
    if (typeof showToast === 'function') showToast('已重命名');
}

async function confirmDeleteGroup(group) {
    const msg = `确定要删除群聊「${group.name || '未命名群'}」吗？\n该群的所有对话记录也将被删除。`;
    if (!confirm(msg)) return;
    const resultStr = await pywebview.api.delete_group(group.id);
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (typeof showToast === 'function') showToast(result.msg || '删除失败');
        return;
    }
    // 如果正在该群对话中，清除群状态
    if (currentGroupSession && currentGroupSession.group_id === group.id) {
        currentGroupSession = null;
        clearPendingMentions();
        resetGroupChainState();
        resetGroupReplyHalt();
        groupReplyQueue = [];
        document.getElementById('btn-group-settings')?.classList.add('hidden');
        if (typeof updateBotDisplay === 'function') updateBotDisplay();
        updateGroupComposerUI();
    }
    await loadGroups();
    if (typeof showToast === 'function') showToast('已删除群聊');
}

async function enterGroupSessions(groupId) {
    selectedGroupId = groupId;
    sidebarView = 'group-sessions';
    const resultStr = await pywebview.api.get_group_sessions(groupId);
    const result = JSON.parse(resultStr);
    if (result.ok && typeof allSessionsCache !== 'undefined') {
        const others = allSessionsCache.filter(s => s.group_id !== groupId);
        allSessionsCache = [...result.sessions, ...others];
    }
    renderGroupSidebarNav();
}

function backToGroupList() {
    if (typeof isMultiSelectMode !== 'undefined' && isMultiSelectMode) return;
    sidebarView = 'groups';
    selectedGroupId = null;
    renderGroupSidebarNav();
}

function updateGroupNavToolbar() {
    const toolbar = document.getElementById('group-session-toolbar');
    const backBtn = document.getElementById('btn-group-back');
    const newBtn = document.getElementById('btn-new-group-session');
    const createBtn = document.getElementById('btn-create-group');
    const inDrill = sidebarView === 'group-sessions';
    if (backBtn) backBtn.classList.toggle('hidden', !inDrill);
    if (newBtn) newBtn.classList.toggle('hidden', !inDrill);
    if (createBtn) createBtn.classList.toggle('hidden', inDrill);
    if (toolbar) toolbar.classList.toggle('hidden', false);
}

function renderGroupSessionList(container, sessions) {
    const group = allGroupsCache.find(g => g.id === selectedGroupId);
    if (!sessions.length) {
        const empty = document.createElement('div');
        empty.className = 'session-empty-state';
        const gname = group ? escapeHtml(group.name) : '该群';
        empty.innerHTML = `
            <p>${gname} 还没有对话</p>
            <button type="button" class="btn-new-session session-empty-cta">开始第一个群对话</button>`;
        empty.querySelector('.session-empty-cta').addEventListener('click', () => newGroupSession());
        container.appendChild(empty);
        return;
    }
    const sorted = [...sessions].sort((a, b) => (b.updated_at > a.updated_at ? 1 : -1));
    for (const s of sorted) {
        container.appendChild(createGroupSessionItem(s, group));
    }
}

function createGroupSessionItem(s, group) {
    const item = document.createElement('div');
    item.className = 'session-item' + (s.id === currentSessionId ? ' active' : '');
    item.dataset.id = s.id;
    const head = document.createElement('div');
    head.className = 'session-card-head';
    head.innerHTML = `
        <span class="session-bot-avatar">${group?.avatar || '👥'}</span>
        <span class="session-bot-name">${escapeHtml(group?.name || '群聊')}</span>
        <span class="session-legacy-tag">${(group?.member_count || 0)} 人</span>`;
    item.appendChild(head);
    const title = document.createElement('div');
    title.className = 'session-title';
    title.textContent = s.title || '新群对话';
    item.appendChild(title);
    const meta = document.createElement('div');
    meta.className = 'session-meta';
    meta.innerHTML = `<span>${formatTime(s.updated_at)}</span><span>${s.message_count}条</span>`;
    const delBtn = document.createElement('button');
    delBtn.className = 'session-delete';
    delBtn.textContent = '✕';
    delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteSession(s.id);
    });
    meta.appendChild(delBtn);
    item.appendChild(meta);
    item.addEventListener('click', () => switchSession(s.id));
    return item;
}

async function newGroupSession() {
    if (!selectedGroupId) return;
    const resultStr = await pywebview.api.new_group_session(selectedGroupId);
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (typeof showToast === 'function') showToast(result.msg || '创建失败');
        return;
    }
    currentSessionId = result.session.id;
    conversationHistory = [];
    chatMessages.innerHTML = '';
    currentGroupSession = {
        group_id: selectedGroupId,
        member_bot_ids: result.session.member_bot_ids || [],
        group_name: allGroupsCache.find(g => g.id === selectedGroupId)?.name || '',
    };
    currentMode = 'chat';
    await loadSessions();
    await loadGroups();
    updateGroupComposerUI();
    updateGroupHeaderDisplay();
    await initGroupChainBudgetFromMeta();
    if (typeof refreshContextUsage === 'function') refreshContextUsage();
}

function applyGroupSessionContext(result) {
    if (result.is_group) {
        currentGroupSession = {
            group_id: result.group_id,
            member_bot_ids: result.member_bot_ids || [],
            group_name: result.group_name || '',
        };
    } else {
        currentGroupSession = null;
        clearPendingMentions();
        resetGroupChainState();
        resetGroupReplyHalt();
        groupReplyQueue = [];
        document.getElementById('btn-group-settings')?.classList.add('hidden');
        if (typeof updateBotDisplay === 'function') updateBotDisplay();
    }
    updateGroupComposerUI();
    if (currentGroupSession) {
        updateGroupHeaderDisplay();
        initGroupChainBudgetFromMeta();
    }
}

function updateGroupHeaderDisplay() {
    const nameEl = document.getElementById('current-bot-name');
    const avatarEl = document.getElementById('current-bot-avatar');
    const badgeEl = document.getElementById('current-bot-mode-badge');
    const settingsBtn = document.getElementById('btn-group-settings');
    if (!currentGroupSession) {
        if (settingsBtn) settingsBtn.classList.add('hidden');
        return;
    }
    if (nameEl) nameEl.textContent = currentGroupSession.group_name || '群聊';
    if (avatarEl) {
        const g = allGroupsCache.find(x => x.id === currentGroupSession.group_id);
        avatarEl.textContent = g?.avatar || '👥';
    }
    if (badgeEl) {
        const count = (currentGroupSession.member_bot_ids || []).length;
        badgeEl.textContent = count ? `群聊 · ${count}人` : '群聊';
        badgeEl.className = 'bot-mode-badge';
        badgeEl.classList.remove('hidden');
    }
    if (settingsBtn) settingsBtn.classList.remove('hidden');
}

function resetGroupChainState() {
    groupChainState = { remaining_budget: null, budget_max: null, spoken_bot_ids: [] };
}

async function initGroupChainBudgetFromMeta() {
    const gid = currentGroupSession?.group_id;
    if (!gid) {
        resetGroupChainState();
        updateGroupChainUI();
        return;
    }
    try {
        const resultStr = await pywebview.api.get_group_meta(gid);
        const result = JSON.parse(resultStr);
        const max = result.ok ? (result.group?.max_chain_rounds ?? 5) : 5;
        groupChainState = {
            remaining_budget: max,
            budget_max: max,
            spoken_bot_ids: [],
        };
    } catch (e) {
        groupChainState = { remaining_budget: 5, budget_max: 5, spoken_bot_ids: [] };
    }
    hideGroupChainExhaustedNotice();
    updateGroupChainUI();
}

function refreshGroupChainBudget() {
    const max = groupChainState.budget_max;
    if (max == null) return;
    groupChainState.remaining_budget = max;
    hideGroupChainExhaustedNotice();
    updateGroupChainUI();
    if (typeof showToast === 'function') showToast(`接话链已刷新（${max}）`);
}

function updateGroupChainUI() {
    const bar = document.getElementById('group-chain-bar');
    const indicator = document.getElementById('group-chain-indicator');
    const isGroup = !!currentGroupSession;
    const members = isGroup ? getGroupMemberBots().length : 0;
    if (bar) bar.classList.toggle('hidden', !isGroup || members < 2);
    if (!indicator || !isGroup) return;
    const rem = groupChainState.remaining_budget;
    const max = groupChainState.budget_max;
    if (rem == null || max == null) {
        indicator.textContent = '接话链：—';
    } else {
        indicator.textContent = `接话链：${rem} / ${max}`;
    }
}

function showGroupChainExhaustedNotice() {
    const el = document.getElementById('group-chain-exhausted');
    if (el) el.classList.remove('hidden');
}

function hideGroupChainExhaustedNotice() {
    const el = document.getElementById('group-chain-exhausted');
    if (el) el.classList.add('hidden');
}

function resetGroupReplyHalt() {
    groupReplyHalted = false;
}

function resetGroupEmptyRetry() {
    groupEmptyRetried = false;
}

function buildGroupApiMessages() {
    if (typeof conversationHistory === 'undefined') return [];
    return conversationHistory.map(m => {
        const copy = Object.assign({}, m);
        if (copy._attachments_full) {
            copy.attachments = copy._attachments_full;
        }
        delete copy._attachments_full;
        return copy;
    });
}

function retryGroupBotReply() {
    const botId = groupReplySpeaker?.id;
    if (!botId) return false;
    setGenerating(true);
    currentThinkingEl = null;
    isThinking = false;
    addMessage('ai', '', true);
    const apiMessages = buildGroupApiMessages();
    pywebview.api.retry_group_bot_reply(JSON.stringify(apiMessages), botId);
    return true;
}

function isGroupReplyHalted() {
    return !!groupReplyHalted;
}

/** 急停：中断当前流式输出，清空接话队列，不再触发后续 Bot 回复 */
function emergencyStopGroup() {
    groupReplyHalted = true;
    groupReplyQueue = [];
    resetGroupChainState();
    hideGroupChainExhaustedNotice();
    updateGroupChainUI();
    groupReplySpeaker = null;
    pywebview.api.stop_generation();
    const msg = document.getElementById('streaming-msg');
    if (msg) {
        const cursor = msg.querySelector('.cursor');
        if (cursor) cursor.remove();
        const contentDiv = msg.querySelector('.message-content');
        if (contentDiv) {
            contentDiv.classList.remove('collapsible');
            msg.querySelector('.expand-btn')?.remove();
        }
        currentThinkingEl = null;
        isThinking = false;
        if (typeof clearWebSearchStatus === 'function') clearWebSearchStatus();
    }
    if (typeof setGenerating === 'function') setGenerating(false);
    if (typeof showToast === 'function') showToast('已急停，后续 Bot 接话已取消');
}

function updateGroupChainStateFromPostprocess(pp) {
    if (!pp) return;
    groupChainState = {
        remaining_budget: pp.remaining_budget ?? groupChainState.remaining_budget,
        budget_max: pp.budget_max ?? groupChainState.budget_max,
        spoken_bot_ids: pp.spoken_bot_ids || [],
    };
    updateGroupChainUI();
    if (pp.chain_exhausted) {
        showGroupChainExhaustedNotice();
    }
}

function updateGroupComposerUI() {
    const btnMention = document.getElementById('btn-composer-mention');
    const btnExpert = document.getElementById('btn-expert-mode');
    const isGroup = !!currentGroupSession;
    if (btnMention) btnMention.classList.toggle('hidden', !isGroup);
    if (btnExpert) btnExpert.classList.toggle('hidden', isGroup);
    if (!isGroup) {
        hideMentionPicker();
        clearPendingMentions();
        document.getElementById('group-chain-bar')?.classList.add('hidden');
        hideGroupChainExhaustedNotice();
    } else {
        renderMentionChips();
        updateGroupChainUI();
    }
    if (typeof refreshComposerToolbar === 'function') {
        refreshComposerToolbar();
    }
}

function getActiveGroupId() {
    return currentGroupSession?.group_id || selectedGroupId || null;
}

function getGroupMemberBotsForGroup(groupId) {
    if (!groupId || !cachedConfig) return [];
    const g = allGroupsCache.find(x => x.id === groupId);
    const ids = currentGroupSession?.group_id === groupId
        ? (currentGroupSession.member_bot_ids || g?.member_bot_ids || [])
        : (g?.member_bot_ids || []);
    return (cachedConfig.bots || []).filter(b => ids.includes(b.id));
}

function getGroupMemberBots() {
    const gid = getActiveGroupId();
    return gid ? getGroupMemberBotsForGroup(gid) : [];
}

function showMentionPicker() {
    const picker = document.getElementById('mention-picker');
    const list = document.getElementById('mention-picker-list');
    if (!picker || !list) return;
    const members = getGroupMemberBots();
    const selectedIds = new Set(pendingMentions.map(m => m.id));
    list.innerHTML = '';
    const userBtn = document.createElement('button');
    userBtn.type = 'button';
    userBtn.className = 'mention-picker-item mention-picker-user'
        + (selectedIds.has(USER_MENTION_ID) ? ' selected' : '');
    userBtn.innerHTML = `
        <span class="mention-picker-check">${selectedIds.has(USER_MENTION_ID) ? '✓' : ''}</span>
        <span>👤</span>
        <span>@用户</span>`;
    userBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleUserMention();
    });
    list.appendChild(userBtn);
    for (const bot of members) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mention-picker-item' + (selectedIds.has(bot.id) ? ' selected' : '');
        btn.innerHTML = `
            <span class="mention-picker-check">${selectedIds.has(bot.id) ? '✓' : ''}</span>
            <span>${bot.avatar || '🤖'}</span>
            <span>${escapeHtml(bot.name)}</span>`;
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMention(bot);
        });
        list.appendChild(btn);
    }
    picker.classList.remove('hidden');
}

function hideMentionPicker() {
    const picker = document.getElementById('mention-picker');
    if (picker) picker.classList.add('hidden');
}

function toggleUserMention() {
    const idx = pendingMentions.findIndex(m => m.id === USER_MENTION_ID);
    if (idx >= 0) {
        pendingMentions.splice(idx, 1);
    } else {
        pendingMentions.push({
            id: USER_MENTION_ID,
            name: '用户',
            avatar: '👤',
            type: 'user',
        });
    }
    renderMentionChips();
    showMentionPicker();
}

function toggleMention(bot) {
    const idx = pendingMentions.findIndex(m => m.id === bot.id);
    if (idx >= 0) {
        pendingMentions.splice(idx, 1);
    } else {
        pendingMentions.push({
            id: bot.id,
            name: bot.name || '',
            avatar: bot.avatar || '🤖',
            type: 'bot',
        });
    }
    renderMentionChips();
    showMentionPicker();
}

function removeMention(botId) {
    pendingMentions = pendingMentions.filter(m => m.id !== botId);
    renderMentionChips();
}

function renderMentionChips() {
    const container = document.getElementById('mention-chips');
    if (!container) return;
    container.innerHTML = '';
    for (const m of pendingMentions) {
        const chip = document.createElement('span');
        chip.className = 'mention-chip' + (m.type === 'user' || m.id === USER_MENTION_ID ? ' mention-chip-user' : '');
        chip.innerHTML = `@${escapeHtml(m.name)}<button type="button" class="mention-chip-remove" data-id="${escapeHtml(m.id)}" aria-label="移除">×</button>`;
        chip.querySelector('.mention-chip-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            removeMention(m.id);
        });
        container.appendChild(chip);
    }
}

function clearPendingMentions() {
    pendingMentions = [];
    renderMentionChips();
    hideMentionPicker();
}

function getPendingMentionIds() {
    return pendingMentions.filter(m => m.id !== USER_MENTION_ID).map(m => m.id);
}

function hasPendingUserMention() {
    return pendingMentions.some(m => m.id === USER_MENTION_ID);
}

function buildMentionPrefix() {
    if (!pendingMentions.length) return '';
    return pendingMentions.map(m => `@${m.name}`).join(' ');
}

function startNextGroupReply(apiMessages) {
    if (groupReplyHalted || !groupReplyQueue.length) {
        groupReplyQueue = [];
        return;
    }
    resetGroupEmptyRetry();
    const botId = groupReplyQueue.shift();
    if (cachedConfig && typeof groupReplySpeaker !== 'undefined') {
        groupReplySpeaker = (cachedConfig.bots || []).find(b => b.id === botId) || null;
    }
    setGenerating(true);
    currentThinkingEl = null;
    isThinking = false;
    addMessage('ai', '', true);
    pywebview.api.send_group_bot_reply(JSON.stringify(apiMessages), botId);
}

function showCreateGroupModal() {
    const modal = document.getElementById('group-modal');
    const list = document.getElementById('group-member-select');
    if (!modal || !list) return;
    document.getElementById('group-name-input').value = '';
    list.innerHTML = '';
    for (const bot of (cachedConfig?.bots || [])) {
        const label = document.createElement('label');
        label.className = 'group-member-option';
        label.innerHTML = `
            <input type="checkbox" value="${escapeHtml(bot.id)}">
            <span>${bot.avatar || '🤖'} ${escapeHtml(bot.name)}</span>`;
        list.appendChild(label);
    }
    modal.classList.remove('hidden');
}

function hideCreateGroupModal() {
    document.getElementById('group-modal')?.classList.add('hidden');
}

function updateGroupRangeFill(slider) {
    if (!slider) return;
    const min = parseFloat(slider.min || '0');
    const max = parseFloat(slider.max || '100');
    const val = parseFloat(slider.value || '0');
    const pct = max > min ? ((val - min) / (max - min)) * 100 : 0;
    slider.style.setProperty('--range-pct', `${pct}%`);
}

async function showGroupSettingsModal() {
    const groupId = getActiveGroupId();
    if (!groupId) {
        if (typeof showToast === 'function') showToast('请先选择或进入一个群聊');
        return;
    }
    const modal = document.getElementById('group-settings-modal');
    const container = document.getElementById('group-member-settings');
    if (!modal || !container) return;
    const resultStr = await pywebview.api.get_group_meta(groupId);
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (typeof showToast === 'function') showToast(result.msg || '加载失败');
        return;
    }
    const meta = result.group || {};
    document.getElementById('group-chain-fast-mode').checked = !!meta.chain_fast_mode;
    document.getElementById('group-auto-compress-enabled').checked = !!meta.auto_compress_enabled;

    const roundVal = meta.max_chain_rounds ?? 5;
    document.getElementById('group-max-chain-rounds').value = roundVal;
    document.getElementById('group-max-chain-rounds-val').textContent = roundVal;
    updateGroupRangeFill(document.getElementById('group-max-chain-rounds'));

    const histVal = meta.chain_history_limit ?? 40;
    document.getElementById('group-chain-history-limit').value = histVal;
    document.getElementById('group-chain-history-limit-val').textContent = histVal;
    updateGroupRangeFill(document.getElementById('group-chain-history-limit'));

    const thrVal = meta.auto_compress_threshold ?? 85;
    document.getElementById('group-auto-compress-threshold').value = thrVal;
    document.getElementById('group-auto-compress-threshold-val').textContent = thrVal + '%';
    updateGroupRangeFill(document.getElementById('group-auto-compress-threshold'));

    // Member settings
    container.innerHTML = '';
    const members = getGroupMemberBotsForGroup(groupId);
    const settings = meta.member_settings || {};
    for (const bot of members) {
        const s = settings[bot.id] || {};
        const row = document.createElement('div');
        row.className = 'group-member-setting-row';
        row.dataset.botId = bot.id;
        const proactivity = s.proactivity_pct ?? s.auto_mention_pct ?? 50;
        row.innerHTML = `
            <div class="group-member-setting-header">
                <span class="group-member-setting-name">${bot.avatar || '🤖'} ${escapeHtml(bot.name)}</span>
            </div>
            <div class="group-member-setting-slider">
                <span>主动值</span>
                <input type="range" class="group-slider-proactivity" min="0" max="100" value="${proactivity}">
                <span class="group-slider-val">${proactivity}%</span>
            </div>`;
        row.querySelectorAll('input[type="range"]').forEach(sl => {
            updateGroupRangeFill(sl);
            sl.addEventListener('input', () => {
                const valSpan = sl.parentElement.querySelector('.group-slider-val');
                if (valSpan) {
                    valSpan.textContent = sl.classList.contains('group-slider-proactivity')
                        ? `${sl.value}%` : sl.value;
                }
                updateGroupRangeFill(sl);
            });
        });
        container.appendChild(row);
    }

    modal.classList.remove('hidden');
}

function hideGroupSettingsModal() {
    document.getElementById('group-settings-modal')?.classList.add('hidden');
}

async function saveGroupSettings() {
    const groupId = getActiveGroupId();
    if (!groupId) return;
    const memberSettings = {};
    document.querySelectorAll('#group-member-settings .group-member-setting-row').forEach(row => {
        const bid = row.dataset.botId;
        memberSettings[bid] = {
            proactivity_pct: parseInt(row.querySelector('.group-slider-proactivity')?.value || '50', 10),
        };
    });
    const settings = {
        max_chain_rounds: parseInt(document.getElementById('group-max-chain-rounds')?.value || '5', 10),
        chain_fast_mode: document.getElementById('group-chain-fast-mode')?.checked || false,
        chain_history_limit: parseInt(document.getElementById('group-chain-history-limit')?.value || '40', 10),
        auto_compress_enabled: document.getElementById('group-auto-compress-enabled')?.checked || false,
        auto_compress_threshold: parseInt(document.getElementById('group-auto-compress-threshold')?.value || '85', 10),
        member_settings: memberSettings,
    };
    const resultStr = await pywebview.api.update_group(
        groupId,
        null,
        null,
        null,
        JSON.stringify(settings),
    );
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (typeof showToast === 'function') showToast(result.msg || '保存失败');
        return;
    }
    hideGroupSettingsModal();
    await loadGroups();
    if (groupChainState.budget_max != null) {
        const newMax = settings.max_chain_rounds;
        groupChainState.budget_max = newMax;
        if ((groupChainState.remaining_budget ?? 0) > newMax) {
            groupChainState.remaining_budget = newMax;
        }
        updateGroupChainUI();
    }
    if (typeof showToast === 'function') showToast('群设置已保存');
}

async function confirmCreateGroup() {
    const name = document.getElementById('group-name-input')?.value?.trim() || '新群聊';
    const checked = document.querySelectorAll('#group-member-select input:checked');
    const memberIds = Array.from(checked).map(cb => cb.value);
    if (memberIds.length < 2) {
        alert('请至少选择 2 个机器人');
        return;
    }
    const resultStr = await pywebview.api.create_group(name, JSON.stringify(memberIds));
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        alert(result.msg || '创建失败');
        return;
    }
    hideCreateGroupModal();
    await loadGroups();
    if (result.group) {
        await enterGroupSessions(result.group.id);
    }
}

function initGroupUI() {
    document.getElementById('sidebar-tab-chat')?.addEventListener('click', () => setMainSidebarTab('private'));
    document.getElementById('sidebar-tab-group')?.addEventListener('click', () => setMainSidebarTab('group'));
    document.getElementById('btn-create-group')?.addEventListener('click', showCreateGroupModal);
    document.getElementById('btn-new-group-session')?.addEventListener('click', () => newGroupSession());
    document.getElementById('btn-group-back')?.addEventListener('click', backToGroupList);
    document.getElementById('group-modal-cancel')?.addEventListener('click', hideCreateGroupModal);
    document.getElementById('group-modal-save')?.addEventListener('click', confirmCreateGroup);
    document.getElementById('btn-group-settings')?.addEventListener('click', showGroupSettingsModal);
    document.getElementById('btn-group-chain-refresh')?.addEventListener('click', refreshGroupChainBudget);
    document.getElementById('group-settings-cancel')?.addEventListener('click', hideGroupSettingsModal);
    document.getElementById('group-settings-save')?.addEventListener('click', saveGroupSettings);
    // Global group settings range sliders
    ['group-max-chain-rounds', 'group-chain-history-limit', 'group-auto-compress-threshold'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                const valEl = document.getElementById(id + '-val');
                if (valEl) valEl.textContent = el.value + (id === 'group-auto-compress-threshold' ? '%' : '');
                updateGroupRangeFill(el);
            });
        }
    });

    document.getElementById('group-rename-cancel')?.addEventListener('click', hideRenameGroupModal);
    document.getElementById('group-rename-confirm')?.addEventListener('click', confirmRenameGroup);
    document.getElementById('group-rename-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); confirmRenameGroup(); }
    });

    document.getElementById('btn-composer-mention')?.addEventListener('click', (e) => {
        e.stopPropagation();
        const picker = document.getElementById('mention-picker');
        if (picker && !picker.classList.contains('hidden')) hideMentionPicker();
        else showMentionPicker();
    });

    const msgInput = document.getElementById('msg-input');
    if (msgInput) {
        msgInput.addEventListener('input', () => {
            if (!currentGroupSession) return;
            if (msgInput.value.endsWith('@')) {
                showMentionPicker();
            }
        });
    }
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#mention-picker')
            && !e.target.closest('#btn-composer-mention')) {
            hideMentionPicker();
        }
    });
}

function onGroupUserOnly() {
    if (typeof setGenerating === 'function') setGenerating(false);
    const streaming = document.getElementById('streaming');
    if (streaming) streaming.remove();
    if (typeof loadSessions === 'function') loadSessions();
    if (typeof loadGroups === 'function') loadGroups();
    clearPendingMentions();
    if (typeof showToast === 'function') showToast('已发送（未 @ 成员，无回复）');
}
