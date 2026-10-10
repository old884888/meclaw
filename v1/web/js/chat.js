// ===== 对话核心 =====

// 流式输出时用户是否在底部附近（控制自动滚动）
let isNearBottom = true;

// ===== 专家模式临时开关 =====
let expertModeActive = false;
let expertPipelineActive = false;
let expertAnswerStarted = false;
let expertScratchpadFinal = '';
let expertStagesDone = 0;

function toggleExpertMode() {
    expertModeActive = !expertModeActive;
    const btn = document.getElementById('btn-expert-mode');
    if (btn) btn.classList.toggle('active', expertModeActive);
}

function resetExpertMode() {
    expertModeActive = false;
    const btn = document.getElementById('btn-expert-mode');
    if (btn) btn.classList.remove('active');
}

// ===== 群聊专家会议临时开关 =====
let councilModeActive = false;
let councilPipelineActive = false;
let councilAwaitingArbitration = false;
let councilBlackboardData = null;
let councilSelectedOptionIndex = 0;
let pendingCouncilSendText = null;

function toggleCouncilMode() {
    councilModeActive = !councilModeActive;
    const btn = document.getElementById('btn-council-mode');
    if (btn) btn.classList.toggle('active', councilModeActive);
}

function resetCouncilMode() {
    councilModeActive = false;
    const btn = document.getElementById('btn-council-mode');
    if (btn) btn.classList.remove('active');
}

async function getCouncilMaxExperts() {
    const gid = typeof getActiveGroupId === 'function' ? getActiveGroupId() : null;
    if (!gid) return 5;
    try {
        const result = JSON.parse(await pywebview.api.get_group_meta(gid));
        return result.ok ? (result.group?.council_max_experts || 5) : 5;
    } catch (e) {
        return 5;
    }
}

function promptCouncilParticipants(members, maxExperts) {
    return new Promise((resolve) => {
        const modal = document.getElementById('council-participant-modal');
        const list = document.getElementById('council-participant-list');
        const hint = document.getElementById('council-participant-hint');
        if (!modal || !list) {
            resolve(members.slice(0, maxExperts).map(m => m.id));
            return;
        }
        if (hint) {
            hint.textContent = `成员超过 ${maxExperts} 人，请勾选 2–${maxExperts} 位参与专家：`;
        }
        list.innerHTML = '';
        for (const bot of members) {
            const label = document.createElement('label');
            label.className = 'council-participant-item';
            label.innerHTML = `
                <input type="checkbox" value="${escapeHtml(bot.id)}">
                <span>${bot.avatar || '🤖'} ${escapeHtml(bot.name)}</span>`;
            list.appendChild(label);
        }
        const onCancel = () => {
            modal.classList.add('hidden');
            cleanup();
            resolve(null);
        };
        const onConfirm = () => {
            const ids = [...list.querySelectorAll('input:checked')].map(i => i.value);
            if (ids.length < 2) {
                alert('请至少选择 2 位专家');
                return;
            }
            if (ids.length > maxExperts) {
                alert(`最多选择 ${maxExperts} 位专家`);
                return;
            }
            modal.classList.add('hidden');
            cleanup();
            resolve(ids);
        };
        const cleanup = () => {
            document.getElementById('council-participant-cancel')?.removeEventListener('click', onCancel);
            document.getElementById('council-participant-confirm')?.removeEventListener('click', onConfirm);
        };
        document.getElementById('council-participant-cancel')?.addEventListener('click', onCancel);
        document.getElementById('council-participant-confirm')?.addEventListener('click', onConfirm);
        modal.classList.remove('hidden');
    });
}

// ===== 消息队列 =====
let messageQueue = [];
const MAX_QUEUE_SIZE = 3;

// 联网状态 DOM（须在文件顶部初始化，避免 pywebview 回调触发 TDZ）
var webSearchStatusEl = null;
var webSearchTimelineEl = null;
var currentWebSearchSteps = [];
var currentWebSearchCitations = [];

function sendMessage() {
    const text = msgInput.value.trim();
    const hasAttachments = pendingAttachments.length > 0;
    if (!text && !hasAttachments) return;

    // 上下文已满 → 阻止发送
    if (isContextFull) {
        alert('上下文已满，请先压缩上下文或新建会话');
        return;
    }

    // 生成中 → 加入队列（有附件时不入队，提示等待）
    if (isGenerating) {
        if (hasAttachments) {
            alert('请等待当前回复完成后再发送附件');
            return;
        }
        if (messageQueue.length >= MAX_QUEUE_SIZE) {
            alert(`队列已满（最多 ${MAX_QUEUE_SIZE} 条）`);
            return;
        }
        messageQueue.push(text);
        msgInput.value = '';
        autoResize();
        renderQueue();
        return;
    }

    // 非生成中 → 正常发送
    sendImmediately(text).catch(e => console.error(e));
}

/**
 * 立即发送消息（不经过队列）
 */
async function sendImmediately(text) {
    const attachments = pendingAttachments.slice();
    const historyAttachments = attachments.map(a => ({
        name: a.name, path: a.path, size: a.size, ext: a.ext,
        is_image: a.is_image, is_text: a.is_text
    }));
    let displayText = text;
    const userPayload = {
        role: 'user',
        content: text,
        attachments: historyAttachments.length ? historyAttachments : undefined,
        _attachments_full: attachments.length ? attachments : undefined,
    };
    if (typeof currentGroupSession !== 'undefined' && currentGroupSession && typeof getPendingMentionIds === 'function') {
        if (typeof initGroupChainBudgetFromMeta === 'function') {
            await initGroupChainBudgetFromMeta();
        } else if (typeof resetGroupChainState === 'function') {
            resetGroupChainState();
        }
        if (typeof resetGroupReplyHalt === 'function') resetGroupReplyHalt();
        if (typeof resetGroupEmptyRetry === 'function') resetGroupEmptyRetry();
        const mentionIds = getPendingMentionIds();
        if (typeof hasPendingUserMention === 'function' && hasPendingUserMention()) {
            userPayload.mention_user = true;
        }
        if (mentionIds.length) {
            userPayload.mention_bot_ids = mentionIds;
            userPayload.mention_bot_id = mentionIds[0];
            const prefix = typeof buildMentionPrefix === 'function' ? buildMentionPrefix() : '';
            displayText = prefix ? `${prefix} ${text}`.trim() : text;
            userPayload.content = displayText;
            groupReplyQueue = mentionIds.slice(1);
        } else {
            groupReplyQueue = [];
        }
    }

    addMessage('user', displayText, false, true, attachments);

    // 专家模式：标记在最后一条用户消息上，发送后重置开关
    if (expertModeActive) {
        userPayload._expert_mode = true;
        resetExpertMode();
        expertPipelineActive = true;
        expertAnswerStarted = false;
        expertScratchpadFinal = '';
        expertStagesDone = 0;
        currentThinkingEl = null;
    }

    conversationHistory.push(userPayload);

    msgInput.value = '';
    autoResize();
    clearAttachments();
    if (typeof clearPendingMentions === 'function') clearPendingMentions();

    if (typeof updateContextBarIncremental === 'function') {
        updateContextBarIncremental(text.length);
    }

    const mentionIds = userPayload.mention_bot_ids || [];
    const isGroupNoMention = typeof currentGroupSession !== 'undefined' && currentGroupSession
        && !mentionIds.length && !isCouncilSend;
    setGenerating(true);
    currentThinkingEl = null;
    isThinking = false;
    resetWebSearchSessionState();
    if (!isGroupNoMention && !isCouncilSend) {
        if (mentionIds.length && cachedConfig && typeof groupReplySpeaker !== 'undefined') {
            groupReplySpeaker = (cachedConfig.bots || []).find(b => b.id === mentionIds[0]) || null;
        }
        addMessage('ai', '', true);
    }

    // 发送给 API 时用完整附件数据
    const apiMessages = conversationHistory.map(m => {
        if (m._attachments_full) {
            const copy = Object.assign({}, m);
            copy.attachments = m._attachments_full;
            delete copy._attachments_full;
            return copy;
        }
        return m;
    });
    pywebview.api.send_message(JSON.stringify(apiMessages));

    // 发送后清除临时字段（不再需要）
    for (const m of conversationHistory) {
        delete m._attachments_full;
        delete m._expert_mode;
        delete m._council_mode;
        delete m._council_participant_ids;
    }
}

/**
 * 从队列取出下一条消息发送
 */
function processQueue() {
    if (messageQueue.length === 0) return;
    const next = messageQueue.shift();
    renderQueue();
    sendImmediately(next);
}

/**
 * 从队列中移除指定条目
 */
function removeFromQueue(index) {
    messageQueue.splice(index, 1);
    renderQueue();
}

/**
 * 编辑队列条目：将 chip 替换为输入框
 */
function editQueueItem(index) {
    const container = document.getElementById('message-queue');
    if (!container) return;
    const chips = container.querySelectorAll('.queue-chip');
    const chip = chips[index];
    if (!chip) return;

    const currentText = messageQueue[index];
    chip.innerHTML = `<input type="text" class="queue-edit-input" value="${escapeHtml(currentText)}">`;
    const input = chip.querySelector('input');
    input.focus();
    input.select();

    const commit = () => {
        const val = input.value.trim();
        if (val) {
            messageQueue[index] = val;
        } else {
            messageQueue.splice(index, 1);
        }
        renderQueue();
    };
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(); }
        if (e.key === 'Escape') { renderQueue(); }
    });
}

/**
 * 渲染队列 UI
 */
