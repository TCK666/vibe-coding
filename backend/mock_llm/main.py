"""mock_llm：OpenAI chat.completions 兼容形状的流式服务（开发期用）。

剧本规则（与真实模型行为对齐，便于后端编排逻辑联调）：
- 请求带 tools 且历史里还没有 tool 结果 → 返回一次 db_query 工具调用(finish_reason=tool_calls)
- 历史里已有 tool 结果 → 流式输出分析文本，末尾附六部分结构化 JSON(finish_reason=stop)

启动: .venv/Scripts/python -m uvicorn mock_llm.main:app --app-dir backend --port 9002
"""
import asyncio
import json
import time
import uuid
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="mock-llm")

CHUNK_SLEEP = 0.03
CHUNK_SIZE = 24

_CUT = (date.today() - timedelta(days=30)).isoformat()  # 近30天分界，与 seed_demo 对齐

SCRIPTS = [
    {
        "keywords": ["转化率", "下单", "加购", "访问", "客户行为", "流量"],
        "tool_sql": (
            f"SELECT visit_channel, device, COUNT(*) AS visits, SUM(ordered_flag) AS orders, "
            f"ROUND(100.0 * SUM(CASE WHEN visit_date >= '{_CUT}' THEN ordered_flag ELSE 0 END) / "
            f"NULLIF(SUM(CASE WHEN visit_date >= '{_CUT}' THEN 1 ELSE 0 END), 0), 1) AS recent_pct, "
            f"ROUND(100.0 * SUM(CASE WHEN visit_date < '{_CUT}' THEN ordered_flag ELSE 0 END) / "
            f"NULLIF(SUM(CASE WHEN visit_date < '{_CUT}' THEN 1 ELSE 0 END), 0), 1) AS prior_pct "
            f"FROM biz_visit_event GROUP BY visit_channel, device ORDER BY visits DESC"
        ),
        "narrative": (
            "## 问题定义\n近30天下单转化率明显下降，需要定位原因。\n\n"
            "## 归因过程\n对访问-加购-下单漏斗按渠道×设备拆解后，移动端自然流量转化率从 8.0% 跌至 3.2%，"
            "其余渠道平稳在 5% 上下；进一步看该组合的加购率由 20% 降至 8%，"
            "结合商品详情页 9 月 26 日改版记录，判断主因是改版后首屏信息层级调整导致加购按钮曝光下降。\n\n"
        ),
        "result": {
            "problem_definition": "近30天下单转化率为何下降？",
            "key_metrics": [
                {"metric_name": "下单转化率（移动端自然流量）", "metric_value": 3.2, "metric_unit": "%", "metric_period": "近30天"},
                {"metric_name": "下单转化率（移动端自然流量，环比前30天）", "metric_value": 8.0, "metric_unit": "%", "metric_period": "前30天"},
                {"metric_name": "加购率（移动端自然流量）", "metric_value": 8.0, "metric_unit": "%", "metric_period": "近30天"},
            ],
            "evidence_list": [
                {"source_type": "db_query", "source_name": "biz_visit_event",
                 "evidence_text": "移动端自然流量转化率 3.2%（16/500），环比前30天 8.0%（40/500）下降 4.8 个百分点",
                 "related_metric": "下单转化率", "confidence": 0.9},
                {"source_type": "db_query", "source_name": "biz_visit_event",
                 "evidence_text": "其余渠道×设备组合转化率稳定在 5% 上下，可排除大盘流量质量问题",
                 "related_metric": "下单转化率", "confidence": 0.85},
                {"source_type": "db_query", "source_name": "biz_visit_event",
                 "evidence_text": "移动端自然流量加购率 20% → 8%，下降先于下单发生，指向详情页改版",
                 "related_metric": "下单转化率", "confidence": 0.8},
            ],
            "conclusion_text": "主要原因是 9 月 26 日商品详情页改版导致移动端自然流量加购转化下降，影响范围集中在该渠道组合，其余渠道平稳。",
            "missing_data_text": "缺少改版前后的首屏热力图数据；缺少竞品同期转化数据。",
            "next_action_text": ["回滚或 AB 调整详情页首屏并观察一周", "对移动端自然流量做分渠道留存对比验证"],
        },
    },
    {
        "keywords": ["评分", "评论", "退款", "差评", "反馈"],
        "tool_sql": (
            f"SELECT p.product_id, p.product_name, p.batch_no, "
            f"ROUND(AVG(CASE WHEN r.created_at >= '{_CUT}' THEN r.rating END), 2) AS recent_avg, "
            f"ROUND(AVG(CASE WHEN r.created_at < '{_CUT}' THEN r.rating END), 2) AS prior_avg, "
            f"COUNT(*) AS cnt FROM biz_rating r JOIN biz_product p ON r.product_id = p.product_id "
            f"WHERE p.product_id = 'P-AIR-300' GROUP BY p.product_id"
        ),
        "narrative": (
            "## 问题定义\n商品评分近期下滑，需要定位差评集中的商品与原因。\n\n"
            "## 归因过程\n评分按商品聚合后，P-AIR-300 空气炸锅（批次 B2026-09）近30天均分 2.8，"
            "环比前30天 4.4 大幅下滑；差评关键词集中在「异味」「涂层脱落」；"
            "与退款数据交叉验证，该商品质量问题退款占比同期从 12% 升至 38%。\n\n"
        ),
        "result": {
            "problem_definition": "近期商品评分为何下滑？哪些商品/批次问题最大？",
            "key_metrics": [
                {"metric_name": "P-AIR-300 平均评分", "metric_value": 2.8, "metric_unit": "分", "metric_period": "近30天"},
                {"metric_name": "P-AIR-300 平均评分（环比前30天）", "metric_value": 4.4, "metric_unit": "分", "metric_period": "前30天"},
                {"metric_name": "质量问题退款占比", "metric_value": 38, "metric_unit": "%", "metric_period": "近30天"},
            ],
            "evidence_list": [
                {"source_type": "db_query", "source_name": "biz_rating",
                 "evidence_text": "P-AIR-300 近30天均分 2.8（100条），环比 4.4 大幅下滑",
                 "related_metric": "平均评分", "confidence": 0.9},
                {"source_type": "text_search", "source_name": "biz_comment",
                 "evidence_text": "近30天 40 条评论中 30 条集中在「异味」「涂层脱落」",
                 "related_metric": "平均评分", "confidence": 0.85},
                {"source_type": "db_query", "source_name": "biz_refund",
                 "evidence_text": "质量问题退款占比 12% → 38%，与评论问题互相印证",
                 "related_metric": "质量问题退款占比", "confidence": 0.85},
            ],
            "conclusion_text": "评分下滑主因是空气炸锅 P-AIR-300（批次 B2026-09）质量缺陷（异味、涂层脱落），并已传导至退款端。",
            "missing_data_text": "缺少该批次的供应商来料检验记录；缺少售后维修工单数据。",
            "next_action_text": ["下架 B2026-09 批次并启动供应商追溯", "对已购用户定向发放补偿券并监控舆情"],
        },
    },
]

