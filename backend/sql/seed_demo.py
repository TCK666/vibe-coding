"""两场景演示数据生成器（幂等：先清后插，日期相对今天动态生成）。

场景一 客户行为分析 —— 埋雷模式：
  移动端自然流量 下单转化率 前30天 8.0% → 近30天 3.2%（其余渠道平稳≈5%），
  加购率 20% → 8%（对应"详情页改版导致首屏加购按钮曝光下降"的归因剧本）。
场景二 评论反馈分析 —— 埋雷模式：
  P-AIR-300 空气炸锅（批次 B2026-09）评分 4.4 → 2.8，差评集中在"异味/涂层脱落"，
  质量问题退款占比 12% → 38%。

运行: .venv/Scripts/python backend/sql/seed_demo.py   （库由 BAAS_DB_URL 决定，默认开发库）
"""
import asyncio
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("BAAS_DB_URL", "sqlite+aiosqlite:///backend/baas_dev.db")

from sqlalchemy import text  # noqa: E402

from app.db.session import engine  # noqa: E402

random.seed(42)
TODAY = date.today()


def d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


DDL = [
    """CREATE TABLE IF NOT EXISTS biz_user (
        user_id INTEGER PRIMARY KEY, user_name VARCHAR(64), register_date VARCHAR(10),
        reg_channel VARCHAR(32), device_pref VARCHAR(16))""",
    """CREATE TABLE IF NOT EXISTS biz_visit_event (
        visit_id INTEGER PRIMARY KEY, user_id INTEGER, visit_date VARCHAR(10),
        visit_channel VARCHAR(32), device VARCHAR(16), add_cart_flag INTEGER, ordered_flag INTEGER)""",
    """CREATE TABLE IF NOT EXISTS biz_add_cart_event (
        cart_id INTEGER PRIMARY KEY, user_id INTEGER, cart_date VARCHAR(10),
        visit_channel VARCHAR(32), device VARCHAR(16))""",
    """CREATE TABLE IF NOT EXISTS biz_order_event (
        order_id INTEGER PRIMARY KEY, user_id INTEGER, order_date VARCHAR(10),
        amount FLOAT, visit_channel VARCHAR(32), device VARCHAR(16))""",
    """CREATE TABLE IF NOT EXISTS biz_product (
        product_id VARCHAR(32) PRIMARY KEY, product_name VARCHAR(128),
        category VARCHAR(64), batch_no VARCHAR(32), launch_date VARCHAR(10))""",
    """CREATE TABLE IF NOT EXISTS biz_rating (
        rating_id INTEGER PRIMARY KEY, product_id VARCHAR(32), user_id INTEGER,
        rating INTEGER, created_at VARCHAR(19))""",
    """CREATE TABLE IF NOT EXISTS biz_comment (
        comment_id INTEGER PRIMARY KEY, product_id VARCHAR(32), user_id INTEGER,
        comment_text TEXT, created_at VARCHAR(19))""",
    """CREATE TABLE IF NOT EXISTS biz_refund (
        refund_id INTEGER PRIMARY KEY, product_id VARCHAR(32), user_id INTEGER,
        refund_date VARCHAR(10), refund_reason VARCHAR(32), amount FLOAT)""",
]

# (渠道, 设备): (前30天访问量, 前期转化数, 近30天访问量, 近期转化数, 前期加购率, 近期加购率)
# 移动端自然流量是"埋雷"组合：8.0% → 3.2%，加购 20% → 8%
VISIT_PLAN = {
    ("自然流量", "移动端"): (500, 40, 500, 16, 0.20, 0.08),
    ("自然流量", "PC端"): (200, 10, 200, 10, 0.15, 0.15),
    ("付费搜索", "移动端"): (200, 11, 200, 10, 0.15, 0.15),
    ("付费搜索", "PC端"): (150, 8, 150, 7, 0.15, 0.15),
    ("直播推荐", "移动端"): (200, 9, 200, 11, 0.15, 0.15),
    ("直播推荐", "PC端"): (120, 6, 120, 6, 0.15, 0.15),
}
CHANNELS = ["自然流量", "付费搜索", "直播推荐", "站内推荐"]