function renderQueue() {
    const container = document.getElementById('message-queue');
    if (!container) return;

    if (messageQueue.length === 0) {
        container.innerHTML = '';
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    container.innerHTML = `<div class="queue-label">待发送 (${messageQueue.length})</div>` +
        messageQueue.map((text, i) => {
            const display = text.length > 40 ? text.slice(0, 40) + '…' : text;
            return `<div class="queue-chip" data-qi="${i}"><span class="queue-chip-text" title="${escapeHtml(text)}">${escapeHtml(display)}</span><button class="queue-chip-edit" data-action="edit" data-qi="${i}" title="编辑">✎</button><button class="queue-chip-remove" data-action="remove" data-qi="${i}" title="移除">✕</button></div>`;
        }).join('');

    // 事件委托
    container.onclick = (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const qi = parseInt(btn.dataset.qi, 10);
        if (btn.dataset.action === 'remove') removeFromQueue(qi);
        else if (btn.dataset.action === 'edit') editQueueItem(qi);
    };
    // 双击文本也可编辑
    container.ondblclick = (e) => {
        const chip = e.target.closest('.queue-chip');
        if (chip) editQueueItem(parseInt(chip.dataset.qi, 10));
    };
}

function stopGeneration() {
    const inGroup = typeof currentGroupSession !== 'undefined' && currentGroupSession;
    if (inGroup && typeof emergencyStopGroup === 'function') {
        emergencyStopGroup();
        return;
    }
    pywebview.api.stop_generation();
}

function setGenerating(state) {
    isGenerating = state;
    const inGroup = typeof currentGroupSession !== 'undefined' && currentGroupSession;
    const btnEstop = document.getElementById('btn-estop');
    btnSend.classList.toggle('hidden', state);
    if (inGroup) {
        btnStop.classList.add('hidden');
        if (btnEstop) btnEstop.classList.toggle('hidden', !state);
    } else {
        btnStop.classList.toggle('hidden', !state);
        if (btnEstop) btnEstop.classList.add('hidden');
    }
    // 输入框不禁用，用户可以继续输入并入队
    if (!state) {
        hideScrollToBottomBtn();
        // 生成结束 → 处理队列
        processQueue();
    }
}

/**
 * 获取当前字体大小配置
 */
function getFontSizes() {
    const cfg = cachedConfig || {};
    return {
        user: cfg.user_font_size || 14,
        bot: cfg.bot_font_size || 14,
        thinking: cfg.thinking_font_size || 12
    };
}

/**
 * 渲染 markdown 内容（AI 消息用）
 */
function renderMarkdown(text) {
    if (typeof marked !== 'undefined' && marked.parse) {
        return marked.parse(text, { breaks: true });
    }
    return escapeHtml(text);
}

function escapeRegExp(str) {
    return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** 群聊消息：markdown + @用户 / @Bot 高亮 */
function renderGroupContent(text) {
    if (!text) return '';
    const members = (typeof getGroupMemberBots === 'function') ? getGroupMemberBots() : [];
    const placeholders = [];
    let processed = text;
    let idx = 0;

    if (processed.includes('@用户')) {
        const ph = `%%MENTION_${idx++}%%`;
        placeholders.push({ ph, html: '<span class="mention-user">@用户</span>' });
        processed = processed.replace(/@用户/g, ph);
    }

    const sorted = [...members].sort((a, b) => (b.name || '').length - (a.name || '').length);
    for (const bot of sorted) {
        const name = bot.name || bot.id;
        if (!name) continue;
        const re = new RegExp('@' + escapeRegExp(name) + '(?!\\S)', 'g');
        if (!re.test(processed)) continue;
        const ph = `%%MENTION_${idx++}%%`;
        placeholders.push({
            ph,
            html: `<span class="mention-bot" data-bot-id="${escapeHtml(bot.id)}">@${escapeHtml(name)}</span>`,
        });
        processed = processed.replace(new RegExp('@' + escapeRegExp(name) + '(?!\\S)', 'g'), ph);
    }

    let html = renderMarkdown(processed);
    for (const { ph, html: span } of placeholders) {
        html = html.split(ph).join(span);
    }
    return html;
}

/**
 * 复制消息文本到剪贴板
 */
async function collectMessageMemory(text, role) {
    const content = (text || '').trim();
    if (!content) {
        showToast('内容为空');
        return;
    }
    try {
        let resultStr;
        if (content.length > 600) {
            const title = content.slice(0, 40).replace(/\s+/g, ' ') + '…';
            resultStr = await pywebview.api.collect_document(title, content, '[]');
        } else {
            resultStr = await pywebview.api.collect_quote(content);
        }
        const result = JSON.parse(resultStr);
        showToast(result.ok ? (result.msg || '已收藏') : (result.msg || '收藏失败'));
    } catch (e) {
        showToast('收藏失败');
    }
}

function copyMessageText(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到剪贴板');
    }).catch(() => {
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            showToast('已复制到剪贴板');
        } catch (e) {
            showToast('复制失败');
        }
    });
}

function showToast(msg, duration) {
    duration = duration || 2000;
    let toast = document.getElementById('global-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'global-toast';
        toast.className = 'toast hidden';
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.remove('hidden');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.add('hidden'), duration);
}

/**
 * 重新回答：保留旧版本，生成新版本
 */
function regenerateLastResponse() {
    if (isGenerating) return;
    if (conversationHistory.length < 2) return;

    const lastMsg = conversationHistory[conversationHistory.length - 1];
    if (lastMsg.role !== 'assistant') return;

    // 找到最后一条 AI 消息的 DOM 行
    const rows = chatMessages.querySelectorAll('.message-row');
    const lastRow = rows[rows.length - 1];
    if (!lastRow) return;

    // 保存当前版本
    const currentContent = lastMsg.content;
    const currentReasoning = lastMsg.reasoning_content || '';
    if (!lastRow._versions) {
        lastRow._versions = [{ content: currentContent, reasoning_content: currentReasoning }];
        lastRow._currentVersion = 0;
    } else {
        // 如果当前不在最新版本，截断后面的版本
        lastRow._versions = lastRow._versions.slice(0, lastRow._currentVersion + 1);
    }

    // 从历史中移除最后一条 AI 回复
    conversationHistory.pop();

    // 找到最后一条用户消息
    const userMsg = conversationHistory[conversationHistory.length - 1];
    if (!userMsg || userMsg.role !== 'user') return;

    // 标记正在重新生成
    lastRow._regenerating = true;

    // 开始流式请求
    setGenerating(true);
    currentThinkingEl = null;
    isThinking = false;

    // 创建新的流式消息行（会替换现有行的内容）
    resetWebSearchSessionState();
    addMessage('ai', '', true);

    pywebview.api.send_message(JSON.stringify(conversationHistory));
}

/**
 * 切换版本
 */
function switchVersion(row, versionIndex) {
    if (!row._versions || versionIndex < 0 || versionIndex >= row._versions.length) return;
    row._currentVersion = versionIndex;
    const version = row._versions[versionIndex];

    // 更新内容
    const contentDiv = row.querySelector('.message-content');
    if (contentDiv) {
        contentDiv.innerHTML = renderMarkdown(version.content);
        const sizes = getFontSizes();
        contentDiv.style.fontSize = sizes.bot + 'px';
    }

    // 更新 thinking 区域
    const thinkingArea = row.querySelector('.thinking-area');
    if (thinkingArea) {
        thinkingArea.innerHTML = '';
        if (version.reasoning_content) {
            const block = document.createElement('div');
            block.className = 'thinking-block';
            block._expanded = false;
            block._thinkingText = version.reasoning_content;
            const thinkingSize = getFontSizes().thinking;
            block.innerHTML = `
                <div class="thinking-header" style="font-size:${thinkingSize}px">
                    <span class="thinking-label">\u{1F4AD} 思考过程</span>
                    <button class="thinking-copy-btn" title="复制思考内容">📋</button>
                    <span class="thinking-arrow">\u{25B8}</span>
                </div>
            `;
            block.querySelector('.thinking-header').addEventListener('click', () => toggleThinking(block));
            block.querySelector('.thinking-copy-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                copyMessageText(version.reasoning_content || '');
            });
            thinkingArea.appendChild(block);
        }
    }

    // 更新复制按钮的文本
    const copyBtn = row.querySelector('.msg-action-btn');
    if (copyBtn) {
        copyBtn.onclick = () => copyMessageText(version.content);
    }

    // 更新版本导航
    updateVersionNav(row);
}

/**
 * 更新版本导航 UI
 */
function updateVersionNav(row) {
    const existing = row.querySelector('.version-nav');
    if (existing) existing.remove();

    if (!row._versions || row._versions.length <= 1) return;

    const actions = row.querySelector('.msg-actions');
    if (!actions) return;

    const nav = document.createElement('div');
    nav.className = 'version-nav';
    const total = row._versions.length;
    const current = (row._currentVersion || 0) + 1;

    const prevBtn = document.createElement('button');
    prevBtn.className = 'version-nav-btn';
    prevBtn.textContent = '◀';
    prevBtn.disabled = current <= 1;
    prevBtn.addEventListener('click', () => switchVersion(row, row._currentVersion - 1));

    const label = document.createElement('span');
    label.className = 'version-nav-label';
    label.textContent = `${current}/${total}`;

    const nextBtn = document.createElement('button');
    nextBtn.className = 'version-nav-btn';
    nextBtn.textContent = '▶';
    nextBtn.disabled = current >= total;
    nextBtn.addEventListener('click', () => switchVersion(row, row._currentVersion + 1));

    nav.appendChild(prevBtn);
    nav.appendChild(label);
    nav.appendChild(nextBtn);
    actions.appendChild(nav);

    // 重新生成按钮：只在最新版本时显示
    const regenBtn = actions.querySelector('.regen-btn');
    if (regenBtn) {
        regenBtn.style.display = (row._currentVersion === total - 1) ? '' : 'none';
    }
}

/**
 * 添加消息到聊天区
 * 结构: .message-row > .avatar + .message-bubble > .thinking-area + .message-content
 * AI 消息额外：+ .msg-actions（重新回答按钮）
 * 流式 AI 消息：content 有 .collapsible 类（可折叠），结束后移除
 */
