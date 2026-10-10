// ===== 侧边栏 + 会话管理 + 文件树 =====

let isMultiSelectMode = false;
let selectedSessionIds = new Set();
let sidebarView = 'bots'; // 'bots' | 'bot-sessions' | 'legacy-sessions'
let selectedBotId = null;
let allSessionsCache = [];

// ---- Bot / 会话导航辅助 ----

function getBotById(botId) {
    if (!botId || !cachedConfig) return null;
    return (cachedConfig.bots || []).find(b => b.id === botId) || null;
}

function getProfileForBot(bot) {
    if (!bot || !cachedConfig) return {};
    return (cachedConfig.api_profiles || []).find(p => p.id === bot.profile_id) || {};
}

function getSessionModeBadgeHtml(bot) {
    if (!bot || typeof getDeepSeekReplyMode !== 'function') return '';
    const profile = getProfileForBot(bot);
    const mode = getDeepSeekReplyMode(bot, profile);
    if (!mode) return '';
    return `<span class="session-mode-badge bot-mode-${mode.kind}" title="${escapeHtml(mode.title)}">${escapeHtml(mode.label)}</span>`;
}

function countLegacySessions() {
    return allSessionsCache.filter(s => !s.bot_id && !s.group_id).length;
}

function getBotLatestActivity(botId) {
    const sessions = allSessionsCache.filter(s => s.bot_id === botId && !s.group_id);
    if (!sessions.length) return '';
    return sessions.reduce((a, b) => (a.updated_at > b.updated_at ? a : b)).updated_at;
}

// 会话管理
async function loadSessions() {
    const resultStr = await pywebview.api.get_sessions();
    const result = JSON.parse(resultStr);
    if (!result.ok) return;
    allSessionsCache = result.sessions;
    renderSidebarNav();
}

function renderSidebarNav() {
    const searchInput = document.getElementById('session-search');
    if (searchInput && searchInput.value.trim()) return;

    const list = document.getElementById('session-list');
    if (!list) return;
    list.innerHTML = '';

    if (sidebarView === 'bots') {
        renderBotList(list);
    } else if (sidebarView === 'bot-sessions') {
        const sessions = allSessionsCache.filter(s => s.bot_id === selectedBotId && !s.group_id);
        renderSessionList(sessions, getBotById(selectedBotId));
    } else if (sidebarView === 'legacy-sessions') {
        const sessions = allSessionsCache.filter(s => !s.bot_id && !s.group_id);
        renderSessionList(sessions, null, { legacy: true });
    }

    updateNavToolbar();
    if (typeof updateBotSelectorLockState === 'function') updateBotSelectorLockState();
}

function renderBotList(container) {
    const bots = [...(cachedConfig?.bots || [])];
    const withActivity = [];
    const withoutActivity = [];

    for (const bot of bots) {
        const latest = getBotLatestActivity(bot.id);
        if (latest) withActivity.push({ bot, latest });
        else withoutActivity.push(bot);
    }

    withActivity.sort((a, b) => (b.latest > a.latest ? 1 : -1));
    withoutActivity.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'zh'));

    for (const { bot, latest } of withActivity) {
        container.appendChild(createBotListItem(bot, formatTime(latest)));
    }
    for (const bot of withoutActivity) {
        container.appendChild(createBotListItem(bot, '暂无对话'));
    }

    const legacyCount = countLegacySessions();
    if (legacyCount > 0) {
        const legacy = document.createElement('div');
        legacy.className = 'bot-list-item legacy-entry';
        legacy.innerHTML = `
            <span class="bot-list-row-avatar">📦</span>
            <div class="bot-list-row-info">
                <div class="bot-list-row-name">历史遗留</div>
                <div class="bot-list-row-meta">${legacyCount} 条未绑定机器人的对话</div>
            </div>`;
        legacy.addEventListener('click', () => enterLegacySessions());
        container.appendChild(legacy);
    }
}

function createBotListItem(bot, metaText) {
    const item = document.createElement('div');
    item.className = 'bot-list-item';
    const profile = getProfileForBot(bot);
    const badge = typeof getDeepSeekReplyMode === 'function' ? getDeepSeekReplyMode(bot, profile) : null;
    const badgeHtml = badge
        ? `<span class="bot-list-mode-badge bot-mode-${badge.kind}">${escapeHtml(badge.label)}</span>`
        : '';
    item.innerHTML = `
        <span class="bot-list-row-avatar">${bot.avatar || '🤖'}</span>
        <div class="bot-list-row-info">
            <div class="bot-list-row-name">${escapeHtml(bot.name || '未命名')}${badgeHtml}</div>
            <div class="bot-list-row-meta">${escapeHtml(metaText)}</div>
        </div>`;
    item.addEventListener('click', () => enterBotSessions(bot.id));
    return item;
}

