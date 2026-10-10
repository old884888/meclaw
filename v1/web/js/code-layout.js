// ===== 编程模式：面板拖拽换位、预览区宽度、布局持久化 =====

const CODE_LAYOUT_STORAGE_KEY = 'meclaw_code_layout';

function loadCodeLayout() {
    try {
        return JSON.parse(localStorage.getItem(CODE_LAYOUT_STORAGE_KEY) || '{}');
    } catch {
        return {};
    }
}

function saveCodeLayout(partial) {
    const next = { ...loadCodeLayout(), ...partial };
    localStorage.setItem(CODE_LAYOUT_STORAGE_KEY, JSON.stringify(next));
}

function applyCodeLayout(layout) {
    const rightPanel = document.getElementById('right-panel');
    if (!rightPanel) return;

    rightPanel.classList.toggle('preview-first', !!layout.previewFirst);

    const w = layout.previewWidth;
    if (typeof w === 'number' && w >= 250 && w <= 600) {
        document.documentElement.style.setProperty('--code-preview-width', w + 'px');
    }
}

function updateCodePanelSplit() {
    const split = document.getElementById('code-panel-split');
    const main = document.getElementById('main-content');
    const preview = document.getElementById('file-preview');
    if (!split || !main || !preview) return;

    const inCode = main.dataset.mode === 'code';
    const previewOpen = !preview.classList.contains('hidden');
    split.classList.toggle('hidden', !inCode || !previewOpen);
}

function onCodeModeChange(mode) {
    if (mode === 'code') {
        applyCodeLayout(loadCodeLayout());
    }
    updateCodePanelSplit();
}

function setupCodePanelSplitResize() {
    const split = document.getElementById('code-panel-split');
    if (!split) return;

    split.addEventListener('mousedown', (e) => {
        if (split.classList.contains('hidden')) return;
        e.preventDefault();

        const rightPanel = document.getElementById('right-panel');
        const preview = document.getElementById('file-preview');
        const previewFirst = rightPanel.classList.contains('preview-first');
        const startX = e.clientX;
        const startWidth = preview.getBoundingClientRect().width;

        split.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        function onMove(ev) {
            const dx = ev.clientX - startX;
            const delta = previewFirst ? dx : -dx;
            let w = Math.round(startWidth + delta);
            w = Math.max(250, Math.min(600, w));
            document.documentElement.style.setProperty('--code-preview-width', w + 'px');
        }

        function onUp() {
            split.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);

            const w = parseInt(getComputedStyle(preview).width, 10);
            if (!Number.isNaN(w)) saveCodeLayout({ previewWidth: w });
        }

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });
}

function setupCodePanelDragSwap() {
    const rightPanel = document.getElementById('right-panel');
    const grips = document.querySelectorAll('.code-panel-grip');
    if (!rightPanel || !grips.length) return;

    let dragPanel = null;

    grips.forEach((grip) => {
        grip.addEventListener('dragstart', (e) => {
            dragPanel = grip.dataset.panel;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', dragPanel);
            grip.closest('.code-panel-header, .preview-header')?.classList.add('panel-dragging');
        });

        grip.addEventListener('dragend', () => {
            dragPanel = null;
            document.querySelectorAll('.panel-dragging').forEach((el) => el.classList.remove('panel-dragging'));
            document.querySelectorAll('.panel-drop-target').forEach((el) => el.classList.remove('panel-drop-target'));
        });
    });

    const dropTargets = [
        document.getElementById('chat-panel-header'),
        document.querySelector('#file-preview .preview-header'),
    ].filter(Boolean);

    dropTargets.forEach((target) => {
        target.addEventListener('dragover', (e) => {
            if (!dragPanel) return;
            const targetPanel = target.closest('#chat-area') ? 'chat' : 'preview';
            if (targetPanel === dragPanel) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            target.classList.add('panel-drop-target');
        });

        target.addEventListener('dragleave', () => {
            target.classList.remove('panel-drop-target');
        });

        target.addEventListener('drop', (e) => {
            e.preventDefault();
            target.classList.remove('panel-drop-target');
            const from = e.dataTransfer.getData('text/plain') || dragPanel;
            const to = target.closest('#chat-area') ? 'chat' : 'preview';
            if (!from || from === to) return;

            const previewFirst = from === 'chat';
            rightPanel.classList.toggle('preview-first', previewFirst);
            saveCodeLayout({ previewFirst });
        });
    });
}

function initCodeLayout() {
    applyCodeLayout(loadCodeLayout());
    setupCodePanelSplitResize();
    setupCodePanelDragSwap();
    updateCodePanelSplit();
}
