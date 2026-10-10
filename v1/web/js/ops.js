// ===== 文件操作 + 回退 + 压缩 =====

// 文件操作确认
async function parseAndConfirmOperations(aiResponse) {
    const resultStr = await pywebview.api.parse_file_operations(aiResponse);
    const result = JSON.parse(resultStr);
    if (!result.ok || !result.operations || result.operations.length === 0) return false;

    pendingOperations = result.operations;
    await showConfirmModal(result.operations);
    return true;
}

async function showConfirmModal(operations) {
    confirmBody.innerHTML = '';

    for (const op of operations) {
        const item = document.createElement('div');
        item.className = 'confirm-item';

        const header = document.createElement('div');
        header.className = 'confirm-item-header';

        const typeTag = document.createElement('span');
        typeTag.className = `op-type ${op.type}`;
        const typeLabels = { create: '创建', edit: '修改', delete: '删除', mkdir: '新建目录' };
        typeTag.textContent = typeLabels[op.type] || op.type;
        header.appendChild(typeTag);

        const pathSpan = document.createElement('span');
        pathSpan.className = 'op-path';
        pathSpan.textContent = op.path;
        header.appendChild(pathSpan);

        item.appendChild(header);

        if (op.type === 'delete') {
            const warning = document.createElement('div');
            warning.className = 'confirm-item-warning';
            warning.textContent = '⚠️ 此操作将删除该文件（已自动备份）';
            item.appendChild(warning);
        } else if (op.type === 'edit' && op.content) {
            const diffResult = await pywebview.api.get_diff(op.path, op.content);
            const diffData = JSON.parse(diffResult);
            if (diffData.ok && diffData.diff) {
                const diffDiv = document.createElement('div');
                diffDiv.className = 'confirm-item-diff';
                renderDiff(diffDiv, diffData.diff);
                item.appendChild(diffDiv);
            }
        } else if (op.type === 'create' && op.content) {
            const preview = document.createElement('div');
            preview.className = 'confirm-item-diff';
            const lines = op.content.split('\n');
            const previewText = lines.length > 20
                ? lines.slice(0, 20).join('\n') + '\n...'
                : op.content;
            preview.textContent = previewText;
            item.appendChild(preview);
        }

        confirmBody.appendChild(item);
    }

    confirmModal.classList.remove('hidden');
}

function renderDiff(container, diffText) {
    const lines = diffText.split('\n');
    for (const line of lines) {
        const span = document.createElement('span');
        if (line.startsWith('+')) {
            span.className = 'diff-add';
        } else if (line.startsWith('-')) {
            span.className = 'diff-remove';
        }
        span.textContent = line + '\n';
        container.appendChild(span);
    }
}

async function executeOperations(ops) {
    for (const op of ops) {
        let resultStr;
        const bot = getActiveBot(cachedConfig);
        if (op.type === 'edit' && op.path === 'memory.md' && bot.soul_folder) {
            resultStr = await pywebview.api.write_memory_file(op.content);
        } else {
            resultStr = await pywebview.api.execute_file_operation(JSON.stringify(op));
        }
        const result = JSON.parse(resultStr);
        if (result.ok) {
            addMessage('ai', '✅ ' + result.msg);
            if (op.path && typeof notifyEditorDiskChanged === 'function') {
                notifyEditorDiskChanged(op.path);
            }
        } else {
            addMessage('error', '❌ ' + result.msg);
        }
    }
}

// 编程模式：渲染文件操作记录块
async function parseAndRenderFileOps(aiResponse, msgElement) {
    const resultStr = await pywebview.api.parse_file_operations(aiResponse);
    const result = JSON.parse(resultStr);
    if (!result.ok || !result.operations || result.operations.length === 0) return;

    const bubble = msgElement.querySelector('.message-bubble');
    const contentDiv = msgElement.querySelector('.message-content');
    const typeIcons = { create: '📄', edit: '🔧', delete: '🗑', mkdir: '📂' };
    const typeClasses = { create: 'file-op-create', edit: 'file-op-edit', delete: 'file-op-delete', mkdir: 'file-op-scan' };
    const typeLabels = { create: '创建', edit: '修改', delete: '删除', mkdir: '新建目录' };

    for (const op of result.operations) {
        const record = document.createElement('div');
        record.className = `file-op-record ${typeClasses[op.type] || ''}`;

        let detail = '';
        if (op.type === 'edit' && op.content) {
            // 获取 diff
            try {
                const diffResult = await pywebview.api.get_diff(op.path, op.content);
                const diffData = JSON.parse(diffResult);
                if (diffData.ok && diffData.diff) {
                    const diffLines = diffData.diff.split('\n').slice(0, 8);
                    detail = '\n' + diffLines.map(l => {
                        if (l.startsWith('+')) return `    <span style="color:#22c55e">${escapeHtml(l)}</span>`;
                        if (l.startsWith('-')) return `    <span style="color:#ef4444">${escapeHtml(l)}</span>`;
                        return `    ${escapeHtml(l)}`;
                    }).join('\n');
                }
            } catch (e) { /* ignore */ }
        }

        record.innerHTML = `<span class="file-op-icon">${typeIcons[op.type] || '📄'}</span> <span class="file-op-text">${typeLabels[op.type] || op.type} ${escapeHtml(op.path)}</span>`;
        if (detail) {
            const detailDiv = document.createElement('div');
            detailDiv.className = 'file-op-detail';
            detailDiv.innerHTML = detail;
            detailDiv.style.cssText = 'font-size:11px;color:var(--text-secondary);margin-top:4px;white-space:pre;font-family:monospace;line-height:1.4;';
            record.appendChild(detailDiv);
        }

        // 点击跳转预览
        if (op.type !== 'delete' && op.type !== 'mkdir') {
            record.addEventListener('click', () => previewFile(op.path));
        }

        bubble.insertBefore(record, contentDiv.nextSibling);
    }

    // 仍然显示确认弹窗
    pendingOperations = result.operations;
    await showConfirmModal(result.operations);
}

// 文件回退
async function showRollbackModal() {
    const resultStr = await pywebview.api.get_backup_list();
    const result = JSON.parse(resultStr);

    rollbackBody.innerHTML = '';

    if (!result.ok || !result.backups || result.backups.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'rollback-body-empty';
        empty.textContent = '暂无备份记录';
        rollbackBody.appendChild(empty);
        rollbackModal.classList.remove('hidden');
        return;
    }

    for (const backup of result.backups) {
        const item = document.createElement('div');
        item.className = 'rollback-item';
        item.dataset.backupPath = backup.backup_path;
        item.dataset.originalPath = backup.original_path;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        item.appendChild(checkbox);

        const info = document.createElement('div');
        info.className = 'rollback-item-info';

        const pathDiv = document.createElement('div');
        pathDiv.className = 'rollback-item-path';
        pathDiv.textContent = backup.original_path;
        info.appendChild(pathDiv);

        const metaDiv = document.createElement('div');
        metaDiv.className = 'rollback-item-meta';
        metaDiv.textContent = backup.time;
        info.appendChild(metaDiv);

        item.appendChild(info);

        item.addEventListener('click', (e) => {
            if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
            }
            item.classList.toggle('selected', checkbox.checked);
        });

        rollbackBody.appendChild(item);
    }

    rollbackModal.classList.remove('hidden');
}