async function enterBotSessions(botId) {
    selectedBotId = botId;
    sidebarView = 'bot-sessions';
    if (!currentSessionId) {
        const resultStr = await pywebview.api.switch_bot(botId);
        const result = JSON.parse(resultStr);
        if (result.ok) {
            await refreshConfig();
            updateBotDisplay();
        }
    }
    await loadSessions();
}

function enterLegacySessions() {
    selectedBotId = null;
    sidebarView = 'legacy-sessions';
    renderSidebarNav();
}

function backToBotList() {
    if (isMultiSelectMode) return;
    sidebarView = 'bots';
    selectedBotId = null;
    renderSidebarNav();
}

function updateNavToolbar() {
    const toolbar = document.getElementById('session-toolbar');
    const backBtn = document.getElementById('btn-session-back');
    const newBtn = document.getElementById('btn-new-session');
    const selectBtn = document.getElementById('btn-select-mode');
    if (!toolbar || !backBtn || !newBtn || !selectBtn) return;

    const inDrillDown = sidebarView === 'bot-sessions' || sidebarView === 'legacy-sessions';
    const showSessionActions = sidebarView === 'bot-sessions' && !isMultiSelectMode;

    backBtn.classList.toggle('hidden', !inDrillDown || isMultiSelectMode);
    newBtn.classList.toggle('hidden', !showSessionActions);
    selectBtn.classList.toggle('hidden', !showSessionActions);
    toolbar.classList.toggle('hidden', isMultiSelectMode);
}

function renderSessionList(sessions, bot, options = {}) {
    const list = document.getElementById('session-list');
    list.innerHTML = '';

    if (!sessions.length) {
        const empty = document.createElement('div');
        empty.className = 'session-empty-state';
        if (options.legacy) {
            empty.innerHTML = '<p>没有历史遗留对话</p>';
        } else if (bot) {
            empty.innerHTML = `
                <p>还没有和 ${escapeHtml(bot.name)} 的对话</p>
                <button type="button" class="btn-new-session session-empty-cta">和它开始第一个对话</button>`;
            empty.querySelector('.session-empty-cta').addEventListener('click', () => newSession(bot.id));
        }
        list.appendChild(empty);
        return;
    }

    const sorted = [...sessions].sort((a, b) => (b.updated_at > a.updated_at ? 1 : -1));
    for (const s of sorted) {
        list.appendChild(createSessionItem(s, bot, options));
    }
}

function createSessionItem(s, bot, options = {}) {
    const item = document.createElement('div');
    item.className = 'session-item' + (s.id === currentSessionId ? ' active' : '');
    item.dataset.id = s.id;

    if (isMultiSelectMode) {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'session-checkbox';
        cb.checked = selectedSessionIds.has(s.id);
        cb.addEventListener('click', (e) => {
            e.stopPropagation();
            if (cb.checked) selectedSessionIds.add(s.id);
            else selectedSessionIds.delete(s.id);
            item.classList.toggle('selected', cb.checked);
            updateSelectCount();
        });
        item.appendChild(cb);
        item.classList.toggle('selected', selectedSessionIds.has(s.id));
    }

    const sessionBot = bot || getBotById(s.bot_id);
    if (sessionBot) {
        const head = document.createElement('div');
        head.className = 'session-card-head';
        head.innerHTML = `
            <span class="session-bot-avatar">${sessionBot.avatar || '🤖'}</span>
            <span class="session-bot-name">${escapeHtml(sessionBot.name || '')}</span>
            ${getSessionModeBadgeHtml(sessionBot)}`;
        item.appendChild(head);
    } else if (options.legacy) {
        const head = document.createElement('div');
        head.className = 'session-card-head';
        head.innerHTML = '<span class="session-legacy-tag">历史遗留</span>';
        item.appendChild(head);
    }

    const title = document.createElement('div');
    title.className = 'session-title';
    title.textContent = s.title || '新对话';
    item.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'session-meta';
    const time = document.createElement('span');
    time.textContent = formatTime(s.updated_at);
    meta.appendChild(time);
    const count = document.createElement('span');
    count.textContent = s.message_count + '条';
    meta.appendChild(count);
    if (!isMultiSelectMode) {
        const delBtn = document.createElement('button');
        delBtn.className = 'session-delete';
        delBtn.textContent = '✕';
        delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSession(s.id);
        });
        meta.appendChild(delBtn);
    }
    item.appendChild(meta);

    if (isMultiSelectMode) {
        item.addEventListener('click', () => {
            const cb = item.querySelector('.session-checkbox');
            cb.checked = !cb.checked;
            if (cb.checked) selectedSessionIds.add(s.id);
            else selectedSessionIds.delete(s.id);
            item.classList.toggle('selected', cb.checked);
            updateSelectCount();
        });
    } else {
        item.addEventListener('click', () => switchSession(s.id));
    }
    return item;
}

