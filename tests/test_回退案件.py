"""回退案件（架构甲「未结案件封锁」）测试夹具。

覆盖硬约束：
- 禁止处置成功案件空
- 禁止无案件号的变小写成功
- 禁止邻房案件串改本房水位
- 未结案则新的变小写整票拒绝；半截失败整票回滚
- 变小写与入流抢锁：不得水位已动而关闭集合未跟
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="livewave-test-")
os.environ["数据目录"] = _TMP
os.environ["夹具目录"] = os.path.join(os.path.dirname(__file__), "..", "fixtures")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import json

import pytest

from app import seed
from app.db import 连接
from app.modules import 回退案件
from app.services import 水位闸, 装载, 贯验

夹具目录 = os.environ["夹具目录"]


@pytest.fixture(autouse=True)
def 清库():
    seed.初始化库()
    conn = 连接()
    for t in ["回退案件", "互动事件", "装载批次", "热度窗", "撤回单", "旁路匣", "窗贯验", "水位线", "直播间", "站规"]:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
    seed.初始化库()
    yield


def 装夹具(名: str) -> dict:
    with open(os.path.join(夹具目录, f"{名}.json"), encoding="utf-8") as f:
        return 装载.装一批(json.load(f))


def 水位(房间键: str) -> str:
    conn = 连接()
    try:
        return conn.execute("SELECT 事件时水位 FROM 水位线 WHERE 房间键=?", (房间键,)).fetchone()[0]
    finally:
        conn.close()


def 案件列(房间键: str = None) -> list:
    conn = 连接()
    try:
        if 房间键:
            return [dict(r) for r in conn.execute("SELECT * FROM 回退案件 WHERE 房间键=? ORDER BY 编号", (房间键,))]
        return [dict(r) for r in conn.execute("SELECT * FROM 回退案件 ORDER BY 编号")]
    finally:
        conn.close()


def 窗态(房间键: str) -> dict:
    conn = 连接()
    try:
        return {r["窗键"]: r["状态"] for r in conn.execute("SELECT * FROM 热度窗 WHERE 房间键=?", (房间键,))}
    finally:
        conn.close()


def 结案(房间键: str, 案件号: str) -> dict:
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        结果 = 回退案件.结案(conn, 房间键, 案件号, seed.此刻())
        conn.commit()
        return 结果
    finally:
        conn.close()


def 核证(房间键: str = None) -> dict:
    conn = 连接()
    try:
        return 回退案件.查案件(conn, 房间键)
    finally:
        conn.close()


def 备抬升():
    """灌水位回退样例：水位抬到 12:02:10，两窗已关闭。"""
    装夹具("水位回退样例")
    assert 水位("房A") == "2026-11-22T12:02:10Z"


def test_首笔变小处置同票落案():
    备抬升()
    r = 水位闸.提交("房A", "2026-11-22T12:00:30Z")
    assert r["valid"] and r["已落盘"]
    assert r["案件号"], "禁止无案件号的变小写成功"
    assert r["处置态"] == "未结"
    assert r["当前水位"] == "2026-11-22T12:00:30Z"

    案件 = 案件列("房A")
    assert len(案件) == 1, "禁止处置成功案件空"
    案 = 案件[0]
    assert 案["案件号"] == r["案件号"]
    assert 案["旧水位"] == "2026-11-22T12:02:10Z"
    assert 案["请求值"] == "2026-11-22T12:00:30Z"
    assert 案["处置态"] == "未结"

    # 关闭集合同票跟上：窗止高于新水位的两扇已关闭窗被重开
    态 = 窗态("房A")
    assert 态["房A|2026-11-22T12:00:00Z"] == "开启"
    assert 态["房A|2026-11-22T12:01:00Z"] == "开启"
    assert len(r["重开列表"]) == 2

    conn = 连接()
    try:
        assert 水位闸.不变式(conn) == []
    finally:
        conn.close()


def test_未结案则次笔整票拒绝数值不降():
    备抬升()
    r1 = 水位闸.提交("房A", "2026-11-22T12:00:30Z")
    r2 = 水位闸.提交("房A", "2026-11-22T12:00:05Z")
    assert not r2["valid"]
    assert not r2["已落盘"]
    assert r2["拒绝列表"], "整票拒绝须给拒绝列表"
    assert r2["未结案件号"] == r1["案件号"]
    assert 水位("房A") == "2026-11-22T12:00:30Z", "未结案则数值不降"
    assert len(案件列("房A")) == 1, "被拒的变小写不得再立案"


def test_结案后可再处置且挂前案上下文():
    备抬升()
    r1 = 水位闸.提交("房A", "2026-11-22T12:00:30Z")
    z = 结案("房A", r1["案件号"])
    assert z["valid"] and z["处置态"] == "已结"

    r2 = 水位闸.提交("房A", "2026-11-22T12:00:05Z")
    assert r2["valid"] and r2["案件号"] and r2["案件号"] != r1["案件号"]
    assert r2["前案案件号"] == r1["案件号"], "之后变小写必须带案件上下文"
    assert 水位("房A") == "2026-11-22T12:00:05Z"

    案件 = 案件列("房A")
    assert [a["处置态"] for a in 案件] == ["已结", "未结"]
    assert 案件[0]["结案时刻"], "结案须落结案时刻"


def test_禁止邻房案件串改本房水位():
    备抬升()
    conn = 连接()
    conn.execute(
        "INSERT INTO 直播间(房间键, 标题, 主播, 开播事件时, 状态) VALUES ('房B','邻房','主播乙','2026-11-22T12:00:00Z','直播中')"
    )
    conn.execute(
        "INSERT INTO 水位线(房间键, 事件时水位, 允许迟到秒, 更新处理时) VALUES ('房B','2026-11-22T12:02:00Z',30,'2026-11-22T12:02:00Z')"
    )
    conn.commit()
    conn.close()

    rA = 水位闸.提交("房A", "2026-11-22T12:00:30Z")
    assert rA["valid"]

    # 邻房不得拿本房案件号结案
    z = 结案("房B", rA["案件号"])
    assert not z["valid"]
    assert 案件列("房A")[0]["处置态"] == "未结", "邻房结案不得生效"

    # 房A 的未结案件不封锁房B；房B 的处置只动自己的水位、落自己的案
    rB = 水位闸.提交("房B", "2026-11-22T12:01:00Z")
    assert rB["valid"] and rB["案件号"]
    assert 水位("房A") == "2026-11-22T12:00:30Z", "邻房案件不得串改本房水位"
    assert 水位("房B") == "2026-11-22T12:01:00Z"
    assert {a["房间键"] for a in 案件列()} == {"房A", "房B"}

    核A, 核B = 核证("房A"), 核证("房B")
    assert 核A["未结封锁"] and 核B["未结封锁"]
    assert 核A["valid"] and 核B["valid"]


def test_半截失败整票回滚():
    备抬升()
    from app.services import 热度窗

    原 = 热度窗.重开越界窗

    def 炸(*a, **k):
        raise RuntimeError("半截失败")

    热度窗.重开越界窗 = 炸
    try:
        with pytest.raises(RuntimeError):
            水位闸.提交("房A", "2026-11-22T12:00:30Z")
    finally:
        热度窗.重开越界窗 = 原

    assert 水位("房A") == "2026-11-22T12:02:10Z", "半截失败水位不得动"
    assert 案件列() == [], "半截失败案件簿不得留案"
    态 = 窗态("房A")
    assert 态["房A|2026-11-22T12:00:00Z"] == "已关闭", "半截失败关闭集合不得动"


def test_变小写与入流抢锁():
    import threading

    备抬升()
    抢锁 = json.load(open(os.path.join(夹具目录, "水位回退抢锁样例.json"), encoding="utf-8"))
    目标 = 抢锁["并发夹具"]["变小写"]["新值"]
    错 = []

    def 处置线程():
        try:
            for _ in range(6):
                r = 水位闸.提交("房A", 目标)
                if not r["valid"] and r.get("未结案件号"):
                    结案("房A", r["未结案件号"])
        except Exception as e:  # noqa: BLE001
            错.append(f"处置:{e}")

    def 入流线程(线: int):
        try:
            for i in range(6):
                ev = dict(抢锁["事件"][i % 3])
                ev["事件编号"] = f"C-{线}-{i}"
                装载.装一批({"批次编号": f"批-抢锁-{线}-{i}", "事件": [ev]})
        except Exception as e:  # noqa: BLE001
            错.append(f"入流:{e}")

    ts = [threading.Thread(target=f) for f in (处置线程, 处置线程)]
    ts += [threading.Thread(target=入流线程, args=(k,)) for k in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not 错, f"抢锁过程异常:{错}"

    果 = 贯验.跑贯验()
    assert 果["是否通过"], f"贯验撕裂:{果['说明']}"
    核 = 核证("房A")
    assert 核["valid"], f"核证失齐:{核['失齐']}"
    # 每笔成功处置都有案；每案都有案件号
    for a in 案件列("房A"):
        assert a["案件号"]


def test_核证只读接口与闸窗对齐():
    备抬升()
    核0 = 核证("房A")
    assert 核0["可直接变小"] and not 核0["未结封锁"] and 核0["valid"]

    r = 水位闸.提交("房A", "2026-11-22T12:00:30Z")
    核1 = 核证("房A")
    assert 核1["未结封锁"] and not 核1["可直接变小"]
    assert 核1["valid"] and 核1["失齐"] == []
    assert 核1["案件"][0]["案件号"] == r["案件号"]

    # 审查闸与核证口径一致：未结封锁时审查同样拒绝
    审 = 水位闸.审查("房A", "2026-11-22T12:00:05Z")
    assert not 审["valid"] and 审["未结案件号"] == r["案件号"]

    结案("房A", r["案件号"])
    核2 = 核证("房A")
    assert 核2["可直接变小"] and 核2["valid"]
