"""群聊专家会议：认知议会式多轮编排。"""

import json
import os
import re
from datetime import datetime

from .expert_helpers import parse_confidence_basis, stream_chat_completion
from .shared_blackboard import SharedBlackboard

ROUND_META = {
    "round1": {"label": "独立诊断", "icon": "🔍"},
    "round2": {"label": "交叉澄清", "icon": "❓"},
    "round3": {"label": "红队攻击", "icon": "🛡"},
    "round4": {"label": "架构师整合", "icon": "🏗"},
    "round5": {"label": "执行细化", "icon": "📋"},
}

RED_TEAM_SYSTEM = """\
你是红队批判者。只找漏洞、失败路径与证伪证据，禁止替作者辩护或提出新方案。
输出格式：
## 草案 A
- 最可能失败路径: ...
- 所需资源: ...
- 证伪证据: ...
**置信度**: XX/100
**依据**: 推理|事实|假设|类比"""

SYNTHESIZER_SYSTEM = """\
你是架构师整合者。必须给出 1-3 个混合方案、决策矩阵与单一明确推荐，禁止"各有优劣"式回避。
输出格式：
## 混合方案
### 方案 1: ...
### 方案 2: ...

## 决策矩阵
| 方案 | 可行性 | 成本 | 风险 | 综合 |
|------|--------|------|------|------|

## 推荐
（明确选一个方案并说明理由）

**置信度**: XX/100
**依据**: 推理|事实|假设|类比"""

COUNCIL_ROLE_PREAMBLE = """\
[专家会议 — Expert Council]
本轮以指定角色参与群聊专家会议。优先完成角色任务；人格设定次之。"""


def _stopped(api):
    return getattr(api, "stop_flag", False)


def _push_js(api, fn, payload):
    try:
        api.window.evaluate_js(f"{fn}({json.dumps(payload, ensure_ascii=False)})")
    except Exception:
        pass


def _push_round(api, round_id, status, extra=None):
    meta = ROUND_META.get(round_id, {})
    payload = {
        "roundId": round_id,
        "label": meta.get("label", round_id),
        "icon": meta.get("icon", "📌"),
        "status": status,
    }
    if extra:
        payload.update(extra)
    _push_js(api, "onCouncilRound", payload)


def _push_speaker(api, round_id, bot, role, status, extra=None):
    payload = {
        "roundId": round_id,
        "botId": bot.get("id", "") if bot else "",
        "botName": bot.get("name", "系统") if bot else "系统",
        "avatar": bot.get("avatar", "🤖") if bot else "⚙",
        "role": role,
        "status": status,
    }
    if extra:
        payload.update(extra)
    _push_js(api, "onCouncilSpeaker", payload)


def _push_blackboard(api, blackboard):
    _push_js(api, "onCouncilBlackboard", blackboard.to_dict())


def _resolve_participants(meta, members, participant_ids=None):
    max_experts = int(meta.get("council_max_experts", 5))
    if participant_ids:
        ids = [i for i in participant_ids if any(b["id"] == i for b in members)]
    else:
        ids = [b["id"] for b in members]
    if len(ids) > max_experts:
        ids = ids[:max_experts]
    experts = [b for b in members if b["id"] in ids]
    return experts, max_experts


def assign_roles(meta, members, participant_ids=None):
    experts, _ = _resolve_participants(meta, members, participant_ids)
    red_id = (meta.get("council_red_team_bot_id") or "").strip()
    synth_id = (meta.get("council_synthesizer_bot_id") or "").strip()

    red_bot = next((b for b in members if b["id"] == red_id), None)
    synth_bot = next((b for b in members if b["id"] == synth_id), None)

    expert_ids = {b["id"] for b in experts}
    if not red_bot:
        candidates = [b for b in experts if b["id"] != synth_id] if synth_bot else experts
        red_bot = candidates[-1] if candidates else None
    if not synth_bot:
        candidates = [b for b in experts if b["id"] != (red_bot or {}).get("id")]
        synth_bot = candidates[0] if candidates else (experts[0] if experts else None)

    return {
        "experts": experts,
        "red_team": red_bot,
        "red_team_system": not red_bot or red_bot["id"] not in expert_ids,
        "synthesizer": synth_bot,
        "synthesizer_system": not synth_bot or synth_bot["id"] not in expert_ids,
    }


def _load_bot_soul(api, bot):
    folder = bot.get("soul_folder", "")
    if not folder:
        return ""
    return api._load_soul_folder(folder) or ""