function updateSessionBarVisibility() {
    const toolbar = document.getElementById('session-toolbar');
    const selectBar = document.getElementById('session-select-bar');
    if (!toolbar || !selectBar) return;
    if (isMultiSelectMode) {
        toolbar.classList.add('hidden');
        selectBar.classList.remove('hidden');
    } else {
        toolbar.classList.remove('hidden');
        selectBar.classList.add('hidden');
    }
}

async function enterMultiSelectMode() {
    if (isMultiSelectMode) return;
    if (sidebarView !== 'bot-sessions') return;
    const searchInput = document.getElementById('session-search');
    if (searchInput && searchInput.value.trim()) {
        clearSearch();
    }
    isMultiSelectMode = true;
    selectedSessionIds.clear();
    updateSessionBarVisibility();
    updateSelectCount();
    await loadSessions();
}

async function exitMultiSelectMode() {
    if (!isMultiSelectMode) return;
    isMultiSelectMode = false;
    selectedSessionIds.clear();
    updateSessionBarVisibility();
    updateSelectCount();
    await loadSessions();
}

function toggleSelectAll() {
    const checkboxes = document.querySelectorAll('.session-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => {
        cb.checked = !allChecked;
        const item = cb.closest('.session-item');
        if (item) item.classList.toggle('selected', cb.checked);
        const id = item ? item.dataset.id : '';
        if (id) {
            if (cb.checked) selectedSessionIds.add(id);
            else selectedSessionIds.delete(id);
        }
    });
    updateSelectCount();
}

function updateSelectCount() {
    const el = document.getElementById('select-count');
    if (el) el.textContent = `已选 ${selectedSessionIds.size} 项`;
}

function showDeleteSessionsConfirm() {
    if (selectedSessionIds.size === 0) return;
    const count = selectedSessionIds.size;
    const body = document.getElementById('session-delete-modal-body');
    if (body) {
        body.textContent = `即将删除 ${count} 条对话记录，此操作不可撤销。确定继续吗？`;
    }
    document.getElementById('session-delete-modal').classList.remove('hidden');
}

async function confirmDeleteSelectedSessions() {
    if (selectedSessionIds.size === 0) return;
    document.getElementById('session-delete-modal').classList.add('hidden');

    const ids = Array.from(selectedSessionIds);
    const resultStr = await pywebview.api.delete_sessions(JSON.stringify(ids));
    const result = JSON.parse(resultStr);
    if (result.ok) {
        if (currentSessionId && selectedSessionIds.has(currentSessionId)) {
            currentSessionId = null;
            conversationHistory = [];
            chatMessages.innerHTML = '';
        }
        await exitMultiSelectMode();
        if (!currentSessionId && sidebarView === 'bot-sessions' && selectedBotId) {
            await newSession(selectedBotId);
        }
    }
}

async function newSession(botId) {
    if (typeof botId !== 'string') botId = undefined;
    const targetBotId = botId || selectedBotId;
    if (!targetBotId) return;
    if (typeof applyGroupSessionContext === 'function') {
        applyGroupSessionContext({ is_group: false });
    }
    const resultStr = await pywebview.api.new_session(targetBotId);
    const result = JSON.parse(resultStr);
    if (!result.ok) return;
    currentSessionId = result.session.id;
    conversationHistory = [];
    chatMessages.innerHTML = '';
    // 重置为对话模式
    currentMode = 'chat';
    currentWorkingDir = null;
    document.getElementById('main-content').dataset.mode = 'chat';
    document.querySelectorAll('.mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === 'chat');
    });
    document.getElementById('code-workdir').classList.add('hidden');
    document.getElementById('code-workdir').textContent = '';
    document.getElementById('code-mode-bar').classList.add('hidden');
    await refreshConfig();
    updateBotDisplay();
    await loadSessions();
    if (typeof updateBotSelectorLockState === 'function') updateBotSelectorLockState();
    await refreshContextUsage();
}

