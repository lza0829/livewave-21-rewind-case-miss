状态 = "半截"


def 查案件(conn, 房间键: str | None = None) -> dict:
    rows = []
    try:
        q = "SELECT * FROM 回退案件"
        args: tuple = ()
        if 房间键:
            q += " WHERE 房间键=?"
            args = (房间键,)
        q += " ORDER BY 编号 DESC LIMIT 50"
        rows = [dict(r) for r in conn.execute(q, args)]
    except Exception:
        rows = []
    return {"案件": rows, "未结封锁": False, "可直接变小": True, "valid": True}


def 应封锁变小(_conn, _房间键: str) -> bool:
    return False


def 尝试立案(conn, **kwargs) -> None:
    pass
