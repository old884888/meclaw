// ===== 编程模式可编辑文件区 =====

let editorReadOnly = false;
let editorLastSaved = '';

function getEditorTextarea() {
    return document.getElementById('code-editor-textarea');
}

function applyEditorWordWrapFromConfig() {
    const ta = getEditorTextarea();
    if (!ta || !cachedConfig) return;
    const wrap = cachedConfig.editor_word_wrap !== false;
    ta.classList.toggle('code-editor-wrap', wrap);
    ta.setAttribute('wrap', wrap ? 'soft' : 'off');
}

function getEditorBuffer() {
    const ta = getEditorTextarea();
    return ta ? ta.value : (currentPreviewContent || '');
}

function setEditorBuffer(text, markSaved) {
    const ta = getEditorTextarea();
    if (!ta) return;
    ta.value = text;
    currentPreviewContent = text;
    if (markSaved) {
        editorLastSaved = text;
        updateEditorSaveStatus(false);
    } else {
        updateEditorSaveStatus(isEditorDirty());
    }
}

function isEditorDirty() {
    if (editorReadOnly) return false;
    return getEditorBuffer() !== editorLastSaved;
}

function updateEditorSaveStatus(dirty) {
    const el = document.getElementById('editor-save-status');
    if (!el) return;
    if (editorReadOnly) {
        el.textContent = '只读';
        el.className = 'editor-save-status editor-status-readonly';
        el.title = '只读';
        return;
    }
    if (dirty) {
        el.textContent = '●';
        el.className = 'editor-save-status editor-status-dirty';
        el.title = '未保存';
    } else {
        el.textContent = '✓';
        el.className = 'editor-save-status editor-status-saved';
        el.title = '已保存';
    }
}

function setEditorReadOnly(readonly, bannerText) {
    editorReadOnly = readonly;
    const ta = getEditorTextarea();
    const banner = document.getElementById('preview-readonly-banner');
    if (ta) ta.readOnly = readonly;
    if (banner) {
        if (readonly && bannerText) {
            banner.textContent = bannerText;
            banner.classList.remove('hidden');
        } else {
            banner.classList.add('hidden');
        }
    }
    updateEditorSaveStatus(isEditorDirty());
}

function openCodeEditor(path, content, options = {}) {
    const { readOnly = false, banner = '', truncated = false } = options;
    setEditorBuffer(content, true);
    setEditorReadOnly(readOnly, banner);
    applyEditorWordWrapFromConfig();
    const ta = getEditorTextarea();
    if (ta && !readOnly) {
        ta.focus();
    }
    if (truncated) {
        updateEditorSaveStatus(false);
    }
}

async function saveCurrentEditorFile() {
    if (!currentPreviewPath || editorReadOnly) return false;
    if (!currentWorkingDir && typeof pywebview !== 'undefined') {
        const wd = await pywebview.api.get_working_dir();
        currentWorkingDir = wd || currentWorkingDir;
    }
    if (!currentWorkingDir) {
        showGlobalToast('请先打开工作文件夹');
        return false;
    }
    const content = getEditorBuffer();
    const resultStr = await pywebview.api.save_working_file(currentPreviewPath, content);
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        if (typeof onError === 'function') onError(result.msg || '保存失败');
        else alert(result.msg || '保存失败');
        return false;
    }
    editorLastSaved = content;
    currentPreviewContent = content;
    updateEditorSaveStatus(false);
    showGlobalToast('已保存');
    return true;
}

function promptNewWorkingFile() {
    if (!currentWorkingDir) {
        showGlobalToast('请先打开工作文件夹');
        return;
    }
    const rel = prompt('新建文件（相对路径，如 src/main.py）', 'newfile.txt');
    if (!rel || !rel.trim()) return;
    const path = rel.trim().replace(/\\/g, '/');
    if (path.includes('..')) {
        alert('路径不能包含 ..');
        return;
    }
    openCodeEditor(path, '', { readOnly: false });
    previewFilename.textContent = path;
    currentPreviewPath = path;
    filePreview.classList.remove('hidden');
    if (typeof updateCodePanelSplit === 'function') updateCodePanelSplit();
    updateEditorSaveStatus(true);
}

function onWorkingFileSaved(savedPath) {
    if (savedPath && currentPreviewPath && savedPath !== currentPreviewPath) return;
    editorLastSaved = getEditorBuffer();
    updateEditorSaveStatus(false);
}

function notifyEditorDiskChanged(relPath) {
    if (!relPath || relPath !== currentPreviewPath) return;
    if (!isEditorDirty()) {
        previewFile(relPath);
        return;
    }
    if (confirm(`文件「${relPath}」已在磁盘更新。是否重新加载？未保存的编辑将丢失。`)) {
        previewFile(relPath);
    }
}

function initCodeEditor() {
    const ta = getEditorTextarea();
    if (!ta || ta.dataset.bound === '1') return;
    ta.dataset.bound = '1';

    ta.addEventListener('input', () => {
        currentPreviewContent = ta.value;
        updateEditorSaveStatus(isEditorDirty());
    });

    document.getElementById('btn-editor-save')?.addEventListener('click', () => {
        saveCurrentEditorFile();
    });

    document.addEventListener('keydown', (e) => {
        if (currentMode !== 'code') return;
        const ta = getEditorTextarea();
        const inEditor = document.activeElement === ta;
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            if (currentPreviewPath && !filePreview.classList.contains('hidden')) {
                saveCurrentEditorFile();
            }
        }
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            promptNewWorkingFile();
        }
    });
}

initCodeEditor();
