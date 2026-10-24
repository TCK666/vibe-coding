"""六部分归因结果：Pydantic 强校验 + markdown 模板渲染。"""
from typing import Any

from pydantic import BaseModel, Field, field_validator


class KeyMetric(BaseModel):
    metric_name: str
    metric_value: float | str
    metric_unit: str = ""
    metric_period: str = ""


class Evidence(BaseModel):
    source_type: str
    source_name: str
    evidence_text: str
    related_metric: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class SixPartResult(BaseModel):
    problem_definition: str
    key_metrics: list[KeyMetric] = []
    evidence_list: list[Evidence] = []
    conclusion_text: str
    missing_data_text: str = ""
    next_action_text: list[str]

    @field_validator("next_action_text")
    @classmethod
    def at_least_two(cls, v: list[str]) -> list[str]:
        v = [str(x) for x in v]
        if len(v) < 2:
            raise ValueError("next_action_text 至少 2 条")
        return v

    @field_validator("problem_definition", "conclusion_text")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("不能为空")
        return str(v)


def validate_six_part(parsed: dict[str, Any]) -> SixPartResult:
    return SixPartResult(**parsed)


def render_markdown(r: SixPartResult) -> str:
    lines = ["# 经营归因分析报告", "", "## 问题定义", r.problem_definition, ""]

    lines += ["## 关键指标", "", "| 指标 | 数值 | 单位 | 周期 |", "|---|---|---|---|"]
    for m in r.key_metrics:
        lines.append(f"| {m.metric_name} | {m.metric_value} | {m.metric_unit} | {m.metric_period} |")
    if not r.key_metrics:
        lines.append("| （无） | | | |")
    lines.append("")

    lines += ["## 证据列表", "", "| 来源类型 | 来源 | 证据 | 关联指标 | 置信度 |", "|---|---|---|---|---|"]
    for e in r.evidence_list:
        lines.append(f"| {e.source_type} | {e.source_name} | {e.evidence_text} | {e.related_metric} | {e.confidence} |")
    if not r.evidence_list:
        lines.append("| （无） | | | | |")
    lines.append("")

    lines += ["## 归因结论", r.conclusion_text, "", "## 待补充数据", r.missing_data_text or "（无）", "", "## 下一步建议", ""]
    lines += [f"{i}. {item}" for i, item in enumerate(r.next_action_text, 1)]
    return "\n".join(lines)