function addMessage(role, content, isStreaming = false, animate = true, attachments) {
    const row = document.createElement('div');
    const rowClass = role === 'user' ? 'user' : (role === 'error' ? 'error' : 'assistant');
    row.className = `message-row ${rowClass}` + (animate ? ' animate-in' : '');

    // 头像（error 消息不显示头像）
    if (role !== 'error') {
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        if (role === 'user') {
            avatar.textContent = cachedConfig ? (cachedConfig.user_avatar || '😎') : '😎';
        } else {
            let bot = cachedConfig ? getActiveBot(cachedConfig) : {};
            if (typeof groupReplySpeaker !== 'undefined' && groupReplySpeaker) {
                bot = groupReplySpeaker;
            }
            avatar.textContent = bot.avatar || '🤖';
        }
        row.appendChild(avatar);
    }

    // 气泡容器
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // thinking 区域
    const thinkingArea = document.createElement('div');
    thinkingArea.className = 'thinking-area';
    bubble.appendChild(thinkingArea);

    // 附件区域（用户消息）
    if (role === 'user' && attachments && attachments.length > 0) {
        const attachDiv = document.createElement('div');
        attachDiv.className = 'message-attachments';
        for (const a of attachments) {
            if (a.is_image && a.base64) {
                const imgWrap = document.createElement('div');
                imgWrap.className = 'msg-attach-image';
                const img = document.createElement('img');
                img.src = a.base64;
                img.alt = a.name;
                img.addEventListener('click', () => window.open(a.base64, '_blank'));
                imgWrap.appendChild(img);
                const label = document.createElement('div');
                label.className = 'msg-attach-label';
                label.textContent = a.name + ' (' + formatFileSize(a.size) + ')';
                imgWrap.appendChild(label);
                attachDiv.appendChild(imgWrap);
            } else {
                const card = document.createElement('div');
                card.className = 'msg-attach-file';
                card.innerHTML = `<span class="msg-attach-icon">${getFileIcon(a.name)}</span>
                    <span class="msg-attach-name">${escapeHtml(a.name)}</span>
                    <span class="msg-attach-size">${formatFileSize(a.size)}</span>`;
                attachDiv.appendChild(card);
            }
        }
        bubble.appendChild(attachDiv);
    }

    // 内容区域
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // 应用字体大小
    const sizes = getFontSizes();
    if (role === 'user') {
        contentDiv.style.fontSize = sizes.user + 'px';
    } else if (role !== 'error') {
        contentDiv.style.fontSize = sizes.bot + 'px';
    }

    if (role === 'user' || role === 'error') {
        const inGroup = typeof currentGroupSession !== 'undefined' && currentGroupSession;
        if (role === 'user' && inGroup && content) {
            contentDiv.innerHTML = renderGroupContent(content);
        } else {
            contentDiv.textContent = content;
        }
    } else {
        // AI 消息：markdown 渲染（非流式时）
        if (content && !isStreaming) {
            const inGroup = typeof currentGroupSession !== 'undefined' && currentGroupSession;
            contentDiv.innerHTML = inGroup ? renderGroupContent(content) : renderMarkdown(content);
        } else {
            contentDiv.textContent = content;
        }
    }

    if (isStreaming) {
        const cursor = document.createElement('span');
        cursor.className = 'cursor';
        cursor.textContent = '█';
        contentDiv.appendChild(cursor);
        row.id = 'streaming-msg';
        // 流式输出时可折叠
        contentDiv.classList.add('collapsible');
    }

    bubble.appendChild(contentDiv);

    // 流式 AI 消息：添加展开按钮（初始隐藏，内容溢出时显示）
    if (role !== 'user' && role !== 'error' && isStreaming) {
        const expandBtn = document.createElement('button');
        expandBtn.className = 'expand-btn hidden';
        expandBtn.textContent = '展开全部 ▾';
        expandBtn.addEventListener('click', () => {
            contentDiv.classList.remove('collapsible');
            contentDiv.classList.add('expanded');
            expandBtn.remove();
        });
        bubble.appendChild(expandBtn);
    }

    // 操作按钮（用户消息 + AI 非流式消息）
    if (!isStreaming && (role === 'user' || role === 'assistant')) {
        const actions = document.createElement('div');
        actions.className = 'msg-actions';
        const copyBtn = document.createElement('button');
        copyBtn.className = 'msg-action-btn';
        copyBtn.textContent = '📋 复制';
        copyBtn.addEventListener('click', () => copyMessageText(content));
        actions.appendChild(copyBtn);
        if (role === 'assistant') {
            const regenBtn = document.createElement('button');
            regenBtn.className = 'msg-action-btn regen-btn';
            regenBtn.textContent = '↻ 重新回答';
            regenBtn.addEventListener('click', regenerateLastResponse);
            actions.appendChild(regenBtn);
        }
        const memBtn = document.createElement('button');
        memBtn.className = 'msg-action-btn';
        memBtn.textContent = role === 'assistant' ? '⭐ 收藏' : '⭐ 记住';
        memBtn.title = '写入当前 Bot 的记忆库';
        memBtn.addEventListener('click', () => collectMessageMemory(content, role));
        actions.appendChild(memBtn);
        // 编程模式：回退按钮
        if (currentMode === 'code') {
            const rollbackBtn = document.createElement('button');
            rollbackBtn.className = 'msg-action-btn rollback-btn';
            rollbackBtn.textContent = '↩ 回退';
            rollbackBtn.addEventListener('click', () => rollbackToMessage(row));
            actions.appendChild(rollbackBtn);
        }
        bubble.appendChild(actions);
    }

    row.appendChild(bubble);
    chatMessages.appendChild(row);
    scrollToBottom();
    return contentDiv;
}

/**
 * 条件滚动：仅在底部附近时自动滚动
 */
function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function conditionalScrollToBottom() {
    const threshold = 120;
    const { scrollTop, scrollHeight, clientHeight } = chatContainer;
    const nearBottom = (scrollHeight - scrollTop - clientHeight) < threshold;
    if (nearBottom) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    } else if (isGenerating) {
        showScrollToBottomBtn();
    }
}

function checkNearBottom() {
    const threshold = 120;
    const { scrollTop, scrollHeight, clientHeight } = chatContainer;
    isNearBottom = (scrollHeight - scrollTop - clientHeight) < threshold;
}

// 浮动"回到底部"按钮
const scrollToBottomBtn = document.createElement('button');
scrollToBottomBtn.id = 'scroll-to-bottom-btn';
scrollToBottomBtn.className = 'scroll-to-bottom-btn hidden';
scrollToBottomBtn.textContent = '↓ 回到最新';
scrollToBottomBtn.addEventListener('click', () => {
    isNearBottom = true;
    scrollToBottom();
    hideScrollToBottomBtn();
});
document.getElementById('chat-area').appendChild(scrollToBottomBtn);

function showScrollToBottomBtn() {
    scrollToBottomBtn.classList.remove('hidden');
}

function hideScrollToBottomBtn() {
    scrollToBottomBtn.classList.add('hidden');
}

// 监听用户滚动
chatContainer.addEventListener('scroll', () => {
    checkNearBottom();
    if (isNearBottom && isGenerating) {
        hideScrollToBottomBtn();
    }
});

function autoResize() {
    msgInput.style.height = 'auto';
    msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
}

// ===== 深度思考 =====

/**
 * 创建流式思考块（展开状态）
 */
function createThinkingBlock() {
    const block = document.createElement('div');
    block.className = 'thinking-block';
    block._expanded = true;
    block._thinkingText = '';
    const sizes = getFontSizes();
    block.innerHTML = `
        <div class="thinking-header" style="font-size:${sizes.thinking}px">
            <span class="thinking-label">\u{1F4AD} 深度思考中...</span>
            <button class="thinking-copy-btn" title="复制思考内容">📋</button>
            <span class="thinking-arrow">\u{25BE}</span>
        </div>
        <div class="thinking-content" style="font-size:${sizes.thinking}px"></div>
    `;
    block.querySelector('.thinking-copy-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        copyMessageText(block._thinkingText || block.querySelector('.thinking-content')?.textContent || '');
    });
    block.querySelector('.thinking-header').addEventListener('click', () => toggleThinking(block));
    return block;
}

/**
 * 切换思考块展开/折叠
 */
function toggleThinking(block) {
    const label = block.querySelector('.thinking-label');
    const arrow = block.querySelector('.thinking-arrow');
    const content = block.querySelector('.thinking-content');

    if (block._expanded && content) {
        // 折叠：保存文本，移除 content 元素
        block._thinkingText = content.textContent;
        content.remove();
        block._expanded = false;
        label.textContent = '\u{1F4AD} 思考过程';
        arrow.textContent = '\u{25B8}';
    } else {
        // 展开：创建 content 元素
        const div = document.createElement('div');
        div.className = 'thinking-content';
        div.style.fontSize = getFontSizes().thinking + 'px';
        div.textContent = block._thinkingText || '';
        block.appendChild(div);
        block._expanded = true;
        label.textContent = '\u{1F4AD} 思考过程';
        arrow.textContent = '\u{25BE}';
    }
}

/**
 * 折叠当前思考块
 */
function collapseThinking() {
    if (!currentThinkingEl) return;
    const content = currentThinkingEl.querySelector('.thinking-content');
    const label = currentThinkingEl.querySelector('.thinking-label');
    const arrow = currentThinkingEl.querySelector('.thinking-arrow');
    if (content) {
        currentThinkingEl._thinkingText = content.textContent;
        content.remove();
    }
    currentThinkingEl._expanded = false;
    if (label) label.textContent = '\u{1F4AD} 思考过程';
    if (arrow) arrow.textContent = '\u{25B8}';
}

// ===== 联网：轮次状态 + 时间线 + 引用 =====

const WEB_SEARCH_STATUS_LABELS = {
    analyzing: { icon: '🔍', text: '联网已开启，分析检索需求', active: true, tone: 'active' },
    round: { icon: '🔄', text: '联网检索轮次', active: true, tone: 'active' },
    generating: { icon: '✍️', text: '检索完成，正在组织回复', active: true, tone: 'active' },
    skipped: { icon: '⏭', text: '未联网检索', active: false, tone: 'muted' },
    error: { icon: '⚠', text: '联网失败', active: false, tone: 'error' },
};

function getStreamingBubble() {
    const msg = document.getElementById('streaming-msg');
    return msg ? msg.querySelector('.message-bubble') : null;
}

function ensureWebSearchStatusEl(bubble) {
    bubble = bubble || getStreamingBubble();
    if (!bubble) return null;
    if (!webSearchStatusEl || !bubble.contains(webSearchStatusEl)) {
        webSearchStatusEl = document.createElement('div');
        webSearchStatusEl.className = 'web-search-status hidden';
        webSearchStatusEl.innerHTML = `
            <span class="web-search-status-icon"></span>
            <span class="web-search-status-text"></span>
            <span class="web-search-status-spinner" aria-hidden="true"></span>
        `;
        const timeline = bubble.querySelector('.web-search-timeline');
        bubble.insertBefore(webSearchStatusEl, timeline || bubble.firstChild);
    }
    return webSearchStatusEl;
}

function ensureWebSearchTimelineEl(bubble) {
    bubble = bubble || getStreamingBubble();
    if (!bubble) return null;
    if (!webSearchTimelineEl || !bubble.contains(webSearchTimelineEl)) {
        webSearchTimelineEl = document.createElement('div');
        webSearchTimelineEl.className = 'web-search-timeline';
        const status = bubble.querySelector('.web-search-status');
        bubble.insertBefore(webSearchTimelineEl, status ? status.nextSibling : bubble.firstChild);
    }
    return webSearchTimelineEl;
}