DEFAULT_SCRIPT = {
    "keywords": [],
    "tool_sql": "SELECT 1",
    "narrative": "## 问题定义\n已收到分析问题。\n\n## 说明\n当前为 mock 剧本：命中「客户行为/评论反馈」关键词时有完整归因演示，其余问题返回本默认结论。\n\n",
    "result": {
        "problem_definition": "当前业务问题（mock 默认剧本）",
        "key_metrics": [
            {"metric_name": "示例指标", "metric_value": 0, "metric_unit": "-", "metric_period": "近30天"},
        ],
        "evidence_list": [
            {"source_type": "system", "source_name": "mock",
             "evidence_text": "默认剧本证据示例", "related_metric": "示例指标", "confidence": 0.5},
        ],
        "conclusion_text": "默认结论：mock 运行正常，可走通全链路。",
        "missing_data_text": "缺少真实业务数据。",
        "next_action_text": ["接入真实模型验证提示词", "补充业务示例数据"],
    },
}


class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    model: str = "mock-attribution"
    messages: list[ChatMessage]
    tools: list[dict] | None = None
    stream: bool = True


def _pick_script(messages: list[ChatMessage]) -> dict:
    for m in reversed(messages):
        if m.role == "user" and m.content:
            for s in SCRIPTS:
                if any(k in m.content for k in s["keywords"]):
                    return s
    return DEFAULT_SCRIPT


def _sse(delta: dict, finish: str | None = None) -> str:
    data = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "mock-attribution",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "mock-llm"}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    script = _pick_script(req.messages)
    has_tool_result = any(m.role == "tool" for m in req.messages)

    if not req.stream:
        if req.tools and not has_tool_result:
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": None, "tool_calls": [{
                        "id": f"call_{uuid.uuid4().hex[:8]}", "type": "function",
                        "function": {"name": "db_query", "arguments": json.dumps({"sql": script["tool_sql"]}, ensure_ascii=False)},
                    }]},
                    "finish_reason": "tool_calls",
                }],
            }
        full = script["narrative"] + "```json\n" + json.dumps(script["result"], ensure_ascii=False, indent=2) + "\n```"
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "model": req.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": full}, "finish_reason": "stop"}],
        }

    async def gen():
        if req.tools and not has_tool_result:
            args = json.dumps({"sql": script["tool_sql"]}, ensure_ascii=False)
            yield _sse({"role": "assistant", "tool_calls": [{
                "index": 0, "id": f"call_{uuid.uuid4().hex[:8]}", "type": "function",
                "function": {"name": "db_query", "arguments": ""},
            }]})
            for i in range(0, len(args), CHUNK_SIZE):
                yield _sse({"tool_calls": [{"index": 0, "function": {"arguments": args[i:i + CHUNK_SIZE]}}]})
                await asyncio.sleep(CHUNK_SLEEP)
            yield _sse({}, finish="tool_calls")
        else:
            full = script["narrative"] + "```json\n" + json.dumps(script["result"], ensure_ascii=False, indent=2) + "\n```"
            yield _sse({"role": "assistant", "content": ""})
            for i in range(0, len(full), CHUNK_SIZE):
                yield _sse({"content": full[i:i + CHUNK_SIZE]})
                await asyncio.sleep(CHUNK_SLEEP)
            yield _sse({}, finish="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
