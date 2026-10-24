"""里程碑8 验收：演示数据精确性/幂等性 + db_query 可查演示表。"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.tool_exec import ToolContext, execute_tool


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _seed():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "seed_demo", Path(__file__).resolve().parents[1] / "sql" / "seed_demo.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # 模块导入即完成 sys.path/env 设置，不自动跑 main

    async def run():
        from app.db.session import engine

        async with engine.begin() as conn:
            for ddl in mod.DDL:
                await conn.execute(__import__("sqlalchemy").text(ddl))
            r1 = await conn.run_sync(lambda c: mod.seed_customer_behavior(c))
            r2 = await conn.run_sync(lambda c: mod.seed_review_feedback(c))
        return r1, r2

    return asyncio.run(run())


def test_seed_precision_and_idempotent(client):
    r1, r2 = _seed()
    assert r1["visits"] > 2000 and r2["ratings"] > 200
    # 幂等：重跑一次不报错、数据量一致
    r1b, r2b = _seed()
    assert r1 == r1b and r2 == r2b

    # 埋雷比例精确（seeder 内部已有 assert，这里再从 SQL 侧验证，边界与 seeder 一致用本地日期）
    async def check():
        from datetime import date, timedelta

        from sqlalchemy import text

        from app.db.session import engine

        cut = (date.today() - timedelta(days=30)).isoformat()
        cut_ts = cut + " 00:00:00"
        async with engine.connect() as conn:
            conv = (
                await conn.execute(text(
                    "SELECT ROUND(100.0*SUM(CASE WHEN visit_date >= :cut THEN ordered_flag ELSE 0 END)/"
                    "SUM(CASE WHEN visit_date >= :cut THEN 1 ELSE 0 END),1) "
                    "FROM biz_visit_event WHERE visit_channel='自然流量' AND device='移动端'"
                ), {"cut": cut})
            ).scalar()
            rating = (
                await conn.execute(text(
                    "SELECT ROUND(AVG(CASE WHEN created_at >= :cut THEN rating END),2) "
                    "FROM biz_rating WHERE product_id='P-AIR-300'"
                ), {"cut": cut_ts})
            ).scalar()
        return conv, rating

    conv, rating = asyncio.run(check())
    assert conv == 3.2
    assert rating == 2.8


def test_db_query_can_read_demo_tables(client):
    ctx = ToolContext(user_id=1, conversation_id=1)

    async def run():
        return await execute_tool(
            "db_query",
            '{"sql": "SELECT visit_channel, device, COUNT(*) AS visits, '
            'ROUND(100.0*SUM(ordered_flag)/COUNT(*),1) AS conv_pct FROM biz_visit_event '
            'GROUP BY visit_channel, device ORDER BY visits DESC"}',
            ctx,
        )

    summary, full = asyncio.run(run())
    assert "自然流量" in full and "conv_pct" in full
