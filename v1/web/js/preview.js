// ===== 文件预览（编程模式可编辑）=====

const PREVIEW_MAX_LINES = 2000;

// 语言映射（保留供后续扩展）
const LANG_MAP = {
    '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.html': 'html',
    '.htm': 'html', '.css': 'css', '.json': 'json', '.md': 'markdown',
    '.yaml': 'yaml', '.yml': 'yaml', '.sh': 'bash', '.bash': 'bash',
    '.sql': 'sql', '.go': 'go', '.rs': 'rust', '.java': 'java',
    '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.toml': 'ini',
    '.ini': 'ini', '.cfg': 'ini', '.xml': 'xml', '.vue': 'html',
    '.ps1': 'powershell', '.bat': 'batch'
};

function getLang(filename) {
    const ext = '.' + filename.split('.').pop().toLowerCase();
    return LANG_MAP[ext] || '';
}

async function previewFile(path) {
    const resultStr = await pywebview.api.read_file(path);
    const result = JSON.parse(resultStr);

    if (!result.ok) {
        showPreviewError(result.msg);
        return;
    }

    currentPreviewPath = path;
    previewFilename.textContent = path;

    if (result.truncated && !result.content) {
        openCodeEditor(path, '', {
            readOnly: true,
            banner: result.msg || '文件过大，无法编辑预览',
        });
    } else {
        const content = result.content || '';
        const readOnly = false;
        let banner = '';
        if (result.truncated) {
            banner = result.msg || '内容已截断，保存将写入当前可见部分';
        }
        openCodeEditor(path, content, { readOnly, banner, truncated: result.truncated });
    }

    if (result.truncated && result.msg) {
        previewTruncateMsg.textContent = result.msg;
        previewTruncateMsg.classList.remove('hidden');
    } else {
        previewTruncateMsg.classList.add('hidden');
    }

    const totalLines = (result.content || '').split('\n').length;
    updatePreviewStatus(totalLines, path, result.encoding || '');

    filePreview.classList.remove('hidden');
    if (typeof updateCodePanelSplit === 'function') updateCodePanelSplit();
}

function updatePreviewStatus(lines, path, encoding) {
    const statusEl = document.getElementById('preview-status');
    if (!statusEl) return;
    const ext = path.split('.').pop() || '';
    const lang = getLang(path) || '文本';
    statusEl.textContent = `${lines} 行 · ${ext.toUpperCase()} · ${encoding || 'UTF-8'}`;
}

function showPreviewError(msg) {
    currentPreviewPath = '';
    currentPreviewContent = '';
    previewFilename.textContent = '无法打开';
    openCodeEditor('', '', { readOnly: true, banner: '❌ ' + msg });
    previewTruncateMsg.classList.add('hidden');
    filePreview.classList.remove('hidden');
    if (typeof updateCodePanelSplit === 'function') updateCodePanelSplit();
}

function closePreview() {
    if (isEditorDirty()) {
        if (!confirm('当前文件有未保存修改，确定关闭？')) return;
    }
    filePreview.classList.add('hidden');
    const ta = getEditorTextarea();
    if (ta) ta.value = '';
    currentPreviewContent = '';
    currentPreviewPath = '';
    editorLastSaved = '';
    document.querySelectorAll('.tree-item.active').forEach(el => el.classList.remove('active'));
    if (typeof updateCodePanelSplit === 'function') updateCodePanelSplit();
}

function copyPreviewContent() {
    const text = getEditorBuffer();
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        const original = btnCopyContent.textContent;
        btnCopyContent.textContent = '✅ 已复制';
        setTimeout(() => { btnCopyContent.textContent = original; }, 1500);
    });
}

function sendFileToAI() {
    if (!currentPreviewPath) return;
    const content = getEditorBuffer();
    const prompt = `请分析以下文件内容：\n\n文件路径：${currentPreviewPath}\n\n\`\`\`\n${content}\n\`\`\``;
    msgInput.value = prompt;
    autoResize();
    msgInput.focus();
}