function formatWebSearchStatusText(payload, cfg) {
    const provider = (payload.provider || '').trim();
    const detail = (payload.detail || '').trim();
    let text = cfg.text;
    if (payload.phase === 'analyzing') {
        text = provider ? `联网已开启（${provider}），分析检索需求` : text;
    } else if (payload.phase === 'round' && detail) {
        text = detail;
    } else if (payload.phase === 'generating') {
        text = provider ? `检索完成（${provider}），正在组织回复` : text;
    } else if (payload.phase === 'skipped' || payload.phase === 'error') {
        if (detail) text += `：${detail}`;
    }
    return text;
}

function onWebSearchStatus(payload) {
    if (!payload || payload.phase === 'end') {
        clearWebSearchStatus();
        return;
    }
    const el = ensureWebSearchStatusEl();
    if (!el) return;
    const cfg = WEB_SEARCH_STATUS_LABELS[payload.phase];
    if (!cfg) return;
    el.querySelector('.web-search-status-icon').textContent = cfg.icon;
    el.querySelector('.web-search-status-text').textContent = formatWebSearchStatusText(payload, cfg);
    el.classList.toggle('web-search-status-active', !!cfg.active);
    el.classList.remove('hidden', 'web-search-status-success', 'web-search-status-muted', 'web-search-status-error');
    if (cfg.tone === 'success') el.classList.add('web-search-status-success');
    else if (cfg.tone === 'muted') el.classList.add('web-search-status-muted');
    else if (cfg.tone === 'error') el.classList.add('web-search-status-error');
    conditionalScrollToBottom();
}

function clearWebSearchStatus() {
    try {
        if (webSearchStatusEl) {
            webSearchStatusEl.classList.add('hidden');
            webSearchStatusEl.classList.remove(
                'web-search-status-active', 'web-search-status-success',
                'web-search-status-muted', 'web-search-status-error'
            );
        }
    } catch (_) {
        webSearchStatusEl = null;
    }
}

function webSearchStepStatusLabel(step) {
    if (step.phase === 'searching' || step.status === 'searching') return '检索中…';
    const n = step.resultCount || (step.items && step.items.length) || 0;
    if (step.status === 'failed' || step.error) return '失败';
    if (n > 0) return `${n} 条`;
    return '无结果';
}

function upsertWebSearchStepRow(step, timeline) {
    if (!timeline || !step || !step.stepId) return;
    let row = timeline.querySelector(`[data-step-id="${step.stepId}"]`);
    if (!row) {
        row = document.createElement('button');
        row.type = 'button';
        row.className = 'web-search-step';
        row.dataset.stepId = step.stepId;
        row.innerHTML = `
            <span class="web-search-step-icon">🌐</span>
            <span class="web-search-step-body">
                <span class="web-search-step-label">联网检索：</span>
                <span class="web-search-step-query"></span>
            </span>
            <span class="web-search-step-meta"></span>
            <span class="web-search-step-chevron">›</span>
        `;
        row.addEventListener('click', () => openWebSearchStepDetail(row._stepData || step));
        timeline.appendChild(row);
    }
    row._stepData = step;
    row.querySelector('.web-search-step-query').textContent = step.query || '';
    const meta = row.querySelector('.web-search-step-meta');
    meta.textContent = webSearchStepStatusLabel(step);
    row.classList.toggle('web-search-step-active', step.phase === 'searching');
    row.classList.toggle('web-search-step-failed', step.status === 'failed' || !!step.error);
}

function onWebSearchStep(payload) {
    if (!payload || !payload.stepId) return;
    const timeline = ensureWebSearchTimelineEl();
    if (!timeline) return;
    const idx = currentWebSearchSteps.findIndex(s => s.stepId === payload.stepId);
    if (idx >= 0) currentWebSearchSteps[idx] = Object.assign({}, currentWebSearchSteps[idx], payload);
    else currentWebSearchSteps.push(payload);
    upsertWebSearchStepRow(payload, timeline);
    conditionalScrollToBottom();
}

function ensureCitationsBtn(bubble, citations) {
    if (!bubble || !citations || !citations.length) return null;
    let btn = bubble.querySelector('.web-search-citations-btn');
    if (!btn) {
        btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'web-search-citations-btn';
        const content = bubble.querySelector('.message-content');
        bubble.insertBefore(btn, content || null);
    }
    btn.textContent = `📖 共 ${citations.length} 条引用`;
    btn.onclick = () => openWebSearchCitationsDrawer(citations);
    return btn;
}

function renderWebSearchForBubble(bubble, steps, citations) {
    if (!bubble) return;
    bubble.querySelectorAll('.web-search-timeline, .web-search-citations-btn').forEach(el => el.remove());
    if (!steps || !steps.length) return;
    const timeline = document.createElement('div');
    timeline.className = 'web-search-timeline';
    const status = bubble.querySelector('.web-search-status');
    bubble.insertBefore(timeline, status ? status.nextSibling : bubble.firstChild);
    for (const step of steps) upsertWebSearchStepRow(step, timeline);
    ensureCitationsBtn(bubble, citations);
}

// ===== 专家模式：思考区 + 回答区（与普通深度思考同款 UI）=====

function stripScratchpadWrapper(text) {
    if (!text) return '';
    const m = String(text).match(/<scratchpad>([\s\S]*?)(?:<\/scratchpad>|$)/i);
    if (m) return m[1].trim();
    return String(text).replace(/<\/?scratchpad>/gi, '').trim();
}

function getExpertDisplayContent(payload) {
    const scratchpad = (payload.scratchpad || '').trim();
    const raw = (payload.content || '').trim();
    if (scratchpad) return scratchpad;
    return stripScratchpadWrapper(raw) || raw;
}

function renderExpertMarkdown(text) {
    const cleaned = stripScratchpadWrapper(text);
    if (!cleaned) return '';
    return `<div class="expert-markdown">${renderMarkdown(cleaned)}</div>`;
}

function ensureExpertStreamingBubble() {
    let msg = document.getElementById('streaming-msg');
    if (!msg) {
        addMessage('ai', '', true);
        msg = document.getElementById('streaming-msg');
        if (!isGenerating) setGenerating(true);
    }
    return msg;
}

function ensureExpertThinkingBlock() {
    ensureExpertStreamingBubble();
    if (!currentThinkingEl) {
        isThinking = true;
        currentThinkingEl = createThinkingBlock();
        const label = currentThinkingEl.querySelector('.thinking-label');
        if (label) label.textContent = '💭 专家思考中...';
        const msg = document.getElementById('streaming-msg');
        if (msg) {
            msg.querySelector('.thinking-area').appendChild(currentThinkingEl);
        }
    }
    return currentThinkingEl;
}

function mergeExpertScratchpadIntoBlock(block, displayText) {
    if (!block || !displayText) return;
    const cleaned = stripScratchpadWrapper(displayText);
    if (!cleaned) return;
    const prev = block._thinkingText || block.querySelector('.thinking-content')?.textContent || '';
    const probe = cleaned.substring(0, Math.min(120, cleaned.length));
    if (probe && prev.includes(probe)) return;
    block._thinkingText = prev ? `${prev}\n\n${cleaned}` : cleaned;
    let contentEl = block.querySelector('.thinking-content');
    if (!contentEl) {
        contentEl = document.createElement('div');
        contentEl.className = 'thinking-content';
        contentEl.style.fontSize = getFontSizes().thinking + 'px';
        block.appendChild(contentEl);
        block._expanded = true;
        const arrow = block.querySelector('.thinking-arrow');
        if (arrow) arrow.textContent = '\u{25BE}';
    }
    contentEl.textContent = block._thinkingText;
    expertScratchpadFinal = block._thinkingText;
}

function appendExpertThinkingText(text) {
    if (!text) return;
    const block = ensureExpertThinkingBlock();
    block._thinkingText = (block._thinkingText || '') + text;
    let contentEl = block.querySelector('.thinking-content');
    if (!contentEl) {
        contentEl = document.createElement('div');
        contentEl.className = 'thinking-content';
        contentEl.style.fontSize = getFontSizes().thinking + 'px';
        block.appendChild(contentEl);
        block._expanded = true;
        const arrow = block.querySelector('.thinking-arrow');
        if (arrow) arrow.textContent = '\u{25BE}';
    }
    contentEl.textContent = stripScratchpadWrapper(block._thinkingText) || block._thinkingText;
    expertScratchpadFinal = contentEl.textContent;
    contentEl.scrollTop = contentEl.scrollHeight;
}

function beginExpertAnswerPhase() {
    expertAnswerStarted = true;
    if (currentThinkingEl) {
        const label = currentThinkingEl.querySelector('.thinking-label');
        if (label) label.textContent = '💭 专家思考 · 收敛验证';
        collapseThinking();
    }
    isThinking = false;
}

function ensureThinkingBlockFromReasoning(msg, reasoning) {
    const area = msg.querySelector('.thinking-area');
    if (!area || area.querySelector('.thinking-block')) return;

    const cleaned = stripScratchpadWrapper(reasoning);
    if (!cleaned) return;

    const block = document.createElement('div');
    block.className = 'thinking-block';
    block._expanded = false;
    block._thinkingText = cleaned;
    const thinkingSize = getFontSizes().thinking;
    block.innerHTML = `
        <div class="thinking-header" style="font-size:${thinkingSize}px">
            <span class="thinking-label">💭 思考过程</span>
            <button class="thinking-copy-btn" title="复制思考内容">📋</button>
            <span class="thinking-arrow">\u{25B8}</span>
        </div>
    `;
    block.querySelector('.thinking-header').addEventListener('click', () => toggleThinking(block));
    block.querySelector('.thinking-copy-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        copyMessageText(cleaned);
    });
    area.appendChild(block);
}

function onExpertStage(payload) {
    if (!payload) return;
    expertPipelineActive = true;
    ensureExpertStreamingBubble();

    const { stageId, label, status, content, scratchpad } = payload;

    if (stageId === 'stage3') {
        if (status === 'running') {
            beginExpertAnswerPhase();
        } else if (status === 'error' && content) {
            beginExpertAnswerPhase();
            const msg = document.getElementById('streaming-msg');
            const contentDiv = msg?.querySelector('.message-content');
            if (contentDiv) {
                const cursor = contentDiv.querySelector('.cursor');
                if (cursor) cursor.remove();
                contentDiv.textContent = content;
            }
        }
        conditionalScrollToBottom();
        return;
    }

    if (status === 'running') {
        ensureExpertThinkingBlock();
        const hdr = currentThinkingEl?.querySelector('.thinking-label');
        if (hdr) hdr.textContent = `💭 专家思考 · ${label || stageId}`;
        appendExpertThinkingText(`\n\n━━ ${label || stageId} ━━\n`);
    } else if (status === 'done') {
        const displayText = getExpertDisplayContent(payload);
        if (currentThinkingEl && displayText) {
            mergeExpertScratchpadIntoBlock(currentThinkingEl, displayText);
        } else if (displayText) {
            expertScratchpadFinal = stripScratchpadWrapper(displayText) || displayText;
        }
        if (stageId === 'stage1' || stageId === 'stage2') {
            expertStagesDone += 1;
        }
        if (currentThinkingEl) {
            const hdr = currentThinkingEl.querySelector('.thinking-label');
            if (hdr) {
                hdr.textContent = stageId === 'stage2'
                    ? '💭 专家思考 · 解构 + 发散'
                    : `💭 专家思考 · ${label || stageId}`;
            }
        }
    } else if (status === 'error' && content) {
        appendExpertThinkingText(`\n[${label || stageId} 出错] ${content}\n`);
    }

    conditionalScrollToBottom();
}

