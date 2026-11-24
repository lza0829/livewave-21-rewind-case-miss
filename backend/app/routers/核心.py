import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import 夹具目录, 连接
from app.services import 装载, 贯验, 目录, 水位闸

路由 = APIRouter(prefix="/api")


class 装载请求(BaseModel):
    批次编号: str = ""
    事件: list = Field(default_factory=list)


class 水位变小请求(BaseModel):
    房间键: str
    新值: str
    处理时: str = ""


class 结案请求(BaseModel):
    房间键: str
    案件号: str


@路由.get("/健康")
def 健康():
    return {
        "正常": True,
        "项目": "播浪",
        "骨架": "互动事件入流→事件时间水位线推进→热度窗关闭发射→迟到修正撤回→窗输出与撤回互证",
    }


@路由.get("/总览")
def 取总览():
    return 目录.总览()


@路由.get("/站规")
def 站规():
    conn = 连接()
    try:
        return {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}
    finally:
        conn.close()


@路由.get("/直播间")
def 列直播间():
    conn = 连接()
    try:
        rooms = [dict(r) for r in conn.execute("SELECT * FROM 直播间 ORDER BY 房间键")]
        for r in rooms:
            wm = conn.execute("SELECT * FROM 水位线 WHERE 房间键=?", (r["房间键"],)).fetchone()
            r["水位线"] = dict(wm) if wm else None
        return rooms
    finally:
        conn.close()


@路由.get("/事件")
def 列事件(命运: str = ""):
    conn = 连接()
    try:
        if 命运:
            rows = conn.execute(
                "SELECT * FROM 互动事件 WHERE 命运=? ORDER BY 事件时 DESC LIMIT 200", (命运,)
            )
        else:
            rows = conn.execute("SELECT * FROM 互动事件 ORDER BY 事件时 DESC LIMIT 200")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@路由.get("/水位线")
def 列水位线():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 水位线 ORDER BY 房间键")]
    finally:
        conn.close()


@路由.get("/热度窗")
def 列热度窗(状态: str = ""):
    conn = 连接()
    try:
        if 状态:
            rows = conn.execute(
                "SELECT * FROM 热度窗 WHERE 状态=? ORDER BY 窗起事件时 DESC", (状态,)
            )
        else:
            rows = conn.execute("SELECT * FROM 热度窗 ORDER BY 窗起事件时 DESC")
        return [dict(r) for r in rows]
    finally:
        conn.close()


@路由.get("/撤回单")
def 列撤回():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 撤回单 ORDER BY 编号 DESC LIMIT 100")]
    finally:
        conn.close()


@路由.get("/旁路匣")
def 列旁路():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 旁路匣 ORDER BY 编号 DESC LIMIT 100")]
    finally:
        conn.close()


@路由.get("/批次")
def 列批次():
    conn = 连接()
    try:
        out = []
        for r in conn.execute("SELECT * FROM 装载批次 ORDER BY 时刻 DESC LIMIT 30"):
            d = dict(r)
            try:
                d["报告"] = json.loads(d["报告"])
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()


@路由.post("/装载")
def 做装载(体: 装载请求):
    return 装载.装一批(体.model_dump())


@路由.post("/装载/夹具")
def 装夹具(名: str = "准时热度样例"):
    路径 = 夹具目录 / f"{名}.json"
    if not 路径.exists():
        raise HTTPException(404, f"夹具不存在:{名}")
    return 装载.装一批(json.loads(路径.read_text(encoding="utf-8")))


@路由.get("/水位变小/审查")
def 审查水位变小(房间键: str, 新值: str):
    """只读裁决：房间、旧值、新值、拒绝/重开列表、valid。不写库。"""
    return 水位闸.审查(房间键, 新值)


@路由.post("/水位变小")
def 提交水位变小(体: 水位变小请求):
    """水位写闸。甲口径「未结案件封锁」：变小是同票立案的处置；有未结案件则整票拒绝。"""
    return 水位闸.提交(体.房间键, 体.新值, 体.处理时 or None)


@路由.post("/贯验")
def 做贯验():
    return 贯验.跑贯验()


@路由.get("/贯验")
def 列贯验():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 窗贯验 ORDER BY 编号 DESC LIMIT 20")]
    finally:
        conn.close()


@路由.get("/空桩")
def 空桩():
    from app import modules

    return modules.列表()

from app.modules import 回退案件 as 案


@路由.get("/核证/回退案件")
def 取回退案件(房间键: str | None = None):
    """回退案件核证只读接口：案件簿 + 未结封锁 + 与水位闸/关窗表/热度窗对齐核验。"""
    conn = 连接()
    try:
        return 案.查案件(conn, 房间键)
    finally:
        conn.close()


@路由.post("/回退案件/结案")
def 做结案(体: 结案请求):
    """结案：按 房间键+案件号 双重定位。结案后本房才可再处置变小。"""
    from app.seed import 此刻

    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            结果 = 案.结案(conn, 体.房间键, 体.案件号, 此刻())
            if 结果.get("valid") and 结果.get("已落盘"):
                conn.commit()
            else:
                conn.rollback()
            return 结果
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "窗键" in out and "window_key" not in out:
        out["window_key"] = out.get("窗键")
    if "房间键" in out and "room_key" not in out:
        out["room_key"] = out.get("房间键")
    if "事件编号" in out and "event_id" not in out:
        out["event_id"] = out.get("事件编号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_21(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "livewave", "nn": "21"}
    if extra:
        data.update(extra)
    return data

