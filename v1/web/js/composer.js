// ===== Composer 工具条（输入区上方：思考模式 / 技能）=====

let composerDepthSaveTimer = null;
let composerSkillsSaveTimer = null;
let composerSkillsPopoverOpen = false;

function closeComposerSkillsPopover() {
    const popover = document.getElementById('composer-skills-popover');
    if (!popover) return;
    popover.classList.add('hidden');
    composerSkillsPopoverOpen = false;
}

function setComposerChip(field, value) {
    document.querySelectorAll(`#composer-toolbar .composer-chip[data-field="${field}"]`).forEach(btn => {
        btn.classList.toggle('active', btn.dataset.value === String(value));
    });
}

function getComposerChip(field) {
    const active = document.querySelector(
        `#composer-toolbar .composer-chip[data-field="${field}"].active`
    );
    return active ? active.dataset.value : '';
}

function patchActiveBotInCache(patch) {
    if (!cachedConfig) return null;
    const bot = getActiveBot(cachedConfig);
    const bots = cachedConfig.bots || [];
    const idx = bots.findIndex(b => b.id === bot.id);
    if (idx < 0) return null;
    bots[idx] = { ...bots[idx], ...patch };
    cachedConfig.bots = bots;
    return bots[idx];
}

async function saveActiveBotPatch(patch) {
    const updated = patchActiveBotInCache(patch);
    if (!updated || !updated.id) return false;
    const resultStr = await pywebview.api.save_bot(JSON.stringify(updated));
    const result = JSON.parse(resultStr);
    if (!result.ok) {
        alert(result.msg || '保存失败');
        return false;
    }
    await refreshConfig();
    updateBotDisplay();
    if (typeof refreshStatusPanel === 'function') {
        const panel = document.getElementById('status-panel');
        if (panel && !panel.classList.contains('hidden')) {
            await refreshStatusPanel();
        }
    }
    return true;
}

async function saveGlobalEnabledSkills(ids) {
    if (!cachedConfig) return false;
    cachedConfig.enabled_skills = ids;
    const result = JSON.parse(await pywebview.api.save_config(JSON.stringify(cachedConfig)));
    if (!result.ok) {
        alert(result.msg || '保存失败');
        return false;
    }
    await refreshConfig();
    updateComposerSkillsSummary();
    return true;
}

function getComposerEnabledSkills(bot) {
    const useGlobal = bot.skills_use_global !== false;
    if (useGlobal) {
        return cachedConfig.enabled_skills || [];
    }
    return bot.enabled_skills || [];
}

function updateComposerSkillsSummary() {
    const btn = document.getElementById('btn-composer-skills');
    if (!btn || !cachedConfig) return;
    const bot = getActiveBot(cachedConfig);
    const useGlobal = bot.skills_use_global !== false;
    const ids = getComposerEnabledSkills(bot);
    const n = ids.length;
    btn.textContent = useGlobal ? `🔧 技能 · 全局 ${n}` : `🔧 技能 · ${n}`;
}

function updateComposerSkillsHint(bot) {
    const hint = document.getElementById('composer-skills-hint');
    if (!hint) return;
    const useGlobal = bot.skills_use_global !== false;
    if (useGlobal) {
        hint.textContent = '全局技能：勾选后立即保存到应用设置';
    } else {
        hint.textContent = '自定义技能：仅当前机器人；保存后不再跟随全局列表';
    }
}

function scheduleComposerSkillsSave() {
    clearTimeout(composerSkillsSaveTimer);
    composerSkillsSaveTimer = setTimeout(async () => {
        const bot = getActiveBot(cachedConfig);
        const useGlobal = bot.skills_use_global !== false;
        const ids = collectEnabledSkillIds('composer-skill-list');
        if (useGlobal) {
            await saveGlobalEnabledSkills(ids);
        } else {
            await saveActiveBotPatch({
                enabled_skills: ids,
                skills_use_global: false,
            });
        }
        updateComposerSkillsSummary();
    }, 300);
}