def _call_as_bot(api, bot, messages, round_id, role, on_token=None):
    prev_reply = getattr(api, "_reply_bot_id", None)
    api._reply_bot_id = bot["id"] if bot else None
    try:
        def token_cb(tok):
            if bot:
                _push_js(api, "onCouncilToken", {
                    "roundId": round_id,
                    "botId": bot["id"],
                    "token": tok,
                })
            if on_token:
                on_token(tok)

        content = stream_chat_completion(api, messages, on_token=token_cb)
        meta = parse_confidence_basis(content)
        return content, meta
    finally:
        api._reply_bot_id = prev_reply


def _build_expert_messages(api, bot, topic, round_prompt, soul="", blackboard_text=""):
    from .api import GLOBAL_IMMERSION_PREAMBLE
    system_parts = [COUNCIL_ROLE_PREAMBLE, GLOBAL_IMMERSION_PREAMBLE]
    if soul:
        system_parts.append(soul)
    system_parts.append(round_prompt)
    user_parts = [f"[议题]\n{topic}"]
    if blackboard_text:
        user_parts.append(blackboard_text)
    return [
        {"role": "system", "content": "\n\n---\n\n".join(system_parts)},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def _save_council_message(api, msg):
    from . import history
    api.current_messages.append(msg)
    if api.current_session_id:
        history.append_messages(api.current_session_id, [msg])


def _write_consensus_entry(api, group_folder, topic, blackboard, recommendation, interrupted=False):
    from .memory.store import write_entry

    points = list(blackboard.current_consensus or [])
    if recommendation:
        points.insert(0, recommendation[:500])
    for div in blackboard.open_divergences[:5]:
        points.append(f"[分歧] {div}")
    try:
        result = write_entry(group_folder, {
            "title": f"专家会议共识: {topic[:40]}",
            "type": "council",
            "importance": 4,
            "keywords": ["专家会议", "共识", "council"],
            "summary": (recommendation or blackboard.serialize_for_prompt())[:800],
            "points": points[:20] or ["（会议未完成或无明确共识）"],
        })
        if result.get("file_path"):
            from .memory import indexer
            indexer.index_after_entry_write(group_folder, result["file_path"])
        return result
    except Exception:
        return None


ROUND1_PROMPT = """\
## Round 1: 独立诊断
仅基于议题独立分析，不得引用他人观点。

输出格式：
## 根因 (Root_Cause)
...

## 方案草案 (Solution_Draft)
...

**置信度**: XX/100
**依据**: 推理|事实|假设|类比"""

ROUND2_PROMPT = """\
## Round 2: 交叉澄清
以下是匿名化草案（作者未知）。你只能提出澄清性问题，禁止反驳、评分或给结论。

输出格式：
## 对草案 {label} 的澄清问题
1. ...
2. ...

**置信度**: XX/100
**依据**: 推理|事实|假设|类比"""

ROUND3_PROMPT = """\
## Round 3: 红队攻击
对下列草案做批判性攻击。若某草案是你本人 Round1 产出，尽量略过或只做最小批判。

{drafts}

""" + RED_TEAM_SYSTEM

ROUND4_PROMPT = """\
## Round 4: 架构师整合
综合黑板与全部轮次产出，给出混合方案与单一推荐。

""" + SYNTHESIZER_SYSTEM

ROUND5_PROMPT = """\
## Round 5: 执行细化
用户已选定方向。输出可执行计划：

## 里程碑
- ...

## 资源预算
...

## 风险缓解
...

## 验收标准
...

**置信度**: XX/100
**依据**: 推理|事实|假设|类比"""


def _anonymize_drafts(drafts):
    lines = []
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    mapping = {}
    for i, d in enumerate(drafts):
        label = labels[i % len(labels)]
        mapping[label] = d
        lines.append(f"### 草案 {label}\n{d.get('content', '')[:2000]}")
    return "\n\n".join(lines), mapping


def run_council_pipeline(api_instance, topic, group_id, session_data, participant_ids=None):
    """执行 Round 1-4，Round 4 后暂停等待仲裁。"""
    from .groups import get_group_memory_folder, load_group_meta
    from .api import GLOBAL_IMMERSION_PREAMBLE

    app_dir = os.path.dirname(api_instance.config_path)
    meta = load_group_meta(app_dir, group_id) or {}
    member_ids = session_data.get("member_bot_ids") or meta.get("member_bot_ids") or []
    bots = api_instance.config.get("bots", [])
    members = [b for b in bots if b["id"] in member_ids]

    if len(members) < 2:
        _push_js(api_instance, "onCouncilDone", {
            "ok": False,
            "msg": "专家会议至少需要 2 位群成员",
        })
        return {"ok": False, "msg": "成员不足"}

    roles = assign_roles(meta, members, participant_ids)
    experts = roles["experts"]
    if len(experts) < 2:
        _push_js(api_instance, "onCouncilDone", {
            "ok": False,
            "msg": "参与专家至少需要 2 位",
        })
        return {"ok": False, "msg": "专家不足"}

    blackboard = SharedBlackboard.create()
    drafts = []
    round_outputs = {}
    api_instance._council_active = True
    api_instance.stop_flag = False

    try:
        _push_js(api_instance, "onCouncilStart", {
            "topic": topic,
            "experts": [{"id": b["id"], "name": b.get("name"), "avatar": b.get("avatar")} for b in experts],
        })

        # Round 1
        _push_round(api_instance, "round1", "running")
        round1_outputs = []
        for bot in experts:
            if _stopped(api_instance):
                break
            soul = _load_bot_soul(api_instance, bot)
            _push_speaker(api_instance, "round1", bot, "expert", "running")
            msgs = _build_expert_messages(api_instance, bot, topic, ROUND1_PROMPT, soul=soul)
            content, conf = _call_as_bot(api_instance, bot, msgs, "round1", "expert")
            round1_outputs.append({"bot_id": bot["id"], "bot_name": bot.get("name"), "content": content, **conf})
            drafts.append({"bot_id": bot["id"], "content": content, **conf})
            _push_speaker(api_instance, "round1", bot, "expert", "done", conf)
            _save_council_message(api_instance, {
                "role": "assistant",
                "content": content,
                "speaker_bot_id": bot["id"],
                "council_round": "round1",
                "council_role": "expert",
                "confidence": conf["confidence"],
                "basis": conf["basis"],
            })
        round_outputs["round1"] = round1_outputs
        blackboard.apply_round_update("Round 1", "\n".join(o["content"][:300] for o in round1_outputs))
        _push_blackboard(api_instance, blackboard)
        _push_round(api_instance, "round1", "done")

        if _stopped(api_instance):
            return _finish_interrupted(api_instance, group_id, topic, blackboard, round_outputs)

        # Round 2
        _push_round(api_instance, "round2", "running")
        anon_text, _ = _anonymize_drafts(drafts)
        bb_text = blackboard.serialize_for_prompt()
        round2_outputs = []
        for bot in experts:
            if _stopped(api_instance):
                break
            soul = _load_bot_soul(api_instance, bot)
            prompt = ROUND2_PROMPT.replace("{label}", "A/B/C...")
            _push_speaker(api_instance, "round2", bot, "expert", "running")
            msgs = _build_expert_messages(
                api_instance, bot, topic,
                prompt + "\n\n" + anon_text, soul=soul, blackboard_text=bb_text,
            )
            content, conf = _call_as_bot(api_instance, bot, msgs, "round2", "expert")
            round2_outputs.append({"bot_id": bot["id"], "content": content, **conf})
            _push_speaker(api_instance, "round2", bot, "expert", "done", conf)
            _save_council_message(api_instance, {
                "role": "assistant",
                "content": content,
                "speaker_bot_id": bot["id"],
                "council_round": "round2",
                "council_role": "expert",
                "confidence": conf["confidence"],
                "basis": conf["basis"],
            })
        round_outputs["round2"] = round2_outputs
        blackboard.apply_round_update("Round 2", "\n".join(o["content"][:200] for o in round2_outputs))
        _push_blackboard(api_instance, blackboard)
        _push_round(api_instance, "round2", "done")

        if _stopped(api_instance):
            return _finish_interrupted(api_instance, group_id, topic, blackboard, round_outputs)

        # Round 3
        _push_round(api_instance, "round3", "running")
        drafts_text, _ = _anonymize_drafts(drafts)
        red_bot = roles["red_team"]
        red_role = "red_team"
        if roles["red_team_system"]:
            red_bot = {"id": "__system_red__", "name": "系统红队", "avatar": "🛡", "soul_folder": ""}
        _push_speaker(api_instance, "round3", red_bot, red_role, "running", {
            "systemRole": roles["red_team_system"],
        })
        prompt = ROUND3_PROMPT.format(drafts=drafts_text)
        soul = _load_bot_soul(api_instance, red_bot) if not roles["red_team_system"] else ""
        msgs = _build_expert_messages(
            api_instance, red_bot if not roles["red_team_system"] else roles["red_team"] or experts[0],
            topic, prompt, soul=soul, blackboard_text=blackboard.serialize_for_prompt(),
        )
        if roles["red_team_system"]:
            msgs[0]["content"] += "\n\n---\n\n" + RED_TEAM_SYSTEM
        call_bot = roles["red_team"] or experts[0]
        content, conf = _call_as_bot(api_instance, call_bot, msgs, "round3", red_role)
        round_outputs["round3"] = content
        _push_speaker(api_instance, "round3", red_bot, red_role, "done", {**conf, "systemRole": roles["red_team_system"]})
        speaker_id = call_bot["id"]
        _save_council_message(api_instance, {
            "role": "assistant",
            "content": content,
            "speaker_bot_id": speaker_id,
            "council_round": "round3",
            "council_role": "red_team",
            "confidence": conf["confidence"],
            "basis": conf["basis"],
            "system_role": roles["red_team_system"],
        })
        blackboard.apply_round_update("Round 3", content)
        _push_blackboard(api_instance, blackboard)
        _push_round(api_instance, "round3", "done")

        if _stopped(api_instance):
            return _finish_interrupted(api_instance, group_id, topic, blackboard, round_outputs)

        # Round 4
        _push_round(api_instance, "round4", "running")
        synth_bot = roles["synthesizer"]
        if roles["synthesizer_system"]:
            synth_bot = {"id": "__system_synth__", "name": "系统架构师", "avatar": "🏗", "soul_folder": ""}
        _push_speaker(api_instance, "round4", synth_bot, "synthesizer", "running", {
            "systemRole": roles["synthesizer_system"],
        })
        call_bot = roles["synthesizer"] or experts[0]
        soul = _load_bot_soul(api_instance, call_bot) if not roles["synthesizer_system"] else ""
        context = blackboard.serialize_for_prompt()
        for label, outs in round_outputs.items():
            if isinstance(outs, list):
                context += "\n\n" + "\n---\n".join(o.get("content", "")[:500] for o in outs)
            elif isinstance(outs, str):
                context += "\n\n" + outs[:1000]
        msgs = _build_expert_messages(api_instance, call_bot, topic, ROUND4_PROMPT, soul=soul, blackboard_text=context)
        if roles["synthesizer_system"]:
            msgs[0]["content"] += "\n\n---\n\n" + SYNTHESIZER_SYSTEM
        content, conf = _call_as_bot(api_instance, call_bot, msgs, "round4", "synthesizer")
        round_outputs["round4"] = content
        recommendation = _extract_recommendation(content)
        options = _extract_options(content)
        _push_speaker(api_instance, "round4", synth_bot, "synthesizer", "done", {**conf, "systemRole": roles["synthesizer_system"]})
        _save_council_message(api_instance, {
            "role": "assistant",
            "content": content,
            "speaker_bot_id": call_bot["id"],
            "council_round": "round4",
            "council_role": "synthesizer",
            "confidence": conf["confidence"],
            "basis": conf["basis"],
            "system_role": roles["synthesizer_system"],
        })
        blackboard.apply_round_update("Round 4", content)
        if recommendation:
            blackboard.current_consensus.append(recommendation[:300])
        _push_blackboard(api_instance, blackboard)
        _push_round(api_instance, "round4", "done")

        api_instance._council_state = {
            "topic": topic,
            "group_id": group_id,
            "blackboard": blackboard.to_dict(),
            "round4_output": content,
            "recommendation": recommendation,
            "options": options,
            "participant_ids": [b["id"] for b in experts],
            "roles": {
                "red_team_id": (roles["red_team"] or {}).get("id"),
                "synthesizer_id": (roles["synthesizer"] or {}).get("id"),
            },
            "awaiting_arbitration": True,
        }

        _push_js(api_instance, "onCouncilArbitration", {
            "recommendation": recommendation,
            "options": options,
            "matrix": content,
            "round4Content": content,
        })
        return {"ok": True, "awaiting_arbitration": True}

    except Exception as e:
        _push_js(api_instance, "onCouncilDone", {"ok": False, "msg": str(e), "interrupted": True})
        return {"ok": False, "msg": str(e)}
    finally:
        if not getattr(api_instance, "_council_state", {}).get("awaiting_arbitration"):
            api_instance._council_active = False


def continue_council_after_arbitration(api_instance, action, option_index=0):
    """仲裁后继续：select/deepen/end。"""
    state = getattr(api_instance, "_council_state", None)
    if not state or not state.get("awaiting_arbitration"):
        return {"ok": False, "msg": "当前无待仲裁的会议"}

    from .groups import get_group_memory_folder, load_group_meta, touch_group

    app_dir = os.path.dirname(api_instance.config_path)
    group_id = state["group_id"]
    topic = state["topic"]
    group_folder = get_group_memory_folder(app_dir, group_id)
    blackboard = SharedBlackboard.create()
    d = state.get("blackboard") or {}
    blackboard.current_consensus = list(d.get("Current_Consensus") or [])
    blackboard.open_divergences = list(d.get("Open_Divergences") or [])
    blackboard.falsified_hypotheses = list(d.get("Falsified_Hypotheses") or [])
    blackboard.key_constraints = list(d.get("Key_Constraints") or [])
    blackboard.escalated_disputes = list(d.get("Escalated_Disputes") or [])
    blackboard.context_version = int(d.get("Context_Version") or 1)

    recommendation = state.get("recommendation") or ""
    options = state.get("options") or []
    selected = options[option_index] if options and 0 <= option_index < len(options) else recommendation

    state["awaiting_arbitration"] = False
    api_instance._council_active = True

    try:
        final_content = state.get("round4_output") or recommendation

        if action == "deepen" and not _stopped(api_instance):
            _push_round(api_instance, "round5", "running")
            meta = load_group_meta(app_dir, group_id) or {}
            member_ids = state.get("participant_ids") or []
            bots = api_instance.config.get("bots", [])
            members = [b for b in bots if b["id"] in member_ids]
            roles = assign_roles(meta, members, member_ids)
            synth = roles["synthesizer"] or (members[0] if members else None)
            if synth:
                _push_speaker(api_instance, "round5", synth, "synthesizer", "running")
                direction = selected or recommendation
                prompt = ROUND5_PROMPT + f"\n\n[用户选定方向]\n{direction}"
                soul = _load_bot_soul(api_instance, synth)
                msgs = _build_expert_messages(
                    api_instance, synth, topic, prompt, soul=soul,
                    blackboard_text=blackboard.serialize_for_prompt(),
                )
                content, conf = _call_as_bot(api_instance, synth, msgs, "round5", "synthesizer")
                final_content = content
                _push_speaker(api_instance, "round5", synth, "synthesizer", "done", conf)
                _save_council_message(api_instance, {
                    "role": "assistant",
                    "content": content,
                    "speaker_bot_id": synth["id"],
                    "council_round": "round5",
                    "council_role": "synthesizer",
                    "confidence": conf["confidence"],
                    "basis": conf["basis"],
                })
                blackboard.apply_round_update("Round 5", content)
                _push_blackboard(api_instance, blackboard)
                _push_round(api_instance, "round5", "done")

        elif action == "select" and selected:
            recommendation = selected

        entry = _write_consensus_entry(
            api_instance, group_folder, topic, blackboard, recommendation or final_content,
        )
        touch_group(app_dir, group_id)

        summary_msg = {
            "role": "assistant",
            "content": final_content,
            "council_summary": True,
            "council_action": action,
        }
        synth_id = (state.get("roles") or {}).get("synthesizer_id")
        if synth_id:
            summary_msg["speaker_bot_id"] = synth_id
        _save_council_message(api_instance, summary_msg)

        _push_js(api_instance, "onCouncilDone", {
            "ok": True,
            "content": final_content,
            "recommendation": recommendation,
            "action": action,
            "entryId": (entry or {}).get("id"),
        })
        return {"ok": True, "content": final_content}
    except Exception as e:
        _push_js(api_instance, "onCouncilDone", {"ok": False, "msg": str(e)})
        return {"ok": False, "msg": str(e)}
    finally:
        api_instance._council_active = False
        api_instance._council_state = None


def _finish_interrupted(api_instance, group_id, topic, blackboard, round_outputs):
    from .groups import get_group_memory_folder, touch_group
    app_dir = os.path.dirname(api_instance.config_path)
    group_folder = get_group_memory_folder(app_dir, group_id)
    _write_consensus_entry(api_instance, group_folder, topic, blackboard, "", interrupted=True)
    touch_group(app_dir, group_id)
    _push_js(api_instance, "onCouncilDone", {
        "ok": True,
        "interrupted": True,
        "content": blackboard.serialize_for_prompt(),
    })
    api_instance._council_active = False
    return {"ok": True, "interrupted": True}


def _extract_recommendation(text):
    if not text:
        return ""
    m = re.search(r"##\s*推荐\s*\n([\s\S]*?)(?:\n##|\n\*\*|$)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"推荐方案[：:]\s*([^\n]+)", text)
    return m.group(1).strip() if m else text[:300].strip()


def _extract_options(text):
    options = []
    if not text:
        return options
    for m in re.finditer(r"###\s*方案\s*(\d+)[：:]\s*([^\n]+)", text):
        options.append(f"方案 {m.group(1)}: {m.group(2).strip()}")
    if not options:
        rec = _extract_recommendation(text)
        if rec:
            options.append(rec[:200])
    return options[:3]