function onExpertStageToken(payload) {
    if (!payload || !payload.stageId || !payload.token) return;
    if (payload.stageId === 'stage3') return;
    expertPipelineActive = true;
    ensureExpertStreamingBubble();
    appendExpertThinkingText(payload.token);
    conditionalScrollToBottom();
}

// 旧回调兼容（后端可能仍调用）
function onExpertProgress(payload) {
    // 如果是 done/error 阶段且没有 stage 数据，忽略
    if (payload && payload.phase) {
        onExpertStage({
            stageId: payload.phase,
            label: payload.detail || payload.phase,
            icon: '📌',
            status: payload.phase === 'error' ? 'error' : 'done',
            content: '',
            scratchpad: '',
        });
    }
}
window.onExpertStage = onExpertStage;
window.onExpertStageToken = onExpertStageToken;
window.onExpertProgress = onExpertProgress;

function resetExpertSessionState() {
    expertPipelineActive = false;
    expertAnswerStarted = false;
    expertScratchpadFinal = '';
    expertStagesDone = 0;
}

function finalizeExpertThinkingBlock(msg, reasoning) {
    if (!msg || !reasoning) return;
    const area = msg.querySelector('.thinking-area');
    if (!area) return;
    let thinkBlock = area.querySelector('.thinking-block');
    const cleaned = stripScratchpadWrapper(reasoning);
    if (!cleaned) return;
    if (thinkBlock) {
        mergeExpertScratchpadIntoBlock(thinkBlock, cleaned);
    } else {
        ensureThinkingBlockFromReasoning(msg, cleaned);
        thinkBlock = area.querySelector('.thinking-block');
    }
    if (!thinkBlock) return;
    const openContent = thinkBlock.querySelector('.thinking-content');
    if (openContent) {
        thinkBlock._thinkingText = openContent.textContent;
        openContent.remove();
        thinkBlock._expanded = false;
    } else if (!thinkBlock._thinkingText) {
        thinkBlock._thinkingText = cleaned;
    }
    const lbl = thinkBlock.querySelector('.thinking-label');
    const arr = thinkBlock.querySelector('.thinking-arrow');
    if (lbl) {
        lbl.textContent = expertStagesDone >= 2
            ? '💭 专家思考 · 解构 → 发散 → 收敛'
            : '💭 专家思考过程';
    }
    if (arr) arr.textContent = '\u{25B8}';
}

// ===== 群聊专家会议 =====

const COUNCIL_ROLE_LABELS = {
    expert: '专家',
    red_team: '红队',
    synthesizer: '架构师',
};

function insertCouncilRoundHeader(payload) {
    if (!payload || payload.status !== 'running') return;
    const existing = chatMessages.querySelector(`[data-council-round="${payload.roundId}"]`);
    if (existing) return;
    const header = document.createElement('div');
    header.className = 'council-round-header';
    header.dataset.councilRound = payload.roundId;
    header.innerHTML = `
        <span class="council-round-icon">${payload.icon || '📌'}</span>
        <span class="council-round-label">${escapeHtml(payload.label || payload.roundId)}</span>
        <button type="button" class="council-blackboard-btn" title="查看共享黑板">📋 黑板</button>`;
    header.querySelector('.council-blackboard-btn')?.addEventListener('click', () => {
        if (councilBlackboardData) showCouncilBlackboardOverlay(councilBlackboardData);
    });
    chatMessages.appendChild(header);
    conditionalScrollToBottom();
}

function appendCouncilBadge(bubble, payload) {
    if (!bubble || !payload) return;
    let badge = bubble.querySelector('.council-speaker-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.className = 'council-speaker-badge';
        bubble.insertBefore(badge, bubble.firstChild);
    }
    const roleLabel = COUNCIL_ROLE_LABELS[payload.role] || payload.role || '';
    const sysTag = payload.systemRole ? ' · 系统' : '';
    const conf = payload.confidence != null ? ` · 置信 ${payload.confidence}` : '';
    const basis = payload.basis ? ` · ${payload.basis}` : '';
    badge.textContent = `${roleLabel}${sysTag}${conf}${basis}`;
}

function onCouncilStart(payload) {
    councilPipelineActive = true;
    if (payload?.topic && typeof showToast === 'function') {
        showToast(`专家会议开始：${payload.topic.slice(0, 40)}`);
    }
}

function onCouncilRound(payload) {
    if (!payload) return;
    councilPipelineActive = true;
    if (payload.status === 'running') insertCouncilRoundHeader(payload);
    conditionalScrollToBottom();
}

function onCouncilSpeaker(payload) {
    if (!payload) return;
    councilPipelineActive = true;
    const botId = payload.botId;
    let bot = null;
    if (botId && cachedConfig) {
        bot = (cachedConfig.bots || []).find(b => b.id === botId) || null;
    }
    if (!bot && payload.botName) {
        bot = { id: botId || '__system__', name: payload.botName, avatar: payload.avatar || '⚙' };
    }
    if (payload.status === 'running') {
        if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = bot;
        addMessage('ai', '', true);
        const row = document.getElementById('streaming-msg');
        if (row) {
            row.dataset.councilRound = payload.roundId || '';
            row.dataset.councilRole = payload.role || '';
        }
    } else if (payload.status === 'done') {
        const row = document.getElementById('streaming-msg');
        const contentDiv = row?.querySelector('.message-content');
        let content = contentDiv ? contentDiv.textContent.replace(/█$/, '').trim() : '';
        if (row) {
            row.removeAttribute('id');
            const cursor = row.querySelector('.cursor');
            if (cursor) cursor.remove();
            if (contentDiv) {
                contentDiv.classList.remove('collapsible');
                contentDiv.innerHTML = renderGroupContent(content);
            }
            appendCouncilBadge(row.querySelector('.message-bubble'), payload);
        }
        if (content) {
            conversationHistory.push({
                role: 'assistant',
                content,
                speaker_bot_id: botId || undefined,
                council_round: payload.roundId,
                council_role: payload.role,
                confidence: payload.confidence,
                basis: payload.basis,
                system_role: payload.systemRole,
            });
        }
        if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = null;
    }
    conditionalScrollToBottom();
}

function onCouncilToken(payload) {
    if (!payload || !payload.token) return;
    const msg = document.getElementById('streaming-msg');
    const contentDiv = msg?.querySelector('.message-content');
    if (!contentDiv) return;
    const cursor = contentDiv.querySelector('.cursor');
    const prefix = cursor
        ? contentDiv.textContent.slice(0, -1)
        : contentDiv.textContent;
    contentDiv.textContent = prefix + payload.token;
    if (cursor) contentDiv.appendChild(cursor);
    conditionalScrollToBottom();
}

function onCouncilBlackboard(data) {
    councilBlackboardData = data;
}

function showCouncilBlackboardOverlay(data) {
    let overlay = document.getElementById('scratchpad-overlay');
    if (!overlay) {
        if (typeof ensureScratchpadOverlay === 'function') ensureScratchpadOverlay();
        overlay = document.getElementById('scratchpad-overlay');
    }
    if (!overlay) return;
    const title = overlay.querySelector('.scratchpad-sheet-title');
    const body = overlay.querySelector('.scratchpad-sheet-body');
    if (title) title.textContent = `📋 共享黑板 v${data?.Context_Version || 1}`;
    if (body) {
        const sections = [
            ['Current_Consensus', '当前共识'],
            ['Open_Divergences', '开放分歧'],
            ['Falsified_Hypotheses', '已证伪假设'],
            ['Key_Constraints', '关键约束'],
            ['Escalated_Disputes', '升级分歧'],
        ];
        let html = '';
        for (const [key, label] of sections) {
            const items = data?.[key] || [];
            if (!items.length) continue;
            html += `<h4>${escapeHtml(label)}</h4><ul>`;
            for (const item of items) {
                html += `<li>${escapeHtml(item)}</li>`;
            }
            html += '</ul>';
        }
        if (data?.Last_Warning) {
            html += `<p class="council-blackboard-warn">⚠ ${escapeHtml(data.Last_Warning)}</p>`;
        }
        body.innerHTML = html || '<p class="scratchpad-empty">黑板暂无内容</p>';
    }
    overlay.classList.remove('hidden');
}

function showCouncilArbitrationModal(payload) {
    councilAwaitingArbitration = true;
    councilSelectedOptionIndex = 0;
    const modal = document.getElementById('council-arbitration-modal');
    const optsEl = document.getElementById('council-arbitration-options');
    const recEl = document.getElementById('council-arbitration-recommendation');
    if (!modal || !optsEl) return;
    const options = payload?.options || [];
    optsEl.innerHTML = '';
    if (options.length) {
        options.forEach((opt, i) => {
            const label = document.createElement('label');
            label.className = 'council-arbitration-option';
            label.innerHTML = `
                <input type="radio" name="council-option" value="${i}" ${i === 0 ? 'checked' : ''}>
                <span>${escapeHtml(opt)}</span>`;
            label.querySelector('input')?.addEventListener('change', (e) => {
                councilSelectedOptionIndex = parseInt(e.target.value, 10);
            });
            optsEl.appendChild(label);
        });
    } else {
        optsEl.innerHTML = '<p class="form-hint">（未解析到独立方案，将使用架构师推荐）</p>';
    }
    if (recEl) {
        recEl.innerHTML = payload?.recommendation
            ? `<strong>推荐：</strong>${escapeHtml(payload.recommendation)}`
            : '';
    }
    modal.classList.remove('hidden');
    setGenerating(false);
}

function hideCouncilArbitrationModal() {
    document.getElementById('council-arbitration-modal')?.classList.add('hidden');
    councilAwaitingArbitration = false;
}