def seed_customer_behavior(conn) -> dict:
    users, visits, carts, orders = [], [], [], []
    uid, vid, cid, oid = 0, 0, 0, 0
    for i in range(300):
        uid += 1
        users.append({
            "user_id": uid, "user_name": f"用户{uid:04d}",
            "register_date": d(random.randint(60, 300)),
            "reg_channel": random.choice(CHANNELS),
            "device_pref": random.choice(["移动端", "PC端"]),
        })

    def emit_period(channel, device, total, n_ordered, cart_ratio, day_lo, day_hi):
        nonlocal vid, cid, oid
        ordered_idx = set(random.sample(range(total), n_ordered))
        cart_idx = set(random.sample(range(total), int(total * cart_ratio)))
        for i in range(total):
            vid += 1
            u = random.choice(users)
            ordered = 1 if i in ordered_idx else 0
            add_cart = 1 if i in cart_idx else 0
            visits.append({
                "visit_id": vid, "user_id": u["user_id"],
                "visit_date": d(random.randint(day_lo, day_hi)),
                "visit_channel": channel, "device": device,
                "add_cart_flag": add_cart, "ordered_flag": ordered,
            })
            if add_cart:
                cid += 1
                carts.append({"cart_id": cid, "user_id": u["user_id"],
                              "cart_date": visits[-1]["visit_date"],
                              "visit_channel": channel, "device": device})
            if ordered:
                oid += 1
                orders.append({"order_id": oid, "user_id": u["user_id"],
                               "order_date": visits[-1]["visit_date"],
                               "amount": round(random.uniform(59, 899), 2),
                               "visit_channel": channel, "device": device})

    for (channel, device), (pv, po, rv, ro, pcr, rcr) in VISIT_PLAN.items():
        emit_period(channel, device, pv, po, pcr, 31, 60)   # 前30天（相对今天 31~60 天前）
        emit_period(channel, device, rv, ro, rcr, 1, 30)    # 近30天

    conn.execute(text("DELETE FROM biz_user"), )
    conn.execute(text("DELETE FROM biz_visit_event"))
    conn.execute(text("DELETE FROM biz_add_cart_event"))
    conn.execute(text("DELETE FROM biz_order_event"))
    for u in users:
        conn.execute(text("INSERT INTO biz_user VALUES (:user_id,:user_name,:register_date,:reg_channel,:device_pref)"), u)
    conn.execute(text("INSERT INTO biz_visit_event VALUES (:visit_id,:user_id,:visit_date,:visit_channel,:device,:add_cart_flag,:ordered_flag)"), visits)
    conn.execute(text("INSERT INTO biz_add_cart_event VALUES (:cart_id,:user_id,:cart_date,:visit_channel,:device)"), carts)
    conn.execute(text("INSERT INTO biz_order_event VALUES (:order_id,:user_id,:order_date,:amount,:visit_channel,:device)"), orders)

    # 精确性自检：移动端自然流量两期转化率（边界=30天前，近期为最近30天）
    check = conn.execute(text(
        "SELECT ROUND(100.0*SUM(CASE WHEN visit_date >= :cut THEN ordered_flag ELSE 0 END)/"
        "SUM(CASE WHEN visit_date >= :cut THEN 1 ELSE 0 END),1) AS recent, "
        "ROUND(100.0*SUM(CASE WHEN visit_date < :cut THEN ordered_flag ELSE 0 END)/"
        "SUM(CASE WHEN visit_date < :cut THEN 1 ELSE 0 END),1) AS prior "
        "FROM biz_visit_event WHERE visit_channel='自然流量' AND device='移动端'"
    ), {"cut": d(30)}).fetchone()
    assert check[0] == 3.2 and check[1] == 8.0, f"埋雷数据不精确: {check}"
    return {"users": len(users), "visits": len(visits), "carts": len(carts), "orders": len(orders)}


RECENT_COMMENTS = ["有明显异味，用了两次不敢用了", "涂层脱落，锅底花了一片", "异味很大，厨房散不掉",
                   "涂层起泡脱落，要求退货", "加热后有刺鼻味道", "涂层掉渣，担心安全问题",
                   "异味重，清洗也去不掉", "用了两周涂层就掉了"]
NORMAL_COMMENTS = ["性价比不错，加热挺快", "容量刚好够一家人用", "操作简单，老人也会用",
                   "外观好看，清洗方便", "功能够用，总体满意"]
REFUND_REASONS_Q = "质量问题"
REFUND_REASONS_N = ["七日无理由", "物流问题", "不想要了"]


