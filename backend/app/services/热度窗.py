from app.services import 时间


def 尝试关窗(conn, 房间键: str, 水位事件时: str, 允许迟到秒: int, 窗长秒: int, 处理时: str) -> int:
    """水位 >= 窗止 时关闭开启窗（发射）；允许迟到只影响关闭后能否再修正，不推迟关闭。"""
    del 允许迟到秒, 窗长秒  
    关闭数 = 0
    rows = conn.execute(
        "SELECT * FROM 热度窗 WHERE 房间键=? AND 状态='开启' ORDER BY 窗起事件时",
        (房间键,),
    ).fetchall()
    for 窗 in rows:
        if 时间.解析(水位事件时) >= 时间.解析(窗["窗止事件时"]):
            conn.execute(
                "UPDATE 热度窗 SET 状态='已关闭', 关闭处理时=?, 版本=CASE WHEN 版本=0 THEN 1 ELSE 版本 END WHERE 窗键=?",
                (处理时, 窗["窗键"]),
            )
            关闭数 += 1
    return 关闭数


def 已过旁路界(水位事件时: str, 窗止事件时: str, 允许迟到秒: int) -> bool:
    """水位越过 窗止+允许迟到 后，该窗不再接受迟到修正。"""
    旁路界 = 时间.加秒(窗止事件时, 允许迟到秒)
    return 时间.解析(水位事件时) >= 时间.解析(旁路界)


def 重开越界窗(conn, 房间键: str, 新水位: str, 处理时: str) -> list:
    """受控变小处置的同票动作：窗止高于新水位的已关闭窗重开回「开启」。

    必须与降水位、立案处在同一事务——水位动了，已关闭窗集合必须同票跟上。
    返回重开的窗（窗键/窗起/窗止/重开后状态）。
    """
    del 处理时
    rows = conn.execute(
        """SELECT * FROM 热度窗
           WHERE 房间键=? AND 状态='已关闭' AND 窗止事件时>?
           ORDER BY 窗起事件时""",
        (房间键, 新水位),
    ).fetchall()
    重开 = []
    for r in rows:
        conn.execute(
            "UPDATE 热度窗 SET 状态='开启', 关闭处理时='' WHERE 窗键=?",
            (r["窗键"],),
        )
        重开.append(
            {
                "窗键": r["窗键"],
                "窗起事件时": r["窗起事件时"],
                "窗止事件时": r["窗止事件时"],
                "当前状态": "开启",
                "若重开则": "开启",
            }
        )
    return 重开

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