let isSwitchingSession = false;

async function switchSession(sessionId) {
    if (isSwitchingSession) return;
    if (sessionId === currentSessionId) return;
    isSwitchingSession = true;
    try {
        const resultStr = await pywebview.api.switch_session(sessionId);
        const result = JSON.parse(resultStr);
        if (!result.ok) return;
        currentSessionId = sessionId;
        conversationHistory = result.messages || [];
        chatMessages.innerHTML = '';
        const animateThreshold = 10;
        const total = conversationHistory.length;
        for (let i = 0; i < total; i++) {
            const msg = conversationHistory[i];
            if (msg && msg.role) {
                const shouldAnimate = i >= total - animateThreshold;
                renderMessage(msg, shouldAnimate);
            }
        }
        scrollToBottom();
        // 恢复会话的模式和工作目录
        const sessionMode = result.mode || 'chat';
        const sessionWorkDir = result.working_dir || '';
        if (sessionMode !== currentMode) {
            // 静默切换模式（不弹文件夹选择）
            currentMode = sessionMode;
            document.getElementById('main-content').dataset.mode = sessionMode;
            document.querySelectorAll('.mode-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.mode === sessionMode);
            });
            const workdirEl = document.getElementById('code-workdir');
            const codeModeBar = document.getElementById('code-mode-bar');
            if (sessionMode === 'code') {
                workdirEl.classList.remove('hidden');
                codeModeBar.classList.remove('hidden');
                document.getElementById('chat-panel').classList.add('hidden');
                document.getElementById('files-panel').classList.remove('hidden');
                document.getElementById('status-panel').classList.add('hidden');
            } else {
                workdirEl.classList.add('hidden');
                codeModeBar.classList.add('hidden');
                document.getElementById('chat-panel').classList.remove('hidden');
                document.getElementById('files-panel').classList.add('hidden');
            }
        }
        if (sessionWorkDir && sessionWorkDir !== currentWorkingDir) {
            currentWorkingDir = sessionWorkDir;
            document.getElementById('code-workdir').textContent = sessionWorkDir;
            await loadFileTree(sessionWorkDir);
        } else if (!sessionWorkDir) {
            currentWorkingDir = null;
            document.getElementById('code-workdir').textContent = '';
        }
        if (result.is_group) {
            sidebarView = 'group-sessions';
            selectedGroupId = result.group_id;
            if (typeof setMainSidebarTab === 'function') setMainSidebarTab('group', { preserveNav: true });
            if (typeof applyGroupSessionContext === 'function') applyGroupSessionContext(result);
            if (typeof renderGroupSidebarNav === 'function') renderGroupSidebarNav();
        } else {
            if (typeof applyGroupSessionContext === 'function') applyGroupSessionContext(result);
            const sessionBotId = result.bot_id || '';
            if (!sessionBotId) {
                sidebarView = 'legacy-sessions';
                selectedBotId = null;
            } else {
                if (typeof mainSidebarTab !== 'undefined' && mainSidebarTab === 'group' && typeof setMainSidebarTab === 'function') {
                    setMainSidebarTab('private');
                }
                sidebarView = 'bot-sessions';
                selectedBotId = sessionBotId;
            }
            await refreshConfig();
            updateBotDisplay();
        }
        await loadBots();
        await loadSessions();
        if (typeof updateBotSelectorLockState === 'function') updateBotSelectorLockState();
        await refreshContextUsage();
    } finally {
        isSwitchingSession = false;
    }
}

async function deleteSession(sessionId) {
    if (!confirm('确定删除这个对话？')) return;
    await pywebview.api.delete_session(sessionId);
    if (currentSessionId === sessionId) {
        currentSessionId = null;
        conversationHistory = [];
        chatMessages.innerHTML = '';
    }
    await loadSessions();
}

// ===== 对话搜索 =====

let searchTimer = null;

function initSessionSearch() {
    const input = document.getElementById('session-search');
    if (!input) return;
    input.addEventListener('input', () => {
        clearTimeout(searchTimer);
        const keyword = input.value.trim();
        if (!keyword) {
            clearSearch();
            return;
        }
        searchTimer = setTimeout(() => doSearch(keyword), 300);
    });
}