async function refreshComposerSkillsPopover() {
    if (!cachedConfig) return;
    const bot = getActiveBot(cachedConfig);
    updateComposerSkillsHint(bot);
    const enabled = getComposerEnabledSkills(bot);
    await renderSkillList('composer-skill-list', 'composer-skill-empty', enabled, {
        onChange: () => {
            updateComposerSkillsSummary();
            scheduleComposerSkillsSave();
        },
    });
}

async function refreshComposerToolbar() {
    if (!cachedConfig) return;
    const toolbar = document.getElementById('composer-toolbar');
    const isGroup = typeof currentGroupSession !== 'undefined' && !!currentGroupSession;
    const isCode = typeof currentMode !== 'undefined' && currentMode === 'code';
    const bot = getActiveBot(cachedConfig);
    const profile = getActiveProfile(cachedConfig);
    const isDeepSeek = profile.provider === 'deepseek';
    const supportsReasoning = typeof modelSupportsCapability === 'function'
        ? modelSupportsCapability(profile, 'reasoning', bot.model || profile.model)
        : isDeepSeek;

    const thinkingGroup = document.querySelector('#composer-toolbar .composer-group-thinking');
    const depthGroup = document.querySelector('#composer-toolbar .composer-depth-chips');
    if (thinkingGroup) {
        thinkingGroup.classList.toggle('hidden', isGroup || !isDeepSeek || !supportsReasoning);
    }

    if (!isGroup && isDeepSeek && supportsReasoning) {
        const enabled = !!bot.thinking_enabled;
        setComposerChip('composer-thinking-enabled', String(enabled));
        const depth = bot.thinking_depth || 'high';
        setComposerChip('composer-thinking-depth', depth);
        if (depthGroup) {
            depthGroup.classList.toggle('hidden', !enabled);
        }
    } else if (depthGroup) {
        depthGroup.classList.add('hidden');
    }

    const skillsGroup = document.querySelector('#composer-toolbar [data-group="skills"]');
    if (skillsGroup) {
        skillsGroup.classList.toggle('hidden', isGroup);
    }
    if (toolbar) {
        toolbar.classList.toggle('hidden', isGroup && !isCode);
    }
    updateComposerSkillsSummary();
    if (composerSkillsPopoverOpen) {
        await refreshComposerSkillsPopover();
    }
}

function initComposerToolbar() {
    const toolbar = document.getElementById('composer-toolbar');
    if (!toolbar || toolbar.dataset.bound === '1') return;
    toolbar.dataset.bound = '1';

    toolbar.addEventListener('click', async (e) => {
        const chip = e.target.closest('.composer-chip[data-field]');
        if (!chip || chip.id === 'btn-composer-skills') return;
        const field = chip.dataset.field;
        const value = chip.dataset.value;
        setComposerChip(field, value);

        if (field === 'composer-thinking-enabled') {
            const enabled = value === 'true';
            const depthGroup = document.querySelector('#composer-toolbar .composer-depth-chips');
            if (depthGroup) depthGroup.classList.toggle('hidden', !enabled);
            await saveActiveBotPatch({ thinking_enabled: enabled });
            return;
        }
        if (field === 'composer-thinking-depth') {
            clearTimeout(composerDepthSaveTimer);
            composerDepthSaveTimer = setTimeout(async () => {
                await saveActiveBotPatch({ thinking_depth: value });
            }, 300);
        }
    });

    const skillsBtn = document.getElementById('btn-composer-skills');
    const popover = document.getElementById('composer-skills-popover');
    if (skillsBtn && popover) {
        skillsBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!composerSkillsPopoverOpen) {
                popover.classList.remove('hidden');
                composerSkillsPopoverOpen = true;
                await refreshComposerSkillsPopover();
            } else {
                closeComposerSkillsPopover();
            }
        });
    }

    document.addEventListener('mousedown', (e) => {
        if (!popover || !composerSkillsPopoverOpen) return;
        if (e.target.closest('.composer-skills-wrap')) return;
        closeComposerSkillsPopover();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && composerSkillsPopoverOpen) {
            closeComposerSkillsPopover();
        }
    });
}

initComposerToolbar();