async function submitCouncilArbitration(action) {
    hideCouncilArbitrationModal();
    setGenerating(true);
    try {
        const resultStr = await pywebview.api.council_arbitration(action, councilSelectedOptionIndex);
        const result = JSON.parse(resultStr);
        if (!result.ok && result.msg) showToast(result.msg);
    } catch (e) {
        showToast('仲裁请求失败');
        setGenerating(false);
    }
}

function onCouncilArbitration(payload) {
    showCouncilArbitrationModal(payload || {});
}

function onCouncilDone(payload) {
    councilPipelineActive = false;
    councilAwaitingArbitration = false;
    hideCouncilArbitrationModal();
    const msg = document.getElementById('streaming-msg');
    if (msg) {
        msg.removeAttribute('id');
        msg.querySelector('.cursor')?.remove();
    }
    if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = null;
    setGenerating(false);
    if (payload?.ok === false && payload.msg) {
        showToast(payload.msg);
        return;
    }
    if (payload?.interrupted) {
        showToast('专家会议已中断，已保留部分产出');
    } else if (payload?.content) {
        showToast('专家会议已完成');
    }
    conditionalScrollToBottom();
}

window.onCouncilStart = onCouncilStart;
window.onCouncilRound = onCouncilRound;
window.onCouncilSpeaker = onCouncilSpeaker;
window.onCouncilToken = onCouncilToken;
window.onCouncilBlackboard = onCouncilBlackboard;
window.onCouncilArbitration = onCouncilArbitration;
window.onCouncilDone = onCouncilDone;
window.toggleCouncilMode = toggleCouncilMode;
window.resetCouncilMode = resetCouncilMode;

// ===== 草稿纸浮层 =====

function ensureScratchpadOverlay() {
    let overlay = document.getElementById('scratchpad-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'scratchpad-overlay';
        overlay.className = 'scratchpad-overlay hidden';
        overlay.innerHTML = `
            <div class="scratchpad-sheet" role="dialog">
                <div class="scratchpad-sheet-header">
                    <span class="scratchpad-sheet-title">📝 草稿纸</span>
                    <button type="button" class="scratchpad-sheet-close" aria-label="关闭">✕</button>
                </div>
                <div class="scratchpad-sheet-body"></div>
            </div>
        `;
        overlay.querySelector('.scratchpad-sheet-close').addEventListener('click', closeScratchpadOverlay);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeScratchpadOverlay(); });
        document.body.appendChild(overlay);
    }
    return overlay;
}

function openScratchpadOverlay(content) {
    const overlay = ensureScratchpadOverlay();
    const body = overlay.querySelector('.scratchpad-sheet-body');
    const cleaned = stripScratchpadWrapper(content);
    if (cleaned) {
        body.innerHTML = renderExpertMarkdown(cleaned);
    } else {
        body.innerHTML = '<p class="scratchpad-empty">暂无草稿纸内容</p>';
    }
    overlay.classList.remove('hidden');
}

function closeScratchpadOverlay() {
    const overlay = document.getElementById('scratchpad-overlay');
    if (overlay) overlay.classList.add('hidden');
}

function resetWebSearchSessionState() {
    currentWebSearchSteps = [];
    currentWebSearchCitations = [];
    webSearchTimelineEl = null;
}

function ensureWebSearchOverlay() {
    let overlay = document.getElementById('web-search-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'web-search-overlay';
        overlay.className = 'web-search-overlay hidden';
        overlay.innerHTML = `
            <div class="web-search-sheet" role="dialog">
                <div class="web-search-sheet-header">
                    <span class="web-search-sheet-title"></span>
                    <button type="button" class="web-search-sheet-close" aria-label="关闭">✕</button>
                </div>
                <div class="web-search-sheet-body"></div>
            </div>
        `;
        overlay.querySelector('.web-search-sheet-close').addEventListener('click', closeWebSearchOverlay);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeWebSearchOverlay(); });
        document.body.appendChild(overlay);
    }
    return overlay;
}

function closeWebSearchOverlay() {
    const overlay = document.getElementById('web-search-overlay');
    if (overlay) overlay.classList.add('hidden');
}

function openWebSearchStepDetail(step) {
    const overlay = ensureWebSearchOverlay();
    const title = overlay.querySelector('.web-search-sheet-title');
    const body = overlay.querySelector('.web-search-sheet-body');
    title.textContent = `🌐 联网检索：${step.query || ''}`;
    const items = step.items || [];
    let cards = '';
    if (items.length) {
        cards = items.map(it => `
            <div class="web-search-result-card">
                <div class="web-search-result-title">${escapeHtml(it.title || '')}</div>
                <div class="web-search-result-snippet">${escapeHtml(it.snippet || '')}</div>
                ${it.url ? `<a class="web-search-result-url" href="${escapeHtml(it.url)}" target="_blank" rel="noopener">${escapeHtml(it.url)}</a>` : ''}
            </div>
        `).join('');
    } else {
        cards = `<p class="web-search-empty">${escapeHtml(step.error || '无有效结果')}</p>`;
    }
    body.innerHTML = `
        <div class="web-search-detail-section">
            <div class="web-search-detail-label">参数</div>
            <pre class="web-search-detail-code">${escapeHtml(JSON.stringify(step.params || { query: step.query }, null, 2))}</pre>
        </div>
        <div class="web-search-detail-section">
            <div class="web-search-detail-label">结果</div>
            ${cards}
        </div>
        <details class="web-search-raw-details">
            <summary>查看原始数据</summary>
            <pre class="web-search-detail-code">${escapeHtml(JSON.stringify({ params: step.params, items: step.items, textPreview: step.textPreview }, null, 2))}</pre>
        </details>
    `;
    overlay.classList.remove('hidden');
}

function openWebSearchCitationsDrawer(citations) {
    const overlay = ensureWebSearchOverlay();
    const title = overlay.querySelector('.web-search-sheet-title');
    const body = overlay.querySelector('.web-search-sheet-body');
    title.textContent = `📖 引用（共 ${citations.length} 条）`;
    body.innerHTML = citations.map(c => `
        <div class="web-search-citation-card">
            <span class="web-search-citation-index">${c.index}</span>
            <div class="web-search-citation-body">
                <div class="web-search-citation-title">${escapeHtml(c.title || '')}</div>
                <div class="web-search-citation-snippet">${escapeHtml(c.snippet || '')}</div>
                <a class="web-search-result-url" href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${escapeHtml(c.url)}</a>
            </div>
        </div>
    `).join('');
    overlay.classList.remove('hidden');
}

// ===== Python 回调 =====

function onReasoningToken(token) {
    if (expertPipelineActive && !expertAnswerStarted) {
        appendExpertThinkingText(token);
        conditionalScrollToBottom();
        if (typeof updateContextBarIncremental === 'function') {
            updateContextBarIncremental(token.length);
        }
        return;
    }
    if (!isThinking) {
        isThinking = true;
        currentThinkingEl = createThinkingBlock();
        const msg = document.getElementById('streaming-msg');
        if (msg) {
            msg.querySelector('.thinking-area').appendChild(currentThinkingEl);
        }
    }
    const contentEl = currentThinkingEl.querySelector('.thinking-content');
    if (contentEl) {
        contentEl.textContent += token;
        contentEl.scrollTop = contentEl.scrollHeight;
    }
    // 本地累加上下文 token
    if (typeof updateContextBarIncremental === 'function') {
        updateContextBarIncremental(token.length);
    }
    conditionalScrollToBottom();
}

function onToken(token) {
    if (expertPipelineActive) {
        ensureExpertStreamingBubble();
    }
    if (isThinking && !expertAnswerStarted) {
        isThinking = false;
        collapseThinking();
    }

    const msg = document.getElementById('streaming-msg');
    if (!msg) return;
    const content = msg.querySelector('.message-content');
    const cursor = content.querySelector('.cursor');
    content.insertBefore(document.createTextNode(token), cursor);
    // 本地累加上下文 token
    if (typeof updateContextBarIncremental === 'function') {
        updateContextBarIncremental(token.length);
    }
    // 检测内容溢出 → 显示展开按钮
    if (content.scrollHeight > content.clientHeight) {
        const expandBtn = msg.querySelector('.expand-btn');
        if (expandBtn && expandBtn.classList.contains('hidden')) {
            expandBtn.classList.remove('hidden');
        }
    }
    conditionalScrollToBottom();
}