def seed_review_feedback(conn) -> dict:
    products, ratings, comments, refunds = [], [], [], []
    for i in range(1, 21):
        pid = "P-AIR-300" if i == 1 else f"P-{1000 + i}"
        products.append({
            "product_id": pid,
            "product_name": "空气炸锅Pro 5L" if i == 1 else f"商品{1000 + i}",
            "category": "厨房电器" if i == 1 else random.choice(["家居", "数码", "服饰"]),
            "batch_no": "B2026-09" if i == 1 else f"B2026-{random.randint(1, 9):02d}",
            "launch_date": d(random.randint(90, 300)),
        })

    rid = 0
    def emit_ratings(pid, count, dist, lo, hi):
        nonlocal rid
        stars = [s for s, n in dist.items() for _ in range(n)]
        random.shuffle(stars)
        for s in stars[:count]:
            rid += 1
            ratings.append({
                "rating_id": rid, "product_id": pid,
                "user_id": random.randint(1, 300),
                "rating": s,
                "created_at": d(random.randint(lo, hi)) + f" {random.randint(8,22):02d}:{random.randint(0,59):02d}:00",
            })

    # P-AIR-300: 前30天 4.4（100条），近30天 2.8（100条）
    dist_prior = {5: 60, 4: 25, 3: 10, 2: 5}          # 440/100 = 4.4
    dist_recent = {5: 30, 4: 5, 3: 15, 2: 15, 1: 35}  # 280/100 = 2.8
    emit_ratings("P-AIR-300", 100, dist_prior, 31, 60)
    emit_ratings("P-AIR-300", 100, dist_recent, 1, 30)
    # 其余商品：评分 4~5，数量少
    for p in products[1:]:
        emit_ratings(p["product_id"], random.randint(5, 15), {5: 8, 4: 6, 3: 1}, 1, 60)

    # P-AIR-300 评论：近30天 40 条，其中 30 条差评关键词；前30天 10 条正常
    cid = 0
    def emit_comments(pid, texts, lo, hi):
        nonlocal cid
        for t in texts:
            cid += 1
            comments.append({
                "comment_id": cid, "product_id": pid,
                "user_id": random.randint(1, 300),
                "comment_text": t,
                "created_at": d(random.randint(lo, hi)) + f" {random.randint(8,22):02d}:00:00",
            })

    emit_comments("P-AIR-300", random.choices(RECENT_COMMENTS, k=30), 1, 30)
    emit_comments("P-AIR-300", random.choices(NORMAL_COMMENTS, k=10), 31, 60)
    for p in products[1:]:
        emit_comments(p["product_id"], random.choices(NORMAL_COMMENTS, k=random.randint(1, 4)), 1, 60)

    # P-AIR-300 退款: 前30天 25 条其中 3 条质量(12%)，近30天 50 条其中 19 条质量(38%)
    rid2 = 0
    def emit_refunds(pid, total, n_quality, lo, hi):
        nonlocal rid2
        q_idx = set(random.sample(range(total), n_quality))
        for i in range(total):
            rid2 += 1
            refunds.append({
                "refund_id": rid2, "product_id": pid,
                "user_id": random.randint(1, 300),
                "refund_date": d(random.randint(lo, hi)),
                "refund_reason": REFUND_REASONS_Q if i in q_idx else random.choice(REFUND_REASONS_N),
                "amount": round(random.uniform(199, 399), 2),
            })

    emit_refunds("P-AIR-300", 25, 3, 31, 60)
    emit_refunds("P-AIR-300", 50, 19, 1, 30)
    for p in products[1:]:
        emit_refunds(p["product_id"], random.randint(0, 5), 0, 1, 60)

    conn.execute(text("DELETE FROM biz_product"))
    conn.execute(text("DELETE FROM biz_rating"))
    conn.execute(text("DELETE FROM biz_comment"))
    conn.execute(text("DELETE FROM biz_refund"))
    for p in products:
        conn.execute(text("INSERT INTO biz_product VALUES (:product_id,:product_name,:category,:batch_no,:launch_date)"), p)
    conn.execute(text("INSERT INTO biz_rating VALUES (:rating_id,:product_id,:user_id,:rating,:created_at)"), ratings)
    conn.execute(text("INSERT INTO biz_comment VALUES (:comment_id,:product_id,:user_id,:comment_text,:created_at)"), comments)
    conn.execute(text("INSERT INTO biz_refund VALUES (:refund_id,:product_id,:user_id,:refund_date,:refund_reason,:amount)"), refunds)

    # 精确性自检
    check = conn.execute(text(
        "SELECT ROUND(AVG(CASE WHEN created_at >= :cut THEN rating END),2) AS recent, "
        "ROUND(AVG(CASE WHEN created_at < :cut THEN rating END),2) AS prior "
        "FROM biz_rating WHERE product_id='P-AIR-300'"
    ), {"cut": d(30) + " 00:00:00"}).fetchone()
    assert check[0] == 2.8 and check[1] == 4.4, f"评分埋雷不精确: {check}"
    q = conn.execute(text(
        "SELECT ROUND(100.0*SUM(CASE WHEN refund_reason='质量问题' AND refund_date >= :cut THEN 1 ELSE 0 END)/"
        "SUM(CASE WHEN refund_date >= :cut THEN 1 ELSE 0 END),0) "
        "FROM biz_refund WHERE product_id='P-AIR-300' AND refund_date >= :cut"
    ), {"cut": d(30)}).scalar()
    assert q == 38.0, f"退款占比埋雷不精确: {q}"
    return {"products": len(products), "ratings": len(ratings), "comments": len(comments), "refunds": len(refunds)}


async def main():
    async with engine.begin() as conn:
        for ddl in DDL:
            await conn.execute(text(ddl))
        r1 = await conn.run_sync(lambda c: seed_customer_behavior(c))
        r2 = await conn.run_sync(lambda c: seed_review_feedback(c))
    print("seed 完成:", r1, r2)


if __name__ == "__main__":
    asyncio.run(main())
