import json
import os


def get_skills_dir(app_dir):
    """返回技能根目录路径"""
    return os.path.join(app_dir, 'skills')


def scan_skills(app_dir):
    """扫描 skills/ 目录，返回技能列表"""
    skills_dir = get_skills_dir(app_dir)
    if not os.path.isdir(skills_dir):
        return []

    skills = []
    for name in sorted(os.listdir(skills_dir)):
        skill_dir = os.path.join(skills_dir, name)
        if not os.path.isdir(skill_dir):
            continue
        skill_json = os.path.join(skill_dir, 'skill.json')
        if not os.path.exists(skill_json):
            continue
        try:
            with open(skill_json, 'r', encoding='utf-8') as f:
                info = json.load(f)
            info['path'] = skill_dir
            skills.append(info)
        except Exception:
            continue
    return skills


def resolve_enabled_skill_ids(bot_config, global_enabled):
    """解析最终启用的技能 ID：默认跟随全局，Bot 可设为自定义列表。"""
    if bot_config.get('skills_use_global', True):
        return list(global_enabled or [])
    return list(bot_config.get('enabled_skills') or [])


def get_enabled_skills(bot_config, app_dir, global_enabled=None):
    """获取 Bot 实际启用的技能详情列表（全局 + 可选覆盖）"""
    enabled_ids = resolve_enabled_skill_ids(
        bot_config,
        global_enabled if global_enabled is not None else [],
    )
    if not enabled_ids:
        return []
    all_skills = scan_skills(app_dir)
    return [s for s in all_skills if s.get('id') in enabled_ids]


def load_skill_instructions(skill_path):
    """读取技能的 instructions.md 内容"""
    path = os.path.join(skill_path, 'instructions.md')
    if not os.path.exists(path):
        return ''
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


WEB_SEARCH_SKILL_ID = "web-search"


def wants_web_search(bot_config, global_enabled=None):
    """是否启用联网 function calling（Bot 字段或勾选联网技能）。"""
    if bot_config.get("web_search"):
        return True
    ids = resolve_enabled_skill_ids(bot_config, global_enabled or [])
    return WEB_SEARCH_SKILL_ID in ids


def create_default_skill(app_dir):
    """创建内置示例技能（仅首次运行时，已存在的不覆盖）"""
    created = False
    if _create_code_review_skill(app_dir):
        created = True
    if _create_web_search_skill(app_dir):
        created = True
    return created


def _create_code_review_skill(app_dir):
    skills_dir = get_skills_dir(app_dir)
    code_review_dir = os.path.join(skills_dir, 'code-review')

    if os.path.exists(code_review_dir):
        return False

    os.makedirs(code_review_dir, exist_ok=True)

    skill_json = {
        "id": "code-review",
        "name": "代码审查",
        "version": "1.0",
        "description": "审查代码质量、安全漏洞和性能问题",
        "icon": "📝"
    }
    with open(os.path.join(code_review_dir, 'skill.json'), 'w', encoding='utf-8') as f:
        json.dump(skill_json, f, indent=2, ensure_ascii=False)

    instructions = (
        "# 代码审查技能\n\n"
        "当用户要求你审查代码时，请按以下维度进行分析：\n\n"
        "## 审查维度\n"
        "1. **代码质量** — 命名规范、结构清晰度、重复代码\n"
        "2. **安全漏洞** — 注入、XSS、敏感信息泄露、权限校验\n"
        "3. **性能问题** — 时间/空间复杂度、N+1 查询、内存泄漏\n"
        "4. **可维护性** — 模块耦合度、文档完整性、测试覆盖\n\n"
        "## 输出格式\n"
        "按严重程度分级：🔴 严重 / 🟡 警告 / 🔵 建议\n"
        "每项给出：问题描述 + 位置 + 修复建议\n"
    )
    with open(os.path.join(code_review_dir, 'instructions.md'), 'w', encoding='utf-8') as f:
        f.write(instructions)

    return True


def _create_web_search_skill(app_dir):
    """内置联网技能：勾选后由后端向 DeepSeek 注入 web_search 工具。"""
    skills_dir = get_skills_dir(app_dir)
    skill_dir = os.path.join(skills_dir, WEB_SEARCH_SKILL_ID)
    if os.path.exists(skill_dir):
        return False

    os.makedirs(skill_dir, exist_ok=True)
    skill_json = {
        "id": WEB_SEARCH_SKILL_ID,
        "name": "联网搜索",
        "version": "1.0",
        "description": "查询实时信息（新闻、价格、文档更新等），需 DeepSeek API",
        "icon": "🌐",
    }
    with open(os.path.join(skill_dir, 'skill.json'), 'w', encoding='utf-8') as f:
        json.dump(skill_json, f, indent=2, ensure_ascii=False)

    instructions = (
        "# 联网搜索\n\n"
        "启用后 MeClaw 会注册 **search_web** 函数工具；请在需要时效信息时调用。\n"
        "不要使用已废弃的 API `web_search` 工具类型。\n\n"
        "## 适用场景\n"
        "- 用户明确要问「最新」「今天」「当前」类事实\n"
        "- 版本号、汇率、赛事结果、政策变动等时效信息\n"
        "- 你不确定答案是否过期时，先搜索再回答\n\n"
        "## 不适用\n"
        "- 纯代码重构、数学推导、已有上下文足够的问题\n\n"
        "## 回答要求\n"
        "- 综合搜索结果与已有知识，注明信息可能的时间点\n"
        "- 若搜索无结果，如实说明并给出可验证的查找建议\n"
    )
    with open(os.path.join(skill_dir, 'instructions.md'), 'w', encoding='utf-8') as f:
        f.write(instructions)
    return True