async function onStreamDone(resultJson) {
    const msg = document.getElementById('streaming-msg');
    if (!msg) {
        resetExpertSessionState();
        setGenerating(false);
        if (resultJson?.content && typeof showToast === 'function') {
            showToast('专家模式已完成，但界面未找到流式消息容器');
        }
        return;
    }
    const cursor = msg.querySelector('.cursor');
    if (cursor) cursor.remove();

    clearWebSearchStatus();

    const steps = resultJson && resultJson.webSearchSteps ? resultJson.webSearchSteps : currentWebSearchSteps;
    const citations = resultJson && resultJson.citations ? resultJson.citations : [];
    currentWebSearchSteps = steps || [];
    currentWebSearchCitations = citations || [];
    let bubble = msg.querySelector('.message-bubble');
    if (bubble && currentWebSearchSteps.length) {
        renderWebSearchForBubble(bubble, currentWebSearchSteps, currentWebSearchCitations);
    }

    const wasExpertRun = expertPipelineActive || expertScratchpadFinal || expertStagesDone > 0;
    let reasoning = (resultJson && resultJson.reasoning) ? resultJson.reasoning : '';
    if (!reasoning && expertScratchpadFinal) {
        reasoning = expertScratchpadFinal;
    }
    const content = resultJson && resultJson.content
        ? resultJson.content
        : msg.querySelector('.message-content').textContent;

    if (reasoning) {
        if (wasExpertRun) {
            finalizeExpertThinkingBlock(msg, reasoning);
        } else {
            ensureThinkingBlockFromReasoning(msg, reasoning);
            const thinkBlock = msg.querySelector('.thinking-block');
            if (thinkBlock) {
                const openContent = thinkBlock.querySelector('.thinking-content');
                if (openContent) {
                    thinkBlock._thinkingText = openContent.textContent;
                    openContent.remove();
                    thinkBlock._expanded = false;
                    const lbl = thinkBlock.querySelector('.thinking-label');
                    const arr = thinkBlock.querySelector('.thinking-arrow');
                    if (lbl) lbl.textContent = '💭 思考过程';
                    if (arr) arr.textContent = '\u{25B8}';
                }
            }
        }
    }

    currentThinkingEl = null;
    isThinking = false;
    resetExpertSessionState();

    // 流式结束后：移除折叠状态，重新渲染为 markdown
    const contentDiv = msg.querySelector('.message-content');
    if (contentDiv) {
        contentDiv.classList.remove('collapsible');
        // 移除展开按钮
        const expandBtn = contentDiv.parentElement.querySelector('.expand-btn');
        if (expandBtn) expandBtn.remove();
        const inGroup = typeof currentGroupSession !== 'undefined' && currentGroupSession;
        contentDiv.innerHTML = inGroup ? renderGroupContent(content) : renderMarkdown(content);
        const sizes = getFontSizes();
        contentDiv.style.fontSize = sizes.bot + 'px';
    }

    // 处理 AI 发送的文件（file:send 标记）
    let aiFiles = [];
    const fileSendMatch = content.match(/<!--file:send:path=(.+?)-->/g);
    if (fileSendMatch) {
        // 显示 loading 占位
        const bubble = msg.querySelector('.message-bubble');
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'ai-files-loading';
        loadingDiv.textContent = '⏳ 正在处理文件...';
        bubble.insertBefore(loadingDiv, contentDiv.nextSibling);

        try {
            const resultStr = await pywebview.api.process_file_sends(content);
            const result = JSON.parse(resultStr);
            if (result.ok && result.files.length) {
                aiFiles = result.files;
                renderAIFiles(bubble, aiFiles, contentDiv);
            }
        } catch (e) {
            // ignore
        }
        loadingDiv.remove();
    }

    // 编程模式：处理 file:read 标记
    if (currentMode === 'code') {
        const fileReadRegex = /file:read:path=([^\s\n:]+)(?::lines=(\d+-\d+))?/g;
        let readMatch;
        while ((readMatch = fileReadRegex.exec(content)) !== null) {
            const filePath = readMatch[1];
            const linesRange = readMatch[2] || null;
            try {
                const resultStr = await pywebview.api.handle_file_read(filePath, linesRange);
                const result = JSON.parse(resultStr);
                if (result.ok) {
                    const bubble = msg.querySelector('.message-bubble');
                    const record = document.createElement('div');
                    record.className = 'file-op-record file-op-read';
                    record.innerHTML = `<span class="file-op-icon">📖</span> <span class="file-op-text">读取 ${escapeHtml(result.path)}（${result.lines} 行）</span>`;
                    record.addEventListener('click', () => previewFile(result.path));
                    bubble.insertBefore(record, contentDiv.nextSibling);
                }
            } catch (e) {
                // ignore
            }
        }
    }

    // 群聊空回复：先快速模式重试一次，仍空则跳过并中断接话链
    const isGroupEmptyReply = typeof currentGroupSession !== 'undefined' && currentGroupSession
        && !(content && content.trim()) && (!aiFiles || !aiFiles.length);
    if (isGroupEmptyReply) {
        msg.querySelector('.msg-actions')?.remove();
        if (typeof groupEmptyRetried !== 'undefined' && !groupEmptyRetried
            && typeof retryGroupBotReply === 'function' && groupReplySpeaker) {
            groupEmptyRetried = true;
            msg.remove();
            if (typeof showToast === 'function') showToast('无有效回复，正在快速模式重试…');
            retryGroupBotReply();
            return;
        }
        if (typeof groupReplyQueue !== 'undefined') groupReplyQueue = [];
        if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = null;
        if (typeof resetGroupChainState === 'function') resetGroupChainState();
        msg.remove();
        if (typeof showToast === 'function') showToast('该成员本轮无有效回复，已跳过');
        setGenerating(false);
        if (typeof refreshContextUsage === 'function') refreshContextUsage();
        return;
    }

    // 添加操作按钮（复制 + 重新回答）
    bubble = msg.querySelector('.message-bubble');
    if (bubble) {
        const actions = document.createElement('div');
        actions.className = 'msg-actions';
        const copyBtn = document.createElement('button');
        copyBtn.className = 'msg-action-btn';
        copyBtn.textContent = '📋 复制';
        copyBtn.addEventListener('click', () => copyMessageText(content));
        actions.appendChild(copyBtn);
        const regenBtn = document.createElement('button');
        regenBtn.className = 'msg-action-btn regen-btn';
        regenBtn.textContent = '↻ 重新回答';
        regenBtn.addEventListener('click', regenerateLastResponse);
        actions.appendChild(regenBtn);
        bubble.appendChild(actions);
    }

    // 保存历史时清除 AI 文件中的 base64
    const historyFiles = aiFiles.map(f => ({
        name: f.name, path: f.path, size: f.size, ext: f.ext,
        is_image: f.is_image, is_text: f.is_text
    }));
    let finalContent = content;
    const assistantMsg = { role: 'assistant', content: finalContent };
    if (typeof groupReplySpeaker !== 'undefined' && groupReplySpeaker) {
        assistantMsg.speaker_bot_id = groupReplySpeaker.id;
    } else {
        const prevUser = conversationHistory[conversationHistory.length - 1];
        if (prevUser && prevUser.mention_bot_id) {
            assistantMsg.speaker_bot_id = prevUser.mention_bot_id;
        }
    }
    if (reasoning) {
        assistantMsg.reasoning_content = reasoning;
    }
    if (currentWebSearchSteps.length) {
        assistantMsg.web_search_steps = currentWebSearchSteps;
    }
    if (currentWebSearchCitations.length) {
        assistantMsg.web_search_citations = currentWebSearchCitations;
    }
    if (historyFiles.length) {
        assistantMsg.ai_files = historyFiles;
    }

    const isGroupSession = typeof currentGroupSession !== 'undefined' && currentGroupSession;
    const halted = typeof isGroupReplyHalted === 'function' && isGroupReplyHalted();
    const pendingMentionChain = typeof groupReplyQueue !== 'undefined' && groupReplyQueue.length > 0;

    function applyGroupPostprocess(pp, msgEl, contentElRef) {
        if (!pp || !pp.ok) return;
        if (pp.content && pp.content !== finalContent) {
            finalContent = pp.content;
            assistantMsg.content = finalContent;
            if (contentElRef) {
                contentElRef.innerHTML = renderGroupContent(finalContent);
            }
        }
        assistantMsg.parsed_mention_bot_ids = pp.parsed_mention_bot_ids || [];
        assistantMsg.mention_user = !!pp.mention_user;
        if (typeof updateGroupChainStateFromPostprocess === 'function') {
            updateGroupChainStateFromPostprocess(pp);
        }
        if (!pendingMentionChain && pp.queue && pp.queue.length && typeof groupReplyQueue !== 'undefined') {
            for (const bid of pp.queue) {
                if (!groupReplyQueue.includes(bid)) {
                    groupReplyQueue.push(bid);
                }
            }
        }
    }

    if (isGroupSession && assistantMsg.speaker_bot_id && !halted) {
        const chainJson = typeof groupChainState !== 'undefined'
            ? JSON.stringify(groupChainState) : '{}';
        if (pendingMentionChain) {
            // 用户 @ 了多个 Bot：后台后处理，不阻塞下一个成员开讲
            pywebview.api.postprocess_group_assistant(
                assistantMsg.speaker_bot_id,
                finalContent,
                chainJson,
                true,
            ).then((ppStr) => {
                if (typeof isGroupReplyHalted === 'function' && isGroupReplyHalted()) return;
                try {
                    applyGroupPostprocess(JSON.parse(ppStr), msg, contentDiv);
                } catch (e) { /* ignore */ }
            }).catch(() => {});
        } else {
            try {
                const ppStr = await pywebview.api.postprocess_group_assistant(
                    assistantMsg.speaker_bot_id,
                    finalContent,
                    chainJson,
                    false,
                );
                if (typeof isGroupReplyHalted === 'function' && isGroupReplyHalted()) {
                    if (typeof groupReplyQueue !== 'undefined') groupReplyQueue = [];
                } else {
                    applyGroupPostprocess(JSON.parse(ppStr), msg, contentDiv);
                }
            } catch (e) {
                // 后处理失败时仍保存原文
            }
        }
    }

    conversationHistory.push(assistantMsg);
    msg.removeAttribute('id');

    if (halted || (typeof isGroupReplyHalted === 'function' && isGroupReplyHalted())) {
        if (typeof groupReplyQueue !== 'undefined') groupReplyQueue = [];
        if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = null;
        if (isGroupSession && assistantMsg.content) {
            await pywebview.api.save_assistant_message(JSON.stringify(assistantMsg));
            if (typeof loadSessions === 'function') loadSessions();
        }
        setGenerating(false);
        return;
    }

    // 群聊：后续被 @ 的成员依次回复
    const isGroupMulti = isGroupSession
        && typeof groupReplyQueue !== 'undefined' && groupReplyQueue.length > 0;

    if (isGroupMulti) {
        await pywebview.api.save_assistant_message(JSON.stringify(assistantMsg));
        const apiMessages = typeof buildGroupApiMessages === 'function'
            ? buildGroupApiMessages() : conversationHistory.map(m => {
                const copy = Object.assign({}, m);
                delete copy._attachments_full;
                return copy;
            });
        if (typeof startNextGroupReply === 'function') {
            startNextGroupReply(apiMessages);
            if (typeof loadSessions === 'function') loadSessions();
            return;
        }
    }

    if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = null;
    setGenerating(false);

    // 版本管理：找到前一个 assistant 行，看是否是重新生成
    const allRows = chatMessages.querySelectorAll('.message-row');
    let prevAssistantRow = null;
    for (let i = allRows.length - 2; i >= 0; i--) {
        if (allRows[i].classList.contains('assistant')) {
            prevAssistantRow = allRows[i];
            break;
        }
    }
    if (prevAssistantRow && prevAssistantRow._versions) {
        // 重新生成场景：把新版本添加到原行
        prevAssistantRow._versions.push({ content, reasoning_content: reasoning });
        prevAssistantRow._currentVersion = prevAssistantRow._versions.length - 1;
        // 删除新的流式行，更新原行显示
        msg.remove();
        // 更新 conversationHistory 中对应的条目
        const histIdx = conversationHistory.length - 1;
        conversationHistory[histIdx] = assistantMsg;
        switchVersion(prevAssistantRow, prevAssistantRow._currentVersion);
    }

    // 精确刷新上下文进度条
    if (typeof refreshContextUsage === 'function') {
        refreshContextUsage();
    }

    if (typeof currentGroupSession !== 'undefined' && currentGroupSession) {
        // 群聊：用户消息已在发送时持久化，这里只需保存助手消息。
        // 不能依赖「上一条是 user」——接话链尾部的上一条是其他 Bot 的 assistant 消息。
        await pywebview.api.save_assistant_message(JSON.stringify(assistantMsg));
        loadSessions();
    } else {
        const userMsg = conversationHistory[conversationHistory.length - 2];
        if (userMsg && userMsg.role === 'user') {
            pywebview.api.save_current_messages(JSON.stringify(userMsg), JSON.stringify(assistantMsg));
            loadSessions();
        }
    }

    // 文件操作处理
    if (currentMode === 'code') {
        // 编程模式：渲染记录块 + 确认弹窗
        parseAndRenderFileOps(content, msg);
    } else {
        parseAndConfirmOperations(content);
    }
}