async function doSearch(keyword) {
    const resultStr = await pywebview.api.search_sessions(keyword);
    const result = JSON.parse(resultStr);
    if (!result.ok) return;
    renderSearchResults(result.results, keyword);
}

function renderSearchResults(results, keyword) {
    const container = document.getElementById('search-results');
    const sessionList = document.getElementById('session-list');
    const toolbar = document.getElementById('session-toolbar');
    const selectBar = document.getElementById('session-select-bar');
    sessionList.classList.add('hidden');
    toolbar.classList.add('hidden');
    selectBar.classList.add('hidden');
    container.classList.remove('hidden');
    container.innerHTML = '';

    if (!results.length) {
        container.innerHTML = `<div class="search-empty">未找到包含"${escapeHtml(keyword)}"的对话</div>`;
        const clearBtn = document.createElement('button');
        clearBtn.className = 'search-clear-btn';
        clearBtn.textContent = '清除搜索';
        clearBtn.addEventListener('click', clearSearch);
        container.appendChild(clearBtn);
        return;
    }

    const header = document.createElement('div');
    header.className = 'search-header';
    header.textContent = `搜索结果：${results.length} 条`;
    container.appendChild(header);

    const groups = new Map();
    for (const r of results) {
        const key = r.bot_id || '__legacy__';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(r);
    }

    const groupOrder = [...groups.keys()].sort((a, b) => {
        if (a === '__legacy__') return 1;
        if (b === '__legacy__') return -1;
        const botA = getBotById(a);
        const botB = getBotById(b);
        return (botA?.name || '').localeCompare(botB?.name || '', 'zh');
    });

    for (const key of groupOrder) {
        const groupResults = groups.get(key);
        const groupHead = document.createElement('div');
        groupHead.className = 'search-group-head';
        if (key === '__legacy__') {
            groupHead.textContent = '📦 历史遗留';
        } else {
            const bot = getBotById(key);
            groupHead.innerHTML = `<span class="search-group-avatar">${bot?.avatar || '🤖'}</span> ${escapeHtml(bot?.name || '未知机器人')}`;
        }
        container.appendChild(groupHead);

        for (const r of groupResults) {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            const bot = getBotById(r.bot_id);
            const badge = bot ? getSessionModeBadgeHtml(bot) : '';
            item.innerHTML = `<div class="search-result-title">📄 ${escapeHtml(r.title)}${badge ? ' ' + badge : ''}</div>`;

            for (const m of r.matches) {
                const snippet = document.createElement('div');
                snippet.className = 'search-result-snippet';
                const roleIcon = m.role === 'user' ? '👤' : '🧑‍💻';
                const escapedText = escapeHtml(m.text);
                const regex = new RegExp(`(${escapeRegex(keyword)})`, 'gi');
                const highlighted = escapedText.replace(regex, '<mark>$1</mark>');
                snippet.innerHTML = `<span class="search-role">${roleIcon}</span> ${highlighted}`;
                item.appendChild(snippet);
            }

            const time = document.createElement('div');
            time.className = 'search-result-time';
            time.textContent = r.updated_at ? formatTime(r.updated_at) : '';
            item.appendChild(time);

            item.addEventListener('click', () => {
                clearSearch();
                switchSession(r.session_id);
                setTimeout(() => highlightMatchedMessage(keyword), 300);
            });
            container.appendChild(item);
        }
    }

    const clearBtn = document.createElement('button');
    clearBtn.className = 'search-clear-btn';
    clearBtn.textContent = '清除搜索';
    clearBtn.addEventListener('click', clearSearch);
    container.appendChild(clearBtn);
}

