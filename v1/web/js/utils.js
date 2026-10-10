// ===== 工具函数 =====

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        const now = new Date();
        const isToday = d.toDateString() === now.toDateString();
        const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        if (isToday) return time;
        return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' + time;
    } catch { return ''; }
}

/** 检测 emoji 在当前系统字体下是否能正常绘制（避免空白方框仍可点选） */
function isEmojiRenderable(emoji) {
    if (!emoji) return false;
    try {
        const canvas = document.createElement('canvas');
        canvas.width = 48;
        canvas.height = 48;
        const ctx = canvas.getContext('2d');
        if (!ctx) return true;
        ctx.textBaseline = 'middle';
        ctx.font = '32px "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji", sans-serif';
        ctx.fillText(emoji, 6, 26);
        const { data } = ctx.getImageData(0, 0, 48, 48);
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] > 0) return true;
        }
        return false;
    } catch {
        return true;
    }
}

function filterRenderableEmojis(list) {
    const seen = new Set();
    const out = [];
    for (const e of list) {
        if (!e || seen.has(e)) continue;
        if (!isEmojiRenderable(e)) continue;
        seen.add(e);
        out.push(e);
    }
    return out;
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'py': '\u{1F40D}', 'js': '\u{1F4C4}', 'ts': '\u{1F4C4}', 'html': '\u{1F310}', 'css': '\u{1F3A8}',
        'json': '\u{1F4CB}', 'md': '\u{1F4DD}', 'txt': '\u{1F4DD}', 'yml': '⚙️', 'yaml': '⚙️',
        'toml': '⚙️', 'xml': '\u{1F4C4}', 'sh': '\u{1F4BB}', 'bat': '\u{1F4BB}', 'cmd': '\u{1F4BB}',
        'go': '\u{1F535}', 'rs': '\u{1F980}', 'java': '☕', 'c': '\u{1F4C4}', 'cpp': '\u{1F4C4}',
        'h': '\u{1F4C4}', 'hpp': '\u{1F4C4}', 'rb': '\u{1F48E}', 'php': '\u{1F418}', 'sql': '\u{1F4DB}',
        'gitignore': '\u{1F4CB}', 'env': '\u{1F512}', 'dockerfile': '\u{1F433}', 'docker-compose': '\u{1F433}'
    };
    return icons[ext] || '\u{1F4C4}';
}
