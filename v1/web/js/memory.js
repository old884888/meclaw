// ===== 记忆库管理（状态面板） =====

const MEMORY_TYPE_LABELS = {
    fact: '事实',
    preference: '偏好',
    project: '项目',
    relationship: '关系',
    quote: '好句',
};

async function refreshMemoryPanel() {
    const entriesEl = document.getElementById('memory-entries-list');
    const itemsEl = document.getElementById('memory-items-list');
    const docsEl = document.getElementById('memory-docs-list');
    const emptyEl = document.getElementById('memory-empty-hint');
    const hintEl = document.getElementById('memory-panel-hint');
    if (!itemsEl) return;

    if (entriesEl) entriesEl.innerHTML = '';
    itemsEl.innerHTML = '';
    if (docsEl) docsEl.innerHTML = '';

    try {
        // Load entries (new format)
        let entries = [];
        try {
            const entriesStr = await pywebview.api.list_memory_entries(50);
            const entriesRes = JSON.parse(entriesStr);
            if (entriesRes.ok) entries = entriesRes.entries || [];
        } catch (e) { /* API may not exist yet */ }

        const itemsStr = await pywebview.api.list_memory_items(80);
        const itemsRes = JSON.parse(itemsStr);
        if (!itemsRes.ok) {
            if (hintEl) hintEl.textContent = itemsRes.msg || '无法加载记忆';
            if (emptyEl) emptyEl.classList.remove('hidden');
            return;
        }

        const docsStr = await pywebview.api.list_memory_docs(20);
        const docsRes = JSON.parse(docsStr);
        const items = itemsRes.items || [];
        const docs = docsRes.ok ? (docsRes.docs || []) : [];

        if (emptyEl) emptyEl.classList.toggle('hidden', entries.length > 0 || items.length > 0 || docs.length > 0);
        if (hintEl) {
            hintEl.textContent = `记忆 ${entries.length} · 条目 ${items.length} · 收藏 ${docs.length}`;
        }

        // Render entries (new format)
        if (entriesEl && entries.length) {
            const sectionTitle = document.createElement('div');
            sectionTitle.className = 'memory-docs-title';
            sectionTitle.textContent = '记忆文档';
            entriesEl.appendChild(sectionTitle);

            for (const entry of entries) {
                const row = document.createElement('div');
                row.className = 'memory-list-item memory-entry-item';
                const typeLabel = MEMORY_TYPE_LABELS[entry.type] || entry.type;
                const title = entry.title || entry.id;
                const desc = (entry.summary || '').slice(0, 80);
                const points = entry.points || [];
                const keywords = entry.keywords || '';
                const related = entry.related || [];

                let detailHtml = '';
                if (points.length) {
                    detailHtml += '<div class="memory-entry-points">' +
                        points.map(p => `<div class="memory-entry-point">- ${escapeHtml(p)}</div>`).join('') +
                        '</div>';
                }
                if (keywords) {
                    detailHtml += `<div class="memory-entry-keywords">关键词: ${escapeHtml(keywords)}</div>`;
                }
                if (related.length) {
                    detailHtml += `<div class="memory-entry-related">关联: ${related.map(r => escapeHtml(r)).join(', ')}</div>`;
                }

                row.innerHTML = `
                    <div class="memory-list-main">
                        <span class="memory-type-badge entry">${escapeHtml(typeLabel)}</span>
                        <span class="memory-list-text" title="${escapeHtml(desc)}">${escapeHtml(title)}</span>
                        <span class="memory-entry-date">${escapeHtml(entry.created_at || '')}</span>
                    </div>
                    <button type="button" class="memory-del-btn" title="删除">✕</button>
                    ${detailHtml ? `<div class="memory-entry-detail hidden">${detailHtml}</div>` : ''}
                `;

                // Click to expand/collapse
                const mainEl = row.querySelector('.memory-list-main');
                const detailEl = row.querySelector('.memory-entry-detail');
                if (mainEl && detailEl) {
                    mainEl.style.cursor = 'pointer';
                    mainEl.addEventListener('click', () => {
                        detailEl.classList.toggle('hidden');
                    });
                }

                row.querySelector('.memory-del-btn').addEventListener('click', async () => {
                    if (!confirm(`删除记忆「${title}」？`)) return;
                    const r = JSON.parse(await pywebview.api.delete_memory_entry(entry.id));
                    if (r.ok) await refreshMemoryPanel();
                    else if (typeof showToast === 'function') showToast(r.msg || '删除失败');
                });
                entriesEl.appendChild(row);
            }
        }

        // Render legacy items
        if (items.length) {
            const sectionTitle = document.createElement('div');
            sectionTitle.className = 'memory-docs-title';
            sectionTitle.textContent = entries.length ? '旧格式条目' : '';
            if (sectionTitle.textContent) itemsEl.appendChild(sectionTitle);
        }
        for (const item of items) {
            const row = document.createElement('div');
            row.className = 'memory-list-item';
            const typeLabel = MEMORY_TYPE_LABELS[item.type] || item.type;
            const text = (item.summary || item.content || '').slice(0, 120);
            row.innerHTML = `
                <div class="memory-list-main">
                    <span class="memory-type-badge">${escapeHtml(typeLabel)}</span>
                    <span class="memory-list-text" title="${escapeHtml(item.content || '')}">${escapeHtml(text)}</span>
                </div>
                <button type="button" class="memory-del-btn" title="删除">✕</button>
            `;
            row.querySelector('.memory-del-btn').addEventListener('click', async () => {
                if (!confirm('删除这条记忆？')) return;
                const r = JSON.parse(await pywebview.api.delete_memory_item(item.id, item.type));
                if (r.ok) await refreshMemoryPanel();
                else if (typeof showToast === 'function') showToast(r.msg || '删除失败');
            });
            itemsEl.appendChild(row);
        }

        if (docsEl && docs.length) {
            const title = document.createElement('div');
            title.className = 'memory-docs-title';
            title.textContent = '长文收藏';
            docsEl.appendChild(title);
            for (const doc of docs) {
                const row = document.createElement('div');
                row.className = 'memory-list-item';
                const text = (doc.title || doc.slug) + (doc.chunk_count ? ` (${doc.chunk_count} 段)` : '');
                row.innerHTML = `
                    <div class="memory-list-main">
                        <span class="memory-type-badge doc">收藏</span>
                        <span class="memory-list-text" title="${escapeHtml(doc.summary || '')}">${escapeHtml(text)}</span>
                    </div>
                    <button type="button" class="memory-del-btn" title="删除">✕</button>
                `;
                row.querySelector('.memory-del-btn').addEventListener('click', async () => {
                    if (!confirm(`删除收藏「${doc.title || doc.slug}」？`)) return;
                    const r = JSON.parse(await pywebview.api.delete_memory_document(doc.slug));
                    if (r.ok) await refreshMemoryPanel();
                    else if (typeof showToast === 'function') showToast(r.msg || '删除失败');
                });
                docsEl.appendChild(row);
            }
        }
    } catch (e) {
        if (hintEl) hintEl.textContent = '加载记忆失败';
    }
}

async function openMemoryFolder() {
    try {
        const r = JSON.parse(await pywebview.api.open_memory_folder());
        if (!r.ok && typeof showToast === 'function') showToast(r.msg || '无法打开文件夹');
    } catch (e) {
        if (typeof showToast === 'function') showToast('无法打开文件夹');
    }
}