function formatErrorDisplay(errorMsg) {
    let text = String(errorMsg || '').trim();
    if (!text.startsWith('❌')) text = '❌ ' + text;
    const jsonStart = text.indexOf('{');
    if (jsonStart >= 0) {
        try {
            const parsed = JSON.parse(text.slice(jsonStart));
            const inner = parsed?.error?.message || parsed?.message;
            if (inner && typeof inner === 'string') {
                return text.slice(0, jsonStart).trim() + ' ' + inner;
            }
        } catch (_) {}
    }
    return text;
}

function applyErrorToMessageRow(row, displayText) {
    row.classList.remove('assistant', 'user');
    row.classList.add('error');
    const cursor = row.querySelector('.cursor');
    if (cursor) cursor.remove();
    const contentEl = row.querySelector('.message-content');
    if (contentEl) {
        contentEl.classList.remove('collapsible', 'expanded');
        contentEl.style.maskImage = '';
        contentEl.style.webkitMaskImage = '';
        contentEl.style.maxHeight = '';
        contentEl.style.overflow = '';
        contentEl.textContent = displayText;
    }
    row.querySelector('.expand-btn')?.remove();
    row.removeAttribute('id');
}

function onError(errorMsg) {
    const display = formatErrorDisplay(errorMsg);
    const msg = document.getElementById('streaming-msg');
    if (msg) {
        applyErrorToMessageRow(msg, display);
    } else {
        addMessage('error', display);
    }
    currentThinkingEl = null;
    isThinking = false;
    clearWebSearchStatus();
    resetExpertSessionState();
    if (typeof currentGroupSession !== 'undefined' && currentGroupSession) {
        if (typeof groupReplyQueue !== 'undefined') groupReplyQueue = [];
        if (typeof resetGroupChainState === 'function') resetGroupChainState();
    }
    setGenerating(false);
    scrollToBottom();
}

// ===== 消息回退 =====

async function rollbackToMessage(row) {
    // 计算该消息在 conversationHistory 中的索引
    const allRows = Array.from(chatMessages.querySelectorAll('.message-row'));
    const rowIndex = allRows.indexOf(row);
    if (rowIndex < 0) return;

    // 统计将被移除的消息数（该消息及之后的）
    const totalRows = allRows.length;
    const removeCount = totalRows - rowIndex;
    if (removeCount <= 0) return;

    // 统计涉及的文件操作数
    let fileOpCount = 0;
    for (let i = rowIndex; i < totalRows; i++) {
        const msg = conversationHistory[i];
        if (msg && msg.content && /file:(create|edit|delete|mkdir|read):/.test(msg.content)) {
            fileOpCount++;
        }
    }

    const confirmMsg = `将移除之后的 ${removeCount} 条消息` +
        (fileOpCount > 0 ? `，涉及 ${fileOpCount} 个文件操作` : '') +
        `。\n回退的消息不会丢失，将保存到 _rollback/ 目录。`;

    if (!confirm(confirmMsg)) return;

    try {
        const resultStr = await pywebview.api.rollback_to_message(rowIndex);
        const result = JSON.parse(resultStr);
        if (result.ok) {
            // 更新 conversationHistory
            conversationHistory = conversationHistory.slice(0, rowIndex);
            // 重新渲染
            chatMessages.innerHTML = '';
            for (const msg of conversationHistory) {
                if (msg && msg.role) renderMessage(msg, false);
            }
            showToast(`已回退，移除了 ${result.removed} 条消息`);
            await refreshContextUsage();
        } else {
            showToast(result.msg || '回退失败');
        }
    } catch (e) {
        showToast('回退失败: ' + e.message);
    }
}

// ===== AI 文件渲染 =====

function renderAIFiles(bubble, files, insertAfter) {
    const container = document.createElement('div');
    container.className = 'ai-files';
    for (const f of files) {
        if (f.is_image && f.base64) {
            const card = document.createElement('div');
            card.className = 'ai-file-card ai-file-image';
            const img = document.createElement('img');
            img.src = f.base64;
            img.alt = f.name;
            img.addEventListener('click', () => window.open(f.base64, '_blank'));
            card.appendChild(img);
            const info = document.createElement('div');
            info.className = 'ai-file-info';
            info.innerHTML = `<span class="ai-file-name">${escapeHtml(f.name)}</span><span class="ai-file-size">${formatFileSize(f.size)}</span>`;
            card.appendChild(info);
            container.appendChild(card);
        } else {
            const card = document.createElement('div');
            card.className = 'ai-file-card ai-file-doc';
            card.innerHTML = `<span class="ai-file-icon">${getFileIcon(f.name)}</span>
                <div class="ai-file-info">
                    <span class="ai-file-name">${escapeHtml(f.name)}</span>
                    <span class="ai-file-size">${formatFileSize(f.size)}</span>
                </div>`;
            container.appendChild(card);
        }
    }
    bubble.insertBefore(container, insertAfter.nextSibling);
}

function renderAIFilesFromHistory(bubble, files, insertAfter) {
    const container = document.createElement('div');
    container.className = 'ai-files';
    for (const f of files) {
        const card = document.createElement('div');
        card.className = 'ai-file-card ai-file-doc';
        card.innerHTML = `<span class="ai-file-icon">${getFileIcon(f.name)}</span>
            <div class="ai-file-info">
                <span class="ai-file-name">${escapeHtml(f.name)}</span>
                <span class="ai-file-size">${formatFileSize(f.size)}</span>
                <span class="ai-file-expired">文件已过期</span>
            </div>`;
        container.appendChild(card);
    }
    bubble.insertBefore(container, insertAfter.nextSibling);
}

// ===== 渲染消息（支持 thinking） =====

function renderMessage(msg, animate = true) {
    if (msg.role === 'user') {
        addMessage('user', msg.content, false, animate, msg.attachments);
    } else if (msg.role === 'assistant') {
        if (msg.speaker_bot_id && cachedConfig && typeof groupReplySpeaker !== 'undefined') {
            groupReplySpeaker = (cachedConfig.bots || []).find(b => b.id === msg.speaker_bot_id) || null;
        }
        const contentDiv = addMessage('ai', msg.content, false, animate);
        if (contentDiv && msg.content) {
            const inGroup = typeof currentGroupSession !== 'undefined' && currentGroupSession;
            if (inGroup) {
                contentDiv.innerHTML = renderGroupContent(msg.content);
            }
        }
        if (msg.web_search_steps && msg.web_search_steps.length) {
            renderWebSearchForBubble(
                contentDiv.parentElement,
                msg.web_search_steps,
                msg.web_search_citations || []
            );
        }
        if (typeof groupReplySpeaker !== 'undefined') groupReplySpeaker = null;
        if (msg.reasoning_content) {
            const block = document.createElement('div');
            block.className = 'thinking-block';
            block._expanded = false;
            block._thinkingText = msg.reasoning_content;
            const thinkingSize = getFontSizes().thinking;
            block.innerHTML = `
                <div class="thinking-header" style="font-size:${thinkingSize}px">
                    <span class="thinking-label">\u{1F4AD} 思考过程</span>
                    <button class="thinking-copy-btn" title="复制思考内容">📋</button>
                    <span class="thinking-arrow">\u{25B8}</span>
                </div>
            `;
            block.querySelector('.thinking-copy-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                copyMessageText(msg.reasoning_content || '');
            });
            block.querySelector('.thinking-header').addEventListener('click', () => toggleThinking(block));
            // contentDiv 的父级是 .message-bubble，再找 .thinking-area
            const bubble = contentDiv.parentElement;
            bubble.querySelector('.thinking-area').appendChild(block);
        }
        // 历史中的 AI 文件
        if (msg.ai_files && msg.ai_files.length) {
            const bubble = contentDiv.parentElement;
            renderAIFilesFromHistory(bubble, msg.ai_files, contentDiv);
        }
        // 历史中的 file:read 记录块
        if (currentMode === 'code') {
            const fileReadRegex = /file:read:path=([^\s\n:]+)(?::lines=(\d+-\d+))?/g;
            let readMatch;
            const bubble = contentDiv.parentElement;
            while ((readMatch = fileReadRegex.exec(msg.content)) !== null) {
                const filePath = readMatch[1];
                const record = document.createElement('div');
                record.className = 'file-op-record file-op-read';
                record.innerHTML = `<span class="file-op-icon">📖</span> <span class="file-op-text">读取 ${escapeHtml(filePath)}</span>`;
                record.addEventListener('click', () => previewFile(filePath));
                bubble.insertBefore(record, contentDiv.nextSibling);
            }
            // 历史中的 file:create/edit/delete/mkdir 记录块
            const fileOpRegex = /```file:(create|edit|delete|mkdir):path=([^\n]+)\n?([\s\S]*?)```/g;
            let opMatch;
            const typeIcons = { create: '📄', edit: '🔧', delete: '🗑', mkdir: '📂' };
            const typeClasses = { create: 'file-op-create', edit: 'file-op-edit', delete: 'file-op-delete', mkdir: 'file-op-scan' };
            const typeLabels = { create: '创建', edit: '修改', delete: '删除', mkdir: '新建目录' };
            while ((opMatch = fileOpRegex.exec(msg.content)) !== null) {
                const opType = opMatch[1];
                const opPath = opMatch[2].trim();
                const record = document.createElement('div');
                record.className = `file-op-record ${typeClasses[opType] || ''}`;
                record.innerHTML = `<span class="file-op-icon">${typeIcons[opType] || '📄'}</span> <span class="file-op-text">${typeLabels[opType] || opType} ${escapeHtml(opPath)}</span>`;
                if (opType !== 'delete' && opType !== 'mkdir') {
                    record.addEventListener('click', () => previewFile(opPath));
                }
                bubble.insertBefore(record, contentDiv.nextSibling);
            }
        }
    }
}
