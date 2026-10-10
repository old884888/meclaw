"""专家会议共享黑板：结构化共识 / 分歧 / 证伪 / 约束。"""

import copy
import re
from dataclasses import dataclass, field


DEFAULT_DISPUTE_FREEZE_THRESHOLD = 2


@dataclass
class SharedBlackboard:
    current_consensus: list = field(default_factory=list)
    open_divergences: list = field(default_factory=list)
    falsified_hypotheses: list = field(default_factory=list)
    key_constraints: list = field(default_factory=list)
    escalated_disputes: list = field(default_factory=list)
    context_version: int = 1
    last_warning: str = ""
    _divergence_rounds: dict = field(default_factory=dict, repr=False)

    @classmethod
    def create(cls):
        return cls(context_version=1)

    def to_dict(self):
        return {
            "Current_Consensus": list(self.current_consensus),
            "Open_Divergences": list(self.open_divergences),
            "Falsified_Hypotheses": list(self.falsified_hypotheses),
            "Key_Constraints": list(self.key_constraints),
            "Escalated_Disputes": list(self.escalated_disputes),
            "Context_Version": self.context_version,
            "Last_Warning": self.last_warning or "",
        }

    def serialize_for_prompt(self):
        d = self.to_dict()
        lines = [f"[共享黑板 v{d['Context_Version']}]"]
        for key in ("Current_Consensus", "Open_Divergences", "Falsified_Hypotheses",
                    "Key_Constraints", "Escalated_Disputes"):
            items = d.get(key) or []
            if not items:
                continue
            lines.append(f"\n### {key}")
            for item in items:
                lines.append(f"- {item}")
        if self.last_warning:
            lines.append(f"\n### 告警\n- {self.last_warning}")
        return "\n".join(lines)

    def apply_round_update(self, round_label, round_output, parser=None):
        """追加式更新；解析失败保留上一版并记告警。"""
        prev = copy.deepcopy(self.to_dict())
        try:
            if parser:
                parsed = parser(round_output) or {}
            else:
                parsed = _default_parse_round(round_output)
            for item in parsed.get("consensus", []):
                if item and item not in self.current_consensus:
                    self.current_consensus.append(item)
            for item in parsed.get("constraints", []):
                if item and item not in self.key_constraints:
                    self.key_constraints.append(item)
            for item in parsed.get("falsified", []):
                if item and item not in self.falsified_hypotheses:
                    self.falsified_hypotheses.append(item)
            for item in parsed.get("divergences", []):
                if item and item not in self.open_divergences:
                    self.open_divergences.append(item)
                    self._divergence_rounds[item] = 1
                elif item in self.open_divergences:
                    self._divergence_rounds[item] = self._divergence_rounds.get(item, 1) + 1
            self._check_dispute_freeze()
            self.context_version += 1
            self.last_warning = ""
            return True
        except Exception as e:
            self.current_consensus = prev.get("Current_Consensus", [])
            self.open_divergences = prev.get("Open_Divergences", [])
            self.falsified_hypotheses = prev.get("Falsified_Hypotheses", [])
            self.key_constraints = prev.get("Key_Constraints", [])
            self.escalated_disputes = prev.get("Escalated_Disputes", [])
            self.context_version = prev.get("Context_Version", self.context_version)
            self.last_warning = f"{round_label} 黑板更新失败: {e}"
            return False

    def _check_dispute_freeze(self, threshold=DEFAULT_DISPUTE_FREEZE_THRESHOLD):
        frozen = []
        for div, count in list(self._divergence_rounds.items()):
            if count >= threshold and div not in self.escalated_disputes:
                self.escalated_disputes.append(div)
                frozen.append(div)
        return frozen


def _default_parse_round(text):
    """从轮次输出中提取列表项（- 开头行）。"""
    result = {"consensus": [], "divergences": [], "falsified": [], "constraints": []}
    if not text:
        return result
    section = "consensus"
    for line in text.splitlines():
        low = line.lower()
        if "分歧" in line or "divergence" in low:
            section = "divergences"
            continue
        if "证伪" in line or "falsif" in low:
            section = "falsified"
            continue
        if "约束" in line or "constraint" in low:
            section = "constraints"
            continue
        if "共识" in line or "consensus" in low:
            section = "consensus"
            continue
        m = re.match(r"^[-*]\s+(.+)", line.strip())
        if m:
            result[section].append(m.group(1).strip())
    if not any(result.values()):
        summary = (text or "").strip()[:500]
        if summary:
            result["consensus"].append(summary)
    return result