function clearSearch() {
    const input = document.getElementById('session-search');
    if (input) input.value = '';
    const container = document.getElementById('search-results');
    const sessionList = document.getElementById('session-list');
    const toolbar = document.getElementById('session-toolbar');
    const selectBar = document.getElementById('session-select-bar');
    container.classList.add('hidden');
    container.innerHTML = '';
    sessionList.classList.remove('hidden');
    updateSessionBarVisibility();
    updateNavToolbar();
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlightMatchedMessage(keyword) {
    const messages = document.querySelectorAll('.message-content');
    for (const el of messages) {
        if (el.textContent.toLowerCase().includes(keyword.toLowerCase())) {
            const row = el.closest('.message-row');
            if (row) {
                row.scrollIntoView({ behavior: 'smooth', block: 'center' });
                row.classList.add('highlight-flash');
                setTimeout(() => row.classList.remove('highlight-flash'), 1500);
            }
            break;
        }
    }
}

// 文件夹与文件树
async function openFolder() {
    const resultStr = await pywebview.api.select_folder();
    const result = JSON.parse(resultStr);
    if (result.ok && result.path) {
        currentWorkingDir = result.path;
        await loadFileTree(result.path);
        openSidebar();
        // 编程模式下同步更新后端和工作目录显示
        if (currentMode === 'code') {
            await pywebview.api.set_working_dir(result.path);
            document.getElementById('code-workdir').textContent = result.path;
        } else {
            switchSidebarTab('files');
        }
    }
}

async function refreshFileTree() {
    await loadFileTree();
}

async function loadFileTree(folderPath) {
    let resultStr;
    if (folderPath) {
        resultStr = await pywebview.api.get_file_tree(folderPath);
    } else {
        resultStr = await pywebview.api.get_file_tree();
    }
    const result = JSON.parse(resultStr);
    if (!result.ok && folderPath) {
        resultStr = await pywebview.api.get_file_tree();
        const retry = JSON.parse(resultStr);
        if (retry.ok) {
            fileTree.innerHTML = '';
            renderFileTree(retry.tree, fileTree);
        }
        return;
    }
    if (result.ok) {
        if (result.tree && result.tree.type === 'file') {
            resultStr = await pywebview.api.get_file_tree();
            const fixed = JSON.parse(resultStr);
            if (fixed.ok) {
                fileTree.innerHTML = '';
                renderFileTree(fixed.tree, fileTree);
            }
            return;
        }
        fileTree.innerHTML = '';
        renderFileTree(result.tree, fileTree);
    }
}

function renderFileTree(node, container) {
    if (!node) return;
    if (node.type === 'folder') {
        const folderDiv = document.createElement('div');
        folderDiv.className = 'tree-item folder';

        const icon = document.createElement('span');
        icon.className = 'icon';
        icon.textContent = '\u{1F4C1}';
        folderDiv.appendChild(icon);

        const name = document.createElement('span');
        name.className = 'name';
        name.textContent = node.name;
        folderDiv.appendChild(name);

        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'tree-children';

        folderDiv.addEventListener('click', (e) => {
            e.stopPropagation();
            const isCollapsed = childrenDiv.classList.toggle('collapsed');
            icon.textContent = isCollapsed ? '\u{1F4C1}' : '\u{1F4C2}';
        });

        container.appendChild(folderDiv);
        container.appendChild(childrenDiv);

        if (node.children) {
            for (const child of node.children) {
                renderFileTree(child, childrenDiv);
            }
        }
    } else {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'tree-item file';
        fileDiv.dataset.path = node.path;

        const icon = document.createElement('span');
        icon.className = 'icon';
        icon.textContent = getFileIcon(node.name);
        fileDiv.appendChild(icon);

        const name = document.createElement('span');
        name.className = 'name';
        name.textContent = node.name;
        fileDiv.appendChild(name);

        fileDiv.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.tree-item.active').forEach(el => el.classList.remove('active'));
            fileDiv.classList.add('active');
            previewFile(node.path);
        });

        container.appendChild(fileDiv);
    }
}

function updateSidebarToggleUI() {
    const collapsed = sidebar.classList.contains('hidden');
    const btn = document.getElementById('btn-sidebar-toggle');
    const main = document.getElementById('main-content');
    if (main) main.classList.toggle('sidebar-collapsed', collapsed);
    if (btn) {
        btn.textContent = collapsed ? '›' : '‹';
        btn.title = collapsed ? '展开侧边栏' : '收起侧边栏';
        btn.setAttribute('aria-label', btn.title);
        btn.setAttribute('aria-expanded', String(!collapsed));
    }
}

function openSidebar() {
    sidebar.classList.remove('hidden');
    resizeHandle.classList.remove('hidden');
    updateSidebarToggleUI();
}

function closeSidebar() {
    sidebar.classList.add('hidden');
    resizeHandle.classList.add('hidden');
    updateSidebarToggleUI();
}

function toggleSidebar() {
    if (sidebar.classList.contains('hidden')) {
        openSidebar();
        if (typeof currentMode !== 'undefined' && currentMode === 'chat' && typeof switchSidebarTab === 'function') {
            switchSidebarTab('chat');
        }
    } else {
        closeSidebar();
    }
}

// 拖拽调整侧边栏宽度
let isResizing = false;
